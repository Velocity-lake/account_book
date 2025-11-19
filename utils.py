import uuid
import re
from datetime import datetime

def gen_id():
    return uuid.uuid4().hex

def parse_datetime(s: str):
    s = (s or "").strip()
    if not s:
        return datetime.now()
    try:
        ss = s.replace("Z", "")
        return datetime.fromisoformat(ss)
    except Exception:
        pass
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:[+-]\d{2}:\d{2})?$", s)
    if m:
        y, mo, d, hh, mm, ss = map(int, m.groups())
        return datetime(y, mo, d, hh, mm, ss)
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            pass
    return datetime.now()

def normalize_ttype(ttype: str):
    t = (ttype or "").strip()
    t = t.replace("　", " ")
    if t in ("收入", "报销类收入"):
        return t
    if t in ("支出", "报销类支出"):
        return t
    if t == "转账":
        return t
    return t

def month_key(dt: datetime):
    return dt.strftime("%Y-%m")

def format_amount(a: float):
    return f"{a:.2f}"

def tx_signature(t: dict):
    dt = parse_datetime(t.get("time", ""))
    ts = dt.strftime("%Y-%m-%d %H:%M:%S")
    amt = str(abs(float(t.get("amount", 0))))
    note = (t.get("note", "") or "").strip()
    return "|".join([ts, amt, note]).lower()
