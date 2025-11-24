import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from storage import load_invest_state, save_invest_state, get_invest_account_names
from utils import parse_datetime, format_amount, gen_id

class InvestBillListPage(ttk.Frame):
    def __init__(self, master, initial_account: str = None):
        super().__init__(master)
        self.state = load_invest_state()
        self.initial_account = initial_account
        self.last_filters = {"year": "", "month": "", "ttype": "", "account": "", "term": ""}
        self.build_ui()
        self.refresh()

    def build_ui(self):
        f = ttk.Frame(self)
        f.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(f, text="年份").pack(side=tk.LEFT, padx=2)
        self.cb_year = ttk.Combobox(f, state="readonly", width=6)
        self.cb_year.pack(side=tk.LEFT, padx=2)
        self.cb_year.bind("<<ComboboxSelected>>", lambda e: self.on_year_change())
        ttk.Label(f, text="月份").pack(side=tk.LEFT, padx=2)
        self.cb_month = ttk.Combobox(f, state="readonly", width=7)
        self.cb_month.pack(side=tk.LEFT, padx=2)
        self.cb_month.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        ttk.Label(f, text="买入/卖出").pack(side=tk.LEFT, padx=2)
        self.cb_type = ttk.Combobox(f, values=["", "买入", "卖出"], state="readonly", width=10)
        self.cb_type.pack(side=tk.LEFT, padx=2)
        self.cb_type.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        ttk.Label(f, text="账户").pack(side=tk.LEFT, padx=2)
        self.cb_account = ttk.Combobox(f, state="readonly", width=14)
        self.cb_account.pack(side=tk.LEFT, padx=2)
        self.cb_account.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        ttk.Label(f, text="搜索").pack(side=tk.LEFT, padx=(6,0))
        self.e_search = ttk.Entry(f, width=20)
        self.e_search.pack(side=tk.LEFT, padx=2)
        self.e_search.bind("<KeyRelease>", lambda e: self.apply_filter())
        ttk.Button(f, text="新增", command=self.add_record).pack(side=tk.RIGHT, padx=4)
        ttk.Button(f, text="导入", command=self.import_records).pack(side=tk.RIGHT, padx=4)
        ttk.Button(f, text="删除选中", command=self.delete_selected).pack(side=tk.RIGHT, padx=4)
        ttk.Button(f, text="导出", command=self.export_all_xlsx).pack(side=tk.RIGHT, padx=4)

        self.all_columns = [
            "交易时间","金额","买入/卖出","账户","备注","id"
        ]
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(table_frame, columns=self.all_columns, show="headings", selectmode="extended")
        self.tree["displaycolumns"] = tuple(self.all_columns)
        for c in self.all_columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=(200 if c == "备注" else 140), stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.vbar.set)
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=self.hbar.set)
        self.hbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑", command=self.on_edit)
        self.menu.add_command(label="删除选中", command=self.delete_selected)
        self.menu.add_separator()
        self.menu.add_command(label="批量修改买入/卖出", command=self.bulk_modify_type)
        self.menu.add_command(label="批量修改账户", command=self.bulk_modify_account)

    def on_year_change(self):
        self._update_months_values()
        self.apply_filter()

    def _update_months_values(self):
        months = set()
        year_sel = self.cb_year.get().strip()
        for t in self.state.get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                if year_sel and dt.strftime("%Y") != year_sel:
                    continue
                months.add(dt.strftime("%Y-%m"))
            except Exception:
                pass
        self.cb_month["values"] = [""] + sorted(list(months))

    def refresh(self):
        self.state = load_invest_state()
        years = set()
        for t in self.state.get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                years.add(dt.strftime("%Y"))
            except Exception:
                pass
        self.cb_year["values"] = [""] + sorted(list(years))
        self._update_months_values()
        # 账户下拉
        try:
            self.cb_account["values"] = [""] + get_invest_account_names(self.state)
            if self.initial_account:
                self.cb_account.set(self.initial_account)
        except Exception:
            pass
        self.apply_filter()

    def apply_filter(self):
        self.tree.delete(*self.tree.get_children())
        year = self.cb_year.get().strip()
        month = self.cb_month.get().strip()
        ttype = self.cb_type.get().strip()
        account_sel = self.cb_account.get().strip()
        term = self.e_search.get().strip().lower()
        rows = list(self.state.get("transactions", []))
        for t in rows:
            dt = parse_datetime(t.get("time"))
            if year and dt.strftime("%Y") != year:
                continue
            if month and dt.strftime("%Y-%m") != month:
                continue
            if ttype and (t.get("ttype") or "") != ttype:
                continue
            acc_val = (t.get("account") or "").strip()
            if account_sel and account_sel != acc_val:
                continue
            if term:
                fields = [
                    dt.strftime("%Y-%m-%d"),
                    format_amount(float(t.get("amount",0))),
                    t.get("ttype",""),
                    t.get("account",""),
                    t.get("note",""),
                    t.get("id",""),
                ]
                joined = "\n".join(str(x) for x in fields).lower()
                if term not in joined:
                    continue
            vals = [
                dt.strftime("%Y-%m-%d"),
                format_amount(float(t.get("amount",0))),
                t.get("ttype",""),
                t.get("account",""),
                t.get("note",""),
                t.get("id",""),
            ]
            self.tree.insert("", tk.END, values=vals)

    def selected_tx_ids(self):
        ids = []
        for iid in self.tree.selection():
            vals = self.tree.item(iid, "values")
            if vals:
                ids.append(vals[-1])
        return ids

    def delete_selected(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(ids)} 条投资账单？"):
            return
        s = load_invest_state()
        s["transactions"] = [t for t in s.get("transactions", []) if t.get("id") not in ids]
        save_invest_state(s)
        self.refresh()

    def add_record(self):
        win = tk.Toplevel(self)
        win.title("新增投资理财交易")
        win.grab_set()
        names = get_invest_account_names(load_invest_state())
        ttk.Label(win, text="交易日期(YYYY-MM-DD)").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        e_date = ttk.Entry(win)
        e_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        e_date.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Button(win, text="选择日期", command=lambda: self._open_calendar_for(win, e_date)).grid(row=0, column=2, padx=4)
        ttk.Label(win, text="金额").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        e_amt = ttk.Entry(win)
        e_amt.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(win, text="买入/卖出").grid(row=2, column=0, padx=8, pady=6, sticky=tk.W)
        cb_tt = ttk.Combobox(win, values=["买入","卖出"], state="readonly")
        cb_tt.grid(row=2, column=1, padx=8, pady=6, sticky=tk.EW)
        cb_tt.set("买入")
        ttk.Label(win, text="账户").grid(row=3, column=0, padx=8, pady=6, sticky=tk.W)
        cb_acc = ttk.Combobox(win, values=names, state="readonly")
        cb_acc.grid(row=3, column=1, padx=8, pady=6, sticky=tk.EW)
        try:
            if self.initial_account and self.initial_account in names:
                cb_acc.set(self.initial_account)
        except Exception:
            pass
        ttk.Label(win, text="备注").grid(row=5, column=0, padx=8, pady=6, sticky=tk.W)
        e_note = ttk.Entry(win)
        e_note.grid(row=5, column=1, padx=8, pady=6, sticky=tk.EW)
        win.columnconfigure(1, weight=1)
        def ok():
            try:
                amt = float(e_amt.get())
            except Exception:
                messagebox.showerror("错误", "请输入数字金额")
                return
            date = (e_date.get() or datetime.now().strftime("%Y-%m-%d")).strip()
            t = {
                "id": gen_id(),
                "time": f"{date}T00:00:00",
                "amount": amt,
                "category": "",
                "ttype": cb_tt.get().strip(),
                "account": cb_acc.get().strip(),
                "note": e_note.get().strip(),
                "record_time": datetime.now().isoformat(),
                "record_source": "手动输入",
            }
            s = load_invest_state()
            s.setdefault("transactions", []).append(t)
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=6, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=6, column=1, padx=8, pady=8)

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_add(iid)
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def selected_tx_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return vals[-1] if vals else None

    def on_edit(self):
        tx_id = self.selected_tx_id()
        if not tx_id:
            return
        s = load_invest_state()
        t = None
        for it in s.get("transactions", []):
            if it.get("id") == tx_id:
                t = dict(it)
                break
        if not t:
            return
        win = tk.Toplevel(self)
        win.title("编辑投资理财交易")
        win.grab_set()
        names = get_invest_account_names(s)
        ttk.Label(win, text="交易日期(YYYY-MM-DD)").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        e_date = ttk.Entry(win)
        e_date.insert(0, t.get("time","")[:10])
        e_date.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Button(win, text="选择日期", command=lambda: self._open_calendar_for(win, e_date)).grid(row=0, column=2, padx=4)
        ttk.Label(win, text="金额").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        e_amt = ttk.Entry(win)
        e_amt.insert(0, str(t.get("amount", "")))
        e_amt.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(win, text="买入/卖出").grid(row=2, column=0, padx=8, pady=6, sticky=tk.W)
        cb_tt = ttk.Combobox(win, values=["买入","卖出"], state="readonly")
        cb_tt.grid(row=2, column=1, padx=8, pady=6, sticky=tk.EW)
        cb_tt.set((t.get("ttype") or "买入"))
        ttk.Label(win, text="账户").grid(row=3, column=0, padx=8, pady=6, sticky=tk.W)
        cb_acc = ttk.Combobox(win, values=names, state="readonly")
        cb_acc.grid(row=3, column=1, padx=8, pady=6, sticky=tk.EW)
        cb_acc.set((t.get("account") or ""))
        ttk.Label(win, text="备注").grid(row=4, column=0, padx=8, pady=6, sticky=tk.W)
        e_note = ttk.Entry(win)
        e_note.insert(0, t.get("note",""))
        e_note.grid(row=4, column=1, padx=8, pady=6, sticky=tk.EW)
        win.columnconfigure(1, weight=1)
        def ok():
            try:
                amt = float(e_amt.get())
            except Exception:
                messagebox.showerror("错误", "请输入数字金额")
                return
            date = (e_date.get() or datetime.now().strftime("%Y-%m-%d")).strip()
            new_t = dict(t)
            new_t.update({
                "time": f"{date}T00:00:00",
                "amount": amt,
                "category": "",
                "ttype": cb_tt.get().strip(),
                "account": cb_acc.get().strip(),
                "note": e_note.get().strip(),
            })
            # 更新投资账单
            for i, it in enumerate(s.get("transactions", [])):
                if it.get("id") == tx_id:
                    s["transactions"][i] = new_t
                    break
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=5, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=5, column=1, padx=8, pady=8)

    def _open_calendar_for(self, anchor_win, target_entry):
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

    def bulk_modify_type(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        win = tk.Toplevel(self)
        win.title("批量修改买入/卖出")
        win.grab_set()
        ttk.Label(win, text="买入/卖出").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        cb_tt = ttk.Combobox(win, values=["买入","卖出"], state="readonly")
        cb_tt.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        def ok():
            val = cb_tt.get().strip()
            if not val:
                win.destroy()
                return
            s = load_invest_state()
            for i, it in enumerate(s.get("transactions", [])):
                if it.get("id") in ids:
                    new = dict(it)
                    new["ttype"] = val
                    # 清理旧转账痕迹
                    new["to_account"] = None
                    new["from_account"] = None
                    new["category"] = ""
                    s["transactions"][i] = new
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=1, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=1, column=1, padx=8, pady=8)

    def bulk_modify_account(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        names = get_invest_account_names(load_invest_state())
        win = tk.Toplevel(self)
        win.title("批量修改账户")
        win.grab_set()
        ttk.Label(win, text="账户").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        cb_acc = ttk.Combobox(win, values=names, state="readonly")
        cb_acc.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        def ok():
            acc = cb_acc.get().strip()
            if not acc:
                win.destroy()
                return
            s = load_invest_state()
            for i, it in enumerate(s.get("transactions", [])):
                if it.get("id") in ids:
                    new = dict(it)
                    new["account"] = acc
                    new["to_account"] = None
                    new["from_account"] = None
                    s["transactions"][i] = new
            save_invest_state(s)
            win.destroy()
            self.refresh()
        ttk.Button(win, text="确定", command=ok).grid(row=1, column=0, padx=8, pady=8)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=1, column=1, padx=8, pady=8)

    def import_records(self):
        paths = filedialog.askopenfilenames(title="导入投资理财账单", filetypes=[("所有文件","*.*"), ("CSV 文件","*.csv"), ("Excel 文件","*.xlsx")])
        if not paths:
            return
        rows_all = []
        names = get_invest_account_names(load_invest_state())
        try:
            for p in paths:
                if p.lower().endswith('.csv'):
                    import csv
                    with open(p, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            rows_all.append(r)
                elif p.lower().endswith('.xlsx'):
                    from xlsx_reader import read_xlsx
                    rows_all.extend(read_xlsx(p))
                else:
                    import csv
                    with open(p, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            rows_all.append(r)
        except Exception as e:
            messagebox.showerror("导入失败", str(e))
            return
        mapped = []
        for r in rows_all:
            try:
                date = (str(r.get("交易时间") or r.get("日期") or r.get("time") or r.get("Date") or "")).strip()[:10]
                amt = float(str(r.get("金额") or r.get("amount") or "0").replace(",",""))
                typ = (str(r.get("买入/卖出") or r.get("方向") or r.get("ttype") or "")).strip()
                acc = (str(r.get("账户") or r.get("account") or "")).strip()
                note = (str(r.get("备注") or r.get("note") or "")).strip()
            except Exception:
                continue
            if not date or not typ or not acc:
                continue
            mapped.append({
                "id": gen_id(),
                "time": f"{date}T00:00:00",
                "amount": amt,
                "category": "",
                "ttype": ("买入" if typ == "买入" else "卖出"),
                "account": acc,
                "note": note,
                "record_time": datetime.now().isoformat(),
                "record_source": "导入",
            })
        if not mapped:
            messagebox.showerror("导入失败", "未识别到有效记录")
            return
        s = load_invest_state()
        s.setdefault("transactions", []).extend(mapped)
        save_invest_state(s)
        messagebox.showinfo("导入成功", f"已导入 {len(mapped)} 条记录")
        self.refresh()

    def export_all_xlsx(self):
        path = filedialog.asksaveasfilename(title="导出投资账单", defaultextension=".xlsx", filetypes=[("Excel 文件","*.xlsx")])
        if not path:
            return
        header = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
        rows = []
        for t in load_invest_state().get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                tstr = dt.strftime("%Y-%m-%d")
            except Exception:
                tstr = str(t.get("time",""))[:10]
            rows.append([
                tstr,
                format_amount(float(t.get("amount",0))),
                t.get("category",""),
                t.get("ttype",""),
                t.get("account",""),
                t.get("to_account",""),
                t.get("from_account",""),
                t.get("note",""),
            ])
        try:
            self._write_xlsx(path, header, rows)
            messagebox.showinfo("导出成功", f"已导出 {len(rows)} 条记录")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _write_xlsx(self, path, header, rows):
        import io, zipfile
        def col_name(i):
            s = ""
            i += 1
            while i:
                i, r = divmod(i-1, 26)
                s = chr(65+r) + s
            return s
        strs = []
        def add_str(s):
            s = str(s)
            if s in strs:
                return strs.index(s)
            strs.append(s)
            return len(strs)-1
        for h in header:
            add_str(h)
        for r in rows:
            for v in r:
                add_str(v)
        shared_xml = io.StringIO()
        shared_xml.write("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
        shared_xml.write("<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"{}\" uniqueCount=\"{}\">".format(len(strs), len(strs)))
        for sval in strs:
            shared_xml.write("<si><t>{}</t></si>".format(str(sval).replace("&","&amp;").replace("<","&lt;")))
        shared_xml.write("</sst>")
        sheet_xml = io.StringIO()
        sheet_xml.write("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
        sheet_xml.write("<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>")
        row_idx = 1
        def write_row(vals):
            nonlocal row_idx
            sheet_xml.write(f"<row r=\"{row_idx}\">")
            for i, v in enumerate(vals):
                c = f"{col_name(i)}{row_idx}"
                idx = add_str(v)
                sheet_xml.write(f"<c r=\"{c}\" t=\"s\"><v>{idx}</v></c>")
            sheet_xml.write("</row>")
            row_idx += 1
        write_row(header)
        for r in rows:
            write_row(r)
        sheet_xml.write("</sheetData></worksheet>")
        workbook_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>"
        wb_rels = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/><Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings\" Target=\"sharedStrings.xml\"/></Relationships>"
        rels_root = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>"
        content_types = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/><Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/></Types>"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels_root)
            z.writestr("xl/workbook.xml", workbook_xml)
            z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
            z.writestr("xl/sharedStrings.xml", shared_xml.getvalue())
            z.writestr("xl/worksheets/sheet1.xml", sheet_xml.getvalue())
