import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List
from models import Account, Transaction
from utils import gen_id

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
USER_DIR = os.path.join(DATA_DIR, "users")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
LEDGER_PATH = os.path.join(DATA_DIR, "ledger.json")
CURRENT_LEDGER_PATH = LEDGER_PATH
LEDGER_DB_PATH = os.path.join(DATA_DIR, "ledger.db")
USER_INDEX_PATH = os.path.join(USER_DIR, "index.json")
DEFAULT_ACCOUNT_TYPES = ["投资理财", "现金", "信用卡", "借款"]
INVEST_LEDGER_PATH = os.path.join(DATA_DIR, "invest_ledger.json")
CURRENT_INVEST_LEDGER_PATH = INVEST_LEDGER_PATH

def ensure_dirs():
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    if not os.path.isdir(USER_DIR):
        os.makedirs(USER_DIR)
    if not os.path.isdir(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

def _db():
    ensure_dirs()
    conn = sqlite3.connect(LEDGER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, time TEXT, amount REAL, category TEXT, ttype TEXT, account TEXT, to_account TEXT, from_account TEXT, note TEXT, record_time TEXT, record_source TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS accounts (name TEXT PRIMARY KEY, balance REAL, type TEXT, note TEXT, bank TEXT, last4 TEXT, credit_limit REAL, status TEXT, bill_day INTEGER, repay_day INTEGER, repay_offset INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS categories (scene TEXT, name TEXT, PRIMARY KEY(scene, name))")
    cur.execute("CREATE TABLE IF NOT EXISTS category_rules (scene TEXT, keyword TEXT, category TEXT, PRIMARY KEY(scene, keyword, category))")
    cur.execute("CREATE TABLE IF NOT EXISTS record_sources (name TEXT PRIMARY KEY)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_time ON transactions(time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_rtime ON transactions(record_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_amount ON transactions(amount)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_ttype ON transactions(ttype)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_ttype_category ON transactions(ttype, category)")
    conn.commit()
    conn.close()

def _get_backend():
    try:
        s = load_state()
        return ((s.get("prefs", {}) or {}).get("storage_backend") or "sqlite")
    except Exception:
        return "sqlite"

def ensure_user_dirs(user_id: str):
    ensure_dirs()
    up = os.path.join(USER_DIR, user_id)
    if not os.path.isdir(up):
        os.makedirs(up)

def default_state():
    return {
        "accounts": [],
        "transactions": [],
        "categories": {
            "支出": [
                "三餐", "零食", "衣服", "交通", "娱乐", "医疗", "学习", "日用品", "住房", "美妆", "子女教育", "水电煤"
            ],
            "收入": [
                "工资", "生活费", "收红包", "外快", "股票基金"
            ],
        },
        "account_types": DEFAULT_ACCOUNT_TYPES,
        "category_rules": {
            "收入": [],
            "支出": [],
        },
        "record_sources": [
            "手动输入", "支付宝", "微信", "浦发银行", "中信银行", "模版导入"
        ],
        "prefs": {
            "freeze_assets": False,
            "menu_layout": "classic",
            "user_management_enabled": False,
            "theme": "light",
            "bill_list": {
                "visible_columns": [
                    "交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"
                ],
                "time_format": "date"
            },
            "credit_cards": {
                "visible_columns": [
                    "银行","卡名","后四位","信用额度","账单日","还款日","还款偏移","今日账期天数","状态","备注"
                ]
            }
        },
    }

def set_ledger_path(path: str):
    global CURRENT_LEDGER_PATH
    CURRENT_LEDGER_PATH = path or LEDGER_PATH

def get_current_ledger_path() -> str:
    return CURRENT_LEDGER_PATH

def get_user_ledger_path(user_id: str) -> str:
    ensure_user_dirs(user_id)
    return os.path.join(USER_DIR, user_id, "ledger.json")

def get_user_invest_ledger_path(user_id: str) -> str:
    ensure_user_dirs(user_id)
    return os.path.join(USER_DIR, user_id, "invest_ledger.json")

def load_state() -> Dict:
    ensure_dirs()
    path = get_current_ledger_path()
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_state(), f, ensure_ascii=False, indent=2)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for a in data.get("accounts", []):
        if "balance" in a:
            a["balance"] = float(a["balance"])
    for t in data.get("transactions", []):
        if "category" not in t:
            mc = t.get("minor_category") or t.get("major_category") or ""
            t["category"] = mc
    if "categories" not in data:
        data["categories"] = default_state()["categories"]
    if "account_types" not in data:
        data["account_types"] = DEFAULT_ACCOUNT_TYPES
    if "category_rules" not in data:
        data["category_rules"] = {"收入": [], "支出": []}
    if "record_sources" not in data:
        data["record_sources"] = default_state()["record_sources"]
    if "prefs" not in data:
        data["prefs"] = default_state()["prefs"]
    else:
        prefs = data.setdefault("prefs", {})
        if "freeze_assets" not in prefs:
            prefs["freeze_assets"] = False
        if "menu_layout" not in prefs:
            prefs["menu_layout"] = "classic"
        if "theme" not in prefs:
            prefs["theme"] = "light"
        bl = prefs.setdefault("bill_list", {})
        if "visible_columns" not in bl:
            bl["visible_columns"] = default_state()["prefs"]["bill_list"]["visible_columns"]
        if "time_format" not in bl:
            bl["time_format"] = default_state()["prefs"]["bill_list"]["time_format"]
        cc = prefs.setdefault("credit_cards", {})
        if "visible_columns" not in cc:
            cc["visible_columns"] = default_state()["prefs"]["credit_cards"]["visible_columns"]
    return data

def _default_invest_state() -> Dict:
    return {
        "accounts": [],
        "transactions": [],
        "valuations": {},
    }

def set_invest_ledger_path(path: str):
    global CURRENT_INVEST_LEDGER_PATH
    CURRENT_INVEST_LEDGER_PATH = path or INVEST_LEDGER_PATH

def get_current_invest_ledger_path() -> str:
    return CURRENT_INVEST_LEDGER_PATH

def load_invest_state() -> Dict:
    ensure_dirs()
    path = get_current_invest_ledger_path()
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_default_invest_state(), f, ensure_ascii=False, indent=2)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for a in data.get("accounts", []):
        if "name" in a:
            a["name"] = str(a["name"])  # 保持字符串
    return data

def save_invest_state(state: Dict):
    ensure_dirs()
    path = get_current_invest_ledger_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_invest_account_names(state: Dict) -> List[str]:
    return [a.get("name") for a in state.get("accounts", [])]

def find_invest_account(state: Dict, name: str) -> Dict:
    for a in state.get("accounts", []):
        if (a.get("name") or "") == name:
            return a
    return None

def add_invest_account(state: Dict, account: Dict):
    if find_invest_account(state, account.get("name")):
        return
    state.setdefault("accounts", []).append({
        "name": account.get("name"),
        "note": account.get("note", ""),
    })

def remove_invest_account(state: Dict, name: str):
    state["accounts"] = [a for a in state.get("accounts", []) if (a.get("name") or "") != name]
    # 同时清理对应估值
    vals = state.setdefault("valuations", {})
    if name in vals:
        try:
            vals.pop(name)
        except Exception:
            pass

def set_account_valuation(state: Dict, name: str, value: float, date: str):
    state.setdefault("valuations", {})[name] = {"value": float(value), "date": date}

def get_account_valuation(state: Dict, name: str) -> Dict:
    return (state.get("valuations") or {}).get(name) or {}

def save_state(state: Dict):
    ensure_dirs()
    path = get_current_ledger_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def migrate_json_to_sqlite():
    _init_db()
    s = load_state()
    conn = _db()
    cur = conn.cursor()
    for t in s.get("transactions", []):
        cur.execute("INSERT OR IGNORE INTO transactions(id, time, amount, category, ttype, account, to_account, from_account, note, record_time, record_source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (t.get("id"), t.get("time"), float(t.get("amount",0)), t.get("category"), t.get("ttype"), t.get("account"), t.get("to_account"), t.get("from_account"), t.get("note"), t.get("record_time"), t.get("record_source")))
    for a in s.get("accounts", []):
        cur.execute("INSERT OR REPLACE INTO accounts(name, balance, type, note, bank, last4, credit_limit, status, bill_day, repay_day, repay_offset) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (a.get("name"), float(a.get("balance",0)), a.get("type"), a.get("note"), a.get("bank"), a.get("last4"), float(a.get("limit",0)), a.get("status"), int(a.get("bill_day",0) or 0), int(a.get("repay_day",0) or 0), int(a.get("repay_offset",0) or 0)))
    cats = s.get("categories", {}) or {}
    for scene, lst in cats.items():
        for name in lst:
            cur.execute("INSERT OR IGNORE INTO categories(scene, name) VALUES(?,?)", (scene, name))
    rules = s.get("category_rules", {}) or {}
    for scene, lst in rules.items():
        for it in lst:
            cur.execute("INSERT OR IGNORE INTO category_rules(scene, keyword, category) VALUES(?,?,?)", (scene, it.get("keyword"), it.get("category")))
    for name in s.get("record_sources", []) or []:
        cur.execute("INSERT OR IGNORE INTO record_sources(name) VALUES(?)", (name,))
    conn.commit()
    conn.close()
    s.setdefault("prefs", {})["storage_backend"] = "sqlite"
    save_state(s)

def backup_state():
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 备份文件名包含用户ID（若由用户路径推断得到）
    cur = get_current_ledger_path()
    try:
        uid = None
        if cur.startswith(USER_DIR):
            parts = os.path.normpath(cur).split(os.sep)
            # .../data/users/<uid>/ledger.json
            for i, p in enumerate(parts):
                if p == "users" and i + 1 < len(parts):
                    uid = parts[i + 1]
                    break
        suffix = (f"_{uid}" if uid else "")
    except Exception:
        suffix = ""
    path = os.path.join(BACKUP_DIR, f"ledger{suffix}_{ts}.json")
    with open(cur, "r", encoding="utf-8") as src:
        with open(path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
    return path

# 用户索引管理（本地）
def load_user_index() -> Dict:
    ensure_dirs()
    if not os.path.isfile(USER_INDEX_PATH):
        with open(USER_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f, ensure_ascii=False, indent=2)
    with open(USER_INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_index(index: Dict):
    ensure_dirs()
    with open(USER_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def find_user_by_name(username: str) -> Dict:
    idx = load_user_index()
    for u in idx.get("users", []):
        if (u.get("username") or "").strip().lower() == (username or "").strip().lower():
            return u
    return None

def create_user(username: str, password_hash: str = None, salt: str = None) -> Dict:
    u = find_user_by_name(username)
    if u:
        return u
    uid = gen_id()
    ensure_user_dirs(uid)
    # 初始化用户账本
    upath = get_user_ledger_path(uid)
    if not os.path.isfile(upath):
        with open(upath, "w", encoding="utf-8") as f:
            json.dump(default_state(), f, ensure_ascii=False, indent=2)
    idx = load_user_index()
    ent = {
        "user_id": uid,
        "username": username,
        "password_hash": password_hash or "",
        "salt": salt or "",
        "created_at": datetime.now().isoformat(),
    }
    idx.setdefault("users", []).append(ent)
    save_user_index(idx)
    return ent

def delete_user(user_id: str):
    idx = load_user_index()
    users = [u for u in idx.get("users", []) if u.get("user_id") != user_id]
    idx["users"] = users
    save_user_index(idx)
    # 不删除用户目录以保证无损；真正删除由用户手动清理备份后再选择。

def get_account_names(state: Dict) -> List[str]:
    return [a["name"] for a in state.get("accounts", [])]

def find_account(state: Dict, name: str) -> Dict:
    for a in state.get("accounts", []):
        if a["name"] == name:
            return a
    return None

def get_account_types(state: Dict) -> List[str]:
    types = set(DEFAULT_ACCOUNT_TYPES)
    for a in state.get("accounts", []):
        t = (a.get("type") or "").strip()
        if t:
            types.add(t)
    return list(types)

def list_accounts_by_type(state: Dict) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for t in get_account_types(state):
        result[t] = []
    for a in state.get("accounts", []):
        typ = a.get("type") or ""
        result.setdefault(typ, []).append(a.get("name"))
    return result

def add_account(state: Dict, account: Account):
    if find_account(state, account.name):
        return
    state["accounts"].append(account.to_dict())
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        a = account.to_dict()
        cur.execute("INSERT OR REPLACE INTO accounts(name, balance, type, note, bank, last4, credit_limit, status, bill_day, repay_day, repay_offset) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (a.get("name"), float(a.get("balance",0)), a.get("type"), a.get("note"), a.get("bank"), a.get("last4"), float(a.get("limit",0)), a.get("status"), int(a.get("bill_day",0) or 0), int(a.get("repay_day",0) or 0), int(a.get("repay_offset",0) or 0)))
        conn.commit()
        conn.close()

def remove_account(state: Dict, name: str):
    state["accounts"] = [a for a in state.get("accounts", []) if a["name"] != name]
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM accounts WHERE name=?", (name,))
        conn.commit()
        conn.close()

def rename_account(state: Dict, old: str, new: str):
    for a in state.get("accounts", []):
        if a["name"] == old:
            a["name"] = new
    for t in state.get("transactions", []):
        if t.get("account") == old:
            t["account"] = new
        if t.get("to_account") == old:
            t["to_account"] = new
        if t.get("from_account") == old:
            t["from_account"] = new
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        cur.execute("UPDATE accounts SET name=? WHERE name=?", (new, old))
        cur.execute("UPDATE transactions SET account=? WHERE account=?", (new, old))
        cur.execute("UPDATE transactions SET to_account=? WHERE to_account=?", (new, old))
        cur.execute("UPDATE transactions SET from_account=? WHERE from_account=?", (new, old))
        conn.commit()
        conn.close()

def add_transaction(state: Dict, tx: Transaction):
    state["transactions"].append(tx.to_dict())
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        t = tx.to_dict()
        cur.execute("INSERT OR IGNORE INTO transactions(id, time, amount, category, ttype, account, to_account, from_account, note, record_time, record_source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (t.get("id"), t.get("time"), float(t.get("amount",0)), t.get("category"), t.get("ttype"), t.get("account"), t.get("to_account"), t.get("from_account"), t.get("note"), t.get("record_time"), t.get("record_source")))
        conn.commit()
        conn.close()

def remove_transaction(state: Dict, tx_id: str):
    state["transactions"] = [t for t in state.get("transactions", []) if t.get("id") != tx_id]
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        conn.commit()
        conn.close()

def get_transaction(state: Dict, tx_id: str):
    for t in state.get("transactions", []):
        if t.get("id") == tx_id:
            return t
    return None
    
def get_transaction_db(tx_id: str):
    _init_db()
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE id=?", (tx_id,))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    return dict(r)

def update_transaction(state: Dict, tx_id: str, new_tx: Transaction):
    for i, t in enumerate(state.get("transactions", [])):
        if t.get("id") == tx_id:
            state["transactions"][i] = new_tx.to_dict()
            return
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        t = new_tx.to_dict()
        cur.execute("UPDATE transactions SET time=?, amount=?, category=?, ttype=?, account=?, to_account=?, from_account=?, note=?, record_time=?, record_source=? WHERE id=?",
                    (t.get("time"), float(t.get("amount",0)), t.get("category"), t.get("ttype"), t.get("account"), t.get("to_account"), t.get("from_account"), t.get("note"), t.get("record_time"), t.get("record_source"), tx_id))
        conn.commit()
        conn.close()

def apply_transaction_delta(state: Dict, t: Dict, sign: int):
    if (state.get("prefs", {}) or {}).get("freeze_assets"):
        return
    amt = float(t.get("amount", 0)) * sign
    typ = t.get("ttype")
    if typ in ["收入", "报销类收入"]:
        a = find_account(state, t.get("account"))
        if a:
            a["balance"] = float(a.get("balance", 0)) + amt
    elif typ in ["支出", "报销类支出"]:
        a = find_account(state, t.get("account"))
        if a:
            a["balance"] = float(a.get("balance", 0)) - amt
    elif typ == "转账":
        fa = find_account(state, t.get("from_account"))
        ta = find_account(state, t.get("to_account"))
        if fa:
            fa["balance"] = float(fa.get("balance", 0)) - amt
        if ta:
            ta["balance"] = float(ta.get("balance", 0)) + amt
    elif typ == "还款":
        ta = find_account(state, t.get("to_account") or t.get("account"))
        if ta:
            ta["balance"] = float(ta.get("balance", 0)) + amt
        fa = find_account(state, t.get("from_account"))
        if fa:
            fa["balance"] = float(fa.get("balance", 0)) - amt

def get_categories(state: Dict, scene: str):
    cats = state.get("categories", {})
    return list(cats.get(scene, []))

def add_category(state: Dict, scene: str, name: str):
    cats = state.setdefault("categories", {})
    lst = cats.setdefault(scene, [])
    if name and name not in lst:
        lst.append(name)

def delete_category(state: Dict, scene: str, name: str):
    cats = state.setdefault("categories", {})
    lst = cats.setdefault(scene, [])
    cats[scene] = [c for c in lst if c != name]

def rename_category(state: Dict, scene: str, old: str, new: str, update_history: bool = False):
    cats = state.setdefault("categories", {})
    lst = cats.setdefault(scene, [])
    for i, c in enumerate(lst):
        if c == old:
            lst[i] = new
            break
    if update_history:
        for t in state.get("transactions", []):
            if t.get("category") == old:
                t["category"] = new

def get_category_rules(state: Dict, scene: str):
    rules = state.get("category_rules", {})
    return list(rules.get(scene, []))

def add_category_rule(state: Dict, scene: str, keyword: str, category: str):
    rules = state.setdefault("category_rules", {})
    lst = rules.setdefault(scene, [])
    k = (keyword or "").strip()
    c = (category or "").strip()
    if not k or not c:
        return
    for it in lst:
        if (it.get("keyword") or "").strip() == k and (it.get("category") or "").strip() == c:
            return
    lst.append({"keyword": k, "category": c})

def remove_category_rule(state: Dict, scene: str, keyword: str, category: str = None):
    rules = state.setdefault("category_rules", {})
    lst = rules.setdefault(scene, [])
    k = (keyword or "").strip()
    c = (category or "").strip() if category is not None else None
    new_lst = []
    for it in lst:
        ik = (it.get("keyword") or "").strip()
        ic = (it.get("category") or "").strip()
        if ik == k and (c is None or ic == c):
            continue
        new_lst.append(it)
    rules[scene] = new_lst

def get_record_sources(state: Dict) -> List[str]:
    lst = state.setdefault("record_sources", [])
    return list(lst)

def add_record_source(state: Dict, name: str):
    name = (name or "").strip()
    if not name:
        return
    lst = state.setdefault("record_sources", [])
    if name not in lst:
        lst.append(name)
    if _get_backend() == "sqlite":
        _init_db()
        conn = _db()
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO record_sources(name) VALUES(?)", (name,))
        conn.commit()
        conn.close()

# 导出目录
def get_export_dir() -> str:
    ensure_dirs()
    return EXPORT_DIR

def query_transactions(filters: Dict, limit: int = None, offset: int = None) -> List[Dict]:
    _init_db()
    conn = _db()
    cur = conn.cursor()
    where = []
    args = []
    year = (filters.get("year") or "").strip()
    month = (filters.get("month") or "").strip()
    ttype = (filters.get("ttype") or "").strip()
    category = (filters.get("category") or "").strip()
    term = (filters.get("term") or "").strip().lower()
    amt_op = (filters.get("amt_op") or "").strip()
    amt_val = (filters.get("amt_val") or "").strip()
    if year:
        where.append("substr(time,1,4)=?")
        args.append(year)
    if month:
        where.append("substr(time,1,7)=?")
        args.append(month)
    if ttype:
        where.append("ttype=?")
        args.append(ttype)
    if category:
        if category == "未分类":
            where.append("(category IS NULL OR trim(category)='')")
        else:
            where.append("category=?")
            args.append(category)
    if amt_op and amt_val and amt_val.isdigit():
        v = float(int(amt_val))
        if amt_op == ">":
            where.append("amount>?")
            args.append(v)
        elif amt_op == "<":
            where.append("amount<?")
            args.append(v)
        elif amt_op == "=":
            where.append("abs(amount-?)<1e-9")
            args.append(v)
    if term:
        like = f"%{term}%"
        where.append("(lower(time) LIKE ? OR lower(category) LIKE ? OR lower(ttype) LIKE ? OR lower(account) LIKE ? OR lower(to_account) LIKE ? OR lower(from_account) LIKE ? OR lower(note) LIKE ? OR lower(record_source) LIKE ? OR lower(id) LIKE ?)")
        args.extend([like, like, like, like, like, like, like, like, like])
    sql = "SELECT id,time,amount,category,ttype,account,to_account,from_account,note,record_time,record_source FROM transactions"
    if where:
        sql += " WHERE " + " AND ".join(where)
    order_col = (filters.get("order_col") or "time")
    order_desc = bool(filters.get("order_desc", False))
    if order_col in ("time","record_time","amount","category","ttype","account"):
        sql += f" ORDER BY {order_col} {'DESC' if order_desc else 'ASC'}"
    if isinstance(limit, int) and limit > 0:
        sql += " LIMIT ?"
        args.append(limit)
        if isinstance(offset, int) and offset >= 0:
            sql += " OFFSET ?"
            args.append(offset)
    cur.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def aggregate_sums(filters: Dict) -> Dict[str, float]:
    _init_db()
    conn = _db()
    cur = conn.cursor()
    where = []
    args = []
    year = (filters.get("year") or "").strip()
    month = (filters.get("month") or "").strip()
    if year:
        where.append("substr(time,1,4)=?")
        args.append(year)
    if month:
        where.append("substr(time,1,7)=?")
        args.append(month)
    sql = "SELECT ttype, SUM(amount) AS s FROM transactions"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY ttype"
    cur.execute(sql, args)
    res = {"收入":0.0, "支出":0.0, "转账":0.0, "报销类收入":0.0, "报销类支出":0.0}
    for r in cur.fetchall():
        k = r["ttype"]
        v = float(r["s"] or 0)
        res[k] = v
    conn.close()
    return res

def list_years() -> List[str]:
    _init_db()
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT substr(time,1,4) AS y FROM transactions ORDER BY y")
    ys = [r["y"] for r in cur.fetchall()]
    conn.close()
    return ys

def list_months(year: str) -> List[str]:
    _init_db()
    conn = _db()
    cur = conn.cursor()
    if year:
        cur.execute("SELECT DISTINCT substr(time,1,7) AS m FROM transactions WHERE substr(time,1,4)=? ORDER BY m", (year,))
    else:
        cur.execute("SELECT DISTINCT substr(time,1,7) AS m FROM transactions ORDER BY m")
    ms = [r["m"] for r in cur.fetchall()]
    conn.close()
    return ms
