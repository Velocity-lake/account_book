import os
import csv
import re
from datetime import datetime
from storage import load_state
from utils import parse_datetime, gen_id
from ocr_adapter import extract_text_from_image

def _parse_money_from_tokens(tokens):
    joined = ' '.join(tokens)
    m = re.findall(r'[¥￥$]?\s*([0-9]+(?:\.[0-9]{1,2})?)', joined)
    if m:
        try:
            return float(m[0])
        except Exception:
            return None
    return None

def _parse_date_from_tokens(tokens):
    joined = ' '.join(tokens)
    patterns = [
        r'(\d{4}-\d{1,2}-\d{1,2})',
        r'(\d{4}/\d{1,2}/\d{1,2})',
        r'(\d{4}年\d{1,2}月\d{1,2}日)'
    ]
    for p in patterns:
        m = re.search(p, joined)
        if m:
            return parse_datetime(m.group(1))
    return None

def _guess_platform(tokens, path):
    s = ' '.join(tokens + [path.lower()])
    if 'taobao' in s or '淘宝' in s:
        return '淘宝'
    if 'jd' in s or '京东' in s:
        return '京东'
    if 'pdd' in s or '拼多多' in s:
        return '拼多多'
    return '电商'

def _guess_category(tokens):
    text = ' '.join(tokens)
    rules = {
        '衣服': '衣服', '服饰': '衣服', '裤': '衣服', '裙': '衣服',
        '餐': '三餐', '饭': '三餐', '外卖': '三餐', '奶茶': '三餐',
        '日用': '日用品', '洗衣液': '日用品', '纸巾': '日用品',
        '鞋': '衣服', '化妆': '美妆', '口红': '美妆', '护肤': '美妆',
        '运输': '交通', '公交': '交通', '地铁': '交通', '打车': '交通'
    }
    for k, v in rules.items():
        if k in text:
            return v
    return '其他'

def _find_account(tokens, account_names):
    text = ' '.join(tokens)
    for name in account_names:
        if name and name in text:
            return name
    return None

def ensure_failure_dir(base_dir):
    data_dir = os.path.join(base_dir, 'data')
    failures_dir = os.path.join(data_dir, 'failures')
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    if not os.path.isdir(failures_dir):
        os.makedirs(failures_dir)
    return failures_dir

def process_images(paths, account_names, import_dt: datetime, existing_transactions):
    results = []
    failures = []
    dedupe = set()
    for p in paths:
        try:
            tokens = extract_text_from_image(p)
            amount = _parse_money_from_tokens(tokens)
            if amount is None:
                raise ValueError('未识别到金额')
            dt = _parse_date_from_tokens(tokens) or import_dt
            platform = _guess_platform(tokens, p)
            merchant = os.path.splitext(os.path.basename(p))[0]
            category = _guess_category(tokens)
            ttype = '支出'
            if re.search(r'退款|退货|返还', ' '.join(tokens)):
                ttype = '报销类收入'
            account = _find_account(tokens, account_names)
            key = f"{platform}|{merchant}|{amount:.2f}|{dt.strftime('%Y-%m-%d')}"
            if key in dedupe:
                failures.append((p, '重复导入（批次内）', ''))
                continue
            dedupe.add(key)
            for t in existing_transactions:
                k2 = f"{t.get('platform','')}|{t.get('note','')}|{float(t.get('amount',0)):.2f}|{parse_datetime(t.get('time','')).strftime('%Y-%m-%d')}"
                if k2 == key:
                    failures.append((p, '与已有记录重复', ''))
                    key = None
                    break
            if key is None:
                continue
            d = {
                'id': gen_id(),
                'time': dt.isoformat(),
                'amount': amount,
                'category': category,
                'ttype': ttype,
                'account': account or '',
                'to_account': None,
                'from_account': None,
                'note': f"{platform}-{merchant}",
                'platform': platform,
                'parse_status': 'ok',
            }
            results.append(d)
        except Exception as e:
            failures.append((p, str(e), ' '.join(tokens) if 'tokens' in locals() else ''))
    return results, failures

def export_failures(failures, base_dir):
    if not failures:
        return None
    failures_dir = ensure_failure_dir(base_dir)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(failures_dir, f'failures_{ts}.csv')
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['文件', '原因', '识别文本片段'])
        for p, reason, snippet in failures:
            w.writerow([p, reason, snippet])
    return path
