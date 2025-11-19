import os
import json
from datetime import datetime
from typing import Dict, List
from models import Account, Transaction

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
LEDGER_PATH = os.path.join(DATA_DIR, "ledger.json")
DEFAULT_ACCOUNT_TYPES = ["投资理财", "现金", "信用卡", "借款"]

def ensure_dirs():
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

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
        "prefs": {
            "freeze_assets": False,
            "menu_layout": "classic",
            "bill_list": {
                "visible_columns": [
                    "交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"
                ]
            }
        },
    }

def load_state() -> Dict:
    ensure_dirs()
    if not os.path.isfile(LEDGER_PATH):
        save_state(default_state())
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
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
    if "prefs" not in data:
        data["prefs"] = default_state()["prefs"]
    else:
        prefs = data.setdefault("prefs", {})
        if "freeze_assets" not in prefs:
            prefs["freeze_assets"] = False
        if "menu_layout" not in prefs:
            prefs["menu_layout"] = "classic"
        bl = prefs.setdefault("bill_list", {})
        if "visible_columns" not in bl:
            bl["visible_columns"] = default_state()["prefs"]["bill_list"]["visible_columns"]
    return data

def save_state(state: Dict):
    ensure_dirs()
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def backup_state():
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"ledger_{ts}.json")
    with open(LEDGER_PATH, "r", encoding="utf-8") as src:
        with open(path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
    return path

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

def remove_account(state: Dict, name: str):
    state["accounts"] = [a for a in state.get("accounts", []) if a["name"] != name]

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

def add_transaction(state: Dict, tx: Transaction):
    state["transactions"].append(tx.to_dict())

def remove_transaction(state: Dict, tx_id: str):
    state["transactions"] = [t for t in state.get("transactions", []) if t.get("id") != tx_id]

def get_transaction(state: Dict, tx_id: str):
    for t in state.get("transactions", []):
        if t.get("id") == tx_id:
            return t
    return None

def update_transaction(state: Dict, tx_id: str, new_tx: Transaction):
    for i, t in enumerate(state.get("transactions", [])):
        if t.get("id") == tx_id:
            state["transactions"][i] = new_tx.to_dict()
            return

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
