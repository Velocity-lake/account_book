import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from storage import load_state, save_state, apply_transaction_delta, get_account_names, get_transaction, remove_transaction, update_transaction, add_category, get_categories, get_category_rules, BASE_DIR
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
        self.last_filters = {"month": "", "ttype": "", "category": "", "term": "", "amt_op": "", "amt_val": ""}
        self._suppress_update = False
        self.build_ui()
        self.refresh()

    def build_ui(self):
        f = ttk.Frame(self)
        f.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(f, text="月份").pack(side=tk.LEFT)
        self.cb_month = ttk.Combobox(f, state="readonly")
        self.cb_month.pack(side=tk.LEFT, padx=4)
        self.cb_month.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        ttk.Label(f, text="所属类别").pack(side=tk.LEFT)
        self.cb_type = ttk.Combobox(f, values=[""] + TRANSACTION_TYPES, state="readonly")
        self.cb_type.pack(side=tk.LEFT, padx=4)
        self.cb_type.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        ttk.Label(f, text="消费类别").pack(side=tk.LEFT)
        self.e_category = ttk.Entry(f)
        self.e_category.pack(side=tk.LEFT, padx=4)
        self.e_category.bind("<KeyRelease>", lambda e: self.apply_filter())
        ttk.Label(f, text="搜索").pack(side=tk.LEFT, padx=(12,0))
        self.e_search = ttk.Entry(f)
        self.e_search.pack(side=tk.LEFT, padx=4)
        self.e_search.bind("<KeyRelease>", lambda e: self.apply_filter())
        ttk.Label(f, text="金额").pack(side=tk.LEFT, padx=(12,0))
        self.cb_amt_op = ttk.Combobox(f, values=["", ">", "<", "="], state="readonly", width=3)
        self.cb_amt_op.pack(side=tk.LEFT, padx=4)
        self.cb_amt_op.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        self.e_amt_val = ttk.Entry(f, width=8)
        self.e_amt_val.pack(side=tk.LEFT, padx=4)
        def _amt_val_sanitize(evt=None):
            s = ''.join(ch for ch in self.e_amt_val.get() if ch.isdigit())[:5]
            if s != self.e_amt_val.get():
                self.e_amt_val.delete(0, tk.END)
                self.e_amt_val.insert(0, s)
            self.apply_filter()
        self.e_amt_val.bind("<KeyRelease>", _amt_val_sanitize)
        ttk.Button(f, text="筛选", command=self.apply_filter).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="重置", command=self.reset_filter).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT, padx=8)
        ttk.Button(f, text="导入并覆盖原有账单", command=self.import_override).pack(side=tk.LEFT, padx=8)
        if self.controller:
            ttk.Button(f, text="导入账单", command=self.open_import_dialog).pack(side=tk.RIGHT, padx=8)
        # 内联导入面板（默认隐藏）
        self.import_panel = ttk.Frame(self)
        bar = ttk.Frame(self.import_panel)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="导入账单", font=("Microsoft YaHei", 12)).pack(side=tk.LEFT)
        btns = ttk.Frame(self.import_panel)
        btns.pack(fill=tk.X, pady=4)
        if self.controller:
            ttk.Button(btns, text="支付宝账单导入", command=self.controller._import_alipay).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="微信账单导入", command=self.controller._import_wechat).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="标准模版导入", command=self.controller._import_standard).pack(side=tk.LEFT, padx=6)
            ttk.Button(btns, text="其它导入", command=self.controller._import_other).pack(side=tk.LEFT, padx=6)
        # 初始隐藏（不使用内联面板，保留但不显示）
        try:
            self.import_panel.pack_forget()
        except Exception:
            pass
        self.all_columns = [
            "交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"
        ]
        try:
            prefs = (self.state.get("prefs", {}) or {}).get("bill_list", {})
            saved = prefs.get("visible_columns")
            if isinstance(saved, list) and saved:
                self.visible_columns = [c for c in self.all_columns if c in saved]
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
            self.tree.column(c, width=(200 if c == "备注" else 140), stretch=False)
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
        self.column_filters = {}
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑", command=self.on_edit)
        self.menu.add_command(label="删除", command=self.on_delete)
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
        self.menu.add_command(label="删除选中", command=self.delete_selected)

        self.header_menu = tk.Menu(self, tearoff=0)
        self.header_menu.add_command(label="筛选该列", command=lambda: self._open_filter_for_last_header())
        self.header_menu.add_command(label="隐藏该列", command=lambda: self._hide_last_header())
        self.header_menu.add_command(label="显示列管理", command=self.open_columns_manager)
        self._last_header_col = None

    def refresh(self):
        self.state = load_state()
        self.tree.delete(*self.tree.get_children())
        months = set()
        rows = list(self.state.get("transactions", []))
        try:
            rows.sort(key=lambda x: parse_datetime(x.get("time","")), reverse=True)
        except Exception:
            pass
        inc_sum = 0.0
        exp_sum = 0.0
        trans_sum = 0.0
        for t in rows:
            dt = datetime.fromisoformat(t.get("time"))
            months.add(month_key(dt))
            rtime = t.get("record_time")
            rtime_str = ""
            if rtime:
                try:
                    rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    rtime_str = str(rtime)
            vals = [
                dt.strftime("%Y-%m-%d"),
                format_amount(float(t.get("amount",0))),
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
            self.tree.insert("", tk.END, values=vals)
            try:
                amt = float(t.get("amount",0))
                typ = normalize_ttype(t.get("ttype"))
                if typ in ["收入","报销类收入"]:
                    inc_sum += amt
                elif typ in ["支出","报销类支出"]:
                    exp_sum += amt
                elif typ == "转账":
                    trans_sum += amt
            except Exception:
                pass
        self.cb_month["values"] = [""] + sorted(list(months))
        self.lbl_inc.configure(text=f"筛选收入：{self._fmt_footer_amount(inc_sum)}")
        self.lbl_exp.configure(text=f"筛选支出：{self._fmt_footer_amount(exp_sum)}")
        self.lbl_trans.configure(text=f"筛选转账：{self._fmt_footer_amount(trans_sum)}")
        try:
            if getattr(self, "current_sort_col", None):
                self.sort_by(self.current_sort_col, bool(getattr(self, "current_sort_desc", False)))
        except Exception:
            pass

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

    def apply_filter(self):
        if not getattr(self, '_suppress_update', False):
            self.last_filters["month"] = self.cb_month.get().strip()
            self.last_filters["ttype"] = self.cb_type.get().strip()
            self.last_filters["category"] = self.e_category.get().strip()
            term_w = getattr(self, 'e_search', None)
            self.last_filters["term"] = (term_w.get().strip().lower() if term_w else '')
            self.last_filters["amt_op"] = (self.cb_amt_op.get().strip() if hasattr(self, 'cb_amt_op') else '')
            self.last_filters["amt_val"] = (self.e_amt_val.get().strip() if hasattr(self, 'e_amt_val') else '')
        month = self.last_filters.get("month", "")
        ttype = self.last_filters.get("ttype", "")
        category = self.last_filters.get("category", "")
        term = self.last_filters.get("term", "")
        amt_op = self.last_filters.get("amt_op", "")
        amt_val = self.last_filters.get("amt_val", "")
        self.tree.delete(*self.tree.get_children())
        rows = list(self.state.get("transactions", []))
        inc_sum = 0.0
        exp_sum = 0.0
        trans_sum = 0.0
        to_insert = []
        for t in rows:
            dt = datetime.fromisoformat(t.get("time"))
            if month and month_key(dt) != month:
                continue
            if ttype and t.get("ttype") != ttype:
                continue
            if category and category != t.get("category"):
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
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                    format_amount(float(t.get("amount",0))),
                    str(t.get("amount","")),
                    t.get("category",""),
                    t.get("ttype",""),
                    t.get("account",""),
                    t.get("to_account",""),
                    t.get("from_account",""),
                    t.get("note",""),
                    (parse_datetime(t.get("record_time")).strftime("%Y-%m-%d %H:%M") if t.get("record_time") else ""),
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
                    rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    rtime_str = str(rtime)
            vals = [
                dt.strftime("%Y-%m-%d"),
                format_amount(float(t.get("amount",0))),
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
            try:
                amt = float(t.get("amount",0))
                typ = normalize_ttype(t.get("ttype"))
                if typ in ["收入","报销类收入"]:
                    inc_sum += amt
                elif typ in ["支出","报销类支出"]:
                    exp_sum += amt
                elif typ == "转账":
                    trans_sum += amt
            except Exception:
                pass
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

    def _fmt_footer_amount(self, v):
        try:
            a = float(v)
        except Exception:
            a = 0.0
        if a < 10000:
            return f"{int(a)}元"
        return f"{a/10000:.1f}万元"

    def reset_filter(self):
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
        self.last_filters = {"month": "", "ttype": "", "category": "", "term": "", "amt_op": "", "amt_val": ""}
        self.apply_filter()

    def reapply_last_filters(self):
        self._suppress_update = True
        try:
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
            col = self.tree['columns'][idx]
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
        for c in self.all_columns:
            var = tk.BooleanVar(value=(c in self.visible_columns))
            ttk.Checkbutton(frm, text=c, variable=var).pack(anchor=tk.W)
            vars[c] = var
        def preset_basic():
            basic = ["交易时间","金额","消费类别","所属类别","账户","备注","id"]
            for c, v in vars.items():
                v.set(c in basic)
        def preset_extended():
            ext = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"]
            for c, v in vars.items():
                v.set(c in ext)
        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, pady=8)
        ttk.Button(btns, text="基础视图", command=preset_basic).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="扩展视图", command=preset_extended).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="全部", command=lambda: [vars[c].set(True) for c in vars]).pack(side=tk.LEFT, padx=4)
        def ok():
            chosen = [c for c, v in vars.items() if v.get()]
            self.set_visible_columns(chosen)
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
            new = dict(dlg.result)
            new["id"] = tx_id
            update_transaction(self.state, tx_id, DummyTx(new))
            apply_transaction_delta(self.state, new, 1)
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

    def import_override(self):
        paths = filedialog.askopenfilenames(title="选择账单文件", filetypes=[("CSV 文件","*.csv"), ("Excel 文件","*.xlsx"), ("所有文件","*.*")])
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
            messagebox.showerror("导入失败", str(e))

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
        cb_account = ttk.Combobox(dlg, values=names, state="readonly")
        cb_account.grid(row=0, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(dlg, text="转出账户").grid(row=1, column=0, padx=8, pady=6, sticky=tk.W)
        cb_from = ttk.Combobox(dlg, values=names, state="readonly")
        cb_from.grid(row=1, column=1, padx=8, pady=6, sticky=tk.EW)
        ttk.Label(dlg, text="转入账户").grid(row=2, column=0, padx=8, pady=6, sticky=tk.W)
        cb_to = ttk.Combobox(dlg, values=names, state="readonly")
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
        cb_cat = ttk.Combobox(dlg, values=[], state="readonly")
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
        sources = ["手动输入", "支付宝", "微信", "模版导入"]
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
        for iid in self.tree.get_children(""):
            self.tree.selection_add(iid)
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
        col = self.tree['columns'][idx]
        self.open_filter_popup(col, event.x_root, event.y_root)

    def pass_column_filters(self, t):
        for col, allowed in self.column_filters.items():
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

    def import_standard_xlsx_file(self):
        path = filedialog.askopenfilename(title="导入账单", filetypes=[("Excel 文件","*.xlsx"), ("所有文件","*.*")])
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
            messagebox.showerror("导入失败", str(e))

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
        self.page.apply_filter()
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="关闭", command=self.destroy).pack(side=tk.RIGHT, padx=8, pady=8)
