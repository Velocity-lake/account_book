import csv
import re
from typing import List, Dict, Union
from datetime import datetime, timedelta
from models import TRANSACTION_TYPES
from utils import parse_datetime, gen_id
from xlsx_reader import read_xlsx, read_xlsx_rows

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
        has_time = ("交易时间" in joined) or ("交易创建时间" in joined) or ("格式化时间" in joined) or ("Formatted Time" in joined)
        has_amt = ("金额" in joined) or ("金额(元)" in joined) or ("金额（元）" in joined) or ("交易金额" in joined) or ("Transaction Amount" in joined)
        if has_time and has_amt:
            header_idx = i
            break
    header = [str(h).strip() for h in rows_raw[header_idx]]
    out = []
    for r in rows_raw[header_idx+1:]:
        d = {}
        for i in range(min(len(header), len(r))):
            key = header[i] if header[i] else f"列{i}"
            d[key] = r[i]
            d[f"列{i}"] = r[i]
        if any(str(v).strip() != '' for v in d.values()):
            out.append(d)
    return out

def read_csv_rows(path: str) -> List[List[str]]:
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
    out = []
    for r in rows_raw:
        if any(str(v).strip() != '' for v in r):
            out.append(r)
    return out

def import_standard_rows(rows: List[Dict], account_names: List[str]) -> List[Dict]:
    required_common = [
        "金额",
        "消费类别",
        "所属类别",
        "账户",
        "转入账户",
        "转出账户",
        "备注",
    ]
    for r in rows[:1]:
        for k in required_common:
            if k not in r:
                missing = [x for x in required_common if x not in r]
                raise ValueError(f"文件不是标准模板或列名不完整，缺失列：{','.join(missing)}")
        if ("交易时间" not in r) and ("格式化时间" not in r):
            raise ValueError("文件不是标准模板或缺少时间列，请包含‘交易时间’或‘格式化时间’")
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
        tstr = str(r.get("格式化时间", r.get("交易时间", ""))).strip()
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
    failures = []
    required_any = ["交易时间", "金额(元)"]
    for idx, r in enumerate(rows, start=1):
        if not all(k in r for k in required_any):
            failures.append((idx, "缺少必填列", ",".join([k for k in required_any if k not in r])))
            continue
        tstr = str(r.get("交易时间", "")).strip()
        if not tstr:
            failures.append((idx, "交易时间为空", ""))
            continue
        try:
            dt = parse_datetime(tstr)
        except Exception:
            failures.append((idx, "交易时间解析失败", tstr))
            continue
        io = str(r.get("收/支", "")).strip()
        ttype = "收入" if io == "收入" else "支出"
        try:
            amt = _parse_money(r.get("金额(元)", "0"))
        except Exception:
            failures.append((idx, "金额不可解析", str(r.get("金额(元)", ""))))
            continue
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
    if failures:
        msg_lines = [f"导入失败：存在 {len(failures)} 条错误"]
        for i, (row_idx, reason, val) in enumerate(failures[:3], start=1):
            msg_lines.append(f"{i}) 第{row_idx}行 {reason}：\"{str(val)[:60]}\"")
        raise ValueError("\n".join(msg_lines))
    if not out:
        raise ValueError("未识别到有效微信账单记录，请检查是否为官方导出模板")
    return out

def map_alipay(rows: List[Dict], account_names: List[str]):
    out = []
    failures = []
    skipped_no_io = 0
    for idx, r in enumerate(rows, start=1):
        # 时间与金额的多列名兼容
        tstr = str(r.get("交易时间", r.get("交易创建时间", ""))).strip()
        if not tstr:
            failures.append((idx, "交易时间为空", ""))
            continue
        dt = parse_datetime(tstr)
        io = str(r.get("收/支", "")).strip()
        if io == "不计收支":
            skipped_no_io += 1
            continue
        ttype = "收入" if io == "收入" else "支出"
        amt_raw = r.get("金额(元)", r.get("金额", r.get("金额（元）", "0")))
        try:
            amt = _parse_money(amt_raw)
        except Exception:
            failures.append((idx, "金额不可解析", str(amt_raw)))
            continue
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
    if failures:
        msg_lines = [f"导入失败：存在 {len(failures)} 条错误"]
        for i, (row_idx, reason, val) in enumerate(failures[:3], start=1):
            msg_lines.append(f"{i}) 第{row_idx}行 {reason}：\"{str(val)[:60]}\"")
        raise ValueError("\n".join(msg_lines))
    if not out and skipped_no_io == 0:
        raise ValueError("未识别到有效支付宝账单记录，请检查是否为官方导出模板或保存为CSV/XLSX再试")
    return out, {"skipped_no_io": skipped_no_io}

def map_spdb(rows: List[Union[Dict, List[str]]], account_names: List[str]) -> List[Dict]:
    e_idx, h_idx, j_idx = 4, 7, 9
    failures = []
    parsed = []
    def extract_time(s: str):
        s1 = ' '.join(str(s or '').strip().split())
        m = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)", s1)
        if m:
            return {"kind": "text", "value": m.group(1)}
        mcn = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}:\d{2})", s1)
        if mcn:
            return {"kind": "cn", "value": mcn.group(1)}
        if re.fullmatch(r"\d+(?:\.\d+)?", s1):
            return {"kind": "excel", "value": float(s1)}
        return {"kind": "none", "value": s1}
    def parse_time_str(s: str):
        from datetime import datetime
        try:
            return datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
        except Exception:
            try:
                return datetime.strptime(s, "%Y/%m/%d %H:%M")
            except Exception:
                return None
    for idx, r in enumerate(rows, start=1):
        t_raw = ''
        if isinstance(r, list):
            t_raw = str(r[2] if len(r) > 2 else '')
        else:
            t_raw = str((r.get("列2") or r.get("C") or ''))
        ts = extract_time(t_raw)
        if ts["kind"] == "none":
            failures.append((idx, "时间缺失或不匹配", t_raw))
            continue
        if ts["kind"] == "excel":
            try:
                from datetime import datetime, timedelta
                dt = datetime(1899, 12, 30) + timedelta(days=ts["value"])  # Excel序列日期
            except Exception:
                failures.append((idx, "Excel序列日期无法解析", ts["value"]))
                continue
        else:
            val = ts["value"]
            if ts["kind"] == "cn":
                # 转换为斜杠格式
                val = val.replace('年','/').replace('月','/').replace('日',' ')
            dt = parse_time_str(val)
            if dt is None:
                failures.append((idx, "时间格式错误", ts["value"]))
                continue
        if isinstance(r, list):
            s_amt = str(r[5] if len(r) > 5 else '0').strip()
            e = str(r[e_idx] if len(r) > e_idx else '').strip()
            h = str(r[h_idx] if len(r) > h_idx else '').strip()
            j = str(r[j_idx] if len(r) > j_idx else '').strip()
        else:
            a_raw = r.get("列5") or r.get("F") or r.get("金额") or r.get("金额(元)") or r.get("交易金额") or r.get("Transaction Amount") or "0"
            s_amt = str(a_raw).strip()
            e = str(r.get("列4", r.get("E", "")).strip())
            h = str(r.get("列7", r.get("H", "")).strip())
            j = str(r.get("列9", r.get("J", "")).strip())
        try:
            neg = (('-' in s_amt) or (float(s_amt) < 0))
        except Exception:
            neg = ('-' in s_amt)
        try:
            amt = _parse_money(s_amt)
        except Exception:
            failures.append((idx, "金额不可解析", s_amt))
            continue
        ttype = "支出" if neg else "收入"
        parts = [x for x in [e, h, j] if x]
        note = " | ".join(parts)
        account = "浦发银行" if "浦发银行" in account_names else ""
        parsed.append({
            "id": gen_id(),
            "time": dt.isoformat(),
            "amount": amt,
            "category": "",
            "ttype": ttype,
            "account": account,
            "to_account": None,
            "from_account": None,
            "note": note,
            "platform": "spdb",
            "parse_status": "ok",
        })
    if failures:
        msg_lines = [f"导入失败：存在 {len(failures)} 条错误"]
        for i, (row_idx, reason, val) in enumerate(failures[:3], start=1):
            msg_lines.append(f"{i}) 第{row_idx}行 {reason}：\"{str(val)[:60]}\"")
        raise ValueError("\n".join(msg_lines))
    return parsed

def map_citic(rows: List[Dict], account_names: List[str]) -> List[Dict]:
    def pick(d, subs):
        for k in d.keys():
            kl = str(k).lower()
            for s in subs:
                if s in kl or s in str(k):
                    v = d.get(k)
                    if v is not None and str(v).strip() != "":
                        return v
        return None
    out = []
    for r in rows:
        date_val = r.get("交易日期") or pick(r, ["交易日期","date"]) or r.get("列2") or r.get("C")
        time_val = r.get("交易时间") or pick(r, ["交易时间","time"]) or None
        def _norm_date(s):
            ss = str(s or "").strip()
            if ss.isdigit() and len(ss) == 8:
                return f"{ss[0:4]}-{ss[4:6]}-{ss[6:8]}"
            return ss
        def _norm_time(s):
            ss = str(s or "").strip()
            if ss.isdigit() and len(ss) == 6:
                return f"{ss[0:2]}:{ss[2:4]}:{ss[4:6]}"
            if ss.isdigit() and len(ss) == 4:
                return f"{ss[0:2]}:{ss[2:4]}:00"
            return ss
        tstr = _norm_date(date_val)
        if not tstr:
            continue
        if time_val:
            tv = _norm_time(time_val)
            tstr = f"{tstr} {tv}" if tv else f"{tstr} 00:00:00"
        else:
            tstr = f"{tstr} 00:00:00"
        dt = None
        try:
            dt = parse_datetime(tstr)
        except Exception:
            dt = parse_datetime(tstr)
        inc_raw = r.get("收入金额") or pick(r, ["收入金额","income amount"]) or None
        exp_raw = r.get("支出金额") or pick(r, ["支出金额","expense amount"]) or None
        if inc_raw is None and exp_raw is None:
            inc_raw = r.get("列5") or r.get("F")
        def _num(s):
            s0 = str(s if s is not None else "").strip()
            s0 = s0.replace(",", "")
            for sym in ["¥","￥","$","元"]:
                s0 = s0.replace(sym, "")
            s0 = s0.strip("'\"")
            s0 = s0.replace('－','-').replace('—','-').replace('–','-')
            if not s0:
                return 0.0
            try:
                return float(s0)
            except Exception:
                return 0.0
        inc_val = _num(inc_raw)
        exp_val = _num(exp_raw)
        amt = 0.0
        ttype = "收入"
        if inc_val > 0 and exp_val <= 0:
            amt = inc_val
            ttype = "收入"
        elif exp_val > 0 and inc_val <= 0:
            amt = exp_val
            ttype = "支出"
        elif inc_val > 0 and exp_val > 0:
            amt = inc_val if inc_val >= exp_val else exp_val
            ttype = "收入" if inc_val >= exp_val else "支出"
        else:
            v = _num(inc_raw if inc_raw is not None else exp_raw)
            if v == 0.0:
                continue
            ttype = "收入" if v >= 0 else "支出"
            amt = abs(v)
        note_parts = []
        s1 = r.get("交易摘要") or pick(r, ["交易摘要","summary"]) or ""
        s2 = r.get("对方用户名") or pick(r, ["对方用户名","counter party","username"]) or ""
        if str(s1).strip():
            note_parts.append(str(s1).strip())
        if str(s2).strip():
            note_parts.append(str(s2).strip())
        note = " | ".join(note_parts)
        account = "中信银行" if "中信银行" in account_names else ""
        out.append({
            "id": gen_id(),
            "time": dt.isoformat(),
            "amount": abs(float(amt)),
            "category": "",
            "ttype": ttype,
            "account": account,
            "to_account": None,
            "from_account": None,
            "note": note,
            "platform": "citic",
            "parse_status": "ok",
        })
    return out

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
            if (("交易时间" in l) or ("交易创建时间" in l) or ("格式化时间" in l)) and (("金额" in l) or ("金额(元)" in l) or ("金额（元）" in l)):
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
