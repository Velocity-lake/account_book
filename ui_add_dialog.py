import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime
from models import TRANSACTION_TYPES
from utils import parse_datetime

class AddTransactionDialog(tk.Toplevel):
    def __init__(self, master, accounts, initial=None):
        super().__init__(master)
        self.accounts = accounts
        self.result = None
        self.title("新增记账")
        self.grab_set()
        self.resizable(False, False)
        self.build(initial)

    def build(self, initial):
        frm = ttk.Frame(self)
        frm.pack(padx=16, pady=16, fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="交易时间").grid(row=0, column=0, sticky=tk.W)
        self.e_time = ttk.Entry(frm)
        self.e_time.grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(frm, text="金额").grid(row=1, column=0, sticky=tk.W)
        self.e_amount = ttk.Entry(frm)
        self.e_amount.grid(row=1, column=1, sticky=tk.EW)
        ttk.Label(frm, text="消费类别").grid(row=2, column=0, sticky=tk.W)
        self.e_category = ttk.Entry(frm)
        self.e_category.grid(row=2, column=1, sticky=tk.EW)
        ttk.Label(frm, text="所属类别").grid(row=3, column=0, sticky=tk.W)
        self.cb_type = ttk.Combobox(frm, values=TRANSACTION_TYPES, state="readonly")
        self.cb_type.grid(row=3, column=1, sticky=tk.EW)
        ttk.Label(frm, text="账户").grid(row=4, column=0, sticky=tk.W)
        self.cb_account = ttk.Combobox(frm, values=self.accounts, state="readonly")
        self.cb_account.grid(row=4, column=1, sticky=tk.EW)
        self.frame_transfer = ttk.Frame(frm)
        ttk.Label(self.frame_transfer, text="转入账户").grid(row=0, column=0, sticky=tk.W)
        self.cb_to = ttk.Combobox(self.frame_transfer, values=self.accounts, state="readonly")
        self.cb_to.grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(self.frame_transfer, text="转出账户").grid(row=1, column=0, sticky=tk.W)
        self.cb_from = ttk.Combobox(self.frame_transfer, values=self.accounts, state="readonly")
        self.cb_from.grid(row=1, column=1, sticky=tk.EW)
        self.frame_transfer.grid(row=5, column=0, columnspan=2, sticky=tk.EW)
        ttk.Label(frm, text="备注").grid(row=6, column=0, sticky=tk.W)
        self.e_note = ttk.Entry(frm)
        self.e_note.grid(row=6, column=1, sticky=tk.EW)
        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=4)
        frm.columnconfigure(1, weight=1)
        self.cb_type.bind("<<ComboboxSelected>>", self.on_type_change)
        if initial:
            self.e_time.insert(0, initial.get("time", "")[:19].replace("T", " "))
            self.e_amount.insert(0, str(initial.get("amount", "")))
            self.e_category.insert(0, initial.get("category", ""))
            self.cb_type.set(initial.get("ttype", ""))
            self.cb_account.set(initial.get("account", ""))
            if initial.get("to_account"):
                self.cb_to.set(initial.get("to_account"))
            if initial.get("from_account"):
                self.cb_from.set(initial.get("from_account"))
            self.e_note.insert(0, initial.get("note", ""))
        else:
            self.cb_type.set(TRANSACTION_TYPES[0])
        self.on_type_change()

    def on_type_change(self, evt=None):
        t = self.cb_type.get()
        if t in ["转账", "还款"]:
            self.frame_transfer.grid()
        else:
            self.frame_transfer.grid_remove()

    def on_ok(self):
        try:
            tstr = self.e_time.get().strip()
            amt = float(self.e_amount.get().strip())
            if amt <= 0:
                raise ValueError("金额必须为正数")
            ttype = self.cb_type.get().strip()
            acc = self.cb_account.get().strip()
            to_acc = self.cb_to.get().strip() or None
            from_acc = self.cb_from.get().strip() or None
            if ttype == "还款" and not (to_acc or acc):
                raise ValueError("还款需要选择目标账户")
            dt = parse_datetime(tstr)
            self.result = {
                "time": dt.isoformat(),
                "amount": amt,
                "category": self.e_category.get().strip(),
                "ttype": ttype,
                "account": acc,
                "to_account": to_acc,
                "from_account": from_acc,
                "note": self.e_note.get().strip(),
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))
