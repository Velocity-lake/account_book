import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime
from models import TRANSACTION_TYPES, Transaction, Account
from storage import load_state, save_state, get_account_names, add_transaction, apply_transaction_delta, get_categories, add_category, delete_category, rename_category, get_account_types, list_accounts_by_type, find_account, backup_state, get_record_sources, add_record_source
from utils import gen_id, parse_datetime, format_amount
from ui_bill_list import BillListDialog

class RecordPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.scene = "支出"
        self.amount_str = ""
        self.category = ""
        self.note = ""
        self.date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.account = ""
        self.to_account = ""
        self.from_account = ""
        self.reimburse = tk.BooleanVar(value=False)
        self._suppress_group_update = False
        self._cell_width_px = 140
        self._h_gap = 12
        self._category_cols = 4
        self.sort_mode = False
        self._sort_items = []
        self.scroll_canvas = None
        self.scroll_content = None
        self._canvas_window = None
        self._top_bar = None
        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        self._top_bar = top
        self.tab_out = ttk.Button(top, text="支出", command=lambda: self.switch_scene("支出"))
        self.tab_in = ttk.Button(top, text="收入", command=lambda: self.switch_scene("收入"))
        self.tab_tr = ttk.Button(top, text="转账", command=lambda: self.switch_scene("转账"))
        self.tab_out.pack(side=tk.LEFT, padx=8, pady=6)
        self.tab_in.pack(side=tk.LEFT, padx=8, pady=6)
        self.tab_tr.pack(side=tk.LEFT, padx=8, pady=6)
        self.btn_sort_mode = ttk.Button(top, text="排序模式", command=self.toggle_sort_mode)
        self.btn_sort_mode.pack(side=tk.RIGHT, padx=4)

        scroll_area = ttk.Frame(self)
        scroll_area.pack(fill=tk.BOTH, expand=True)
        self.scroll_canvas = tk.Canvas(scroll_area, highlightthickness=0)
        vbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=vbar.set)
        self.scroll_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        vbar.grid(row=0, column=1, sticky=tk.NS)
        scroll_area.grid_rowconfigure(0, weight=1)
        scroll_area.grid_columnconfigure(0, weight=1)
        self.scroll_content = ttk.Frame(self.scroll_canvas)
        self._canvas_window = self.scroll_canvas.create_window((0,0), window=self.scroll_content, anchor='nw')
        def _on_cfg(event=None):
            try:
                self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
            except Exception:
                pass
        self.scroll_content.bind("<Configure>", _on_cfg)
        def _on_canvas_cfg(e):
            try:
                self.scroll_canvas.itemconfigure(self._canvas_window, width=e.width)
            except Exception:
                pass
        self.scroll_canvas.bind("<Configure>", _on_canvas_cfg)
        self.scroll_canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)

        self.scene_frame = ttk.Frame(self.scroll_content)
        self.scene_frame.pack(fill=tk.X, padx=8, pady=2)
        self.quick_area = ttk.Frame(self.scroll_content)
        # 初始不占位，按需显示

        self.amount_area = ttk.Frame(self.scroll_content)
        self.amount_area.pack(fill=tk.X, padx=8, pady=4)
        self.e_note = ttk.Entry(self.amount_area)
        self.e_note.insert(0, "点此输入备注...")
        self.e_note.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.e_amount = ttk.Entry(self.amount_area, width=24)
        self.e_amount.insert(0, "点击输入金额")
        self.e_amount.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.e_amount.bind("<KeyRelease>", self.on_amount_key)
        self.e_amount.bind("<FocusIn>", self._amount_focus_in)
        self.e_amount.bind("<FocusOut>", self._amount_focus_out)
        self.lbl_amount_preview = ttk.Label(self.scroll_content, text="格式化金额：0.00", font=("Microsoft YaHei", 10))
        self.lbl_amount_preview.pack(anchor=tk.W, padx=14)
        self.e_note.bind("<FocusIn>", self._note_focus_in)
        self.e_note.bind("<FocusOut>", self._note_focus_out)

        self.info_area = ttk.Frame(self.scroll_content)
        self.info_area.pack(fill=tk.X, padx=8, pady=4)
        self.lbl_acc = ttk.Label(self.info_area, text="账户")
        self.lbl_acc.pack(side=tk.LEFT, padx=4)
        # 分组账户选择（一级分类 + 账户）
        self.cb_acc_group = ttk.Combobox(self.info_area, values=get_account_types(load_state()), state="readonly")
        self.cb_acc_group.pack(side=tk.LEFT, padx=4)
        self.cb_account = ttk.Combobox(self.info_area, state="readonly")
        self.cb_account.pack(side=tk.LEFT, padx=4)
        self.cb_acc_group.bind("<<ComboboxSelected>>", lambda e: self._update_accounts_by_group())
        self.cb_account.bind("<<ComboboxSelected>>", lambda e: self._on_account_change())
        self.btn_date = ttk.Button(self.info_area, text=self._date_button_text(), command=lambda: self.show_calendar(self.info_area))
        self.btn_date.pack(side=tk.LEFT, padx=4)
        ttk.Label(self.info_area, text="记录来源").pack(side=tk.LEFT, padx=4)
        self.cb_record_source = ttk.Combobox(self.info_area, state="normal")
        try:
            s = load_state()
            self.cb_record_source["values"] = get_record_sources(s)
            self.cb_record_source.set("手动输入")
        except Exception:
            self.cb_record_source["values"] = ["手动输入"]
            self.cb_record_source.set("手动输入")
        def _on_src_change(evt=None):
            try:
                name = (self.cb_record_source.get() or "").strip()
                if not name:
                    return
                s2 = load_state()
                add_record_source(s2, name)
                save_state(s2)
                self.cb_record_source["values"] = get_record_sources(s2)
            except Exception:
                pass
        self.cb_record_source.bind("<<ComboboxSelected>>", _on_src_change)
        self.cb_record_source.bind("<FocusOut>", _on_src_change)
        self.cb_record_source.bind("<Return>", lambda e: (_on_src_change(), "break"))
        self.cb_record_source.pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(self.info_area, text="报销", variable=self.reimburse).pack(side=tk.LEFT, padx=4)
        self.calendar_win = None

        self.keyboard = ttk.Frame(self.scroll_content)
        self.keyboard.pack(fill=tk.X, padx=8, pady=8)
        keys = ["1","2","3","⌫","4","5","6","-","7","8","9","+","再记","0",".","保存"]
        for i, k in enumerate(keys):
            style = 'Primary.TButton' if k == '保存' else ('Secondary.TButton' if k == '再记' else 'TButton')
            b = ttk.Button(self.keyboard, text=k, style=style, command=lambda x=k: self.on_key(x))
            r, c = divmod(i, 4)
            b.grid(row=r, column=c, sticky=tk.EW, padx=4, pady=4)
        for i in range(4):
            self.keyboard.columnconfigure(i, weight=1)

        self.switch_scene(self.scene)

    def refresh(self):
        self.switch_scene(self.scene)

    def switch_scene(self, sc):
        self.scene = sc
        for w in self.scene_frame.winfo_children():
            w.destroy()
        for w in self.quick_area.winfo_children():
            w.destroy()
        if sc in ["支出", "收入"]:
            # 显示分组账户选择
            if not self.cb_account.winfo_ismapped():
                self.lbl_acc.pack(side=tk.LEFT, padx=4)
                self.cb_acc_group.pack(side=tk.LEFT, padx=4)
                self.cb_account.pack(side=tk.LEFT, padx=4)
                self._fill_all_accounts()
            try:
                self.btn_sort_mode.configure(text=("退出排序" if self.sort_mode else "排序模式"))
            except Exception:
                pass
            if self.sort_mode:
                self.build_sort_list(sc)
            else:
                self._render_quick_categories(sc)
                self.build_category_grid(sc)
        else:
            # 隐藏单账户选择
            if self.cb_account.winfo_ismapped():
                self.lbl_acc.pack_forget()
                self.cb_acc_group.pack_forget()
                self.cb_account.pack_forget()
            self.build_transfer_area()
        self.update_amount_label()

    def toggle_sort_mode(self):
        self.sort_mode = not self.sort_mode
        self.switch_scene(self.scene)

    def build_sort_list(self, sc):
        s = load_state()
        cats = get_categories(s, sc)
        self._sort_items = list(cats)
        frm = ttk.Frame(self.scene_frame)
        frm.pack(fill=tk.BOTH, expand=True)
        lb = tk.Listbox(frm)
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for name in self._sort_items:
            lb.insert(tk.END, name)
        def _press(e):
            try:
                self._drag_index = lb.nearest(e.y)
                lb.selection_clear(0, tk.END)
                lb.selection_set(self._drag_index)
            except Exception:
                pass
        def _motion(e):
            try:
                idx = lb.nearest(e.y)
                lb.selection_clear(0, tk.END)
                lb.selection_set(idx)
            except Exception:
                pass
        def _release(e):
            try:
                src = getattr(self, "_drag_index", None)
                dst = lb.nearest(e.y)
                if src is None or dst is None:
                    return
                if src < 0 or dst < 0 or src == dst:
                    return
                it = self._sort_items.pop(src)
                self._sort_items.insert(dst, it)
                lb.delete(0, tk.END)
                for name in self._sort_items:
                    lb.insert(tk.END, name)
                lb.selection_clear(0, tk.END)
                lb.selection_set(dst)
            except Exception:
                pass
        lb.bind("<ButtonPress-1>", _press)
        lb.bind("<B1-Motion>", _motion)
        lb.bind("<ButtonRelease-1>", _release)
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, padx=8, pady=8)
        def _save():
            try:
                s2 = load_state()
                cats2 = s2.setdefault("categories", {}).setdefault(sc, [])
                cats2[:] = list(self._sort_items)
                save_state(s2)
            except Exception:
                pass
            self.sort_mode = False
            self.switch_scene(sc)
        def _cancel():
            self.sort_mode = False
            self.switch_scene(sc)
        ttk.Button(btns, text="保存顺序", command=_save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="取消", command=_cancel).pack(side=tk.RIGHT, padx=4)

    def _on_mouse_wheel(self, event):
        try:
            w = event.widget
            while w is not None:
                if w is self._top_bar:
                    return "break"
                w = getattr(w, 'master', None)
        except Exception:
            pass
        try:
            delta_units = -1 * (event.delta // 120)
            y0, y1 = self.scroll_canvas.yview()
            if delta_units < 0 and y0 <= 0.0:
                return "break"
            if delta_units > 0 and y1 >= 1.0:
                return "break"
            self.scroll_canvas.yview_scroll(delta_units, "units")
            return "break"
        except Exception:
            return

    def build_category_grid(self, sc):
        s = load_state()
        cats = get_categories(s, sc)
        self.category_buttons = {}
        grid = ttk.Frame(self.scene_frame)
        grid.pack(fill=tk.X)

        def render(cols):
            for i in range(cols):
                grid.columnconfigure(i, minsize=self._cell_width_px, weight=1, uniform='cat')
            idx = 0
            if sc == "支出":
                rel_types = {"支出", "报销类支出"}
            elif sc == "收入":
                rel_types = {"收入", "报销类收入"}
            else:
                rel_types = set()
            used_set = set()
            try:
                for t in s.get("transactions", []):
                    tt = t.get("ttype")
                    if tt in rel_types:
                        c = t.get("category") or ""
                        if c:
                            used_set.add(c)
            except Exception:
                pass
            for name in cats:
                btn = tk.Label(
                    grid,
                    text=name,
                    borderwidth=1,
                    relief=tk.GROOVE,
                    padx=8,
                    pady=6,
                    anchor=tk.CENTER,
                    wraplength=self._cell_width_px - 16,
                )
                try:
                    if name not in used_set:
                        btn.configure(fg="blue")
                except Exception:
                    pass
                btn.grid(row=idx//cols, column=idx%cols, padx=6, pady=6, sticky=tk.NSEW)
                btn.bind("<Button-1>", lambda e, n=name: self.select_category(n))
                btn.bind("<Button-3>", lambda e, n=name: self.on_category_menu(e, n))
                btn.bind("<Double-1>", lambda e, n=name, scene=sc: self.open_bill_list_for_category(scene, n))
                btn.default_bg = btn.cget("bg")
                self.category_buttons[name] = btn
                if self.category == name:
                    color = "#ffecec" if self.scene == "支出" else "#e8ffea"
                    btn.configure(bg=color)
                idx += 1
            add_entry = ttk.Entry(grid)
            add_entry.insert(0, "输入类别名后回车")
            def _f_in(e=None):
                if (add_entry.get() or "").strip() == "输入类别名后回车":
                    add_entry.delete(0, tk.END)
            def _f_out(e=None):
                if not (add_entry.get() or "").strip():
                    add_entry.insert(0, "输入类别名后回车")
            def _commit(e=None):
                name = (add_entry.get() or "").strip()
                if not name or name == "输入类别名后回车":
                    return
                add_category(s, sc, name)
                save_state(s)
                self.switch_scene(self.scene)
            add_entry.bind("<FocusIn>", _f_in)
            add_entry.bind("<FocusOut>", _f_out)
            add_entry.bind("<Return>", _commit)
            add_entry.grid(row=idx//cols, column=idx%cols, padx=6, pady=6, sticky=tk.NSEW)

        w = max(grid.winfo_width(), self.scene_frame.winfo_width())
        cell_total = self._cell_width_px + self._h_gap
        cols = max(1, (w // cell_total) if w > 0 else self._category_cols)
        self._category_cols = cols
        render(cols)

        def on_resize(event):
            w = event.width
            cell_total = self._cell_width_px + self._h_gap
            new_cols = max(1, w // cell_total)
            if new_cols != self._category_cols:
                self._category_cols = new_cols
                for c in grid.winfo_children():
                    c.destroy()
                self.category_buttons = {}
                render(new_cols)

        grid.bind("<Configure>", on_resize)

    def _render_quick_categories(self, sc):
        s = load_state()
        if sc == "支出":
            rel = {"支出","报销类支出"}
        else:
            rel = {"收入","报销类收入"}
        items = []
        for t in sorted(s.get("transactions", []), key=lambda x: parse_datetime(x.get("time","")), reverse=True):
            tt = (t.get("ttype") or "")
            if tt in rel:
                c = (t.get("category") or "").strip()
                if c and c not in items:
                    items.append(c)
            if len(items) >= 6:
                break
        # 动态控制 quick_area 的占位，避免空白
        for w in self.quick_area.winfo_children():
            w.destroy()
        if not items:
            try:
                self.quick_area.pack_forget()
            except Exception:
                pass
            return
        try:
            if not self.quick_area.winfo_ismapped():
                self.quick_area.pack(fill=tk.X, padx=8, pady=2)
        except Exception:
            pass
        ttk.Label(self.quick_area, text="最近使用：").pack(side=tk.LEFT)
        for name in items:
            b = ttk.Button(self.quick_area, text=name, style='Secondary.TButton', command=lambda n=name: self.select_category(n))
            b.pack(side=tk.LEFT, padx=4)

    def build_transfer_area(self):
        f = ttk.Frame(self.scene_frame)
        f.pack(fill=tk.X)
        ttk.Label(f, text="转出分类").grid(row=0, column=0, sticky=tk.W, padx=4, pady=6)
        self.cb_from_group = ttk.Combobox(f, values=get_account_types(load_state()), state="readonly")
        self.cb_from_group.grid(row=0, column=1, sticky=tk.EW, padx=4)
        ttk.Label(f, text="转出账户").grid(row=0, column=2, sticky=tk.W, padx=4, pady=6)
        self.cb_from = ttk.Combobox(f, state="readonly")
        self.cb_from.grid(row=0, column=3, sticky=tk.EW, padx=4)
        ttk.Label(f, text="转入分类").grid(row=1, column=0, sticky=tk.W, padx=4, pady=6)
        self.cb_to_group = ttk.Combobox(f, values=get_account_types(load_state()), state="readonly")
        self.cb_to_group.grid(row=1, column=1, sticky=tk.EW, padx=4)
        ttk.Label(f, text="转入账户").grid(row=1, column=2, sticky=tk.W, padx=4, pady=6)
        self.cb_to = ttk.Combobox(f, state="readonly")
        self.cb_to.grid(row=1, column=3, sticky=tk.EW, padx=4)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(3, weight=1)
        self.cb_from_group.bind("<<ComboboxSelected>>", lambda e: self._update_transfer_accounts('from'))
        self.cb_to_group.bind("<<ComboboxSelected>>", lambda e: self._update_transfer_accounts('to'))
        self.cb_from.bind("<<ComboboxSelected>>", lambda e: self._on_transfer_account_combo_selected('from'))
        self.cb_to.bind("<<ComboboxSelected>>", lambda e: self._on_transfer_account_combo_selected('to'))
        # 初始填充所有账户
        try:
            s = load_state()
            names = get_account_names(s)
            self.cb_from["values"] = names + ["新增账户"]
            self.cb_to["values"] = names + ["新增账户"]
        except Exception:
            pass

    def _on_account_change(self):
        self.account = self.cb_account.get().strip()
        if not self.account:
            return
        s = load_state()
        a = find_account(s, self.account)
        if a:
            typ = (a.get("type") or "").strip()
            try:
                self._suppress_group_update = True
                self.cb_acc_group.set(typ or "")
            finally:
                self._suppress_group_update = False
    def _on_account_combo_selected(self):
        val = (self.cb_account.get() or "").strip()
        if val == "新增账户":
            from ui_account_manager import AccountDialog
            dlg = AccountDialog(self, None)
            self.wait_window(dlg)
            if dlg.result:
                s = load_state()
                from storage import add_account, save_state
                a = dlg.result
                add_account(s, Account(**a))
                save_state(s)
                self._fill_all_accounts()
                try:
                    self.cb_account.set(a.get("name",""))
                    self._on_account_change()
                except Exception:
                    pass
        else:
            self._on_account_change()

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
        now = datetime.now()
        self.date_str = f"{y:04d}-{m:02d}-{d:02d} {now.strftime('%H:%M:%S')}"
        if self.calendar_win and self.calendar_win.winfo_exists():
            self.calendar_win.destroy()
        if hasattr(self, 'btn_date'):
            self.btn_date.configure(text=self._date_button_text())

    def _on_transfer_account_change(self, side):
        name = (self.cb_from.get().strip() if side=='from' else self.cb_to.get().strip())
        if not name:
            return
        s = load_state()
        a = find_account(s, name)
        if a:
            typ = (a.get("type") or "").strip()
            try:
                self._suppress_group_update = True
                if side=='from':
                    self.cb_from_group.set(typ or "")
                else:
                    self.cb_to_group.set(typ or "")
            finally:
                self._suppress_group_update = False

    def select_category(self, name):
        self.category = name
        for n, btn in getattr(self, 'category_buttons', {}).items():
            if n == name:
                color = "#ffecec" if self.scene == "支出" else "#e8ffea"
                btn.configure(bg=color)
            else:
                btn.configure(bg=getattr(btn, 'default_bg', btn.cget('bg')))

    def on_category_menu(self, event, name):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="进入该类别清单", command=lambda: self.open_bill_list_for_category(self.scene, name))
        m.add_command(label="重命名", command=lambda: self.rename_category(name))
        m.add_command(label="删除", command=lambda: self.delete_category(name))
        m.post(event.x_root, event.y_root)

    def on_add_category(self):
        dlg = tk.Toplevel(self)
        dlg.title("新增类别")
        dlg.grab_set()
        e = ttk.Entry(dlg)
        e.pack(padx=12, pady=12)
        def ok():
            name = e.get().strip()
            s = load_state()
            add_category(s, self.scene, name)
            save_state(s)
            dlg.destroy()
            self.switch_scene(self.scene)
        ttk.Button(dlg, text="确定", command=ok).pack(pady=8)
        self.wait_window(dlg)

    def rename_category(self, old):
        dlg = tk.Toplevel(self)
        dlg.title("重命名类别")
        dlg.grab_set()
        e = ttk.Entry(dlg)
        e.insert(0, old)
        e.pack(padx=12, pady=12)
        update_hist = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text="同时更新历史记录", variable=update_hist).pack(padx=12)
        def ok():
            new = e.get().strip()
            s = load_state()
            rename_category(s, self.scene, old, new, update_hist.get())
            save_state(s)
            dlg.destroy()
            if self.category == old:
                self.category = new
            self.switch_scene(self.scene)
        ttk.Button(dlg, text="确定", command=ok).pack(pady=8)
        self.wait_window(dlg)

    def delete_category(self, name):
        s = load_state()
        cnt = 0
        for t in s.get("transactions", []):
            if (t.get("category") or "") == name:
                cnt += 1
        do_clear = messagebox.askyesno("删除类别", f"该类别在 {cnt} 条账单中使用。是否同时清空这些账单的消费类别？")
        if do_clear:
            backup_state()
            for t in s.get("transactions", []):
                if (t.get("category") or "") == name:
                    t["category"] = ""
        delete_category(s, self.scene, name)
        save_state(s)
        if self.category == name:
            self.category = ""
        self.switch_scene(self.scene)

    def open_bill_list_for_category(self, scene, name):
        filters = {"ttype": scene, "category": name}
        BillListDialog(self, initial_filters=filters)

    def on_key(self, k):
        if k == "⌫":
            cur = self.e_amount.index(tk.INSERT)
            if cur > 0:
                s = self.e_amount.get()
                s = s[:cur-1] + s[cur:]
                self.set_amount_input(s, cur-1)
        elif k == "再记":
            self.e_amount.delete(0, tk.END)
            self.e_note.delete(0, tk.END)
            self.category = ""
        elif k == "保存":
            self.save_transaction()
        elif k in ["+","-"]:
            pass
        else:
            cur = self.e_amount.index(tk.INSERT)
            s = self.e_amount.get()
            s = s[:cur] + k + s[cur:]
            self.set_amount_input(s, cur+1)
        self.update_amount_label()

    def update_amount_label(self):
        s = self.e_amount.get().strip()
        if s == "点击输入金额":
            self.lbl_amount_preview.configure(text="格式化金额：0.00")
            return
        if re.fullmatch(r"\d{1,10}(\.\d{0,2})?", s):
            try:
                self.lbl_amount_preview.configure(text=f"格式化金额：{format_amount(float(s))}")
            except Exception:
                self.lbl_amount_preview.configure(text="格式化金额：0.00")
        else:
            self.lbl_amount_preview.configure(text="格式化金额：0.00")

    def _date_button_text(self):
        try:
            dt = datetime.strptime(self.date_str, "%Y-%m-%d %H:%M:%S")
            if dt.date() == datetime.now().date():
                return "今天"
            return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"
        except Exception:
            return "今天"

    def _note_focus_in(self, e):
        if self.e_note.get().strip() == "点此输入备注...":
            self.e_note.delete(0, tk.END)

    def _note_focus_out(self, e):
        if not self.e_note.get().strip():
            self.e_note.delete(0, tk.END)
            self.e_note.insert(0, "点此输入备注...")

    def save_transaction(self):
        try:
            s_amt = self.e_amount.get().strip()
            if not re.fullmatch(r"\d{1,10}(\.\d{1,2})?", s_amt):
                raise ValueError("请输入有效金额，最多10位整数和2位小数")
            amt = float(s_amt)
            if amt <= 0:
                raise ValueError("请输入有效金额")
            ttype = self.scene
            if self.scene == "支出" and self.reimburse.get():
                ttype = "报销类支出"
            if self.scene == "收入" and self.reimburse.get():
                ttype = "报销类收入"
            acc = self.account
            s = load_state()
            if self.scene == "转账":
                fa = (self.cb_from.get().strip() or None)
                ta = (self.cb_to.get().strip() or None)
                d = {
                    "id": gen_id(),
                    "time": parse_datetime(self.date_str).isoformat(),
                    "amount": amt,
                    "category": "转账",
                    "ttype": "转账",
                    "account": "",
                    "to_account": ta,
                    "from_account": fa,
                    "note": ("" if self.e_note.get().strip() == "点此输入备注..." else self.e_note.get().strip()),
                    "record_time": datetime.now().isoformat(),
                    "record_source": "手动输入",
                }
            else:
                if not self.category:
                    raise ValueError("请选择类别")
                if not acc:
                    names = get_account_names(s)
                    if not names:
                        raise ValueError("请先新增账户")
                    acc = names[0]
                try:
                    src_val = (self.cb_record_source.get() or "").strip() or "手动输入"
                except Exception:
                    src_val = "手动输入"
                d = {
                    "id": gen_id(),
                    "time": parse_datetime(self.date_str).isoformat(),
                    "amount": amt,
                    "category": self.category,
                    "ttype": ttype,
                    "account": acc,
                    "to_account": None,
                    "from_account": None,
                    "note": ("" if self.e_note.get().strip() == "点此输入备注..." else self.e_note.get().strip()),
                    "record_time": datetime.now().isoformat(),
                    "record_source": src_val,
                }
            s["transactions"].append(d)
            apply_transaction_delta(s, d, 1)
            save_state(s)
            messagebox.showinfo("成功", "已记录到账单列表")
            self.e_amount.delete(0, tk.END)
            self.update_amount_label()
            self.e_note.delete(0, tk.END)
            self.e_note.insert(0, "点此输入备注...")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def on_amount_key(self, evt):
        s = self.e_amount.get()
        self.set_amount_input(s, self.e_amount.index(tk.INSERT))
        self.update_amount_label()

    def set_amount_input(self, s, cursor):
        s2 = re.sub(r"[^0-9.]", "", s)
        parts = s2.split(".")
        if len(parts) > 2:
            s2 = parts[0] + "." + "".join(parts[1:])
            parts = s2.split(".")
        intp = parts[0][:10]
        decp = (parts[1][:2] if len(parts) == 2 else "")
        s2 = intp + ("." + decp if decp != "" else "")
        self.e_amount.delete(0, tk.END)
        self.e_amount.insert(0, s2)
        try:
            self.e_amount.icursor(min(cursor, len(s2)))
        except Exception:
            pass

    def _amount_focus_in(self, e):
        if self.e_amount.get().strip() == "点击输入金额":
            self.e_amount.delete(0, tk.END)

    def _amount_focus_out(self, e):
        if not self.e_amount.get().strip():
            self.e_amount.delete(0, tk.END)
            self.e_amount.insert(0, "点击输入金额")

    def _update_accounts_by_group(self):
        if getattr(self, '_suppress_group_update', False):
            return
        s = load_state()
        typ = self.cb_acc_group.get().strip()
        if not typ:
            names = get_account_names(s)
        else:
            names = list(list_accounts_by_type(s).get(typ, []))
        self.cb_account["values"] = names + ["新增账户"]
        try:
            cur = self.cb_account.get().strip()
            if cur and cur in names:
                pass
            elif names:
                self.cb_account.set(names[0])
                self._on_account_change()
        except Exception:
            pass

    def _update_transfer_accounts(self, which):
        s = load_state()
        if which == 'from':
            typ = self.cb_from_group.get().strip()
            names = get_account_names(s) if not typ else list(list_accounts_by_type(s).get(typ, []))
            self.cb_from["values"] = names
            try:
                cur = self.cb_from.get().strip()
                if cur and cur in names:
                    pass
                elif names:
                    self.cb_from.set(names[0])
            except Exception:
                pass

    def _fill_all_accounts(self):
        s = load_state()
        names = get_account_names(s)
        self.cb_account["values"] = names + ["新增账户"]
        if names:
            try:
                self.cb_account.set(names[0])
                self._on_account_change()
            except Exception:
                pass

    def _fill_all_transfer_accounts(self):
        s = load_state()
        names = get_account_names(s)
        self.cb_from["values"] = names + ["新增账户"]
        self.cb_to["values"] = names + ["新增账户"]
        if names:
            try:
                self.cb_from.set(names[0])
                self._on_transfer_account_change('from')
                self.cb_to.set(names[-1] if len(names) > 1 else names[0])
                self._on_transfer_account_change('to')
            except Exception:
                pass
        else:
            typ = self.cb_to_group.get().strip()
            names = get_account_names(s) if not typ else list(list_accounts_by_type(s).get(typ, []))
            self.cb_to["values"] = names + ["新增账户"]
            try:
                cur = self.cb_to.get().strip()
                if cur and cur in names:
                    pass
                elif names:
                    self.cb_to.set(names[0])
            except Exception:
                pass

    def _on_transfer_account_combo_selected(self, side):
        val = (self.cb_from.get().strip() if side=='from' else self.cb_to.get().strip())
        if val == "新增账户":
            from ui_account_manager import AccountDialog
            dlg = AccountDialog(self, None)
            self.wait_window(dlg)
            if dlg.result:
                s = load_state()
                from storage import add_account, save_state
                a = dlg.result
                add_account(s, Account(**a))
                save_state(s)
                self._update_transfer_accounts(side)
                try:
                    if side=='from':
                        self.cb_from.set(a.get("name",""))
                        self._on_transfer_account_change('from')
                    else:
                        self.cb_to.set(a.get("name",""))
                        self._on_transfer_account_change('to')
                except Exception:
                    pass
        else:
            self._on_transfer_account_change(side)
