from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

TRANSACTION_TYPES = [
    "收入",
    "支出",
    "报销类支出",
    "报销类收入",
    "转账",
]

@dataclass
class Account:
    name: str
    balance: float = 0.0
    type: str = "普通账户"
    note: str = ""
    bank: str = ""
    last4: str = ""
    limit: float = 0.0
    status: str = "有效"
    bill_day: int = 0
    repay_day: int = 0
    repay_offset: int = 0

    def to_dict(self):
        return asdict(self)

@dataclass
class Transaction:
    id: str
    time: datetime
    amount: float
    category: str
    ttype: str
    account: str
    to_account: Optional[str] = None
    from_account: Optional[str] = None
    note: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "time": self.time.isoformat(),
            "amount": self.amount,
            "category": self.category,
            "ttype": self.ttype,
            "account": self.account,
            "to_account": self.to_account,
            "from_account": self.from_account,
            "note": self.note,
        }
