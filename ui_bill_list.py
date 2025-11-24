import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os
import time
import threading
import subprocess
from datetime import datetime, timedelta
from storage import load_state, save_state, apply_transaction_delta, get_account_names, get_transaction, remove_transaction, update_transaction, add_category, get_categories, get_category_rules, BASE_DIR, query_transactions, aggregate_sums, list_years, list_months
from utils import month_key, format_amount, gen_id, parse_datetime, normalize_ttype
from models import TRANSACTION_TYPES
from ui_add_dialog import AddTransactionDialog
from importers import import_standard_xlsx, try_import
import zipfile

class BillListPage(ttk.Frame):
    def __init__(self, master, controller=None):
        super().__init__(master)
        self.controller = controller
        self.state = load_state()
        self.last_filters = {"year": "", "month": "", "ttype": "", "category": "", "term": "", "amt_op": "", "amt_val": ""}
        self._suppress_update = False
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
        ttk.Label(f, text="所属类别").pack(side=tk.LEFT, padx=2)
        self.cb_type = ttk.Combobox(f, values=[""] + TRANSACTION_TYPES, state="readonly", width=10)
        self.cb_type.pack(side=tk.LEFT, padx=2)
        self.cb_type.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        ttk.Label(f, text="消费类别").pack(side=tk.LEFT, padx=2)
        self.e_category = ttk.Entry(f, width=14)
        self.e_category.pack(side=tk.LEFT, padx=2)
        self.e_category.bind("<KeyRelease>", lambda e: self.apply_filter())
        ttk.Label(f, text="搜索").pack(side=tk.LEFT, padx=(6,0))
        self.e_search = ttk.Entry(f, width=20)
        self.e_search.pack(side=tk.LEFT, padx=2)
        self.e_search.bind("<KeyRelease>", lambda e: self.apply_filter())
        ttk.Label(f, text="金额").pack(side=tk.LEFT, padx=(6,0))
        self.cb_amt_op = ttk.Combobox(f, values=["", ">", "<", "="], state="readonly", width=3)
        self.cb_amt_op.pack(side=tk.LEFT, padx=2)
        self.cb_amt_op.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        self.e_amt_val = ttk.Entry(f, width=8)
        self.e_amt_val.pack(side=tk.LEFT, padx=2)
        def _amt_val_sanitize(evt=None):
            s = ''.join(ch for ch in self.e_amt_val.get() if ch.isdigit())[:5]
            if s != self.e_amt_val.get():
                self.e_amt_val.delete(0, tk.END)
                self.e_amt_val.insert(0, s)
            self.apply_filter()
        self.e_amt_val.bind("<KeyRelease>", _amt_val_sanitize)
        ttk.Label(f, text="相差秒数").pack(side=tk.LEFT, padx=(6,0))
        self.e_dup_secs = ttk.Entry(f, width=6)
        self.e_dup_secs.pack(side=tk.LEFT, padx=2)
        def _dup_secs_sanitize(evt=None):
            s = ''.join(ch for ch in self.e_dup_secs.get() if ch.isdigit())[:5]
            if s != self.e_dup_secs.get():
                self.e_dup_secs.delete(0, tk.END)
                self.e_dup_secs.insert(0, s)
        self.e_dup_secs.bind("<KeyRelease>", _dup_secs_sanitize)
        self.e_dup_secs.insert(0, "10")
        ttk.Button(f, text="筛选", command=self.apply_filter).pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="重置", command=self.reset_filter).pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="查重", command=self.run_dedupe).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="导入并覆盖原有账单", command=self.import_override).pack(side=tk.LEFT, padx=4)
        if self.controller:
            ttk.Button(f, text="导入账单", command=self.open_import_dialog).pack(side=tk.RIGHT, padx=4)
        ttk.Button(f, text="导出筛选CSV", command=self.export_filtered_csv).pack(side=tk.RIGHT, padx=2)
        ttk.Button(f, text="Excel批量录入", command=self.open_excel_batch_entry).pack(side=tk.RIGHT, padx=4)
        # 内联导入面板（默认隐藏）
        self.import_panel = ttk.Frame(self)
        bar = ttk.Frame(self.import_panel)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="导入账单", font=("Microsoft YaHei", 12)).pack(side=tk.LEFT)
        btns = ttk.Frame(self.import_panel)
        btns.pack(fill=tk.X, pady=4)
        if self.controller:
            ttk.Button(btns, text="支付宝账单导入", command=self.controller._import_alipay).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="浦发银行账单导入", command=self.controller._import_spdb).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="中信银行账单导入", command=self.controller._import_citic).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="微信账单导入", command=self.controller._import_wechat).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="标准模版导入", command=self.controller._import_standard).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="其它导入", command=self.controller._import_other).pack(side=tk.LEFT, padx=6)
        # 初始隐藏（不使用内联面板，保留但不显示）
        try:
            self.import_panel.pack_forget()
        except Exception:
            pass
        self.all_columns = [
            "交易时间","金额","疑似重复","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"
        ]
        try:
            prefs = (self.state.get("prefs", {}) or {}).get("bill_list", {})
            saved = prefs.get("visible_columns")
            if isinstance(saved, list) and saved:
                self.visible_columns = [c for c in self.all_columns if c in saved]
                if "疑似重复" not in self.visible_columns:
                    self.visible_columns.append("疑似重复")
            else:
                self.visible_columns = list(self.all_columns)
        except Exception:
            self.visible_columns = list(self.all_columns)
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(table_frame, columns=self.all_columns, show="headings", selectmode="extended")
        self.tree["displaycolumns"] = tuple(self.visible_columns)
        self.sort_states = {c: 'asc' for c in self.all_columns}
        self.sort_states["交易时间"] = 'desc'
        self.current_sort_col = "交易时间"
        self.current_sort_desc = True
        for c in self.all_columns:
            self.tree.heading(c, text=f"{c} ▾", command=lambda col=c: self.on_heading_click(col))
            w_default = (200 if c == "备注" else 140)
            try:
                prefs = (self.state.get("prefs", {}) or {}).get("bill_list", {})
                cw = (prefs.get("column_widths", {}) or {}).get(c)
                w_default = int(cw) if cw else w_default
            except Exception:
                pass
            self.tree.column(c, width=w_default, stretch=False)
        # Use grid to keep scrollbar anchored at bottom across resizes
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.vbar.set)
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=self.hbar.set)
        self.hbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        status = ttk.Frame(self)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_inc = ttk.Label(status, text="筛选收入：0.00元")
        self.lbl_inc.pack(side=tk.LEFT, padx=8)
        self.lbl_exp = ttk.Label(status, text="筛选支出：0.00元")
        self.lbl_exp.pack(side=tk.LEFT, padx=8)
        self.lbl_trans = ttk.Label(status, text="筛选转账：0.00元")
        self.lbl_trans.pack(side=tk.LEFT, padx=8)
        try:
            self.lbl_inc.configure(foreground="#2ecc71")
            self.lbl_exp.configure(foreground="#ff6b6b")
        except Exception:
            pass
        sel_bar = ttk.Frame(status)
        sel_bar.pack(side=tk.RIGHT)
        self.lbl_sel_count = ttk.Label(sel_bar, text="选中条数：0")
        self.lbl_sel_count.pack(side=tk.LEFT, padx=8)
        self.lbl_sel_inc = ttk.Label(sel_bar, text="选中收入：0.00元")
        self.lbl_sel_inc.pack(side=tk.LEFT, padx=8)
        self.lbl_sel_exp = ttk.Label(sel_bar, text="选中支出：0.00元")
        self.lbl_sel_exp.pack(side=tk.LEFT, padx=8)
        self.lbl_sel_trans = ttk.Label(sel_bar, text="选中转账：0.00元")
        self.lbl_sel_trans.pack(side=tk.LEFT, padx=8)
        try:
            self.lbl_sel_inc.configure(foreground="#2ecc71")
            self.lbl_sel_exp.configure(foreground="#ff6b6b")
        except Exception:
            pass
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Shift-Button-1>", self.on_heading_shift_click)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Control-a>", self.on_ctrl_a)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Shift-MouseWheel>", lambda e: self.tree.xview_scroll(-1 * (e.delta//120), "units"))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_selection_summary())
        self.tree.bind("<ButtonRelease-1>", self._maybe_save_column_widths)
        self.column_filters = {}
        try:
            s = load_state()
            self.use_pagination = bool((s.get("prefs", {}) or {}).get("use_pagination", False))
        except Exception:
            self.use_pagination = False
        self.page_size = 200
        self.current_page = 0
        self.page_bar = ttk.Frame(status)
        self.page_bar.pack(side=tk.RIGHT)
        ttk.Button(self.page_bar, text="上一页", command=lambda: self._goto_page(max(self.current_page-1,0))).pack(side=tk.RIGHT, padx=4)
        ttk.Button(self.page_bar, text="下一页", command=lambda: self._goto_page(self.current_page+1)).pack(side=tk.RIGHT, padx=4)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑", command=self.on_edit)
        self.menu.add_command(label="删除", command=self.on_delete)
        self.menu.add_command(label="记录当日账单", command=self.on_record_for_row)
        self.menu.add_separator()
        self.menu.add_command(label="批量改为收入", command=self.bulk_change_to_income)
        self.menu.add_command(label="批量改为支出", command=self.bulk_change_to_expense)
        self.menu.add_command(label="批量改为转账", command=self.bulk_change_to_transfer)
        self.menu_batch = tk.Menu(self.menu, tearoff=0)
        self.menu_batch.add_command(label="批量修改账户", command=self.bulk_modify_accounts)
        self.menu_batch.add_command(label="批量修改消费类别", command=self.bulk_modify_category)
        self.menu_batch.add_command(label="批量修改记账来源", command=self.bulk_modify_record_source)
        self.menu.add_cascade(label="批量修改", menu=self.menu_batch)
        self.menu.add_command(label="AI预填消费类别", command=self.ai_prefill_category)
        self.menu.add_separator()
        self.menu.add_command(label="导出疑似重复", command=self.export_suspected)
        self.menu.add_command(label="一键删除疑似重复（保留每组最早一条）", command=self.dedupe_delete_keep_first)
        self.menu.add_separator()
        self.menu.add_command(label="删除选中", command=self.delete_selected)

        self.header_menu = tk.Menu(self, tearoff=0)
        self.header_menu.add_command(label="筛选该列", command=lambda: self._open_filter_for_last_header())
        self.header_menu.add_command(label="取消该列筛选", command=lambda: self._clear_filter_for_last_header())
        self.header_menu.add_command(label="隐藏该列", command=lambda: self._hide_last_header())
        self.header_menu.add_command(label="显示列管理", command=self.open_columns_manager)
        self._last_header_col = None


    def on_year_change(self):
        try:
            self._update_months_values()
        except Exception:
            pass
        self.apply_filter()

    def _update_months_values(self):
        try:
            year_sel = self.cb_year.get().strip()
        except Exception:
            year_sel = ""
        try:
            ms = list_months(year_sel)
        except Exception:
            ms = []
        self.cb_month["values"] = [""] + sorted(list(ms))
        # 若当前月份不在新列表中，清空选择
        cur = self.cb_month.get().strip()
        if cur and cur not in self.cb_month["values"]:
            self.cb_month.set("")

    def refresh(self):
        self.state = load_state()
        try:
            ys = list_years()
        except Exception:
            ys = []
        try:
            self.cb_year["values"] = [""] + sorted(list(ys))
        except Exception:
            pass
        self._update_months_values()
        self.reapply_last_filters()
        try:
            if getattr(self, "current_sort_col", None):
                self.sort_by(self.current_sort_col, bool(getattr(self, "current_sort_desc", False)))
        except Exception:
            pass

    def _get_dup_threshold_secs(self):
        try:
            s = ''.join(ch for ch in self.e_dup_secs.get() if ch.isdigit())
            v = int(s) if s else 10
            return max(0, min(86400, v))
        except Exception:
            return 10

    def _compute_suspicions(self, threshold_secs: int):
        res = {}
        groups = {}
        for t in self.state.get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                a = float(t.get("amount", 0))
                k = format_amount(abs(a))
                groups.setdefault(k, []).append((dt, t.get("id")))
            except Exception:
                pass
        for _, lst in groups.items():
            lst.sort(key=lambda x: x[0])
            n = len(lst)
            j = 0
            for i in range(n):
                while j < n and (lst[j][0] - lst[i][0]).total_seconds() <= threshold_secs:
                    j += 1
                if j - i > 1:
                    for k in range(i, j):
                        res[lst[k][1]] = True
        return res

    def run_dedupe(self):
        self.suspected_map = self._compute_suspicions(self._get_dup_threshold_secs())
        cur = self.column_filters.get("疑似重复")
        if cur == {"是"}:
            self.column_filters.pop("疑似重复", None)
        else:
            self.column_filters["疑似重复"] = {"是"}
        self.apply_filter()

    def on_heading_click(self, col):
        dir = self.sort_states.get(col, 'asc')
        new_dir = 'desc' if dir == 'asc' else 'asc'
        self.sort_states[col] = new_dir
        desc = (new_dir == 'desc')
        self.current_sort_col = col
        self.current_sort_desc = desc
        self.sort_by(col, desc)

    def sort_by(self, col, descending=False):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        def keyfunc(v):
            val = v[0]
            if col == "交易时间":
                try:
                    return parse_datetime(val)
                except Exception:
                    return datetime.min
            if col == "记账时间":
                try:
                    return parse_datetime(val)
                except Exception:
                    return datetime.min
            if col == "金额":
                try:
                    return float(str(val).replace(",",""))
                except Exception:
                    return float("inf")
            return str(val)
        items.sort(key=keyfunc, reverse=descending)
        for idx, (_, k) in enumerate(items):
            self.tree.move(k, "", idx)

    def _maybe_save_column_widths(self, e=None):
        try:
            widths = {}
            for c in self.all_columns:
                widths[c] = int(self.tree.column(c, 'width'))
            s = load_state()
            bl = s.setdefault("prefs", {}).setdefault("bill_list", {})
            bl["column_widths"] = widths
            save_state(s)
        except Exception:
            pass

    def export_filtered_csv(self):
        try:
            from storage import get_export_dir
            dirp = get_export_dir()
            import os, time
            ts = time.strftime('%Y%m%d_%H%M%S')
            fp = os.path.join(dirp, f"billlist_filtered_{ts}.csv")
            cols = list(self.visible_columns)
            with open(fp, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(cols)
                for iid in self.tree.get_children(""):
                    vals = self.tree.item(iid, 'values')
                    row = []
                    for c in cols:
                        idx = self.all_columns.index(c)
                        row.append(vals[idx])
                    w.writerow(row)
            messagebox.showinfo("已导出", fp)
        except Exception as e:
            try:
                messagebox.showerror("导出失败", str(e))
            except Exception:
                pass

    def apply_filter(self):
        if not getattr(self, '_suppress_update', False):
            self.last_filters["year"] = self.cb_year.get().strip()
            self.last_filters["month"] = self.cb_month.get().strip()
            self.last_filters["ttype"] = self.cb_type.get().strip()
            self.last_filters["category"] = self.e_category.get().strip()
            term_w = getattr(self, 'e_search', None)
            self.last_filters["term"] = (term_w.get().strip().lower() if term_w else '')
            self.last_filters["amt_op"] = (self.cb_amt_op.get().strip() if hasattr(self, 'cb_amt_op') else '')
            self.last_filters["amt_val"] = (self.e_amt_val.get().strip() if hasattr(self, 'e_amt_val') else '')
        year = self.last_filters.get("year", "")
        month = self.last_filters.get("month", "")
        ttype = self.last_filters.get("ttype", "")
        category = self.last_filters.get("category", "")
        term = self.last_filters.get("term", "")
        amt_op = self.last_filters.get("amt_op", "")
        amt_val = self.last_filters.get("amt_val", "")
        self.tree.delete(*self.tree.get_children())
        self.suspected_map = self._compute_suspicions(self._get_dup_threshold_secs())
        rows = []
        try:
            fmt_pref = ((self.state.get("prefs", {}) or {}).get("bill_list", {}) or {}).get("time_format", "date")
        except Exception:
            fmt_pref = "date"
        tx_fmt = "%Y-%m-%d %H:%M:%S" if fmt_pref == "full" else "%Y-%m-%d"
        rt_fmt = tx_fmt
        inc_sum = 0.0
        exp_sum = 0.0
        trans_sum = 0.0
        to_insert = []
        try:
            order_col = self.current_sort_col if getattr(self, 'current_sort_col', None) else '交易时间'
            map_col = {'交易时间':'time','记账时间':'record_time','金额':'amount','所属类别':'ttype','消费类别':'category','账户':'account'}
            oc = map_col.get(order_col, 'time')
            od = bool(getattr(self, 'current_sort_desc', False))
            lim = (self.page_size if self.use_pagination else None)
            off = (self.current_page * self.page_size if self.use_pagination else None)
            rows = query_transactions({"year": year, "month": month, "ttype": ttype, "category": category, "term": term, "amt_op": amt_op, "amt_val": amt_val, "order_col": oc, "order_desc": od}, lim, off)
            sums = aggregate_sums({"year": year, "month": month})
            inc_sum = float(sums.get("收入",0)) + float(sums.get("报销类收入",0))
            exp_sum = float(sums.get("支出",0)) + float(sums.get("报销类支出",0))
            trans_sum = float(sums.get("转账",0))
        except Exception:
            rows = list(self.state.get("transactions", []))
        for t in rows:
            dt = datetime.fromisoformat(t.get("time"))
            if year and dt.strftime("%Y") != year:
                continue
            if month and month_key(dt) != month:
                continue
            if ttype and t.get("ttype") != ttype:
                continue
            cat_filter = (category or "").strip()
            cat_value = (t.get("category") or "").strip()
            if cat_filter:
                if cat_filter == "未分类":
                    if cat_value != "":
                        continue
                else:
                    if cat_filter != cat_value:
                        continue
            if not self.pass_column_filters(t):
                continue
            if amt_op and amt_val and amt_val.isdigit():
                try:
                    a = float(t.get("amount",0))
                    v = int(amt_val)
                    if amt_op == ">" and not (a > v):
                        continue
                    if amt_op == "<" and not (a < v):
                        continue
                    if amt_op == "=" and not (abs(a - v) < 1e-9):
                        continue
                except Exception:
                    pass
            if term:
                fields = [
                    dt.strftime(tx_fmt),
                    format_amount(float(t.get("amount",0))),
                    str(t.get("amount","")),
                    t.get("category",""),
                    t.get("ttype",""),
                    t.get("account",""),
                    t.get("to_account",""),
                    t.get("from_account",""),
                    t.get("note",""),
                    (parse_datetime(t.get("record_time")).strftime(rt_fmt) if t.get("record_time") else ""),
                    t.get("record_source",""),
                    t.get("id",""),
                ]
                joined = "\n".join(str(x) for x in fields).lower()
                if term not in joined:
                    continue
            rtime = t.get("record_time")
            rtime_str = ""
            if rtime:
                try:
                    rtime_str = parse_datetime(rtime).strftime(rt_fmt)
                except Exception:
                    rtime_str = str(rtime)
            vals = [
                dt.strftime(tx_fmt),
                format_amount(float(t.get("amount",0))),
                ("是" if self.suspected_map.get(t.get("id")) else ""),
                t.get("category",""),
                t.get("ttype",""),
                t.get("account",""),
                t.get("to_account",""),
                t.get("from_account",""),
                t.get("note",""),
                rtime_str,
                t.get("record_source",""),
                t.get("id"),
            ]
            to_insert.append(vals)
        # 预排序再插入，保持当前排序列与方向
        if getattr(self, "current_sort_col", None):
            col = self.current_sort_col
            desc = bool(getattr(self, "current_sort_desc", False))
            idx = self.all_columns.index(col) if col in self.all_columns else 0
            def sort_key(vals):
                v = vals[idx]
                if col == "交易时间":
                    try:
                        return parse_datetime(v)
                    except Exception:
                        return datetime.min
                if col == "记账时间":
                    try:
                        return parse_datetime(v)
                    except Exception:
                        return datetime.min
                if col == "金额":
                    try:
                        return float(str(v).replace(",",""))
                    except Exception:
                        return float("inf")
                return str(v)
            to_insert.sort(key=sort_key, reverse=desc)
        for vals in to_insert:
            self.tree.insert("", tk.END, values=vals)
        self.lbl_inc.configure(text=f"筛选收入：{self._fmt_footer_amount(inc_sum)}")
        self.lbl_exp.configure(text=f"筛选支出：{self._fmt_footer_amount(exp_sum)}")
        self.lbl_trans.configure(text=f"筛选转账：{self._fmt_footer_amount(trans_sum)}")
        # 插入前已按排序列排序，无需再次移动节点
        self.update_selection_summary()

    def _goto_page(self, p):
        if not getattr(self, 'use_pagination', False):
            return
        if p < 0:
            p = 0
        self.current_page = p
        self.apply_filter()

    def _fmt_footer_amount(self, v):
        try:
            a = float(v)
        except Exception:
            a = 0.0
        if a < 10000:
            return f"{int(a)}元"
        return f"{a/10000:.1f}万元"

    def reset_filter(self):
        if hasattr(self, 'cb_year'):
            self.cb_year.set("")
        self.cb_month.set("")
        self.cb_type.set("")
        self.e_category.delete(0, tk.END)
        if hasattr(self, 'e_search'):
            self.e_search.delete(0, tk.END)
        if hasattr(self, 'cb_amt_op'):
            self.cb_amt_op.set("")
        if hasattr(self, 'e_amt_val'):
            self.e_amt_val.delete(0, tk.END)
        self.column_filters.clear()
        self.last_filters = {"year": "", "month": "", "ttype": "", "category": "", "term": "", "amt_op": "", "amt_val": ""}
        self.apply_filter()

    def reapply_last_filters(self):
        self._suppress_update = True
        try:
            if hasattr(self, 'cb_year'):
                self.cb_year.set(self.last_filters.get("year", ""))
            # 根据年份重建月份选项后再回填月份
            try:
                self._update_months_values()
            except Exception:
                pass
            self.cb_month.set(self.last_filters.get("month", ""))
            self.cb_type.set(self.last_filters.get("ttype", ""))
            self.e_category.delete(0, tk.END)
            self.e_category.insert(0, self.last_filters.get("category", ""))
            if hasattr(self, 'e_search'):
                self.e_search.delete(0, tk.END)
                self.e_search.insert(0, self.last_filters.get("term", ""))
            if hasattr(self, 'cb_amt_op'):
                self.cb_amt_op.set(self.last_filters.get("amt_op", ""))
            if hasattr(self, 'e_amt_val'):
                self.e_amt_val.delete(0, tk.END)
                self.e_amt_val.insert(0, self.last_filters.get("amt_val", ""))
            self.apply_filter()
        finally:
            self._suppress_update = False

    def update_selection_summary(self):
        if getattr(self, '_suppress_update', False):
            return
        inc = 0.0
        exp = 0.0
        trans = 0.0
        ids = []
        for iid in self.tree.selection():
            vals = self.tree.item(iid, "values")
            if vals:
                ids.append(vals[-1])
        for tx_id in ids:
            t = get_transaction(self.state, tx_id)
            if not t:
                continue
            typ = normalize_ttype(t.get("ttype"))
            try:
                a = float(t.get("amount",0))
            except Exception:
                a = 0.0
            if typ in ["收入","报销类收入"]:
                inc += a
            elif typ in ["支出","报销类支出"]:
                exp += a
            elif typ == "转账":
                trans += a
        self.lbl_sel_count.configure(text=f"选中条数：{len(ids)}")
        self.lbl_sel_inc.configure(text=f"选中收入：{self._fmt_footer_amount(inc)}")
        self.lbl_sel_exp.configure(text=f"选中支出：{self._fmt_footer_amount(exp)}")
        self.lbl_sel_trans.configure(text=f"选中转账：{self._fmt_footer_amount(trans)}")

    def on_right_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == 'heading':
            col_id = self.tree.identify_column(event.x)
            idx = int(col_id.replace('#','')) - 1
            col = self.tree['displaycolumns'][idx]
            self._last_header_col = col
            try:
                self.header_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.header_menu.grab_release()
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_add(iid)
            self.menu.post(event.x_root, event.y_root)

    def _open_filter_for_last_header(self):
        if self._last_header_col:
            # Place popup roughly centered on screen
            x = self.winfo_rootx() + 60
            y = self.winfo_rooty() + 60
            self.open_filter_popup(self._last_header_col, x, y)

    def _clear_filter_for_last_header(self):
        if self._last_header_col:
            try:
                self.column_filters.pop(self._last_header_col, None)
            except Exception:
                pass
            self.apply_filter()

    def _hide_last_header(self):
        if self._last_header_col:
            self.hide_column(self._last_header_col)

    def hide_column(self, col):
        if col in self.visible_columns and len(self.visible_columns) > 1:
            self.visible_columns = [c for c in self.visible_columns if c != col]
            self.tree["displaycolumns"] = tuple(self.visible_columns)
            try:
                s = load_state()
                prefs = s.setdefault("prefs", {}).setdefault("bill_list", {})
                prefs["visible_columns"] = list(self.visible_columns)
                save_state(s)
            except Exception:
                pass

    def set_visible_columns(self, cols):
        keep = [c for c in self.all_columns if c in cols]
        if not keep:
            keep = [self.all_columns[0]]
        self.visible_columns = keep
        self.tree["displaycolumns"] = tuple(self.visible_columns)
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {}).setdefault("bill_list", {})
            prefs["visible_columns"] = list(self.visible_columns)
            save_state(s)
        except Exception:
            pass

    def open_columns_manager(self):
        win = tk.Toplevel(self)
        win.title("显示列管理")
        win.transient(self)
        win.grab_set()
        frm = ttk.Frame(win)
        frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        vars = {}
        left = ttk.Frame(frm)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for c in self.all_columns:
            var = tk.BooleanVar(value=(c in self.visible_columns))
            ttk.Checkbutton(left, text=c, variable=var).pack(anchor=tk.W)
            vars[c] = var
        right = ttk.Frame(frm)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12)
        ttk.Label(right, text="显示列顺序").pack(anchor=tk.W)
        lb = tk.Listbox(right)
        lb.pack(fill=tk.BOTH, expand=True)
        for c in self.visible_columns:
            lb.insert(tk.END, c)
        def move_up():
            idx = lb.curselection()
            if not idx:
                return
            i = idx[0]
            if i == 0:
                return
            txt = lb.get(i)
            lb.delete(i)
            lb.insert(i-1, txt)
            lb.selection_set(i-1)
        def move_down():
            idx = lb.curselection()
            if not idx:
                return
            i = idx[0]
            if i >= lb.size()-1:
                return
            txt = lb.get(i)
            lb.delete(i)
            lb.insert(i+1, txt)
            lb.selection_set(i+1)
        btns_order = ttk.Frame(right)
        btns_order.pack(fill=tk.X, pady=4)
        ttk.Button(btns_order, text="上移", command=move_up).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns_order, text="下移", command=move_down).pack(side=tk.LEFT, padx=4)
        def preset_basic():
            basic = ["交易时间","金额","消费类别","所属类别","账户","备注","id"]
            for c, v in vars.items():
                v.set(c in basic)
            lb.delete(0, tk.END)
            for c in basic:
                lb.insert(tk.END, c)
        def preset_extended():
            ext = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"]
            for c, v in vars.items():
                v.set(c in ext)
            lb.delete(0, tk.END)
            for c in ext:
                lb.insert(tk.END, c)
        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, pady=8)
        ttk.Button(btns, text="基础视图", command=preset_basic).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="扩展视图", command=preset_extended).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="全部", command=lambda: [vars[c].set(True) for c in vars]).pack(side=tk.LEFT, padx=4)
        def ok():
            chosen = [c for c, v in vars.items() if v.get()]
            order = [lb.get(i) for i in range(lb.size())]
            ordered = [c for c in order if c in chosen]
            if not ordered:
                ordered = chosen
            self.set_visible_columns(ordered)
            win.destroy()
        ttk.Button(btns, text="确定", command=ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    def selected_tx_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[-1]

    def selected_tx_ids(self):
        ids = []
        for iid in self.tree.selection():
            vals = self.tree.item(iid, "values")
            if vals:
                ids.append(vals[-1])
        return ids

    def on_edit(self):
        tx_id = self.selected_tx_id()
        if not tx_id:
            return
        t = get_transaction(self.state, tx_id)
        dlg = AddTransactionDialog(self, get_account_names(self.state), initial=t)
        self.wait_window(dlg)
        if dlg.result:
            old = get_transaction(self.state, tx_id)
            apply_transaction_delta(self.state, old, -1)
            new = dict(old)
            new.update(dlg.result)
            new["id"] = tx_id
            typ = normalize_ttype(new.get("ttype"))
            if typ in ["收入","报销类收入","支出","报销类支出"]:
                sc = "收入" if typ in ["收入","报销类收入"] else "支出"
                cat = (new.get("category") or "").strip()
                if cat:
                	add_category(self.state, sc, cat)
            update_transaction(self.state, tx_id, DummyTx(new))
            apply_transaction_delta(self.state, new, 1)
            save_state(self.state)
            self.reapply_last_filters()

    def on_record_for_row(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], 'values')
        if not vals:
            return
        tstr = str(vals[0]).strip()
        try:
            dt = parse_datetime(tstr)
            dstr = dt.strftime('%Y-%m-%d')
        except Exception:
            messagebox.showerror("错误", "无法读取该行的交易时间")
            return
        initial = {"time": f"{dstr}T12:00:00", "ttype": "支出"}
        dlg = AddTransactionDialog(self, get_account_names(self.state), initial=initial)
        self.wait_window(dlg)
        if getattr(dlg, 'result', None):
            new = dict(dlg.result)
            new["id"] = gen_id()
            try:
                typ = normalize_ttype(new.get("ttype"))
                if typ in ["收入","报销类收入","支出","报销类支出"]:
                    sc = "收入" if typ in ["收入","报销类收入"] else "支出"
                    cat = (new.get("category") or "").strip()
                    if cat:
                        add_category(self.state, sc, cat)
            except Exception:
                pass
            try:
                new["record_time"] = datetime.now().isoformat()
                new["record_source"] = "账单列表右键"
            except Exception:
                pass
            apply_transaction_delta(self.state, new, 1)
            try:
                self.state.setdefault("transactions", []).append(new)
            except Exception:
                pass
            save_state(self.state)
            self.reapply_last_filters()

    def on_delete(self):
        tx_id = self.selected_tx_id()
        if not tx_id:
            return
        if not messagebox.askyesno("确认", "删除该记录并同步账户变化？"):
            return
        t = get_transaction(self.state, tx_id)
        apply_transaction_delta(self.state, t, -1)
        remove_transaction(self.state, tx_id)
        save_state(self.state)
        self.reapply_last_filters()

    def delete_selected(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(ids)} 条记录并同步账户变化？"):
            return
        for tx_id in ids:
            t = get_transaction(self.state, tx_id)
            if t:
                apply_transaction_delta(self.state, t, -1)
                remove_transaction(self.state, tx_id)
        save_state(self.state)
        self.reapply_last_filters()

    def open_import_dialog(self):
        if not self.controller:
            return
        win = tk.Toplevel(self)
        win.title("导入账单")
        win.transient(self)
        win.grab_set()
        frm = ttk.Frame(win)
        frm.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        ttk.Label(frm, text="请选择导入方式", font=("Microsoft YaHei", 12)).pack(anchor=tk.CENTER, pady=8)
        row = ttk.Frame(frm)
        row.pack(pady=4)
        ttk.Button(row, text="支付宝账单导入", command=lambda: (win.destroy(), self.controller._import_alipay())).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="浦发银行账单导入", command=lambda: (win.destroy(), self.controller._import_spdb())).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="中信银行账单导入", command=lambda: (win.destroy(), self.controller._import_citic())).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="微信账单导入", command=lambda: (win.destroy(), self.controller._import_wechat())).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="标准模版导入", command=lambda: (win.destroy(), self.controller._import_standard())).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="其它导入", command=lambda: (win.destroy(), self.controller._import_other())).pack(side=tk.LEFT, padx=8)
        try:
            win.update_idletasks()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            ww = max(380, win.winfo_reqwidth())
            wh = max(200, win.winfo_reqheight())
            x = (sw - ww)//2
            y = (sh - wh)//2
            win.geometry(f"{ww}x{wh}+{x}+{y}")
        except Exception:
            pass

    def open_excel_batch_entry(self):
        try:
            temp_dir = os.path.join(BASE_DIR, "temp")
            try:
                os.makedirs(temp_dir, exist_ok=True)
            except Exception:
                pass
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(temp_dir, f"batch_entry_{ts}.xlsx")
            cols = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
            self._write_xlsx(path, cols, [])
            try:
                os.startfile(path)
            except Exception:
                try:
                    subprocess.Popen(["powershell", "-NoProfile", "-Command", f"Start-Process -FilePath '{path}'"], shell=False)
                except Exception:
                    pass
            threading.Thread(target=lambda: self._watch_and_import_xlsx(path), daemon=True).start()
            try:
                messagebox.showinfo("提示", "已打开Excel模板，请填写并关闭后自动导入")
            except Exception:
                pass
        except Exception as e:
            self._show_error_dialog(str(e))

    def _is_excel_running(self):
        try:
            out = subprocess.check_output(["tasklist"], creationflags=0)
            return b"EXCEL.EXE" in out
        except Exception:
            return False

    def _watch_and_import_xlsx(self, path):
        try:
            last_mtime = None
            stable = 0
            while True:
                if not os.path.exists(path):
                    time.sleep(1)
                    continue
                try:
                    m = os.path.getmtime(path)
                except Exception:
                    m = None
                if m is not None:
                    if last_mtime is None or m != last_mtime:
                        last_mtime = m
                        stable = 0
                    else:
                        stable += 1
                if stable >= 3 and not self._is_excel_running():
                    break
                time.sleep(1)
            s = load_state()
            account_names = get_account_names(s)
            rows = import_standard_xlsx(path, account_names)
            now_iso = datetime.now().isoformat()
            for r in rows:
                r["record_time"] = now_iso
                r["record_source"] = "Excel批量录入"
                cat_sync = (r.get("category") or "").strip()
                typ_sync = normalize_ttype(r.get("ttype"))
                if cat_sync and typ_sync in ["收入","报销类收入","支出","报销类支出"]:
                    sc_sync = "收入" if typ_sync in ["收入","报销类收入"] else "支出"
                    add_category(s, sc_sync, cat_sync)
            if any((not r.get("account")) for r in rows):
                acc = self.ask_default_account(account_names)
                if not acc:
                    raise ValueError("未选择默认账户，无法完成导入")
                for r in rows:
                    if not r.get("account"):
                        r["account"] = acc
            from utils import tx_signature
            existing = set()
            for t in s.get("transactions", []):
                try:
                    existing.add(tx_signature(t))
                except Exception:
                    pass
            success = 0
            dup = 0
            dup_rows = []
            for r in rows:
                sig = tx_signature(r)
                if sig in existing:
                    dup += 1
                    dup_rows.append([
                        r.get("time", "")[:19].replace("T"," "),
                        str(r.get("amount", "")),
                        r.get("消费类别","") or r.get("category",""),
                        r.get("ttype",""),
                        r.get("account",""),
                        r.get("to_account","") or "",
                        r.get("from_account","") or "",
                        r.get("note",""),
                    ])
                    continue
                existing.add(sig)
                s["transactions"].append(r)
                apply_transaction_delta(s, r, 1)
                success += 1
            save_state(s)
            self.state = s
            msg = f"批量录入导入完成\n成功: {success} 条"
            if dup:
                msg += f"\n重复: {dup} 条"
            if dup_rows:
                try:
                    cols = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
                    ts = datetime.now().strftime("%Y%m%d_%H%M")
                    out_path = os.path.join(BASE_DIR, f"duplicates_{ts}.xlsx")
                    self._write_xlsx(out_path, cols, dup_rows)
                    msg += f"\n重复条目已导出: {out_path}"
                except Exception:
                    pass
            try:
                messagebox.showinfo("导入结果", msg)
            except Exception:
                pass
            try:
                self.apply_filter()
            except Exception:
                self.refresh()
        except Exception as e:
            try:
                self._show_error_dialog(str(e))
            except Exception:
                pass
    def import_override(self):
        paths = filedialog.askopenfilenames(title="选择账单文件", filetypes=[("所有文件","*.*"), ("CSV 文件","*.csv"), ("Excel 文件","*.xlsx")])
        if not paths:
            return
        if not messagebox.askyesno("确认", "将覆盖现有账单并按新导入重算账户余额，是否继续？"):
            return
        try:
            from storage import backup_state
            backup_state()
            s = load_state()
            account_names = get_account_names(s)
            rows = []
            stats_total = {"skipped_no_io": 0}
            for p in paths:
                res = try_import(p, account_names)
                rows.extend(res.get("rows", []))
                stats_total["skipped_no_io"] += int(res.get("stats", {}).get("skipped_no_io", 0))
            use_ai = messagebox.askyesno("预填消费类别", "是否让系统进行预填消费类别？")
            now_iso = datetime.now().isoformat()
            ai_prefill = 0
            for r in rows:
                r["record_time"] = now_iso
                plat = (r.get("platform") or "").strip()
                if plat == "alipay":
                    r["record_source"] = "支付宝"
                elif plat == "wechat":
                    r["record_source"] = "微信"
                elif plat == "spdb":
                    r["record_source"] = "浦发银行"
                elif plat == "citic":
                    r["record_source"] = "中信银行"
                else:
                    r["record_source"] = "模版导入"
                cat_sync = (r.get("category") or "").strip()
                typ_sync = normalize_ttype(r.get("ttype"))
                if cat_sync and typ_sync in ["收入","报销类收入","支出","报销类支出"]:
                    sc_sync = "收入" if typ_sync in ["收入","报销类收入"] else "支出"
                    add_category(s, sc_sync, cat_sync)
                if use_ai:
                    cat = (r.get("category") or "").strip()
                    typ = normalize_ttype(r.get("ttype"))
                    if not cat and typ in ["收入","报销类收入","支出","报销类支出"]:
                        text = " ".join([str(r.get("note","")), str(r.get("record_source","")), str(r.get("account",""))]).lower()
                        sc = "收入" if typ in ["收入","报销类收入"] else "支出"
                        try:
                            pred = self._predict_category_for_billlist(text, sc, s)
                        except Exception:
                            pred = None
                        if pred:
                            r["category"] = pred
                            add_category(s, sc, pred)
                            ai_prefill += 1
            if any((not r.get("account")) for r in rows):
                acc = self.ask_default_account(account_names)
                if not acc:
                    raise ValueError("未选择默认账户，无法完成导入")
                for r in rows:
                    if not r.get("account"):
                        r["account"] = acc
            s["transactions"] = []
            freeze = bool((s.get("prefs", {}) or {}).get("freeze_assets"))
            if not freeze:
                for a in s.get("accounts", []):
                    try:
                        a["balance"] = 0.0
                    except Exception:
                        pass
            from utils import tx_signature
            existing = set()
            dup_rows = []
            success = 0
            dup = 0
            for r in rows:
                sig = tx_signature(r)
                if sig in existing:
                    dup += 1
                    dup_rows.append([
                        r.get("time", "")[:19].replace("T"," "),
                        str(r.get("amount", "")),
                        r.get("category",""),
                        r.get("ttype",""),
                        r.get("account",""),
                        r.get("to_account","") or "",
                        r.get("from_account","") or "",
                        r.get("note",""),
                    ])
                    continue
                existing.add(sig)
                s["transactions"].append(r)
                apply_transaction_delta(s, r, 1)
                success += 1
            save_state(s)
            self.state = s
            total = len(rows)
            skipped = total - success
            msg = f"覆盖导入完成\n总计: {total} 条\n成功: {success} 条"
            if dup:
                msg += f"\n重复: {dup} 条"
            skipped_no_io = int(stats_total.get("skipped_no_io", 0))
            if skipped_no_io:
                msg += f"\n跳过（不计收支）: {skipped_no_io} 条"
            if skipped - dup:
                msg += f"\n其他未导入: {skipped - dup} 条"
            if use_ai:
                msg += f"\nAI预填类别: {ai_prefill} 条"
            # 导出重复条目
            if dup_rows:
                try:
                    cols = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
                    ts = datetime.now().strftime("%Y%m%d_%H%M")
                    out_path = os.path.join(BASE_DIR, f"duplicates_{ts}.xlsx")
                    self._write_xlsx(out_path, cols, dup_rows)
                    msg += f"\n重复条目已导出: {out_path}"
                except Exception:
                    pass
            messagebox.showinfo("导入结果", msg)
            self.apply_filter()
        except Exception as e:
            self._show_error_dialog(str(e))

    def bulk_change_to_transfer(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        count = 0
        for tx_id in ids:
            old = get_transaction(self.state, tx_id)
            if not old:
                continue
            try:
                apply_transaction_delta(self.state, old, -1)
                new = dict(old)
                new["ttype"] = "转账"
                new["category"] = "转账"
                new["account"] = ""
                new["to_account"] = None
                new["from_account"] = None
                update_transaction(self.state, tx_id, DummyTx(new))
                apply_transaction_delta(self.state, new, 1)
                count += 1
            except Exception:
                pass
        save_state(self.state)
        messagebox.showinfo("批量修改完成", f"已修改为转账: {count} 条")
        self.apply_filter()

    def bulk_modify_accounts(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        names = get_account_names(self.state)
        dlg = tk.Toplevel(self)
        dlg.title("批量修改账户")
        dlg.grab_set()
        ttk.Label(dlg, text="账户").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        cb_account = ttk.Combobox(dlg, values=list(names) + ["新增账户"], state="readonly")
        cb_account.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(dlg, text="转出账户").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        cb_from = ttk.Combobox(dlg, values=list(names) + ["新增账户"], state="readonly")
        cb_from.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(dlg, text="转入账户").grid(row=2, column=0, padx=8, pady=6, sticky=tk.W)
        cb_to = ttk.Combobox(dlg, values=list(names) + ["新增账户"], state="readonly")
        cb_to.grid(row=2, column=1, padx=8, pady=6, sticky=tk.EW)
        only_empty = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text="仅填充空值，不覆盖已有", variable=only_empty).grid(row=3, column=0, columnspan=2, padx=8, pady=6, sticky=tk.W)
        btns = ttk.Frame(dlg)
        btns.grid(row=4, column=0, columnspan=2, pady=8)
        result = {"account": None, "from": None, "to": None, "only_empty": False}
        def on_ok():
            result["account"] = cb_account.get().strip() or None
            result["from"] = cb_from.get().strip() or None
            result["to"] = cb_to.get().strip() or None
            result["only_empty"] = bool(only_empty.get())
            dlg.destroy()
        def on_cancel():
            result["account"] = None
            result["from"] = None
            result["to"] = None
            result["only_empty"] = False
            dlg.destroy()
        def _on_acc_selected(widget):
            val = (widget.get() or "").strip()
            if val == "新增账户":
                from ui_account_manager import AccountDialog
                dlg_acc = AccountDialog(self, None)
                self.wait_window(dlg_acc)
                if dlg_acc.result:
                    from storage import load_state, add_account, save_state, get_account_names
                    from models import Account
                    s2 = load_state()
                    a = dlg_acc.result
                    add_account(s2, Account(**a))
                    save_state(s2)
                    new_names = get_account_names(s2)
                    cb_account["values"] = list(new_names) + ["新增账户"]
                    cb_from["values"] = list(new_names) + ["新增账户"]
                    cb_to["values"] = list(new_names) + ["新增账户"]
                    widget.set(a.get("name",""))
        cb_account.bind("<<ComboboxSelected>>", lambda e: _on_acc_selected(cb_account))
        cb_from.bind("<<ComboboxSelected>>", lambda e: _on_acc_selected(cb_from))
        cb_to.bind("<<ComboboxSelected>>", lambda e: _on_acc_selected(cb_to))
        ttk.Button(btns, text="确定", command=on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=6)
        dlg.columnconfigure(1, weight=1)
        self.wait_window(dlg)
        acc_sel = result["account"]
        fa = result["from"]
        ta = result["to"]
        if acc_sel is None and fa is None and ta is None:
            return
        count = 0
        for tx_id in ids:
            old = get_transaction(self.state, tx_id)
            if not old:
                continue
            new = dict(old)
            if result["only_empty"]:
                if acc_sel is not None and not new.get("account"):
                    new["account"] = acc_sel
                if fa is not None and not new.get("from_account"):
                    new["from_account"] = fa
                if ta is not None and not new.get("to_account"):
                    new["to_account"] = ta
            else:
                if acc_sel is not None:
                    new["account"] = acc_sel
                if fa is not None:
                    new["from_account"] = fa
                if ta is not None:
                    new["to_account"] = ta
            try:
                apply_transaction_delta(self.state, old, -1)
                update_transaction(self.state, tx_id, DummyTx(new))
                apply_transaction_delta(self.state, new, 1)
                count += 1
            except Exception:
                pass
        save_state(self.state)
        messagebox.showinfo("批量修改完成", f"已更新账户信息: {count} 条")
        self.apply_filter()

    def bulk_modify_category(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        dlg = tk.Toplevel(self)
        dlg.title("批量修改消费类别")
        dlg.grab_set()
        ttk.Label(dlg, text="所属类别").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        cb_scene = ttk.Combobox(dlg, values=["收入","支出"], state="readonly")
        cb_scene.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        cb_scene.set("支出")
        ttk.Label(dlg, text="消费类别").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        cb_cat = ttk.Combobox(dlg, values=[], state="normal")
        cb_cat.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(dlg, text="或手动输入").grid(row=2, column=0, padx=8, pady=6, sticky=tk.W)
        e_cat = ttk.Entry(dlg)
        e_cat.grid(row=2, column=1, padx=8, pady=6, sticky=tk.EW)
        def on_scene_change(evt=None):
            sc = cb_scene.get().strip()
            cats = get_categories(load_state(), sc)
            cb_cat["values"] = cats
            if cats:
                cb_cat.set(cats[0])
        cb_scene.bind("<<ComboboxSelected>>", on_scene_change)
        on_scene_change()
        btns = ttk.Frame(dlg)
        btns.grid(row=3, column=0, columnspan=2, pady=8)
        result = {"scene": None, "category": None, "input": None}
        def on_ok():
            result["scene"] = cb_scene.get().strip()
            result["category"] = cb_cat.get().strip() or None
            s_in = e_cat.get().strip()
            result["input"] = s_in if s_in else None
            dlg.destroy()
        def on_cancel():
            dlg.destroy()
        ttk.Button(btns, text="确定", command=on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=6)
        dlg.columnconfigure(1, weight=1)
        self.wait_window(dlg)
        sc = result.get("scene")
        if not sc:
            return
        cat_final = result.get("input") or result.get("category")
        if not cat_final:
            return
        add_category(self.state, sc, cat_final)
        count = 0
        for tx_id in ids:
            old = get_transaction(self.state, tx_id)
            if not old:
                continue
            typ = (old.get("ttype") or "").strip()
            if sc == "收入" and typ not in ["收入","报销类收入"]:
                continue
            if sc == "支出" and typ not in ["支出","报销类支出"]:
                continue
            new = dict(old)
            new["category"] = cat_final
            try:
                apply_transaction_delta(self.state, old, -1)
                update_transaction(self.state, tx_id, DummyTx(new))
                apply_transaction_delta(self.state, new, 1)
                count += 1
            except Exception:
                pass
        save_state(self.state)
        messagebox.showinfo("批量修改完成", f"已更新消费类别: {count} 条")
        self.apply_filter()

    def bulk_change_to_income(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        count = 0
        for tx_id in ids:
            old = get_transaction(self.state, tx_id)
            if not old:
                continue
            new = dict(old)
            new["ttype"] = "收入"
            try:
                apply_transaction_delta(self.state, old, -1)
                update_transaction(self.state, tx_id, DummyTx(new))
                apply_transaction_delta(self.state, new, 1)
                count += 1
            except Exception:
                pass
        save_state(self.state)
        messagebox.showinfo("批量修改完成", f"已改为收入: {count} 条")
        self.apply_filter()

    def bulk_change_to_expense(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        count = 0
        for tx_id in ids:
            old = get_transaction(self.state, tx_id)
            if not old:
                continue
            new = dict(old)
            new["ttype"] = "支出"
            try:
                apply_transaction_delta(self.state, old, -1)
                update_transaction(self.state, tx_id, DummyTx(new))
                apply_transaction_delta(self.state, new, 1)
                count += 1
            except Exception:
                pass
        save_state(self.state)
        messagebox.showinfo("批量修改完成", f"已改为支出: {count} 条")
        self.apply_filter()

    def bulk_modify_record_source(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        dlg = tk.Toplevel(self)
        dlg.title("批量修改记账来源")
        dlg.grab_set()
        ttk.Label(dlg, text="选择来源").grid(row=0, column=0, padx=8, pady=6, sticky=tk.W)
        try:
            from storage import load_state, get_record_sources, add_record_source, save_state
            s2 = load_state()
            sources = get_record_sources(s2)
        except Exception:
            sources = ["手动输入"]
        cb = ttk.Combobox(dlg, values=sources, state="readonly")
        cb.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        cb.set(sources[0])
        ttk.Label(dlg, text="或输入").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        e_src = ttk.Entry(dlg)
        e_src.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        only_empty = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text="仅填充空值，不覆盖已有", variable=only_empty).grid(row=2, column=0, columnspan=2, padx=8, pady=6, sticky=tk.W)
        btns = ttk.Frame(dlg)
        btns.grid(row=3, column=0, columnspan=2, pady=8)
        res = {"src": None, "only_empty": False}
        def on_ok():
            s = e_src.get().strip()
            res["src"] = s if s else cb.get().strip()
            res["only_empty"] = bool(only_empty.get())
            dlg.destroy()
        def on_cancel():
            dlg.destroy()
        ttk.Button(btns, text="确定", command=on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=6)
        dlg.columnconfigure(1, weight=1)
        self.wait_window(dlg)
        src = res.get("src")
        if not src:
            return
        try:
            s3 = load_state()
            add_record_source(s3, src)
            save_state(s3)
        except Exception:
            pass
        count = 0
        for tx_id in ids:
            old = get_transaction(self.state, tx_id)
            if not old:
                continue
            new = dict(old)
            if res.get("only_empty"):
                if not (new.get("record_source") or "").strip():
                    new["record_source"] = src
                else:
                    continue
            else:
                new["record_source"] = src
            try:
                apply_transaction_delta(self.state, old, -1)
                update_transaction(self.state, tx_id, DummyTx(new))
                apply_transaction_delta(self.state, new, 1)
                count += 1
            except Exception:
                pass
        save_state(self.state)
        messagebox.showinfo("批量修改完成", f"已更新记账来源: {count} 条")
        self.apply_filter()

    def ai_prefill_category(self):
        ids = self.selected_tx_ids()
        if not ids:
            return
        s = load_state()
        filled = 0
        skipped = 0
        for tx_id in ids:
            t = get_transaction(s, tx_id)
            if not t:
                skipped += 1
                continue
            typ = normalize_ttype(t.get("ttype"))
            if typ not in ["收入","报销类收入","支出","报销类支出"]:
                skipped += 1
                continue
            cat = (t.get("category") or "").strip()
            if cat:
                skipped += 1
                continue
            text = " ".join([
                str(t.get("note","")),
                str(t.get("record_source","")),
                str(t.get("account","")),
            ]).lower()
            scene = "收入" if typ in ["收入","报销类收入"] else "支出"
            pred = self._predict_category_for_billlist(text, scene, s)
            if not pred:
                skipped += 1
                continue
            new = dict(t)
            new["category"] = pred
            add_category(s, scene, pred)
            update_transaction(s, tx_id, DummyTx(new))
            filled += 1
        save_state(s)
        self.state = s
        messagebox.showinfo("AI预填完成", f"已预填: {filled} 条\n跳过: {skipped} 条")
        self.refresh()

    def _predict_category_for_billlist(self, text: str, scene: str, state) -> str:
        s = (text or "").lower()
        try:
            rules = get_category_rules(state, scene)
            for it in rules:
                kw = (it.get("keyword") or "").lower()
                cat = (it.get("category") or "").strip()
                if kw and cat and kw in s:
                    return cat
        except Exception:
            pass
        if scene == "支出":
            if any(k in s for k in ["早餐","午餐","晚餐","外卖","餐厅","饭店","奶茶","咖啡"]):
                return "三餐"
            if any(k in s for k in ["公交","地铁","打车","出租","滴滴","出行","高铁","火车","机票"]):
                return "交通"
            if any(k in s for k in ["电影","娱乐","网游","游戏","剧场","ktv","音乐"]):
                return "娱乐"
            if any(k in s for k in ["医院","医疗","看病","药店","药品","体检"]):
                return "医疗"
            if any(k in s for k in ["学习","课程","培训","书籍","教材"]):
                return "学习"
            if any(k in s for k in ["纸巾","清洁","生活","用品","日用品"]):
                return "日用品"
            if any(k in s for k in ["房租","租金","物业","水费","电费","燃气","煤气"]):
                return "水电煤"
            if any(k in s for k in ["化妆","美妆","美容","护肤"]):
                return "美妆"
            if any(k in s for k in ["孩子","幼儿园","课外","辅导","教育"]):
                return "子女教育"
        else:
            if any(k in s for k in ["工资","薪资","薪水","发薪"]):
                return "工资"
            if any(k in s for k in ["生活费","零用","家人汇款"]):
                return "生活费"
            if any(k in s for k in ["红包","收红包","礼金"]):
                return "收红包"
            if any(k in s for k in ["外快","兼职","劳务","项目款","佣金"]):
                return "外快"
            if any(k in s for k in ["基金","股票","理财","分红"]):
                return "股票基金"
        return ""

    def on_ctrl_a(self, event):
        try:
            self._suppress_update = True
            items = self.tree.get_children("")
            self.tree.selection_set(items)
        finally:
            self._suppress_update = False
        self.update_selection_summary()
        return "break"

    def open_filter_popup(self, col, x, y):
        win = tk.Toplevel(self)
        win.title(f"筛选: {col}")
        win.geometry(f"320x480+{x}+{y}")
        try:
            win.minsize(300, 420)
        except Exception:
            pass
        win.transient(self)
        win.grab_set()

        container = ttk.Frame(win)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=1)

        top = ttk.Frame(container)
        top.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=4)
        ttk.Button(top, text="升序", command=lambda: (self.sort_by(col, False), win.destroy())).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="降序", command=lambda: (self.sort_by(col, True), win.destroy())).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="清除该列筛选", command=lambda: (self.column_filters.pop(col, None), self.apply_filter(), win.destroy())).pack(side=tk.RIGHT, padx=4)

        values = set()
        for t in self.state.get("transactions", []):
            if col == "交易时间":
                dt = datetime.fromisoformat(t.get("time"))
                values.add(dt.strftime("%Y-%m-%d"))
            elif col == "金额":
                values.add(format_amount(float(t.get("amount",0))))
            elif col == "疑似重复":
                values.add("是" if self._compute_suspicions(self._get_dup_threshold_secs()).get(t.get("id")) else "")
            elif col == "消费类别":
                values.add(t.get("category",""))
            elif col == "所属类别":
                values.add(t.get("ttype",""))
            elif col == "账户":
                values.add(t.get("account",""))
            elif col == "转入账户":
                values.add(t.get("to_account",""))
            elif col == "转出账户":
                values.add(t.get("from_account",""))
            elif col == "备注":
                values.add(t.get("note",""))
            elif col == "记账时间":
                rt = t.get("record_time")
                values.add(parse_datetime(rt).strftime("%Y-%m-%d %H:%M") if rt else "")
            elif col == "记账来源":
                values.add(t.get("record_source",""))
        base_vals = sorted([v for v in values if v is not None])

        search_var = tk.StringVar()
        ttk.Entry(container, textvariable=search_var).grid(row=1, column=0, sticky=tk.EW, padx=8, pady=4)

        canvas = tk.Canvas(container, borderwidth=0)
        frame = ttk.Frame(canvas)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=2, column=0, sticky=tk.NSEW, padx=8, pady=4)
        vsb.grid(row=2, column=1, sticky=tk.NS)
        canvas.create_window((0,0), window=frame, anchor='nw')
        def _on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", _on_frame_configure)

        selected_set = set(self.column_filters.get(col, []))
        vars = []
        all_var = tk.BooleanVar(value=(len(selected_set)==0 or len(selected_set)==len(base_vals)))

        def rebuild():
            for w in frame.winfo_children():
                w.destroy()
            vars.clear()
            chk_all = ttk.Checkbutton(frame, text="(全选)", variable=all_var)
            chk_all.grid(sticky=tk.W)
            def on_all_change(*args):
                if all_var.get():
                    for v, var in vars:
                        var.set(True)
                else:
                    for v, var in vars:
                        var.set(False)
            all_var.trace_add('write', on_all_change)
            term = search_var.get().strip()
            show_vals = [v for v in base_vals if (not term or term in str(v))]
            for v in show_vals:
                var = tk.BooleanVar(value=(not selected_set or v in selected_set))
                cb = ttk.Checkbutton(frame, text=str(v), variable=var)
                cb.grid(sticky=tk.W)
                vars.append((v, var))
            frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        rebuild()
        search_var.trace_add('write', lambda *args: rebuild())

        btns = ttk.Frame(container)
        btns.grid(row=3, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        def on_ok():
            chosen = [v for v, var in vars if var.get()]
            if len(chosen) == len(base_vals) or len(chosen)==0:
                self.column_filters.pop(col, None)
            else:
                self.column_filters[col] = set(chosen)
            win.destroy()
            self.apply_filter()
        def on_cancel():
            win.destroy()
        ttk.Button(btns, text="确定", command=on_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="取消", command=on_cancel).pack(side=tk.RIGHT, padx=4)

    def on_heading_shift_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != 'heading':
            return
        col_id = self.tree.identify_column(event.x)
        idx = int(col_id.replace('#','')) - 1
        col = self.tree['displaycolumns'][idx]
        self.open_filter_popup(col, event.x_root, event.y_root)

    def pass_column_filters(self, t):
        rel = self.column_filters.get("账户相关")
        if rel:
            vals = [t.get("account",""), t.get("to_account",""), t.get("from_account","")]
            if not any(v in rel for v in vals):
                return False
        for col, allowed in self.column_filters.items():
            if col == "账户相关":
                continue
            val = ""
            if col == "交易时间":
                dt = datetime.fromisoformat(t.get("time"))
                val = dt.strftime("%Y-%m-%d")
            elif col == "金额":
                val = format_amount(float(t.get("amount",0)))
            elif col == "消费类别":
                val = t.get("category","")
            elif col == "所属类别":
                val = t.get("ttype","")
            elif col == "账户":
                val = t.get("account","")
            elif col == "转入账户":
                val = t.get("to_account","")
            elif col == "转出账户":
                val = t.get("from_account","")
            elif col == "备注":
                val = t.get("note","")
            elif col == "记账时间":
                rt = t.get("record_time")
                val = parse_datetime(rt).strftime("%Y-%m-%d %H:%M") if rt else ""
            elif col == "记账来源":
                val = t.get("record_source","")
            elif col == "疑似重复":
                val = "是" if getattr(self, 'suspected_map', {}).get(t.get("id")) else ""
            if allowed and val not in allowed:
                return False
        return True

    def on_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        vals = self.tree.item(iid, 'values')
        tx_id = vals[-1]
        t = get_transaction(self.state, tx_id)
        if not t:
            return
        win = tk.Toplevel(self)
        win.title("记录详情")
        win.transient(self)
        win.grab_set()
        grid = ttk.Frame(win)
        grid.pack(padx=12, pady=12)
        items = [
            ("交易时间", t.get("time")[:19].replace("T"," ")),
            ("金额", format_amount(float(t.get("amount",0)))),
            ("消费类别", t.get("category","")),
            ("所属类别", t.get("ttype","")),
            ("账户", t.get("account","")),
            ("转入账户", t.get("to_account","")),
            ("转出账户", t.get("from_account","")),
            ("备注", t.get("note","")),
            ("ID", t.get("id")),
        ]
        for i, (k, v) in enumerate(items):
            ttk.Label(grid, text=k).grid(row=i, column=0, sticky=tk.W, padx=4, pady=2)
            ttk.Label(grid, text=str(v)).grid(row=i, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=8)

    def export_all_xlsx(self):
        path = filedialog.asksaveasfilename(title="导出账单", defaultextension=".xlsx", filetypes=[("Excel 文件","*.xlsx")])
        if not path:
            return
        header = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
        s = load_state()
        rows = []
        for t in s.get("transactions", []):
            try:
                dt = datetime.fromisoformat(t.get("time"))
                tstr = dt.strftime("%Y-%m-%d")
            except Exception:
                tstr = str(t.get("time",""))[:19].replace("T"," ")
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

    def export_suspected(self):
        self.suspected_map = self._compute_suspicions(self._get_dup_threshold_secs())
        rows = []
        for t in self.state.get("transactions", []):
            if not self.suspected_map.get(t.get("id")):
                continue
            try:
                dt = parse_datetime(t.get("time"))
                tstr = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                tstr = str(t.get("time",""))[:19].replace("T"," ")
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
        if not rows:
            messagebox.showinfo("导出结果", "无疑似重复记录")
            return
        try:
            import os
            from datetime import datetime
            cols = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            out_path = os.path.join(BASE_DIR, f"duplicates_{ts}.xlsx")
            self._write_xlsx(out_path, cols, rows)
            messagebox.showinfo("导出成功", f"已导出 {len(rows)} 条到\n{out_path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def dedupe_delete_keep_first(self):
        try:
            from storage import backup_state
            backup_state()
        except Exception:
            pass
        threshold = self._get_dup_threshold_secs()
        groups = {}
        for t in self.state.get("transactions", []):
            try:
                dt = parse_datetime(t.get("time"))
                a = float(t.get("amount",0))
                k = format_amount(abs(a))
                groups.setdefault(k, []).append((dt, t))
            except Exception:
                pass
        removed = 0
        for _, lst in groups.items():
            lst.sort(key=lambda x: x[0])
            cur = []
            def flush():
                nonlocal removed
                if len(cur) > 1:
                    keep = cur[0][1]
                    for _, t in cur[1:]:
                        try:
                            apply_transaction_delta(self.state, t, -1)
                            remove_transaction(self.state, t.get("id"))
                            removed += 1
                        except Exception:
                            pass
                cur.clear()
            for item in lst:
                if not cur:
                    cur.append(item)
                else:
                    if (item[0] - cur[0][0]).total_seconds() <= threshold:
                        cur.append(item)
                    else:
                        flush()
                        cur.append(item)
            flush()
        save_state(self.state)
        self.refresh()
        messagebox.showinfo("删除完成", f"已删除疑似重复: {removed} 条")

    def import_standard_xlsx_file(self):
        path = filedialog.askopenfilename(title="导入账单", filetypes=[("所有文件","*.*"), ("Excel 文件","*.xlsx")])
        if not path:
            return
        try:
            s = load_state()
            account_names = get_account_names(s)
            rows = import_standard_xlsx(path, account_names)
            now_iso = datetime.now().isoformat()
            for r in rows:
                r["record_time"] = now_iso
                r["record_source"] = "模版导入"
            if any((not r.get("account")) for r in rows):
                acc = self.ask_default_account(account_names)
                if not acc:
                    raise ValueError("未选择默认账户，无法完成导入")
                for r in rows:
                    if not r.get("account"):
                        r["account"] = acc
            from utils import tx_signature
            existing = {tx_signature(t) for t in s.get("transactions", [])}
            success = 0
            dup = 0
            for r in rows:
                sig = tx_signature(r)
                if sig in existing:
                    dup += 1
                    continue
                existing.add(sig)
                s["transactions"].append(r)
                apply_transaction_delta(s, r, 1)
                success += 1
            save_state(s)
            self.state = s
            total = len(rows)
            msg = f"导入完成\n总计: {total} 条\n成功: {success} 条"
            if dup:
                msg += f"\n重复: {dup} 条"
            messagebox.showinfo("导入结果", msg)
            self.refresh()
        except Exception as e:
            self._show_error_dialog(str(e))

    def ask_default_account(self, account_names):
        if not account_names:
            return None
        dlg = tk.Toplevel(self)
        dlg.title("选择默认账户")
        dlg.grab_set()
        ttk.Label(dlg, text="部分记录未指定账户，请选择默认账户：").pack(padx=12, pady=8)
        cb = ttk.Combobox(dlg, values=account_names, state="readonly")
        cb.pack(padx=12, pady=8)
        if account_names:
            cb.set(account_names[0])
        chosen = {"value": None}
        def ok():
            chosen["value"] = cb.get().strip()
            dlg.destroy()
        def cancel():
            chosen["value"] = None
            dlg.destroy()
        f = ttk.Frame(dlg)
        f.pack(pady=8)
        ttk.Button(f, text="确定", command=ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(f, text="取消", command=cancel).pack(side=tk.LEFT, padx=6)
        self.wait_window(dlg)
        return chosen["value"]

    def _show_error_dialog(self, text: str):
        win = tk.Toplevel(self)
        win.title("导入失败")
        win.transient(self)
        win.grab_set()
        frm = ttk.Frame(win)
        frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        txt = tk.Text(frm, height=12, wrap="word")
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", str(text))
        txt.configure(state="disabled")
        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, pady=8)
        def copy():
            try:
                win.clipboard_clear()
                win.clipboard_append(str(text))
            except Exception:
                pass
        ttk.Button(btns, text="复制错误信息", command=copy).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="关闭", command=win.destroy).pack(side=tk.RIGHT, padx=6)

    def _write_xlsx(self, path, header, rows):
        import io
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

class DummyTx:
    def __init__(self, d):
        self.d = d
    def to_dict(self):
        return self.d

class BillListDialog(tk.Toplevel):
    def __init__(self, master, initial_filters=None):
        super().__init__(master)
        self.title("账单列表（筛选视图）")
        self.transient(master)
        self.grab_set()
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)
        self.page = BillListPage(container)
        self.page.pack(fill=tk.BOTH, expand=True)
        # 预置筛选条件
        f = initial_filters or {}
        if f.get("month"):
            try:
                self.page.cb_month.set(f.get("month"))
            except Exception:
                pass
        if f.get("ttype"):
            self.page.cb_type.set(f.get("ttype"))
        if f.get("category"):
            self.page.e_category.delete(0, tk.END)
            self.page.e_category.insert(0, f.get("category"))
        day = f.get("day")
        if day:
            self.page.column_filters["交易时间"] = {day}
        days = f.get("days")
        if days:
            ds = set()
            for d in days:
                try:
                    ds.add(d.strftime("%Y-%m-%d"))
                except Exception:
                    s = str(d)
                    ds.add(s[:10])
            self.page.column_filters["交易时间"] = ds
        dr = f.get("date_range")
        if dr and isinstance(dr, (list, tuple)) and len(dr) == 2:
            s, e = dr
            try:
                d0 = datetime.fromisoformat(str(s))
            except Exception:
                d0 = datetime.strptime(str(s)[:10], "%Y-%m-%d")
            try:
                d1 = datetime.fromisoformat(str(e))
            except Exception:
                d1 = datetime.strptime(str(e)[:10], "%Y-%m-%d")
            ds = set()
            cur = d0
            while cur <= d1:
                ds.add(cur.strftime("%Y-%m-%d"))
                cur += timedelta(days=1)
            self.page.column_filters["交易时间"] = ds
        acc_rel = f.get("account_related")
        if acc_rel:
            self.page.column_filters["账户相关"] = {str(acc_rel)}
        self.page.apply_filter()
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="关闭", command=self.destroy).pack(side=tk.RIGHT, padx=8, pady=8)
