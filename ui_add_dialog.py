import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime
from models import TRANSACTION_TYPES
from utils import parse_datetime, normalize_ttype
from storage import get_categories, load_state

class AddTransactionDialog(tk.Toplevel):
    def __init__(self, master, accounts, initial=None):
        super().__init__(master)
        self.accounts = accounts
        self.result = None
        self.title("新增记账")
        self.grab_set()
        self.resizable(False, False)
        self.date_str = ""
        self.calendar_win = None
        self.build(initial)

    def build(self, initial):
        frm = ttk.Frame(self)
        frm.pack(padx=16, pady=16, fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="交易时间").grid(row=0, column=0, sticky=tk.W)
        self.btn_date = ttk.Button(frm, text=self._date_button_text(), command=lambda: self.show_calendar(frm))
        self.btn_date.grid(row=0, column=1, sticky=tk.W)
        ttk.Label(frm, text="金额").grid(row=1, column=0, sticky=tk.W)
        self.e_amount = ttk.Entry(frm)
        self.e_amount.grid(row=1, column=1, sticky=tk.EW)
        ttk.Label(frm, text="消费类别").grid(row=2, column=0, sticky=tk.W)
        self.cb_category = ttk.Combobox(frm, values=[], state="normal")
        self.cb_category.grid(row=2, column=1, sticky=tk.EW)
        ttk.Label(frm, text="所属类别").grid(row=3, column=0, sticky=tk.W)
        self.cb_type = ttk.Combobox(frm, values=TRANSACTION_TYPES, state="readonly")
        self.cb_type.grid(row=3, column=1, sticky=tk.EW)
        ttk.Label(frm, text="账户").grid(row=4, column=0, sticky=tk.W)
        self.cb_account = ttk.Combobox(frm, values=list(self.accounts) + ["新增账户"], state="readonly")
        self.cb_account.grid(row=4, column=1, sticky=tk.EW)
        self.frame_transfer = ttk.Frame(frm)
        ttk.Label(self.frame_transfer, text="转入账户").grid(row=0, column=0, sticky=tk.W)
        self.cb_to = ttk.Combobox(self.frame_transfer, values=list(self.accounts) + ["新增账户"], state="readonly")
        self.cb_to.grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(self.frame_transfer, text="转出账户").grid(row=1, column=0, sticky=tk.W)
        self.cb_from = ttk.Combobox(self.frame_transfer, values=list(self.accounts) + ["新增账户"], state="readonly")
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
        def _on_acc_selected(widget):
            val = (widget.get() or "").strip()
            if val == "新增账户":
                from ui_account_manager import AccountDialog
                dlg = AccountDialog(self, None)
                self.wait_window(dlg)
                if dlg.result:
                    from storage import load_state, add_account, save_state, get_account_names
                    from models import Account
                    s = load_state()
                    a = dlg.result
                    add_account(s, Account(**a))
                    save_state(s)
                    names = get_account_names(s)
                    self.accounts = names
                    self.cb_account["values"] = list(names) + ["新增账户"]
                    self.cb_to["values"] = list(names) + ["新增账户"]
                    self.cb_from["values"] = list(names) + ["新增账户"]
                    widget.set(a.get("name",""))
        self.cb_account.bind("<<ComboboxSelected>>", lambda e: _on_acc_selected(self.cb_account))
        self.cb_to.bind("<<ComboboxSelected>>", lambda e: _on_acc_selected(self.cb_to))
        self.cb_from.bind("<<ComboboxSelected>>", lambda e: _on_acc_selected(self.cb_from))
        if initial:
            self.date_str = (initial.get("time", "")[:19].replace("T", " ") or "")
            if self.btn_date:
                self.btn_date.configure(text=self._date_button_text())
            self.e_amount.insert(0, str(initial.get("amount", "")))
            self.cb_category.set(initial.get("category", ""))
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
        typ = normalize_ttype(t)
        cats = []
        if typ in ["收入","报销类收入","支出","报销类支出"]:
            sc = "收入" if typ in ["收入","报销类收入"] else "支出"
            try:
                cats = get_categories(load_state(), sc)
            except Exception:
                cats = []
        self.cb_category["values"] = list(cats)
        if not (self.cb_category.get() or "").strip() and cats:
            self.cb_category.set(cats[0])

    def on_ok(self):
        try:
            tstr = (self.date_str or "").strip()
            if not tstr:
                raise ValueError("请选择交易日期")
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
                "category": self.cb_category.get().strip(),
                "ttype": ttype,
                "account": acc,
                "to_account": to_acc,
                "from_account": from_acc,
                "note": self.e_note.get().strip(),
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _date_button_text(self):
        try:
            if not (self.date_str or "").strip():
                return "请选择日期"
            dt = datetime.strptime(self.date_str, "%Y-%m-%d %H:%M:%S")
            if dt.date() == datetime.now().date():
                return "今天"
            return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"
        except Exception:
            return "请选择日期"

    def show_calendar(self, anchor):
        if self.calendar_win and self.calendar_win.winfo_exists():
            self.calendar_win.destroy()
        self.calendar_win = tk.Toplevel(self)
        self.calendar_win.title("选择日期")
        self.calendar_win.transient(self)
        self.calendar_win.grab_set()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height()
        self.calendar_win.geometry(f"420x300+{x}+{y}")
        now = datetime.now()
        self.cal_year = tk.IntVar(value=now.year)
        self.cal_month = tk.IntVar(value=now.month)
        top = ttk.Frame(self.calendar_win)
        top.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(top, text="◀", width=2, command=lambda: (self.cal_year.set(int(self.cal_year.get())-1), self._build_days())).pack(side=tk.LEFT)
        ttk.Label(top, text="年").pack(side=tk.LEFT)
        ycb = ttk.Combobox(top, values=[str(i) for i in range(now.year-10, now.year+11)], textvariable=self.cal_year, state="readonly", width=4)
        ycb.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="▶", width=2, command=lambda: (self.cal_year.set(int(self.cal_year.get())+1), self._build_days())).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="◀", width=2, command=lambda: (self.cal_month.set(12 if int(self.cal_month.get())==1 else int(self.cal_month.get())-1), self._build_days())).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="月").pack(side=tk.LEFT)
        mcb = ttk.Combobox(top, values=[str(i) for i in range(1,13)], textvariable=self.cal_month, state="readonly", width=2)
        mcb.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="▶", width=2, command=lambda: (self.cal_month.set(1 if int(self.cal_month.get())==12 else int(self.cal_month.get())+1), self._build_days())).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="今日", command=lambda: (self.cal_year.set(datetime.now().year), self.cal_month.set(datetime.now().month), self._build_days())).pack(side=tk.LEFT, padx=6)
        ycb.bind("<<ComboboxSelected>>", lambda e: self._build_days())
        mcb.bind("<<ComboboxSelected>>", lambda e: self._build_days())
        self.days_frame = ttk.Frame(self.calendar_win)
        self.days_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._build_days()

    def _build_days(self):
        for w in self.days_frame.winfo_children():
            w.destroy()
        year = int(self.cal_year.get())
        month = int(self.cal_month.get())
        import calendar
        cal = calendar.Calendar(firstweekday=0)
        row = 0
        for week in cal.monthdayscalendar(year, month):
            col = 0
            for d in week:
                txt = str(d) if d != 0 else ""
                b = ttk.Button(self.days_frame, text=txt or " ", width=4)
                if d != 0:
                    b.configure(command=lambda day=d: self._pick_date(year, month, day))
                b.grid(row=row, column=col, padx=2, pady=2)
                col += 1
            row += 1

    def _pick_date(self, y, m, d):
        self.date_str = f"{y:04d}-{m:02d}-{d:02d} 12:00:00"
        if self.calendar_win and self.calendar_win.winfo_exists():
            self.calendar_win.destroy()
        if hasattr(self, 'btn_date'):
            self.btn_date.configure(text=self._date_button_text())
