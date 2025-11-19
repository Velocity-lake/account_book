import csv
from typing import List, Dict
from datetime import datetime, timedelta
from models import TRANSACTION_TYPES
from utils import parse_datetime, gen_id
from xlsx_reader import read_xlsx

def _parse_money(val) -> float:
    s = str(val).strip()
    s = s.replace(',', '')
    for sym in ['¥', '￥', '$', '元']:
        s = s.replace(sym, '')
    s = s.strip("'\"")
    s = s.replace('－', '-')
    s = s.replace('—', '-')
    s = s.replace('–', '-')
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1]
    v = float(s)
    return abs(v)

def read_csv(path: str):
    content = None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk", errors="strict") as f:
            content = f.read()
    import io
    buf = io.StringIO(content)
    rows_raw = list(csv.reader(buf))
    if not rows_raw:
        return []
    header_idx = 0
    for i, r in enumerate(rows_raw):
        cells = [str(x).strip() for x in r]
        joined = ",".join(cells)
        if (("交易时间" in joined) or ("交易创建时间" in joined)) and (("金额" in joined) or ("金额(元)" in joined) or ("金额（元）" in joined)):
            header_idx = i
            break
    header = [str(h).strip() for h in rows_raw[header_idx]]
    out = []
    for r in rows_raw[header_idx+1:]:
        d = {}
        for i in range(min(len(header), len(r))):
            key = header[i] if header[i] else f"列{i}"
            d[key] = r[i]
        if any(str(v).strip() != '' for v in d.values()):
            out.append(d)
    return out

def import_standard_rows(rows: List[Dict], account_names: List[str]) -> List[Dict]:
    required = [
        "交易时间",
        "金额",
        "消费类别",
        "所属类别",
        "账户",
        "转入账户",
        "转出账户",
        "备注",
    ]
    for r in rows[:1]:
        for k in required:
            if k not in r:
                missing = [x for x in required if x not in r]
                raise ValueError(f"文件不是标准模板或列名不完整，缺失列：{','.join(missing)}")
    out = []
    for r in rows:
        ttype = r.get("所属类别", "").strip()
        if ttype not in TRANSACTION_TYPES:
            raise ValueError("所属类别不合法")
        acc = r.get("账户", "").strip()
        if acc and acc not in account_names:
            raise ValueError("账户不存在")
        to_acc = r.get("转入账户", "").strip() or None
        from_acc = r.get("转出账户", "").strip() or None
        if ttype == "还款" and not (to_acc or acc):
            raise ValueError("还款需要目标账户")
        amt = _parse_money(r.get("金额", "0"))
        tstr = str(r.get("交易时间", "")).strip()
        dt = None
        try:
            if tstr and all(ch.isdigit() or ch == '.' for ch in tstr):
                val = float(tstr)
                dt = datetime(1899, 12, 30) + timedelta(days=val)
            else:
                dt = parse_datetime(tstr)
        except Exception:
            dt = parse_datetime(tstr)
        out.append({
            "id": gen_id(),
            "time": dt.isoformat(),
            "amount": amt,
            "category": r.get("消费类别", "").strip(),
            "ttype": ttype,
            "account": acc,
            "to_account": to_acc,
            "from_account": from_acc,
            "note": r.get("备注", "").strip(),
        })
    return out

def import_standard_csv(path: str, account_names: List[str]) -> List[Dict]:
    rows = read_csv(path)
    return import_standard_rows(rows, account_names)

def import_standard_xlsx(path: str, account_names: List[str]) -> List[Dict]:
    rows = read_xlsx(path)
    return import_standard_rows(rows, account_names)

# 平台模板解析与自动检测
WECHAT_COLS = ["交易时间", "收/支", "金额(元)"]
ALIPAY_COLS = ["交易时间", "收/支", "金额(元)"]

def detect_platform(rows: List[Dict]) -> str:
    if not rows:
        return "unknown"
    # 使用首行键集合进行模板识别，同时支持常见变体
    keys = {str(k).strip() for k in rows[0].keys()}
    lowers = {k.lower() for k in keys}
    def has_exact(names):
        return any(n in keys for n in names) or any(n.lower() in lowers for n in names)
    def has_substr(subs):
        return any(any(sub in k for k in keys) for sub in subs) or any(any(sub.lower() in k for k in lowers) for sub in subs)
    # 优先识别支付宝（包含“交易创建时间/商品名称”等特征）
    if has_exact(["交易分类"]) or has_exact(["收/付款方式"]) or has_exact(["商品说明"]) or has_exact(["商品名称"]) or has_exact(["交易号"]) or ((has_exact(["交易时间"]) or has_exact(["交易创建时间"])) and (has_exact(["金额(元)"]) or has_exact(["金额"]) or has_exact(["金额（元）"]) or has_substr(["金额"]))):
        return "alipay"
    # 微信：交易类型/支付方式/商品 或 收/支 + 金额(元)/金额
    if has_exact(["交易类型"]) or has_exact(["支付方式"]) or has_exact(["商品"]) or (has_exact(["收/支"]) and (has_exact(["金额(元)"]) or has_exact(["金额"]) or has_substr(["金额"]))):
        return "wechat"
    return "unknown"

def map_wechat(rows: List[Dict], account_names: List[str]) -> List[Dict]:
    out = []
    required_any = ["交易时间", "金额(元)"]
    for r in rows:
        if not all(k in r for k in required_any):
            continue
        tstr = str(r.get("交易时间", "")).strip()
        dt = parse_datetime(tstr)
        io = str(r.get("收/支", "")).strip()
        ttype = "收入" if io == "收入" else "支出"
        amt = _parse_money(r.get("金额(元)", "0"))
        category = str(r.get("交易类型", "")).strip()
        prod = str(r.get("商品", "")).strip()
        partner = str(r.get("交易对方", "")).strip()
        note_raw = str(r.get("备注", "")).strip()
        parts = [x for x in [category, partner, prod, note_raw] if x]
        note = " | ".join(parts)
        pay = str(r.get("支付方式", "")).strip()
        account = pay if pay in account_names else ""
        out.append({
            "id": gen_id(),
            "time": dt.isoformat(),
            "amount": amt,
            "category": category,
            "ttype": ttype,
            "account": account,
            "to_account": None,
            "from_account": None,
            "note": note,
            "platform": "wechat",
            "parse_status": "ok",
        })
    if not out:
        raise ValueError("未识别到有效微信账单记录，请检查是否为官方导出模板")
    return out

def map_alipay(rows: List[Dict], account_names: List[str]):
    out = []
    skipped_no_io = 0
    for r in rows:
        # 时间与金额的多列名兼容
        tstr = str(r.get("交易时间", r.get("交易创建时间", ""))).strip()
        if not tstr:
            continue
        dt = parse_datetime(tstr)
        io = str(r.get("收/支", "")).strip()
        if io == "不计收支":
            skipped_no_io += 1
            continue
        ttype = "收入" if io == "收入" else "支出"
        amt_raw = r.get("金额(元)", r.get("金额", r.get("金额（元）", "0")))
        amt = _parse_money(amt_raw)
        category = str(r.get("交易分类", "")).strip()
        prod = str(r.get("商品说明", "")).strip() or str(r.get("商品名称", "")).strip()
        partner = str(r.get("交易对方", "")).strip()
        note_raw = str(r.get("备注", "")).strip()
        parts = [x for x in [partner, prod, note_raw] if x]
        note = " | ".join(parts)
        pay = str(r.get("收/付款方式", r.get("支付方式", "")).strip())
        account = pay if pay in account_names else ""
        out.append({
            "id": gen_id(),
            "time": dt.isoformat(),
            "amount": amt,
            "category": category,
            "ttype": ttype,
            "account": account,
            "to_account": None,
            "from_account": None,
            "note": note,
            "platform": "alipay",
            "parse_status": "ok",
        })
    if not out and skipped_no_io == 0:
        raise ValueError("未识别到有效支付宝账单记录，请检查是否为官方导出模板或保存为CSV/XLSX再试")
    return out, {"skipped_no_io": skipped_no_io}

def try_import(path: str, account_names: List[str]):
    pl = path.lower()
    if pl.endswith(".csv"):
        rows = read_csv(path)
        plat = detect_platform(rows)
        if plat == "wechat":
            r = map_wechat(rows, account_names)
            return {"rows": r, "stats": {"skipped_no_io": 0}}
        if plat == "alipay":
            r, stats = map_alipay(rows, account_names)
            return {"rows": r, "stats": stats}
        r = import_standard_rows(rows, account_names)
        return {"rows": r, "stats": {"skipped_no_io": 0}}
    if pl.endswith(".xlsx"):
        rows = read_xlsx(path)
        plat = detect_platform(rows)
        if plat == "wechat":
            r = map_wechat(rows, account_names)
            return {"rows": r, "stats": {"skipped_no_io": 0}}
        if plat == "alipay":
            r, stats = map_alipay(rows, account_names)
            return {"rows": r, "stats": stats}
        r = import_standard_rows(rows, account_names)
        return {"rows": r, "stats": {"skipped_no_io": 0}}
    if pl.endswith(".txt"):
        # 兼容TXT，尝试以GBK+制表符解析
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk") as f:
                content = f.read()
        lines = [l for l in content.splitlines() if l.strip()]
        # 寻找表头行
        header_idx = 0
        for i, l in enumerate(lines):
            if (("交易时间" in l) or ("交易创建时间" in l)) and (("金额" in l) or ("金额(元)" in l) or ("金额（元）" in l)):
                header_idx = i
                break
        header = [h.strip() for h in lines[header_idx].split("\t")]
        rows = []
        for l in lines[header_idx+1:]:
            parts = l.split("\t")
            d = {}
            for i in range(min(len(header), len(parts))):
                d[header[i]] = parts[i]
            if d:
                rows.append(d)
        plat = detect_platform(rows)
        if plat == "wechat":
            return map_wechat(rows, account_names)
        if plat == "alipay":
            return map_alipay(rows, account_names)
        return import_standard_rows(rows, account_names)
    raise ValueError("仅支持CSV或XLSX导入，请将账单另存为CSV或Excel后再导入")
