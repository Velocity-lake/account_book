import tkinter as tk
from tkinter import ttk
import math
from collections import defaultdict
from utils import normalize_ttype, format_amount, parse_datetime as parse_dt
from ui_bill_list import BillListDialog

class IncomePieBigDialog(tk.Toplevel):
    def __init__(self, dashboard, txs):
        super().__init__(dashboard)
        self.title("收入类别占比（大图）")
        self.dashboard = dashboard
        self.geometry("1000x640")
        self.grab_set()
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=12, pady=8)
        self.year_var = tk.StringVar()
        self.month_var = tk.StringVar()
        ttk.Label(header, text="年份").pack(side=tk.LEFT)
        self.cb_year = ttk.Combobox(header, state="readonly", textvariable=self.year_var, width=6)
        self.cb_year.pack(side=tk.LEFT, padx=6)
        ttk.Label(header, text="月份").pack(side=tk.LEFT)
        self.cb_month = ttk.Combobox(header, state="readonly", textvariable=self.month_var, width=4)
        self.cb_month.pack(side=tk.LEFT, padx=6)
        ttk.Button(header, text="上一月", command=self._prev_month).pack(side=tk.LEFT, padx=6)
        ttk.Button(header, text="下一月", command=self._next_month).pack(side=tk.LEFT, padx=6)
        self.cb_year.bind("<<ComboboxSelected>>", lambda e: self._on_combo_change())
        self.cb_month.bind("<<ComboboxSelected>>", lambda e: self._on_combo_change())
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(main)
        right = ttk.Frame(main, width=360)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12,6), pady=12)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(6,12), pady=12)
        self.canvas = tk.Canvas(left, width=900, height=560, bg="#ffffff")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("pie_tip"))
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", lambda e: self._rerender())
        cols = ["消费类别","金额","占比"]
        self.tree = ttk.Treeview(right, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140 if c != "金额" else 160)
        self.tree.pack(fill=tk.Y, expand=True)
        self.tree.bind("<Double-Button-1>", self.on_row_dbl)
        self._init_period_defaults()
        self._compute_items()
        self._rerender()

    def render_pie(self, total):
        self.canvas.delete("all")
        self.update_idletasks()
        w = int(self.canvas.winfo_width())
        h = int(self.canvas.winfo_height())
        w = max(w, 900)
        h = max(h, 560)
        self.canvas.create_text(16, 20, text="收入类别占比", anchor="w")
        cx = w//2
        cy = h//2 + 10
        r = int(min(w-80, h-100)/2)
        bbox = (cx-r, cy-r, cx+r, cy+r)
        palette = ["#2ecc71","#27ae60","#1abc9c","#16a085","#2ca877","#6bd490","#8bd8bd","#4cd3b5","#7fdc8b"]
        start = 0.0
        self.id_map = {}
        show_items = self.items
        if len(show_items) > 12:
            top = show_items[:12]
            other_sum = sum(v for _, v in show_items[12:])
            if other_sum > 0:
                top.append(("其他", other_sum))
            show_items = top
        for i, (name, val) in enumerate(show_items):
            extent = 360.0 * (val/total)
            color = palette[i % len(palette)]
            arc = self.canvas.create_arc(bbox, start=start, extent=extent, fill=color, outline="white", width=1, style=tk.PIESLICE, tags=("pie_slice",))
            mid = start + extent/2
            rad = math.radians(mid)
            lx = cx + int((r+24) * math.cos(rad))
            ly = cy - int((r+24) * math.sin(rad))
            pct = val/total*100
            self.canvas.create_text(lx, ly, text=f"{name} {pct:.0f}%", anchor="center", fill="#333333")
            self.id_map[arc] = {"name":name, "value":val, "pct":pct, "kind":"income"}
            start += extent

    def on_motion(self, e):
        self.canvas.delete("pie_tip")
        item = None
        near = self.canvas.find_closest(e.x, e.y)
        if near:
            i = near[0]
            if i in getattr(self, "id_map", {}):
                item = self.id_map[i]
        if item:
            t = f"{item['name']} 金额: {format_amount(item['value'])} 占比: {item['pct']:.1f}%"
            self.canvas.create_text(e.x+10, e.y-10, text=t, anchor="w", fill="#000000", tags=("pie_tip",))

    def on_click(self, e):
        near = self.canvas.find_closest(e.x, e.y)
        if not near:
            return
        info = getattr(self, "id_map", {}).get(near[0])
        if not info:
            return
        name = info.get("name")
        month_str = f"{self.year_var.get()}-{int(self.month_var.get()):02d}"
        BillListDialog(self.dashboard.view, initial_filters={"month": month_str, "ttype": "收入", "category": name})

    def fill_table(self, total):
        self.tree.delete(*self.tree.get_children())
        for name, val in self.items:
            pct = val/total*100
            self.tree.insert("", tk.END, values=[name, format_amount(val), f"{pct:.1f}%"])

    def on_row_dbl(self, e):
        iid = self.tree.identify_row(e.y)
        if not iid:
            return
        vals = self.tree.item(iid, 'values')
        name = vals[0]
        month_str = f"{self.year_var.get()}-{int(self.month_var.get()):02d}"
        BillListDialog(self.dashboard.view, initial_filters={"month": month_str, "ttype": "收入", "category": name})

    def _init_period_defaults(self):
        from storage import load_state
        s = load_state()
        years = sorted({str(parse_dt(t.get("time",""))).split('T')[0][:4] for t in s.get("transactions", [])})
        from datetime import datetime as _dt
        now = _dt.now()
        if not years:
            years = [str(now.year)]
        self.cb_year["values"] = years
        self.cb_month["values"] = [f"{m:02d}" for m in range(1,13)]
        try:
            if self.dashboard.mode.get() == "日度":
                y, m = map(int, self.dashboard.period.get().split("-"))
            elif self.dashboard.mode.get() == "月份":
                y = int(self.dashboard.period.get())
                m = now.month
            else:
                y = int(self.dashboard.period.get())
                m = now.month
        except Exception:
            y, m = now.year, now.month
        self.year_var.set(str(y))
        self.month_var.set(f"{m:02d}")

    def _compute_items(self):
        from storage import load_state
        s = load_state()
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
        except Exception:
            from datetime import datetime as _dt
            y, m = _dt.now().year, _dt.now().month
        incs = defaultdict(float)
        for t in s.get("transactions", []):
            dt = parse_dt(t.get("time",""))
            if dt.year == y and dt.month == m:
                typ = normalize_ttype(t.get("ttype"))
                if typ in ["收入","报销类收入"]:
                    incs[t.get("category","") or "未分类"] += float(t.get("amount",0))
        self.items = [(k, v) for k, v in incs.items() if v > 0]
        self.items.sort(key=lambda x: x[1], reverse=True)
        self._total = sum(v for _, v in self.items) or 1.0

    def _rerender(self):
        total = getattr(self, "_total", 1.0)
        self.render_pie(total)
        self.fill_table(total)

    def _on_combo_change(self):
        self._compute_items()
        self._rerender()

    def _prev_month(self):
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            m -= 1
            if m == 0:
                y -= 1
                m = 12
            self.year_var.set(str(y))
            self.month_var.set(f"{m:02d}")
            self._on_combo_change()
        except Exception:
            pass

    def _next_month(self):
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            m += 1
            if m == 13:
                y += 1
                m = 1
            self.year_var.set(str(y))
            self.month_var.set(f"{m:02d}")
            self._on_combo_change()
        except Exception:
            pass
