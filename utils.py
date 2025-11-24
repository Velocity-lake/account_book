import uuid
import re
from datetime import datetime
import hashlib
import secrets

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

def make_salt() -> str:
    return secrets.token_hex(16)

def hash_password(password: str, salt: str) -> str:
    pw = (password or "").encode("utf-8")
    sa = bytes.fromhex(salt)
    dk = hashlib.pbkdf2_hmac("sha256", pw, sa, 100_000, dklen=32)
    return dk.hex()

def verify_password(password: str, salt: str, password_hash: str) -> bool:
    try:
        return hash_password(password, salt) == (password_hash or "")
    except Exception:
        return False

def xnpv(rate: float, cash_flows: list):
    try:
        if rate <= -1.0:
            return float("inf")
        if not cash_flows:
            return 0.0
        base = cash_flows[0][0]
        total = 0.0
        for dt, amt in cash_flows:
            days = (dt - base).days
            total += float(amt) / ((1.0 + rate) ** (days / 365.0))
        return total
    except Exception:
        return float("inf")

def xirr(cash_flows: list, tol: float = 1e-7, max_iter: int = 100):
    try:
        if not cash_flows or len(cash_flows) < 2:
            return None
        pos = any(amt > 0 for _, amt in cash_flows)
        neg = any(amt < 0 for _, amt in cash_flows)
        if not (pos and neg):
            return None
        r = 0.1
        def npv(r):
            return xnpv(r, cash_flows)
        def dnpv(r):
            base = cash_flows[0][0]
            s = 0.0
            for dt, amt in cash_flows:
                days = (dt - base).days
                t = days / 365.0
                s += -t * float(amt) / ((1.0 + r) ** (t + 1.0))
            return s
        for _ in range(max_iter):
            f = npv(r)
            df = dnpv(r)
            if abs(df) < 1e-12:
                break
            nr = r - f / df
            if abs(nr - r) < tol:
                r = nr
                return r
            r = nr
        lo, hi = -0.999, 10.0
        flo, fhi = npv(lo), npv(hi)
        if flo == float("inf") and fhi == float("inf"):
            return None
        for _ in range(max_iter):
            mid = (lo + hi) / 2.0
            fmid = npv(mid)
            if abs(fmid) < tol:
                return mid
            if (fmid > 0 and flo > 0) or (fmid < 0 and flo < 0):
                lo, flo = mid, fmid
            else:
                hi, fhi = mid, fmid
        return None
    except Exception:
        return None
