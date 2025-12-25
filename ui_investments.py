import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from storage import load_invest_state, save_invest_state, get_invest_account_names, add_invest_account, remove_invest_account, set_account_valuation, get_account_valuation
from utils import gen_id, parse_datetime, xirr

class InvestmentsPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.state = load_invest_state()
        self.build_ui()
        self.refresh()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(top, text="投资理财", font=("Microsoft YaHei", 16)).pack(side=tk.LEFT)
        btns = ttk.Frame(top)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="新增账户", command=self.add_account).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="删除账户", command=self.delete_account).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="设置估值", command=self.set_valuation).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="打开账单列表", command=self.open_bill_list).pack(side=tk.LEFT, padx=4)

        cols = ["账户名","累计买入","累计卖出","当前市值","盈亏","ROI","XIRR","持有天数"]
        table = ttk.Frame(self)
        table.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vbar.set)
        vbar.grid(row=0, column=1, sticky="ns")
        hbar = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hbar.set)
        hbar.grid(row=1, column=0, sticky="ew")
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

    def refresh(self):
        self.state = load_invest_state()
        self.tree.delete(*self.tree.get_children())
        names = get_invest_account_names(self.state)
        # 汇总账户
        summary = self._compute_summary_stats()
        self.tree.insert("", tk.END, values=[
            "汇总账户",
            str(int(round(summary['in_amt']))),
            str(int(round(summary['out_amt']))),
            str(int(round(summary['value']))),
            str(int(round(summary['pnl']))),
            (f"{summary['roi']*100:.2f}%" if summary['roi'] is not None else "—"),
            (f"{summary['xirr']*100:.2f}%" if summary['xirr'] is not None else "—"),
            str(summary['days']),
        ])
        # 各账户
        for name in names:
            stats = self._compute_stats_for_account(name)
            vals = [
                name,
                str(int(round(stats['in_amt']))),
                str(int(round(stats['out_amt']))),
                str(int(round(stats['value']))),
                str(int(round(stats['pnl']))),
                (f"{stats['roi']*100:.2f}%" if stats['roi'] is not None else "—"),
                (f"{stats['xirr']*100:.2f}%" if stats['xirr'] is not None else "—"),
                str(stats['days']),
            ]
            self.tree.insert("", tk.END, values=vals)
        # 行右键菜单
        self.tree.bind("<Button-3>", self.on_right_click)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="查看该账户账单明细", command=self.open_selected_account_bills)
        self.menu.add_command(label="添加记账", command=self.add_record_for_selected)
        self.menu.add_command(label="修改当前市值", command=self.quick_edit_valuation)

    def _compute_stats_for_account(self, name: str):
        in_amt = 0.0
        out_amt = 0.0
        value = 0.0
        cash_flows = []
        base_dt = None
        for t in self.state.get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                amt = float(t.get("amount", 0))
                typ = (t.get("ttype") or "").strip()
                acc = (t.get("account") or "").strip()
                cf = None
                if acc == name and typ == "买入":
                    in_amt += amt
                    cf = -amt
                elif acc == name and typ == "卖出":
                    out_amt += amt
                    cf = amt
                else:
                    # 兼容旧数据：按转入/转出判断
                    to_acc = (t.get("to_account") or "").strip()
                    from_acc = (t.get("from_account") or "").strip()
                    if to_acc == name:
                        in_amt += amt
                        cf = -amt
                    elif from_acc == name:
                        out_amt += amt
                        cf = amt
                if cf is None:
                    continue
                cash_flows.append((dt, cf))
                if base_dt is None or dt < base_dt:
                    base_dt = dt
            except Exception:
                pass
        val = get_account_valuation(self.state, name)
        if val and isinstance(val.get("value"), (int,float)):
            value = float(val.get("value"))
            try:
                vdt = parse_datetime(val.get("date"))
            except Exception:
                vdt = datetime.now()
            cash_flows.append((vdt, value))
        xirr_val = None
        try:
            xirr_val = xirr(sorted(cash_flows, key=lambda x: x[0]))
        except Exception:
            xirr_val = None
        pnl = value + out_amt - in_amt
        roi = None
        try:
            if in_amt > 0:
                roi = pnl / in_amt
        except Exception:
            roi = None
        days = 0
        try:
            if base_dt:
                last_dt = cash_flows[-1][0] if cash_flows else base_dt
                days = (last_dt - base_dt).days
        except Exception:
            days = 0
        return {
            "in_amt": in_amt,
            "out_amt": out_amt,
            "value": value,
            "pnl": pnl,
            "roi": roi,
            "xirr": xirr_val,
            "days": days,
        }

    def add_account(self):
        win = tk.Toplevel(self)
        win.title("新增投资账户")
        win.grab_set()
        ttk.Label(win, text="账户名").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        e_name = ttk.Entry(win)
        e_name.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(win, text="备注").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        e_note = ttk.Entry(win)
        e_note.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        win.columnconfigure(1, weight=1)
        def ok():
            name = (e_name.get() or "").strip()
            if not name:
                messagebox.showerror("错误", "请输入账户名")
                return
            s = load_invest_state()
            add_invest_account(s, {"name": name, "note": e_note.get().strip()})
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=2, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=2, column=1, padx=8, pady=8)

    def delete_account(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("确认", f"删除账户“{name}”以及其估值信息？"):
            return
        s = load_invest_state()
        remove_invest_account(s, name)
        save_invest_state(s)
        self.refresh()

    def set_valuation(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[0]
        win = tk.Toplevel(self)
        win.title("设置估值")
        win.grab_set()
        ttk.Label(win, text="估值金额").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        e_val = ttk.Entry(win)
        e_val.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(win, text="估值日期(YYYY-MM-DD)").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        e_date = ttk.Entry(win)
        e_date.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        win.columnconfigure(1, weight=1)
        def ok():
            try:
                v = float(e_val.get())
            except Exception:
                messagebox.showerror("错误", "请输入数字估值")
                return
            ds = (e_date.get() or datetime.now().strftime("%Y-%m-%d")).strip()
            s = load_invest_state()
            set_account_valuation(s, name, v, ds)
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=2, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=2, column=1, padx=8, pady=8)

    def open_bill_list(self):
        try:
            from storage import load_state
            prefs = (load_state().get("prefs", {}) or {})
            if not bool(prefs.get("investments_enabled", True)):
                return
        except Exception:
            pass
        try:
            from ui_invest_bill_list import InvestBillListPage
        except Exception:
            messagebox.showerror("错误", "投资账单列表模块未找到")
            return
        win = tk.Toplevel(self)
        win.title("投资理财账单列表")
        win.transient(self)
        win.grab_set()
        page = InvestBillListPage(win)
        page.pack(fill=tk.BOTH, expand=True)
        try:
            win.geometry("1000x600")
        except Exception:
            pass

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_add(iid)
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def open_selected_account_bills(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], 'values')
        acc = vals[0]
        try:
            from ui_invest_bill_list import InvestBillListPage
        except Exception:
            messagebox.showerror("错误", "投资账单列表模块未找到")
            return
        win = tk.Toplevel(self)
        win.title("投资理财账单列表")
        win.transient(self)
        win.grab_set()
        page = InvestBillListPage(win, initial_account=acc)
        page.pack(fill=tk.BOTH, expand=True)
        try:
            win.geometry("1000x600")
        except Exception:
            pass
    def add_record_for_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        acc = self.tree.item(sel[0], 'values')[0]
        if acc == "汇总账户":
            return
        try:
            from ui_invest_bill_list import InvestBillListPage
        except Exception:
            messagebox.showerror("错误", "投资账单列表模块未找到")
            return
        win = tk.Toplevel(self)
        win.title("投资理财账单列表")
        win.transient(self)
        win.grab_set()
        page = InvestBillListPage(win, initial_account=acc)
        page.pack(fill=tk.BOTH, expand=True)
        # 直接打开新增弹窗
        try:
            self.after(100, page.add_record)
        except Exception:
            pass
        try:
            win.geometry("1000x600")
        except Exception:
            pass

    def quick_edit_valuation(self):
        sel = self.tree.selection()
        if not sel:
            return
        acc = self.tree.item(sel[0], 'values')[0]
        if acc == "汇总账户":
            return
        win = tk.Toplevel(self)
        win.title("修改当前市值")
        win.grab_set()
        ttk.Label(win, text="当前市值").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        e_val = ttk.Entry(win)
        e_val.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(win, text="估值日期(YYYY-MM-DD)").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        e_date = ttk.Entry(win)
        e_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        e_date.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Button(win, text="选择日期", command=lambda: self._open_calendar_quick(win, e_date)).grid(row=1, column=2, padx=4)
        win.columnconfigure(1, weight=1)
        def ok():
            try:
                v = float(e_val.get())
            except Exception:
                messagebox.showerror("错误", "请输入数字估值")
                return
            ds = (e_date.get() or datetime.now().strftime("%Y-%m-%d")).strip()
            s = load_invest_state()
            set_account_valuation(s, acc, v, ds)
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=2, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=2, column=1, padx=8, pady=8)

    def _open_calendar_quick(self, anchor_win, target_entry):
        cal = tk.Toplevel(self)
        cal.title("选择日期")
        cal.transient(anchor_win)
        cal.grab_set()
        try:
            x = anchor_win.winfo_rootx()
            y = anchor_win.winfo_rooty() + 60
            cal.geometry(f"420x300+{x}+{y}")
        except Exception:
            pass
        now = datetime.now()
        year_var = tk.IntVar(value=now.year)
        month_var = tk.IntVar(value=now.month)
        top = ttk.Frame(cal)
        top.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(top, text="◀", width=2, command=lambda: (year_var.set(int(year_var.get())-1), build_days())).pack(side=tk.LEFT)
        ttk.Label(top, text="年").pack(side=tk.LEFT)
        ycb = ttk.Combobox(top, values=[str(i) for i in range(now.year-10, now.year+11)], textvariable=year_var, state="readonly", width=4)
        ycb.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="▶", width=2, command=lambda: (year_var.set(int(year_var.get())+1), build_days())).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="◀", width=2, command=lambda: (month_var.set(12 if int(month_var.get())==1 else int(month_var.get())-1), build_days())).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="月").pack(side=tk.LEFT)
        mcb = ttk.Combobox(top, values=[str(i) for i in range(1,13)], textvariable=month_var, state="readonly", width=2)
        mcb.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="▶", width=2, command=lambda: (month_var.set(1 if int(month_var.get())==12 else int(month_var.get())+1), build_days())).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="今日", command=lambda: (year_var.set(datetime.now().year), month_var.set(datetime.now().month), build_days())).pack(side=tk.LEFT, padx=6)
        ycb.bind("<<ComboboxSelected>>", lambda e: build_days())
        mcb.bind("<<ComboboxSelected>>", lambda e: build_days())
        days_frame = ttk.Frame(cal)
        days_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        def build_days():
            for w in days_frame.winfo_children():
                w.destroy()
            import calendar
            calmod = calendar.Calendar(firstweekday=0)
            row = 0
            for week in calmod.monthdayscalendar(int(year_var.get()), int(month_var.get())):
                col = 0
                for d in week:
                    txt = str(d) if d != 0 else ""
                    b = ttk.Button(days_frame, text=txt or " ", width=4)
                    if d != 0:
                        b.configure(command=lambda day=d: pick(day))
                    b.grid(row=row, column=col, padx=2, pady=2)
                    col += 1
                row += 1
        def pick(day):
            y = int(year_var.get())
            m = int(month_var.get())
            target_entry.delete(0, tk.END)
            target_entry.insert(0, f"{y:04d}-{m:02d}-{day:02d}")
            cal.destroy()
        build_days()

    def _compute_summary_stats(self):
        in_amt = 0.0
        out_amt = 0.0
        value = 0.0
        cash_flows = []
        base_dt = None
        for t in self.state.get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                amt = float(t.get("amount", 0))
                typ = (t.get("ttype") or "").strip()
                cf = None
                if typ == "买入":
                    in_amt += amt
                    cf = -amt
                elif typ == "卖出":
                    out_amt += amt
                    cf = amt
                else:
                    to_acc = (t.get("to_account") or "").strip()
                    from_acc = (t.get("from_account") or "").strip()
                    if to_acc:
                        in_amt += amt
                        cf = -amt
                    elif from_acc:
                        out_amt += amt
                        cf = amt
                if cf is None:
                    continue
                cash_flows.append((dt, cf))
                if base_dt is None or dt < base_dt:
                    base_dt = dt
            except Exception:
                pass
        vals = (self.state.get("valuations") or {})
        for _, ent in vals.items():
            try:
                v = float(ent.get("value", 0))
                value += v
                vdt = parse_datetime(ent.get("date"))
                cash_flows.append((vdt, v))
            except Exception:
                pass
        xirr_val = None
        try:
            if cash_flows:
                xirr_val = xirr(sorted(cash_flows, key=lambda x: x[0]))
        except Exception:
            xirr_val = None
        pnl = value + out_amt - in_amt
        roi = None
        try:
            if in_amt > 0:
                roi = pnl / in_amt
        except Exception:
            roi = None
        days = 0
        try:
            if base_dt:
                last_dt = cash_flows[-1][0] if cash_flows else base_dt
                days = (last_dt - base_dt).days
        except Exception:
            days = 0
        return {
            "in_amt": in_amt,
            "out_amt": out_amt,
            "value": value,
            "pnl": pnl,
            "roi": roi,
            "xirr": xirr_val,
            "days": days,
        }
