import tkinter as tk
from tkinter import ttk
from storage import load_state, save_state, get_categories, add_category, get_category_rules, add_category_rule, remove_category_rule

class SettingsPage(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        try:
            s = load_state()
            val = (s.get("prefs", {}) or {}).get("menu_layout", getattr(controller, 'menu_layout_mode', 'classic'))
        except Exception:
            val = getattr(controller, 'menu_layout_mode', 'classic')
        self.layout_var = tk.StringVar(value=val)
        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(top, text="软件设置", font=("Microsoft YaHei", 16)).pack(side=tk.LEFT)

        layout = ttk.LabelFrame(self, text="菜单布局")
        layout.pack(fill=tk.X, padx=8, pady=8)
        ttk.Radiobutton(layout, text="经典布局", value="classic", variable=self.layout_var, command=self.on_layout_change).pack(side=tk.LEFT, padx=8, pady=6)
        ttk.Radiobutton(layout, text="精简布局", value="compact", variable=self.layout_var, command=self.on_layout_change).pack(side=tk.LEFT, padx=8, pady=6)

        data = ttk.LabelFrame(self, text="数据导入导出")
        data.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(data, text="导入账单", command=self.controller.show_import_panel).pack(side=tk.LEFT, padx=6, pady=6)
        ttk.Button(data, text="导出账单", command=self.controller.export_records).pack(side=tk.LEFT, padx=6, pady=6)
        ttk.Button(data, text="智能导入（截图）", command=self.controller.import_ai_images).pack(side=tk.LEFT, padx=6, pady=6)

        tmpl = ttk.LabelFrame(self, text="模板与备份")
        tmpl.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(tmpl, text="下载标准模板", command=self.controller.download_template).pack(side=tk.LEFT, padx=6, pady=6)
        ttk.Button(tmpl, text="备份数据", command=self.controller.backup).pack(side=tk.LEFT, padx=6, pady=6)

        system = ttk.LabelFrame(self, text="系统与工具")
        system.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(system, text="刷新数据", command=self.controller.refresh_all).pack(side=tk.LEFT, padx=6, pady=6)

        ai = ttk.LabelFrame(self, text="消费类别预填（关键词规则）")
        ai.pack(fill=tk.BOTH, padx=8, pady=8)
        frm = ttk.Frame(ai)
        frm.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(frm, text="所属类别").grid(row=0, column=0, sticky=tk.W)
        self.cb_scene = ttk.Combobox(frm, values=["收入","支出"], state="readonly")
        self.cb_scene.grid(row=0, column=1, sticky=tk.EW, padx=8)
        self.cb_scene.set("支出")
        ttk.Label(frm, text="关键词").grid(row=0, column=2, sticky=tk.W)
        self.e_keyword = ttk.Entry(frm)
        self.e_keyword.grid(row=0, column=3, sticky=tk.EW, padx=8)
        ttk.Label(frm, text="消费类别").grid(row=0, column=4, sticky=tk.W)
        self.cb_category = ttk.Combobox(frm, values=self._get_scene_categories("支出"), state="readonly")
        self.cb_category.grid(row=0, column=5, sticky=tk.EW, padx=8)
        ttk.Label(frm, text="或输入").grid(row=0, column=6, sticky=tk.W)
        self.e_category_input = ttk.Entry(frm)
        self.e_category_input.grid(row=0, column=7, sticky=tk.EW, padx=8)
        frm.columnconfigure(3, weight=1)
        frm.columnconfigure(7, weight=1)
        def on_scene_change(event=None):
            sc = self.cb_scene.get().strip()
            self.cb_category["values"] = self._get_scene_categories(sc)
            vals = self._get_scene_categories(sc)
            if vals:
                self.cb_category.set(vals[0])
            self._reload_rules()
        self.cb_scene.bind("<<ComboboxSelected>>", on_scene_change)
        ttk.Button(frm, text="添加规则", command=self.on_add_rule).grid(row=0, column=8, padx=8)

        table = ttk.Frame(ai)
        table.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.rules_tree = ttk.Treeview(table, columns=["scene","keyword","category"], show="headings")
        for c, w in [("scene", 120), ("keyword", 220), ("category", 160)]:
            self.rules_tree.heading(c, text=("所属类别" if c=="scene" else ("关键词" if c=="keyword" else "消费类别")))
            self.rules_tree.column(c, width=w, stretch=False)
        self.rules_tree.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(ai)
        btns.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(btns, text="删除选中规则", command=self.on_delete_rule).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="重置全部规则", command=self.on_reset_rules).pack(side=tk.LEFT, padx=6)
        self._reload_rules()

    def on_layout_change(self):
        mode = self.layout_var.get()
        self.controller.set_menu_layout(mode)
        try:
            s = load_state()
            s.setdefault("prefs", {})["menu_layout"] = mode
            save_state(s)
        except Exception:
            pass

    def _get_scene_categories(self, sc: str):
        s = load_state()
        return get_categories(s, sc)

    def _reload_rules(self):
        s = load_state()
        self.rules_tree.delete(*self.rules_tree.get_children())
        for sc in ["收入","支出"]:
            for it in get_category_rules(s, sc):
                self.rules_tree.insert("", tk.END, values=[sc, it.get("keyword",""), it.get("category","")])

    def on_add_rule(self):
        sc = self.cb_scene.get().strip()
        kw = self.e_keyword.get().strip()
        cat = self.cb_category.get().strip()
        cat2 = self.e_category_input.get().strip()
        if cat2:
            cat = cat2
        if not sc or not kw or not cat:
            return
        s = load_state()
        add_category(s, sc, cat)
        add_category_rule(s, sc, kw, cat)
        save_state(s)
        self.e_keyword.delete(0, tk.END)
        self.e_category_input.delete(0, tk.END)
        self._reload_rules()

    def on_delete_rule(self):
        sel = []
        for iid in self.rules_tree.selection():
            vals = self.rules_tree.item(iid, "values")
            if vals:
                sel.append(vals)
        if not sel:
            return
        s = load_state()
        for sc, kw, cat in sel:
            remove_category_rule(s, sc, kw, cat)
        save_state(s)
        self._reload_rules()

    def on_reset_rules(self):
        s = load_state()
        s.setdefault("category_rules", {})["收入"] = []
        s.setdefault("category_rules", {})["支出"] = []
        save_state(s)
        self._reload_rules()