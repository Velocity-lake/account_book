import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta
from storage import load_state, save_state, remove_account, find_account

class CreditCardPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.state = load_state()
        self.filters = {"bank": "", "status": "", "q": ""}
        self.sort_key = ("今日账期天数", False)
        self.build_ui()
        self.refresh()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(top, text="信用卡管理", font=("Microsoft YaHei", 16)).pack(side=tk.LEFT)
        ttk.Label(top, text="银行").pack(side=tk.LEFT, padx=6)
        self.cb_bank = ttk.Combobox(top, values=self._get_banks(), state="normal")
        self.cb_bank.pack(side=tk.LEFT)
        self.cb_bank.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())
        ttk.Label(top, text="状态").pack(side=tk.LEFT, padx=6)
        self.cb_status = ttk.Combobox(top, values=["","有效","停用","注销"], state="normal")
        self.cb_status.pack(side=tk.LEFT)
        self.cb_status.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())
        self.e_search = ttk.Entry(top)
        self.e_search.pack(side=tk.LEFT, padx=6)
        self.e_search.bind("<Return>", lambda e: self._on_filter_change())
        ttk.Button(top, text="列管理", command=self._manage_columns).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="删除选中", command=self._delete_selected).pack(side=tk.RIGHT, padx=4)

        prefs = (self.state.get("prefs", {}) or {}).get("credit_cards", {})
        self.visible_columns = list((prefs or {}).get("visible_columns", [])) or self._all_columns()
        cols = list(self.visible_columns)
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for c in cols:
            self.tree.heading(c, text=c, command=lambda col=c: self._sort_by(col))
            self.tree.column(c, width=(120 if c not in ("备注","今日账期天数") else (220 if c=="备注" else 140)), stretch=False)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑", command=self._edit_selected)
        self.menu.add_command(label="删除选中", command=self._delete_selected)

    def _all_columns(self):
        return ["银行","卡名","后四位","信用额度","账单日","还款日","还款偏移","今日账期天数","状态","备注"]

    def _get_banks(self):
        banks = set()
        for a in self.state.get("accounts", []):
            if (a.get("type") or "") == "信用卡":
                b = (a.get("bank") or "").strip()
                if b:
                    banks.add(b)
        return [""] + sorted(banks)

    def refresh(self):
        self.state = load_state()
        self.tree.delete(*self.tree.get_children())
        cols = list(self.visible_columns)
        rows = []
        for a in self.state.get("accounts", []):
            if (a.get("type") or "") != "信用卡":
                continue
            if self.filters.get("bank") and (a.get("bank") or "") != self.filters.get("bank"):
                continue
            if self.filters.get("status") and (a.get("status") or "") != self.filters.get("status"):
                continue
            if self.filters.get("q"):
                q = self.filters.get("q").strip()
                text = " ".join([str(a.get("name","")), str(a.get("bank","")), str(a.get("last4","")), str(a.get("note",""))])
                if q and (q not in text):
                    continue
            term = self._calc_term_days(a)
            row_map = {
                "银行": a.get("bank",""),
                "卡名": a.get("name",""),
                "后四位": a.get("last4",""),
                "信用额度": str(a.get("limit",0.0)),
                "账单日": str(a.get("bill_day",0)),
                "还款日": str(a.get("repay_day",0)),
                "还款偏移": str(a.get("repay_offset",0)),
                "今日账期天数": str(term),
                "状态": a.get("status",""),
                "备注": a.get("note",""),
            }
            rows.append([row_map.get(c, "") for c in cols])
        key, desc = self.sort_key
        idx = cols.index(key) if key in cols else 0
        rows.sort(key=lambda r: self._sort_value(idx, r), reverse=desc)
        for r in rows:
            self.tree.insert("", tk.END, values=r)

    def _sort_value(self, idx, row):
        v = row[idx]
        try:
            return float(v)
        except Exception:
            return str(v)

    def _on_filter_change(self):
        self.filters["bank"] = self.cb_bank.get().strip()
        self.filters["status"] = self.cb_status.get().strip()
        self.filters["q"] = self.e_search.get().strip()
        self.refresh()

    def _sort_by(self, col):
        if self.sort_key[0] == col:
            self.sort_key = (col, not self.sort_key[1])
        else:
            self.sort_key = (col, False)
        self.refresh()

    def _on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            try:
                sel = set(self.tree.selection())
                sel.add(iid)
                self.tree.selection_set(list(sel))
            except Exception:
                self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    def _edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], 'values')
        name = vals[1]
        a = find_account(self.state, name)
        if not a:
            return
        dlg = CreditCardDialog(self, a)
        self.wait_window(dlg)
        if dlg.result:
            a.update(dlg.result)
            save_state(self.state)
            self.refresh()

    def _delete_selected(self):
        sels = self.tree.selection()
        if not sels:
            return
        names = []
        for iid in sels:
            v = self.tree.item(iid, 'values')
            if v:
                names.append(v[1])
        if not names:
            return
        if not messagebox.askyesno("确认", f"删除选中 {len(names)} 张信用卡？删除后账单中的引用不会自动移除"):
            return
        for n in names:
            remove_account(self.state, n)
        save_state(self.state)
        self.refresh()

    def _manage_columns(self):
        dlg = ColumnDialog(self, self.visible_columns, self._all_columns())
        self.wait_window(dlg)
        if dlg.result:
            self.visible_columns = list(dlg.result)
            s = load_state()
            prefs = s.setdefault("prefs", {}).setdefault("credit_cards", {})
            prefs["visible_columns"] = list(self.visible_columns)
            save_state(s)
            try:
                self.tree.destroy()
            except Exception:
                pass
            cols = list(self.visible_columns)
            self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
            for c in cols:
                self.tree.heading(c, text=c, command=lambda col=c: self._sort_by(col))
                self.tree.column(c, width=(120 if c not in ("备注","今日账期天数") else (220 if c=="备注" else 140)), stretch=False)
            self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            self.tree.bind("<Button-3>", self._on_right_click)
            self.refresh()

    def _calc_term_days(self, a):
        today = date.today()
        bill_day = int(a.get("bill_day", 0) or 0)
        repay_day = int(a.get("repay_day", 0) or 0)
        offset = int(a.get("repay_offset", 0) or 0)
        def last_day(y, m):
            if m == 12:
                return 31
            return (date(y, m+1, 1) - timedelta(days=1)).day
        def make_date(y, m, d):
            ld = last_day(y, m)
            dd = d if d > 0 else ld
            dd = dd if dd <= ld else ld
            return date(y, m, dd)
        y = today.year
        m = today.month
        bill_this = make_date(y, m, bill_day or 1)
        if today <= bill_this:
            cy_y, cy_m = y, m
        else:
            cy_m = m + 1
            cy_y = y + (1 if cy_m > 12 else 0)
            cy_m = 1 if cy_m > 12 else cy_m
        bill_dt = make_date(cy_y, cy_m, bill_day or 1)
        if offset and offset > 0:
            repay_dt = bill_dt + timedelta(days=offset)
        else:
            rm = cy_m + 1
            ry = cy_y + (1 if rm > 12 else 0)
            rm = 1 if rm > 12 else rm
            repay_dt = make_date(ry, rm, repay_day or 1)
        if repay_dt <= today:
            rm = repay_dt.month + 1
            ry = repay_dt.year + (1 if rm > 12 else 0)
            rm = 1 if rm > 12 else rm
            repay_dt = make_date(ry, rm, repay_day or (repay_dt.day))
        return (repay_dt - today).days

class CreditCardDialog(tk.Toplevel):
    def __init__(self, master, initial):
        super().__init__(master)
        self.result = None
        self.title("编辑信用卡")
        self.grab_set()
        f = ttk.Frame(self)
        f.pack(padx=16, pady=16)
        ttk.Label(f, text="卡名").grid(row=0, column=0)
        self.e_name = ttk.Entry(f)
        self.e_name.grid(row=0, column=1)
        ttk.Label(f, text="银行").grid(row=1, column=0)
        self.e_bank = ttk.Entry(f)
        self.e_bank.grid(row=1, column=1)
        ttk.Label(f, text="后四位").grid(row=2, column=0)
        self.e_last4 = ttk.Entry(f)
        self.e_last4.grid(row=2, column=1)
        ttk.Label(f, text="信用额度").grid(row=3, column=0)
        self.e_limit = ttk.Entry(f)
        self.e_limit.grid(row=3, column=1)
        ttk.Label(f, text="账单日").grid(row=4, column=0)
        self.e_bill_day = ttk.Entry(f)
        self.e_bill_day.grid(row=4, column=1)
        ttk.Label(f, text="还款日").grid(row=5, column=0)
        self.e_repay_day = ttk.Entry(f)
        self.e_repay_day.grid(row=5, column=1)
        ttk.Label(f, text="还款偏移").grid(row=6, column=0)
        self.e_repay_offset = ttk.Entry(f)
        self.e_repay_offset.grid(row=6, column=1)
        ttk.Label(f, text="状态").grid(row=7, column=0)
        self.cb_status = ttk.Combobox(f, values=["有效","停用","注销"], state="normal")
        self.cb_status.grid(row=7, column=1)
        ttk.Label(f, text="备注").grid(row=8, column=0)
        self.e_note = ttk.Entry(f)
        self.e_note.grid(row=8, column=1)
        b = ttk.Frame(f)
        b.grid(row=9, column=0, columnspan=2, pady=8)
        ttk.Button(b, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(b, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=4)
        f.columnconfigure(1, weight=1)
        if initial:
            self.e_name.insert(0, initial.get("name",""))
            self.e_bank.insert(0, initial.get("bank",""))
            self.e_last4.insert(0, initial.get("last4",""))
            self.e_limit.insert(0, str(initial.get("limit",0)))
            self.e_bill_day.insert(0, str(initial.get("bill_day",0)))
            self.e_repay_day.insert(0, str(initial.get("repay_day",0)))
            self.e_repay_offset.insert(0, str(initial.get("repay_offset",0)))
            self.cb_status.set(initial.get("status","有效"))
            self.e_note.insert(0, initial.get("note",""))

    def on_ok(self):
        try:
            name = self.e_name.get().strip()
            bank = self.e_bank.get().strip()
            last4 = self.e_last4.get().strip()
            limit = float(self.e_limit.get().strip() or "0")
            bill_day = int(self.e_bill_day.get().strip() or "0")
            repay_day = int(self.e_repay_day.get().strip() or "0")
            repay_offset = int(self.e_repay_offset.get().strip() or "0")
            status = self.cb_status.get().strip() or "有效"
            note = self.e_note.get().strip()
            if not name:
                raise ValueError("卡名不能为空")
            self.result = {
                "name": name,
                "bank": bank,
                "last4": last4,
                "limit": limit,
                "bill_day": bill_day,
                "repay_day": repay_day,
                "repay_offset": repay_offset,
                "status": status,
                "type": "信用卡",
                "note": note,
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))

class ColumnDialog(tk.Toplevel):
    def __init__(self, master, current, all_cols):
        super().__init__(master)
        self.result = None
        self.title("列管理")
        self.grab_set()
        f = ttk.Frame(self)
        f.pack(padx=12, pady=12)
        self.vars = {}
        for i, c in enumerate(all_cols):
            v = tk.BooleanVar(value=(c in current))
            self.vars[c] = v
            ttk.Checkbutton(f, text=c, variable=v).grid(row=i, column=0, sticky=tk.W)
        b = ttk.Frame(f)
        b.grid(row=len(all_cols), column=0, pady=8)
        ttk.Button(b, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(b, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=4)

    def on_ok(self):
        res = []
        for c, v in self.vars.items():
            if v.get():
                res.append(c)
        self.result = res
        self.destroy()
