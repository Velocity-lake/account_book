import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
from datetime import datetime, timedelta
from collections import defaultdict
from storage import load_state, save_state, apply_transaction_delta, get_account_names, get_transaction, remove_transaction, update_transaction, add_category, get_categories, get_category_rules, query_transactions
import os
import time
 
from utils import parse_datetime, format_amount, normalize_ttype, gen_id
from ui_bill_list import BillListDialog
from ui_income_big import IncomePieBigDialog
from ui_expense_big import ExpensePieBigDialog
from ui_add_dialog import AddTransactionDialog
import math
import calendar
from datetime import datetime

class DashboardPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.mode = tk.StringVar(value="月份")
        self.period = tk.StringVar()
        self.build_ui()
        self.refresh()

    def build_ui(self):
        self.vcanvas = tk.Canvas(self, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.vcanvas.yview)
        self.vcanvas.configure(yscrollcommand=self.vbar.set)
        self.vcanvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        header = ttk.Frame(self)
        header.pack(fill=tk.X, before=self.vcanvas)
        top = ttk.Frame(header)
        top.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(top, text="首页总览", font=("Microsoft YaHei", 16)).pack(side=tk.LEFT)
        
        tabs = ttk.Frame(top)
        tabs.pack(side=tk.LEFT, padx=12)
        ttk.Radiobutton(tabs, text="日度", variable=self.mode, value="日度", command=self.on_mode_change).pack(side=tk.LEFT)
        ttk.Radiobutton(tabs, text="月份", variable=self.mode, value="月份", command=self.on_mode_change).pack(side=tk.LEFT)
        ttk.Radiobutton(tabs, text="年份", variable=self.mode, value="年份", command=self.on_mode_change).pack(side=tk.LEFT)
        self.cb_period = ttk.Combobox(top, state="readonly", textvariable=self.period)
        self.cb_period.pack(side=tk.LEFT, padx=8)
        self.cb_period.bind("<<ComboboxSelected>>", lambda e: self.compute_and_render())
        self.btn_prev = ttk.Button(top, text="上一期", command=self.prev_period)
        self.btn_prev.pack(side=tk.LEFT, padx=4)
        self.btn_curr = ttk.Button(top, text="本期", command=self.current_period)
        self.btn_curr.pack(side=tk.LEFT, padx=4)
        self.btn_next = ttk.Button(top, text="下一期", command=self.next_period)
        self.btn_next.pack(side=tk.LEFT, padx=4)
        kpi = ttk.Frame(header)
        kpi.pack(fill=tk.X, padx=8, pady=8)
        self.k_income = ttk.Label(kpi, text="总收入: 0.00")
        self.k_expense = ttk.Label(kpi, text="总支出: 0.00")
        self.k_net = ttk.Label(kpi, text="净现金流: 0.00")
        self.k_assets = ttk.Label(kpi, text="期末总资产: 0.00")
        self.k_change = ttk.Label(kpi, text="资产变动: 0.00")
        for w in [self.k_income, self.k_expense, self.k_net, self.k_assets, self.k_change]:
            w.pack(side=tk.LEFT, padx=12)
        header.bind("<MouseWheel>", self._on_mousewheel)
        self.view = ttk.Frame(self.vcanvas)
        self._view_win = self.vcanvas.create_window((0,0), window=self.view, anchor="nw")
        self.view.bind("<Configure>", lambda e: self.vcanvas.configure(scrollregion=self.vcanvas.bbox("all")))
        self.vcanvas.bind("<Configure>", lambda e: self.vcanvas.itemconfigure(self._view_win, width=e.width))
        self.vcanvas.bind("<MouseWheel>", self._on_mousewheel)
        self.view.bind("<MouseWheel>", self._on_mousewheel)
        try:
            self.vcanvas.bind_all("<MouseWheel>", self._on_mousewheel)
        except Exception:
            pass
        self.vcanvas.bind("<ButtonPress-1>", self._drag_v_start)
        self.vcanvas.bind("<B1-Motion>", self._drag_v_move)
        self.view.bind("<ButtonPress-1>", self._drag_v_start)
        self.view.bind("<B1-Motion>", self._drag_v_move)

        self.paned = ttk.Panedwindow(self.view, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        self.left_main = ttk.Frame(self.paned)
        self.right_panel = ttk.Frame(self.paned, width=400)
        self.paned.add(self.left_main, weight=3)
        self.paned.add(self.right_panel, weight=1)
        self.paned.bind("<MouseWheel>", self._on_mousewheel)
        self.left_main.bind("<MouseWheel>", self._on_mousewheel)
        self.right_panel.bind("<MouseWheel>", self._on_mousewheel)
        self.right_module = None
        try:
            self.paned.bind("<ButtonRelease-1>", self._on_sash_release)
            self.after(0, self._apply_saved_sash)
        except Exception:
            pass

        try:
            base = None
            try:
                base = tkfont.nametofont("TkDefaultFont")
            except Exception:
                base = tkfont.nametofont("TkTextFont")
            fam = base.cget("family") or "Microsoft YaHei"
            sz = base.cget("size")
            try:
                sz = abs(int(sz))
            except Exception:
                sz = 10
            self._chart_small_font = (fam, max(sz-1, 8))
        except Exception:
            self._chart_small_font = ("Microsoft YaHei", 10)

        bars = ttk.Frame(self.left_main)
        bars.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.canvas_bars_axis = tk.Canvas(bars, width=72, height=240, bg="#ffffff")
        self.canvas_bars_axis.pack(side=tk.LEFT, fill=tk.Y)
        self.canvas_bars = tk.Canvas(bars, height=240, bg="#ffffff")
        self.canvas_bars.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Shared horizontal scrollbar placed between bars and trend
        self.scrollx = ttk.Scrollbar(self.left_main, orient="horizontal", command=self._scrollx)
        self.scrollx.pack(fill=tk.X)
        self.canvas_bars.configure(xscrollcommand=self._on_scrollx)
        self.canvas_bars.bind("<Motion>", self.on_bars_motion)
        self.canvas_bars.bind("<Leave>", lambda e: self.canvas_bars.delete("bars_tip"))
        self.canvas_bars.bind("<Button-1>", self.on_bars_click)
        self.canvas_bars.bind("<Button-3>", self.on_bars_right_click)
        try:
            self.canvas_bars.bind("<Configure>", lambda e: self._on_chart_configure("bars"))
            self.canvas_bars_axis.bind("<Configure>", lambda e: self._on_chart_configure("bars"))
        except Exception:
            pass

        trend = ttk.Frame(self.left_main)
        trend.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.canvas_trend_axis = tk.Canvas(trend, width=72, height=220, bg="#ffffff")
        self.canvas_trend_axis.pack(side=tk.LEFT, fill=tk.Y)
        self.canvas_trend = tk.Canvas(trend, height=220, bg="#ffffff")
        self.canvas_trend.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas_trend.bind("<Motion>", self.on_trend_motion)
        self.canvas_trend.bind("<Leave>", lambda e: self.canvas_trend.delete("trend_tip"))
        self.canvas_trend.bind("<Button-1>", self.on_trend_click)
        self.canvas_trend.bind("<Button-3>", self.on_trend_right_click)
        self.canvas_trend.configure(xscrollcommand=self._on_scrollx)
        try:
            self.canvas_trend.bind("<Configure>", lambda e: self._on_chart_configure("trend"))
            self.canvas_trend_axis.bind("<Configure>", lambda e: self._on_chart_configure("trend"))
        except Exception:
            pass

        pies = ttk.Frame(self.left_main)
        pies.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.canvas_pie_income = tk.Canvas(pies, height=240, bg="#ffffff")
        self.canvas_pie_expense = tk.Canvas(pies, height=240, bg="#ffffff")
        self.canvas_pie_income.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,4))
        self.canvas_pie_expense.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0))
        # (scrollbar already placed between bars and trend)
        self.canvas_pie_income.bind("<Motion>", self.on_pie_income_motion)
        self.canvas_pie_income.bind("<Leave>", lambda e: self.canvas_pie_income.delete("pie_tip"))
        self.canvas_pie_income.bind("<Button-1>", self.on_pie_income_click)
        
        self.canvas_pie_expense.bind("<Motion>", self.on_pie_expense_motion)
        self.canvas_pie_expense.bind("<Leave>", lambda e: self.canvas_pie_expense.delete("pie_tip"))
        self.canvas_pie_expense.bind("<Button-1>", self.on_pie_expense_click)
        
        try:
            self.canvas_pie_income.bind("<Configure>", lambda e: self._on_chart_configure("pie_i"))
            self.canvas_pie_expense.bind("<Configure>", lambda e: self._on_chart_configure("pie_e"))
        except Exception:
            pass

        bottom = ttk.Frame(self.left_main)
        bottom.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Label(bottom, text="账户余额").pack(anchor=tk.W)
        self.tree_accounts = ttk.Treeview(bottom, columns=["账户","余额","本期净流"], show="headings")
        for c in ["账户","余额","本期净流"]:
            self.tree_accounts.heading(c, text=c)
            self.tree_accounts.column(c, width=160)
        self.tree_accounts.pack(fill=tk.BOTH, expand=True)

        recent = ttk.Frame(self.left_main)
        recent.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Label(recent, text="本期最近记录").pack(anchor=tk.W)
        cols = ["日期","消费类别","金额","账户","备注"]
        self.tree_recent = ttk.Treeview(recent, columns=cols, show="headings")
        for c in cols:
            self.tree_recent.heading(c, text=c)
            self.tree_recent.column(c, width=160 if c != "备注" else 280)
        self.tree_recent.pack(fill=tk.BOTH, expand=True)

        # Shift + wheel horizontal scroll on charts
        self.canvas_bars.bind("<Shift-MouseWheel>", lambda e: self._scrollx('scroll', -1 * (e.delta//120), 'units'))
        self.canvas_trend.bind("<Shift-MouseWheel>", lambda e: self._scrollx('scroll', -1 * (e.delta//120), 'units'))
        self.show_right_module()
        try:
            self.after_idle(self._ensure_first_layout)
        except Exception:
            pass

    def _on_mousewheel(self, e):
        try:
            delta = -1 * (e.delta // 120)
        except Exception:
            delta = -1
        try:
            w = e.widget
            while w is not None:
                if hasattr(w, "yview"):
                    try:
                        y0, y1 = w.yview()
                    except Exception:
                        y0, y1 = None, None
                    if y0 is not None and y1 is not None:
                        if delta < 0 and y0 <= 0.0:
                            pass
                        elif delta > 0 and y1 >= 1.0:
                            pass
                        else:
                            try:
                                w.yview_scroll(delta, "units")
                            except Exception:
                                pass
                            return "break"
                w = getattr(w, "master", None)
        except Exception:
            pass
        try:
            y0, y1 = self.vcanvas.yview()
            if delta < 0 and y0 <= 0.0:
                return "break"
            if delta > 0 and y1 >= 1.0:
                return "break"
            self.vcanvas.yview_scroll(delta, "units")
            return "break"
        except Exception:
            return

    def _drag_v_start(self, e):
        try:
            cx = self.vcanvas.canvasx(self.vcanvas.winfo_pointerx() - self.vcanvas.winfo_rootx())
            cy = self.vcanvas.canvasy(self.vcanvas.winfo_pointery() - self.vcanvas.winfo_rooty())
            self.vcanvas.scan_mark(int(cx), int(cy))
        except Exception:
            pass

    def _drag_v_move(self, e):
        try:
            cx = self.vcanvas.canvasx(self.vcanvas.winfo_pointerx() - self.vcanvas.winfo_rootx())
            cy = self.vcanvas.canvasy(self.vcanvas.winfo_pointery() - self.vcanvas.winfo_rooty())
            self.vcanvas.scan_dragto(int(cx), int(cy), gain=1)
        except Exception:
            pass

    def _x_positions(self, n, w, left_pad, right_pad):
        if n <= 1:
            return [left_pad + (w - left_pad - right_pad)/2]
        plot_w = w - left_pad - right_pad
        return [left_pad + plot_w * (i/(n-1)) for i in range(n)]

    def _scrollx(self, *args):
        try:
            self.canvas_bars.xview(*args)
            self.canvas_trend.xview(*args)
        except Exception:
            pass

    def _on_scrollx(self, lo, hi):
        try:
            self.scrollx.set(lo, hi)
        except Exception:
            pass

    def _on_chart_configure(self, kind):
        try:
            wlist = [
                int(self.canvas_bars.winfo_width() or 0),
                int(self.canvas_trend.winfo_width() or 0),
                int(self.canvas_pie_income.winfo_width() or 0),
                int(self.canvas_pie_expense.winfo_width() or 0),
            ]
            if max(wlist) < 50:
                return
            self._schedule_recompute()
        except Exception:
            pass

    def _schedule_recompute(self):
        try:
            if getattr(self, "_recomp_id", None):
                self.after_cancel(self._recomp_id)
            self._recomp_id = self.after(80, self._recompute_after_resize)
        except Exception:
            pass

    def _recompute_after_resize(self):
        try:
            self._recomp_id = None
            self.compute_and_render()
        except Exception:
            pass

    def _ensure_first_layout(self):
        try:
            ws = [
                int(self.canvas_bars.winfo_width() or 0),
                int(self.canvas_trend.winfo_width() or 0),
                int(self.canvas_pie_income.winfo_width() or 0),
                int(self.canvas_pie_expense.winfo_width() or 0),
            ]
            if max(ws) < 50:
                self.after(120, self._ensure_first_layout)
                return
            self.compute_and_render()
        except Exception:
            pass

    def refresh(self):
        self.fill_periods()
        try:
            s = load_state()
            last = (s.get("prefs", {}) or {}).get("dashboard", {})
            lm = last.get("last_mode")
            lp = last.get("last_period")
            if lm in ("日度","月份","年份"):
                self.mode.set(lm)
            if lp:
                self.period.set(lp)
        except Exception:
            pass
        if not self.period.get():
            self.current_period()
        self.show_right_module()
        self.fill_periods()
        self.update_controls_visibility()
        self.compute_and_render()

    def on_mode_change(self):
        self.show_right_module()
        self.fill_periods()
        self.current_period()
        self.update_controls_visibility()
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {})
            dash = prefs.setdefault("dashboard", {})
            dash["last_mode"] = self.mode.get()
            dash["last_period"] = self.period.get()
            save_state(s)
        except Exception:
            pass

    def fill_periods(self):
        s = load_state()
        vals = set()
        if self.mode.get() == "日度":
            for t in s.get("transactions", []):
                dt = parse_datetime(t.get("time",""))
                vals.add(dt.strftime("%Y-%m"))
            if not vals:
                dt = datetime.now()
                vals = {dt.strftime("%Y-%m")}
        elif self.mode.get() == "月份":
            for t in s.get("transactions", []):
                dt = parse_datetime(t.get("time",""))
                vals.add(dt.strftime("%Y"))
            if not vals:
                vals = {datetime.now().strftime("%Y")}
        else:
            years = set()
            for t in s.get("transactions", []):
                dt = parse_datetime(t.get("time",""))
                years.add(dt.strftime("%Y"))
            if not years:
                years = {datetime.now().strftime("%Y")}
            vals = years
        self.cb_period["values"] = sorted(vals)
        self.update_controls_visibility()

    def update_controls_visibility(self):
        if self.mode.get() == "年份":
            try:
                self.cb_period.pack_forget()
                self.btn_prev.pack_forget()
                self.btn_curr.pack_forget()
                self.btn_next.pack_forget()
            except Exception:
                pass
        else:
            try:
                if not self.cb_period.winfo_ismapped():
                    self.cb_period.pack(side=tk.LEFT, padx=8)
                if not self.btn_prev.winfo_ismapped():
                    self.btn_prev.pack(side=tk.LEFT, padx=4)
                if not self.btn_curr.winfo_ismapped():
                    self.btn_curr.pack(side=tk.LEFT, padx=4)
                if not self.btn_next.winfo_ismapped():
                    self.btn_next.pack(side=tk.LEFT, padx=4)
            except Exception:
                pass

    def period_range(self):
        val = self.period.get()
        if self.mode.get() == "日度":
            dt = datetime.strptime(val+"-01", "%Y-%m-%d")
            start = dt
            if dt.month == 12:
                end = datetime(dt.year+1, 1, 1)
            else:
                end = datetime(dt.year, dt.month+1, 1)
            return start, end
        elif self.mode.get() == "月份":
            dt = datetime.strptime(val+"-01-01", "%Y-%m-%d")
            start = dt
            end = datetime(dt.year+1, 1, 1)
            return start, end
        else:
            s = load_state()
            years = []
            for t in s.get("transactions", []):
                dt = parse_datetime(t.get("time",""))
                years.append(dt.year)
            if not years:
                y = int(datetime.now().strftime("%Y"))
                return datetime(y,1,1), datetime(y+1,1,1)
            y0 = min(years)
            y1 = max(years)
            return datetime(y0,1,1), datetime(y1+1,1,1)

    def prev_period(self):
        val = self.period.get()
        if not val:
            return
        if self.mode.get() == "日度":
            y, m = map(int, val.split("-"))
            m -= 1
            if m == 0:
                y -= 1
                m = 12
            self.period.set(f"{y:04d}-{m:02d}")
        elif self.mode.get() == "月份":
            y = int(val) - 1
            self.period.set(str(y))
        else:
            return
        self.compute_and_render()
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {})
            dash = prefs.setdefault("dashboard", {})
            dash["last_period"] = self.period.get()
            dash["last_mode"] = self.mode.get()
            save_state(s)
        except Exception:
            pass

    def next_period(self):
        val = self.period.get()
        if not val:
            return
        if self.mode.get() == "日度":
            y, m = map(int, val.split("-"))
            m += 1
            if m == 13:
                y += 1
                m = 1
            self.period.set(f"{y:04d}-{m:02d}")
        elif self.mode.get() == "月份":
            y = int(val) + 1
            self.period.set(str(y))
        else:
            return
        self.compute_and_render()
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {})
            dash = prefs.setdefault("dashboard", {})
            dash["last_period"] = self.period.get()
            dash["last_mode"] = self.mode.get()
            save_state(s)
        except Exception:
            pass

    def current_period(self):
        if self.mode.get() == "日度":
            self.period.set(datetime.now().strftime("%Y-%m"))
        elif self.mode.get() == "月份":
            self.period.set(datetime.now().strftime("%Y"))
        else:
            self.period.set(datetime.now().strftime("%Y"))
        self.compute_and_render()
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {})
            dash = prefs.setdefault("dashboard", {})
            dash["last_period"] = self.period.get()
            dash["last_mode"] = self.mode.get()
            save_state(s)
        except Exception:
            pass

    def compute_and_render(self):
        s = load_state()
        start, end = self.period_range()
        txs = []
        for t in s.get("transactions", []):
            dt = parse_datetime(t.get("time",""))
            if start <= dt < end:
                txs.append(t)
        self._current_txs = txs
        inc = 0.0
        exp = 0.0
        for t in txs:
            typ = normalize_ttype(t.get("ttype"))
            amt = float(t.get("amount",0))
            if typ in ["收入","报销类收入"]:
                inc += amt
            elif typ in ["支出","报销类支出"]:
                exp += amt
        net = inc - exp
        assets = sum(float(a.get("balance",0)) for a in s.get("accounts", []))
        change = net
        self.k_income.configure(text=f"总收入: {format_amount(inc)}")
        self.k_expense.configure(text=f"总支出: {format_amount(exp)}")
        self.k_net.configure(text=f"净现金流: {format_amount(net)}")
        self.k_assets.configure(text=f"期末总资产: {format_amount(assets)}")
        self.k_change.configure(text=f"资产变动: {format_amount(change)}")

        self.render_dual_bars(self.canvas_bars, txs)
        self.render_trend(self.canvas_trend, txs)
        self.render_category_pies(txs)
        self.render_accounts(self.tree_accounts, s, txs)
        self.render_recent(self.tree_recent, txs)
        if getattr(self, "right_module", None):
            try:
                self.right_module.refresh(self.period.get(), txs)
            except Exception:
                pass

    def render_dual_bars(self, canvas, txs):
        canvas.delete("all")
        if hasattr(self, "canvas_bars_axis"):
            try:
                self.canvas_bars_axis.delete("all")
            except Exception:
                pass
        w = int(canvas.winfo_width() or 800)
        h = int(canvas.winfo_height() or 240)
        canvas.create_text(12, 16, text="收入/支出柱状图", anchor="w")
        start, end = self.period_range()
        buckets = []
        if self.mode.get() == "日度":
            days = (end - start).days
            for i in range(days):
                d0 = start + timedelta(days=i)
                d1 = d0 + timedelta(days=1)
                inc = 0.0
                exp = 0.0
                for t in txs:
                    dt = parse_datetime(t.get("time",""))
                    if d0 <= dt < d1:
                        typ = normalize_ttype(t.get("ttype"))
                        amt = float(t.get("amount",0))
                        if typ in ["收入","报销类收入"]:
                            inc += amt
                        elif typ in ["支出","报销类支出"]:
                            exp += amt
                buckets.append((f"{d0.day}日", inc, exp))
        elif self.mode.get() == "月份":
            for m in range(1,13):
                inc = 0.0
                exp = 0.0
                for t in txs:
                    dt = parse_datetime(t.get("time",""))
                    if dt.month == m:
                        typ = normalize_ttype(t.get("ttype"))
                        amt = float(t.get("amount",0))
                        if typ in ["收入","报销类收入"]:
                            inc += amt
                        elif typ in ["支出","报销类支出"]:
                            exp += amt
                buckets.append((f"{m}月", inc, exp))
        else:
            years = sorted({parse_datetime(t.get("time","")).year for t in txs})
            for y in years:
                inc = 0.0
                exp = 0.0
                for t in txs:
                    dt = parse_datetime(t.get("time",""))
                    if dt.year == y:
                        typ = normalize_ttype(t.get("ttype"))
                        amt = float(t.get("amount",0))
                        if typ in ["收入","报销类收入"]:
                            inc += amt
                        elif typ in ["支出","报销类支出"]:
                            exp += amt
                buckets.append((f"{y}年", inc, exp))
        if not buckets:
            canvas.create_text(w//2, h//2, text="暂无数据")
            return
        maxv_raw = max(max(inc, exp) for _, inc, exp in buckets) or 1.0
        import math
        tick_count = 4
        step = max(1, math.ceil(maxv_raw / tick_count))
        maxv = step * tick_count
        left_pad = 36
        right_pad = 24
        bottom_pad = 36
        bar_w = 18
        gap_in_pair = 6
        pair_gap = 16
        group_w = bar_w*2 + gap_in_pair
        req_total = left_pad + (group_w + pair_gap) * max(0, len(buckets)-1) + group_w + right_pad
        total_width = max(req_total, w)
        self._plot_total_width = total_width
        canvas.configure(scrollregion=(0,0,total_width,h))
        plot_h = h - bottom_pad - 48
        if hasattr(self, "canvas_bars_axis"):
            ax = self.canvas_bars_axis
            aw = int(ax.winfo_width() or 72)
            ax.create_line(aw-1, h-bottom_pad, aw-1, h-bottom_pad-plot_h, fill="#666666")
            for i in range(tick_count+1):
                v = step * i
                yy = h - bottom_pad - int(plot_h * (v/maxv))
                ax.create_line(aw-5, yy, aw-1, yy, fill="#666666")
                ax.create_text(aw-8, yy, text=str(int(v)), anchor="e", fill="#333333")
        canvas.create_text(w-120, 16, text="绿:收入 红:支出", anchor="w", fill="#333333")
        self._bar_items = []
        xs = self._x_positions(len(buckets), total_width, left_pad, right_pad)
        self._bar_xs = xs
        self._bar_label_ids = {}
        for idx, (label, inc, exp) in enumerate(buckets):
            xc = xs[idx]
            left = xc - group_w/2
            ih = int(plot_h * (inc/maxv))
            eh = int(plot_h * (exp/maxv))
            r1 = canvas.create_rectangle(left, h-bottom_pad-ih, left+bar_w, h-bottom_pad, fill="#2ecc71", outline="", tags=("bar_inc",))
            r2 = canvas.create_rectangle(left+bar_w+gap_in_pair, h-bottom_pad-eh, left+bar_w*2+gap_in_pair, h-bottom_pad, fill="#ff6b6b", outline="", tags=("bar_exp",))
            if ih > 0:
                canvas.create_text(left+bar_w/2, h-bottom_pad-ih-4, text=f"{inc:.0f}", anchor="s", fill="#2ecc71", font=self._chart_small_font)
            if eh > 0:
                canvas.create_text(left+bar_w+gap_in_pair+bar_w/2, h-bottom_pad-eh-4, text=f"{exp:.0f}", anchor="s", fill="#ff6b6b", font=self._chart_small_font)
            item_base = {"index":idx,"x0":left,"x1":left+bar_w*2+gap_in_pair,"y1":h-bottom_pad,"label":label}
            self._bar_items.append({**item_base, "kind":"inc","x1":left+bar_w, "y0":h-bottom_pad-ih, "value":inc})
            self._bar_items.append({**item_base, "kind":"exp","x0":left+bar_w+gap_in_pair, "y0":h-bottom_pad-eh, "value":exp})
            tid = canvas.create_text(xc, h-bottom_pad+12, text=label, anchor="n", tags=("bars_x_label",))
            self._bar_label_ids[tid] = idx

    def on_bars_motion(self, e):
        c = self.canvas_bars
        x = c.canvasx(e.x)
        y = c.canvasy(e.y)
        hit = None
        for it in getattr(self, "_bar_items", []):
            if it["x0"] <= x <= it["x1"] and it["y0"] <= y <= it["y1"]:
                hit = it
                break
        c.delete("bars_tip")
        if hit:
            t = f"{hit['label']} {'收入' if hit['kind']=='inc' else '支出'}: {format_amount(hit['value'])}"
            c.create_text(x+10, y-10, text=t, anchor="w", fill="#000000", tags=("bars_tip",))

    def on_bars_click(self, e):
        x = self.canvas_bars.canvasx(e.x)
        y = self.canvas_bars.canvasy(e.y)
        hit = None
        for it in getattr(self, "_bar_items", []):
            if it["x0"] <= x <= it["x1"] and it["y0"] <= y <= it["y1"]:
                hit = it
                break
        if not hit:
            return
        start, end = self.period_range()
        if self.mode.get() == "日度":
            d0 = start + timedelta(days=hit["index"]) 
            day_str = d0.strftime('%Y-%m-%d')
            month_str = start.strftime('%Y-%m')
            ttype = "收入" if hit["kind"] == "inc" else "支出"
            BillListDialog(self.view, initial_filters={"month": month_str, "day": day_str, "ttype": ttype})
        elif self.mode.get() == "月份":
            m = hit["index"] + 1
            year = self.period.get().strip()
            month_str = f"{year}-{m:02d}"
            ttype = "收入" if hit["kind"] == "inc" else "支出"
            BillListDialog(self.view, initial_filters={"month": month_str, "ttype": ttype})
        else:
            years = sorted({parse_datetime(t.get("time","")).year for t in getattr(self, "_current_txs", [])})
            y = years[hit["index"]] if years else int(datetime.now().strftime("%Y"))
            s = f"{y}-01-01"
            e = f"{y}-12-31"
            ttype = "收入" if hit["kind"] == "inc" else "支出"
            BillListDialog(self.view, initial_filters={"date_range": (s, e), "ttype": ttype})

    def on_bars_right_click(self, e):
        x = self.canvas_bars.canvasx(e.x)
        y = self.canvas_bars.canvasy(e.y)
        hit = None
        for it in getattr(self, "_bar_items", []):
            if it["x0"] <= x <= it["x1"] and it["y0"] <= y <= it["y1"]:
                hit = it
                break
        m = tk.Menu(self, tearoff=0)
        added = False
        if self.mode.get() == "日度" and hit:
            start, _ = self.period_range()
            d0 = start + timedelta(days=hit["index"])
            y2, m2, d2 = d0.year, d0.month, d0.day
            m.add_command(label="记录当日账单", command=lambda: self._record_for_day(y2, m2, d2))
            added = True
        elif self.mode.get() == "日度":
            try:
                near = self.canvas_bars.find_closest(e.x, e.y)
            except Exception:
                near = None
            if near:
                i = near[0]
                tags = self.canvas_bars.gettags(i)
                if tags and "bars_x_label" in tags:
                    idx = getattr(self, "_bar_label_ids", {}).get(i)
                    if idx is not None:
                        start, _ = self.period_range()
                        d0 = start + timedelta(days=idx)
                        y2, m2, d2 = d0.year, d0.month, d0.day
                        m.add_command(label="记录当日账单", command=lambda: self._record_for_day(y2, m2, d2))
                        added = True
        if added:
            m.add_separator()
        
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def render_trend(self, canvas, txs):
        canvas.delete("all")
        if hasattr(self, "canvas_trend_axis"):
            try:
                self.canvas_trend_axis.delete("all")
            except Exception:
                pass
        w = int(canvas.winfo_width() or 800)
        h = int(canvas.winfo_height() or 220)
        canvas.create_text(12, 16, text="现金流趋势", anchor="w")
        start, end = self.period_range()
        points = []
        if self.mode.get() == "日度":
            days = (end - start).days
            for i in range(days):
                d0 = start + timedelta(days=i)
                d1 = d0 + timedelta(days=1)
                s = 0.0
                for t in txs:
                    dt = parse_datetime(t.get("time",""))
                    if d0 <= dt < d1:
                        typ = normalize_ttype(t.get("ttype"))
                        amt = float(t.get("amount",0))
                        if typ in ["收入","报销类收入"]:
                            s += amt
                        elif typ in ["支出","报销类支出"]:
                            s -= amt
                points.append((i, s))
        elif self.mode.get() == "月份":
            for m in range(1,13):
                s = 0.0
                for t in txs:
                    dt = parse_datetime(t.get("time",""))
                    if dt.month == m:
                        typ = normalize_ttype(t.get("ttype"))
                        amt = float(t.get("amount",0))
                        if typ in ["收入","报销类收入"]:
                            s += amt
                        elif typ in ["支出","报销类支出"]:
                            s -= amt
                points.append((m-1, s))
        else:
            years = sorted({parse_datetime(t.get("time","")).year for t in txs})
            for i, y in enumerate(years):
                s = 0.0
                for t in txs:
                    dt = parse_datetime(t.get("time",""))
                    if dt.year == y:
                        typ = normalize_ttype(t.get("ttype"))
                        amt = float(t.get("amount",0))
                        if typ in ["收入","报销类收入"]:
                            s += amt
                        elif typ in ["支出","报销类支出"]:
                            s -= amt
                points.append((i, s))
        if not points:
            canvas.create_text(w//2, h//2, text="暂无数据")
            return
        maxv = max(abs(v) for _, v in points) or 1.0
        left_pad = 36
        right_pad = 24
        top_pad = 48
        bottom_pad = 36
        total_width = getattr(self, "_plot_total_width", 0) or w
        plot_w = total_width - left_pad - right_pad
        plot_h = h - top_pad - bottom_pad
        mid_y = top_pad + plot_h/2
        canvas.create_line(left_pad, mid_y, total_width-right_pad, mid_y, fill="#cccccc")
        tick_count = 4
        import math
        step = max(1, math.ceil(maxv / tick_count))
        maxv = step * tick_count
        ax = getattr(self, "canvas_trend_axis", None)
        if ax:
            aw = int(ax.winfo_width() or 72)
            ax.create_line(aw-1, mid_y, aw-1, top_pad, fill="#666666")
            ax.create_line(aw-1, mid_y, aw-1, h-bottom_pad, fill="#666666")
            for i in range(1, tick_count+1):
                v = step * i
                yy_pos = mid_y - int((plot_h/2) * (v/maxv))
                ax.create_line(aw-5, yy_pos, aw-1, yy_pos, fill="#666666")
                ax.create_text(aw-8, yy_pos, text=str(int(v)), anchor="e", fill="#333333")
                yy_neg = mid_y + int((plot_h/2) * (v/maxv))
                ax.create_line(aw-5, yy_neg, aw-1, yy_neg, fill="#666666")
                ax.create_text(aw-8, yy_neg, text=str(-int(v)), anchor="e", fill="#333333")
        canvas.create_line(left_pad, h-bottom_pad, total_width-right_pad, h-bottom_pad, fill="#666666")
        x_labels = []
        xs = getattr(self, "_bar_xs", self._x_positions(len(points), total_width, left_pad, right_pad))
        self._trend_label_ids = {}
        if self.mode.get() == "日度":
            for i in range(len(points)):
                d0 = start + timedelta(days=i)
                x_labels.append((xs[i], f"{d0.day}日"))
        elif self.mode.get() == "月份":
            for i in range(len(points)):
                x_labels.append((xs[i], f"{i+1}月"))
        else:
            years = sorted({parse_datetime(t.get("time","")).year for t in txs})
            for i in range(len(years)):
                x_labels.append((xs[i], f"{years[i]}年"))
        for i, (x, lbl) in enumerate(x_labels):
            tid = canvas.create_text(x, h-bottom_pad+12, text=lbl, anchor="n", fill="#333333", tags=("trend_x_label",))
            if self.mode.get() == "日度":
                self._trend_label_ids[tid] = i
        prev = None
        n = len(points)
        self._trend_points = []
        try:
            diffs = [abs(xs[i+1]-xs[i]) for i in range(len(xs)-1)]
            avg = sum(diffs)/len(diffs) if diffs else 20
            hr = int(max(6, min(12, avg*0.3)))
            self._trend_hit_r2 = hr*hr
        except Exception:
            self._trend_hit_r2 = 64
        for i, v in points:
            x = xs[i]
            y = mid_y - (plot_h/2) * (v/maxv)
            if prev:
                canvas.create_line(prev[0], prev[1], x, y, fill="#3399ff", width=2)
            canvas.create_oval(x-2, y-2, x+2, y+2, fill="#3399ff", outline="")
            canvas.create_text(x, y-8, text=f"{v:.0f}", anchor="s", fill="#3399ff", font=self._chart_small_font)
            if self.mode.get() == "日度":
                lbl = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            elif self.mode.get() == "月份":
                lbl = f"{i+1:02d}月"
            else:
                years = sorted({parse_datetime(t.get("time","")).year for t in txs})
                lbl = f"{years[i]}年"
            self._trend_points.append({"x":x, "y":y, "value":v, "label":lbl, "index":i})
            prev = (x, y)
        canvas.configure(scrollregion=(0,0,total_width,h))

    def on_trend_motion(self, e):
        c = self.canvas_trend
        x = c.canvasx(e.x)
        y = c.canvasy(e.y)
        hit = None
        best = None
        best_d2 = None
        for it in getattr(self, "_trend_points", []):
            dx = it["x"] - x
            dy = it["y"] - y
            d2 = dx*dx + dy*dy
            if d2 <= getattr(self, "_trend_hit_r2", 64):
                hit = it
                break
            if best_d2 is None or d2 < best_d2:
                best = it
                best_d2 = d2
        c.delete("trend_tip")
        if hit:
            t = f"{hit['label']} 现金流: {format_amount(hit['value'])}"
            c.create_text(x+10, y-10, text=t, anchor="w", fill="#000000", tags=("trend_tip",))
        elif best and best_d2 is not None and best_d2 <= getattr(self, "_trend_hit_r2", 64)*4:
            t = f"{best['label']} 现金流: {format_amount(best['value'])}"
            c.create_text(x+10, y-10, text=t, anchor="w", fill="#000000", tags=("trend_tip",))

    def on_trend_click(self, e):
        x = self.canvas_trend.canvasx(e.x)
        y = self.canvas_trend.canvasy(e.y)
        hit = None
        best = None
        best_d2 = None
        for it in getattr(self, "_trend_points", []):
            dx = it["x"] - x
            dy = it["y"] - y
            d2 = dx*dx + dy*dy
            if d2 <= getattr(self, "_trend_hit_r2", 64):
                hit = it
                break
            if best_d2 is None or d2 < best_d2:
                best = it
                best_d2 = d2
        if not hit:
            if not (best and best_d2 is not None and best_d2 <= getattr(self, "_trend_hit_r2", 64)*4):
                return
            hit = best
        txs = []
        start, end = self.period_range()
        if self.mode.get() == "日度":
            d0 = start + timedelta(days=hit["index"])
            d1 = d0 + timedelta(days=1)
            for t in getattr(self, "_current_txs", []):
                dt = parse_datetime(t.get("time",""))
                if d0 <= dt < d1:
                    txs.append(t)
            title = f"{d0.strftime('%Y-%m-%d')} 明细"
        elif self.mode.get() == "月份":
            m = hit["index"] + 1
            for t in getattr(self, "_current_txs", []):
                dt = parse_datetime(t.get("time",""))
                if dt.month == m:
                    txs.append(t)
            title = f"{m:02d}月 明细"
        if self.mode.get() == "日度":
            day_str = d0.strftime('%Y-%m-%d')
            BillListDialog(self.view, initial_filters={"month": start.strftime('%Y-%m'), "day": day_str})
        elif self.mode.get() == "月份":
            year = self.period.get().strip()
            BillListDialog(self.view, initial_filters={"month": f"{year}-{m:02d}"})
        else:
            years = sorted({parse_datetime(t.get("time","")).year for t in getattr(self, "_current_txs", [])})
            y = years[hit["index"]] if years else int(datetime.now().strftime("%Y"))
            s = f"{y}-01-01"
            e = f"{y}-12-31"
            BillListDialog(self.view, initial_filters={"date_range": (s, e)})

    def on_trend_right_click(self, e):
        x = self.canvas_trend.canvasx(e.x)
        y = self.canvas_trend.canvasy(e.y)
        hit = None
        best = None
        best_d2 = None
        for it in getattr(self, "_trend_points", []):
            dx = it["x"] - x
            dy = it["y"] - y
            d2 = dx*dx + dy*dy
            if d2 <= getattr(self, "_trend_hit_r2", 64):
                hit = it
                break
            if best_d2 is None or d2 < best_d2:
                best = it
                best_d2 = d2
        if not hit:
            if not (best and best_d2 is not None and best_d2 <= getattr(self, "_trend_hit_r2", 64)*4):
                hit = None
            else:
                hit = best
        m = tk.Menu(self, tearoff=0)
        added = False
        if self.mode.get() == "日度" and hit:
            start, _ = self.period_range()
            d0 = start + timedelta(days=hit["index"])
            y2, m2, d2 = d0.year, d0.month, d0.day
            m.add_command(label="记录当日账单", command=lambda: self._record_for_day(y2, m2, d2))
            added = True
        elif self.mode.get() == "日度":
            try:
                near = self.canvas_trend.find_closest(e.x, e.y)
            except Exception:
                near = None
            if near:
                i = near[0]
                tags = self.canvas_trend.gettags(i)
                if tags and "trend_x_label" in tags:
                    idx = getattr(self, "_trend_label_ids", {}).get(i)
                    if idx is not None:
                        start, _ = self.period_range()
                        d0 = start + timedelta(days=idx)
                        y2, m2, d2 = d0.year, d0.month, d0.day
                        m.add_command(label="记录当日账单", command=lambda: self._record_for_day(y2, m2, d2))
                        added = True
        if added:
            m.add_separator()
        
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _record_for_day(self, y, m, d):
        try:
            s = load_state()
            accounts = get_account_names(s)
            initial = {"time": f"{y:04d}-{m:02d}-{d:02d}T12:00:00", "ttype": "支出"}
            dlg = AddTransactionDialog(self, accounts, initial=initial)
            self.wait_window(dlg)
            if getattr(dlg, "result", None):
                new = dict(dlg.result)
                new["id"] = gen_id()
                try:
                    cat = (new.get("category") or "").strip()
                    typ = normalize_ttype(new.get("ttype"))
                    if cat and typ in ["收入","报销类收入","支出","报销类支出"]:
                        add_category(s, "收入" if typ in ["收入","报销类收入"] else "支出", cat)
                except Exception:
                    pass
                try:
                    new["record_time"] = datetime.now().isoformat()
                    new["record_source"] = "首页右键"
                except Exception:
                    pass
                try:
                    apply_transaction_delta(s, new, 1)
                except Exception:
                    pass
                try:
                    s.setdefault("transactions", []).append(new)
                except Exception:
                    pass
                try:
                    save_state(s)
                except Exception:
                    pass
                try:
                    self.compute_and_render()
                except Exception:
                    pass
        except Exception:
            pass

    def render_category_pies(self, txs):
        incs = defaultdict(float)
        exps = defaultdict(float)
        for t in txs:
            typ = normalize_ttype(t.get("ttype"))
            amt = float(t.get("amount",0))
            cat = t.get("category","") or "未分类"
            if typ in ["收入","报销类收入"]:
                incs[cat] += amt
            elif typ in ["支出","报销类支出"]:
                exps[cat] += amt
        self._render_pie(self.canvas_pie_income, incs, "收入类别占比", kind="income")
        self._render_pie(self.canvas_pie_expense, exps, "支出类别占比", kind="expense")

    def _render_pie(self, canvas, data_map, title, kind="income"):
        canvas.delete("all")
        w = int(canvas.winfo_width() or 800)
        h = int(canvas.winfo_height() or 240)
        title_id = canvas.create_text(12, 16, text=title, anchor="w", tags=("pie_title",))
        items = [(k, v) for k, v in data_map.items() if v > 0]
        items.sort(key=lambda x: x[1], reverse=True)
        if len(items) > 8:
            top = items[:8]
            other_sum = sum(v for _, v in items[8:])
            if other_sum > 0:
                top.append(("其他", other_sum))
            items = top
        total = sum(v for _, v in items) or 1.0
        cx = w//2
        cy = h//2 + 10
        if w < 80 or h < 80:
            canvas.create_text(w//2, h//2, text="暂无数据")
            return
        r = max(20, int(min(w-40, h-60)/2))
        bbox = (cx-r, cy-r, cx+r, cy+r)
        palette_inc = ["#2ecc71","#27ae60","#1abc9c","#16a085","#2ca877","#6bd490","#8bd8bd","#4cd3b5","#7fdc8b"]
        palette_exp = ["#ff6b6b","#e74c3c","#c0392b","#ff7675","#f06292","#ff8a65","#f4a261","#e9c46a","#f28b82"]
        palette = palette_inc if kind=="income" else palette_exp
        start = 0.0
        id_map = {}
        for i, (name, val) in enumerate(items):
            extent = 360.0 * (val/total)
            color = palette[i % len(palette)]
            arc = canvas.create_arc(bbox, start=start, extent=extent, fill=color, outline="white", width=1, style=tk.PIESLICE, tags=("pie_slice",))
            mid = start + extent/2
            rad = math.radians(mid)
            lx = cx + int((r+18) * math.cos(rad))
            ly = cy - int((r+18) * math.sin(rad))
            pct = val/total*100
            canvas.create_text(lx, ly, text=f"{name} {pct:.0f}%", anchor="center", fill="#333333")
            id_map[arc] = {"name":name, "value":val, "pct":pct, "kind":kind}
            start += extent
        if kind=="income":
            self._pie_income_ids = id_map
            self._pie_income_title_id = title_id
        else:
            self._pie_expense_ids = id_map
            self._pie_expense_title_id = title_id

    def on_pie_income_motion(self, e):
        self._on_pie_motion(self.canvas_pie_income, getattr(self, "_pie_income_ids", {}), e.x, e.y)

    def on_pie_expense_motion(self, e):
        self._on_pie_motion(self.canvas_pie_expense, getattr(self, "_pie_expense_ids", {}), e.x, e.y)

    def _on_pie_motion(self, canvas, id_map, x, y):
        canvas.delete("pie_tip")
        item = None
        near = canvas.find_closest(x, y)
        if near:
            i = near[0]
            if i in id_map:
                item = id_map[i]
        if item:
            t = f"{item['name']} 金额: {format_amount(item['value'])} 占比: {item['pct']:.1f}%"
            canvas.create_text(x+10, y-10, text=t, anchor="w", fill="#000000", tags=("pie_tip",))

    def on_pie_income_click(self, e):
        near = self.canvas_pie_income.find_closest(e.x, e.y)
        if near:
            i = near[0]
            tags = self.canvas_pie_income.gettags(i)
            if "pie_title" in tags:
                self.open_income_pie_big()
                return
        self._on_pie_click(self.canvas_pie_income, getattr(self, "_pie_income_ids", {}), e.x, e.y)

    def on_pie_expense_click(self, e):
        near = self.canvas_pie_expense.find_closest(e.x, e.y)
        if near:
            i = near[0]
            tags = self.canvas_pie_expense.gettags(i)
            if "pie_title" in tags:
                self.open_expense_pie_big()
                return
        self._on_pie_click(self.canvas_pie_expense, getattr(self, "_pie_expense_ids", {}), e.x, e.y)

    def _on_pie_click(self, canvas, id_map, x, y):
        near = canvas.find_closest(x, y)
        if not near:
            return
        info = id_map.get(near[0])
        if not info:
            return
        name = info.get("name")
        kind = info.get("kind")
        ttype = "收入" if kind == "income" else "支出"
        start, end = self.period_range()
        if self.mode.get() == "日度":
            month_str = start.strftime('%Y-%m')
            BillListDialog(self.view, initial_filters={"month": month_str, "ttype": ttype, "category": name})
        elif self.mode.get() == "月份":
            s = start.strftime('%Y-%m-%d')
            e = (end - timedelta(days=1)).strftime('%Y-%m-%d')
            BillListDialog(self.view, initial_filters={"date_range": (s, e), "ttype": ttype, "category": name})
        else:
            s = start.strftime('%Y-%m-%d')
            e = (end - timedelta(days=1)).strftime('%Y-%m-%d')
            BillListDialog(self.view, initial_filters={"date_range": (s, e), "ttype": ttype, "category": name})

    def open_expense_pie_big(self):
        txs = getattr(self, "_current_txs", [])
        ExpensePieBigDialog(self, txs)

    def open_income_pie_big(self):
        txs = getattr(self, "_current_txs", [])
        IncomePieBigDialog(self, txs)


    def show_tx_popup(self, title, txs):
        win = tk.Toplevel(self)
        win.title(title)
        win.grab_set()
        top = ttk.Frame(win)
        top.pack(fill=tk.X, padx=12, pady=8)
        total = sum(float(t.get("amount",0)) if normalize_ttype(t.get("ttype")) in ["收入","报销类收入"] else -float(t.get("amount",0)) for t in txs)
        ttk.Label(top, text=f"条目: {len(txs)}    净值: {format_amount(total)}").pack(side=tk.LEFT)
        cols = ["交易时间","金额","消费类别","所属类别","账户","备注","id"]
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=120 if c not in ["备注","id"] else (220 if c=="备注" else 140))
        tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        def add_rows():
            tree.delete(*tree.get_children())
            for t in sorted(txs, key=lambda x: parse_datetime(x.get("time","")), reverse=True):
                dt = parse_datetime(t.get("time",""))
                tree.insert("", tk.END, values=[
                    dt.strftime("%Y-%m-%d %H:%M"),
                    format_amount(float(t.get("amount",0))),
                    t.get("category",""),
                    t.get("ttype",""),
                    t.get("account",""),
                    t.get("note",""),
                    t.get("id",""),
                ])
        add_rows()
        def on_double(event):
            iid = tree.identify_row(event.y)
            if not iid:
                return
            vals = tree.item(iid, 'values')
            tx_id = vals[-1]
            t = None
            for tt in txs:
                if tt.get("id") == tx_id:
                    t = tt
                    break
            if not t:
                return
            dwin = tk.Toplevel(win)
            dwin.title("记录详情")
            grid = ttk.Frame(dwin)
            grid.pack(padx=12, pady=12)
            items = [
                ("交易时间", parse_datetime(t.get("time","")).strftime("%Y-%m-%d %H:%M")),
                ("金额", format_amount(float(t.get("amount",0)))),
                ("消费类别", t.get("category","")),
                ("所属类别", t.get("ttype","")),
                ("账户", t.get("account","")),
                ("转入账户", t.get("to_account","")),
                ("转出账户", t.get("from_account","")),
                ("备注", t.get("note","")),
                ("ID", t.get("id","")),
            ]
            for i, (k, v) in enumerate(items):
                ttk.Label(grid, text=k).grid(row=i, column=0, sticky=tk.W, padx=4, pady=2)
                ttk.Label(grid, text=str(v)).grid(row=i, column=1, sticky=tk.W, padx=4, pady=2)
            ttk.Button(dwin, text="关闭", command=dwin.destroy).pack(pady=8)
        tree.bind("<Double-1>", on_double)
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=8)

    def render_accounts(self, tree, state, txs):
        tree.delete(*tree.get_children())
        flows = defaultdict(float)
        for t in txs:
            typ = normalize_ttype(t.get("ttype"))
            amt = float(t.get("amount",0))
            acc = t.get("account","")
            if typ in ["收入","报销类收入"] and acc:
                flows[acc] += amt
            elif typ in ["支出","报销类支出"] and acc:
                flows[acc] -= amt
        items = []
        for a in state.get("accounts", []):
            name = a.get("name")
            bal = float(a.get("balance",0))
            flow = flows.get(name, 0.0)
            items.append((name, bal, flow))
        items.sort(key=lambda x: x[1], reverse=True)
        for name, bal, flow in items:
            tree.insert("", tk.END, values=[name, format_amount(bal), format_amount(flow)])

    def render_recent(self, tree, txs):
        tree.delete(*tree.get_children())
        txs2 = sorted(txs, key=lambda t: parse_datetime(t.get("time","")), reverse=True)[:20]
        for t in txs2:
            dt = parse_datetime(t.get("time",""))
            tree.insert("", tk.END, values=[dt.strftime("%Y-%m-%d"), t.get("category",""), format_amount(float(t.get("amount",0))), t.get("account",""), t.get("note","")])

    def show_right_module(self):
        for w in self.right_panel.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.right_module = None
        if self.mode.get() == "日度":
            m = DailyModule(self.right_panel, self.period.get, self._set_period_and_refresh)
            m.pack(fill=tk.BOTH, expand=True)
            self.right_module = m
        elif self.mode.get() == "月份":
            m = MonthlyModule(self.right_panel, self.period.get, self._set_period_and_refresh)
            m.pack(fill=tk.BOTH, expand=True)
            self.right_module = m
        elif self.mode.get() == "年份":
            m = YearlyModule(self.right_panel, self.period.get, self._set_period_and_refresh)
            m.pack(fill=tk.BOTH, expand=True)
            self.right_module = m

    def _set_period_and_refresh(self, val):
        try:
            self.period.set(val)
            self.compute_and_render()
        except Exception:
            pass

    

    def _apply_saved_sash(self):
        try:
            s = load_state()
            pos = int(s.get("prefs", {}).get("dashboard", {}).get("sash_pos", 0))
            if pos > 0:
                self.paned.sashpos(0, pos)
        except Exception:
            pass

    def _on_sash_release(self, e):
        try:
            pos = int(self.paned.sashpos(0))
            if getattr(self, "_last_sash_pos", None) == pos:
                return
            self._last_sash_pos = pos
            s = load_state()
            prefs = s.setdefault("prefs", {})
            dash = prefs.setdefault("dashboard", {})
            dash["sash_pos"] = pos
            save_state(s)
        except Exception:
            pass

class DailyModule(ttk.Frame):
    def __init__(self, master, get_period_cb, set_period_cb):
        super().__init__(master)
        self.get_period_cb = get_period_cb
        self.set_period_cb = set_period_cb
        self.year_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.header = ttk.Frame(self)
        self.header.pack(fill=tk.X, padx=8, pady=8)
        self.title_lbl = ttk.Label(self.header, text="", font=("Microsoft YaHei", 12))
        self.title_lbl.pack(side=tk.TOP)
        ctrl = ttk.Frame(self.header)
        ctrl.pack(fill=tk.X, pady=4)
        self.cb_year = ttk.Combobox(ctrl, state="readonly", textvariable=self.year_var, width=6)
        self.cb_year.pack(side=tk.LEFT)
        self.cb_year.bind("<<ComboboxSelected>>", lambda e: self._on_combo_change())
        self.cb_month = ttk.Combobox(ctrl, state="readonly", textvariable=self.month_var, width=4)
        self.cb_month.pack(side=tk.LEFT, padx=4)
        self.cb_month.bind("<<ComboboxSelected>>", lambda e: self._on_combo_change())
        ttk.Button(ctrl, text="◀", width=3, command=self._prev_month).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="▶", width=3, command=self._next_month).pack(side=tk.LEFT, padx=4)
        self.calendar_frame = ttk.Frame(self)
        self.calendar_frame.pack(fill=tk.X, padx=8, pady=8)
        self.detail_frame = ttk.Frame(self)
        self.detail_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        tools = ttk.Frame(self.detail_frame)
        tools.pack(fill=tk.X)
        ttk.Button(tools, text="列管理", command=self._open_cols).pack(side=tk.RIGHT)
        self.list_view = DashboardListView(self.detail_frame)
        self.list_view.pack(fill=tk.BOTH, expand=True)

    def refresh(self, period_val, txs):
        try:
            y, m = map(int, period_val.split("-"))
        except Exception:
            now = datetime.now()
            y, m = now.year, now.month
        self.title_lbl.configure(text=f"{y:04d}年{m:02d}月")
        s = load_state()
        years = sorted({parse_datetime(t.get("time","")).year for t in s.get("transactions", [])}) or [y]
        self.cb_year["values"] = [str(yy) for yy in years]
        self.cb_month["values"] = [f"{mm:02d}" for mm in range(1,13)]
        self.year_var.set(str(y))
        self.month_var.set(f"{m:02d}")
        self._render_calendar(y, m, txs)
        self._render_list(y, m, txs)

    def _on_combo_change(self):
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            self.set_period_cb(f"{y:04d}-{m:02d}")
        except Exception:
            pass

    def _prev_month(self):
        try:
            y = int(self.year_var.get())
            m = int(self.month_var.get())
            m -= 1
            if m == 0:
                y -= 1
                m = 12
            self.set_period_cb(f"{y:04d}-{m:02d}")
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
            self.set_period_cb(f"{y:04d}-{m:02d}")
        except Exception:
            pass

    def _render_calendar(self, y, m, txs):
        for w in self.calendar_frame.winfo_children():
            w.destroy()
        head = ttk.Frame(self.calendar_frame)
        head.pack(fill=tk.X)
        for i in range(7):
            head.grid_columnconfigure(i, weight=1, uniform="weekday")
        for i, name in enumerate(["周一","周二","周三","周四","周五","周六","周日"]):
            ttk.Label(head, text=name, anchor="center").grid(row=0, column=i, padx=4, pady=4, sticky="nsew")
        grid = ttk.Frame(self.calendar_frame)
        grid.pack(fill=tk.X)
        for i in range(7):
            grid.grid_columnconfigure(i, weight=1, uniform="day")
        first_weekday, days_in_month = calendar.monthrange(y, m)
        def day_summary(d):
            inc = 0.0
            exp = 0.0
            for t in txs:
                dt = parse_datetime(t.get("time",""))
                if dt.year == y and dt.month == m and dt.day == d:
                    typ = normalize_ttype(t.get("ttype"))
                    amt = float(t.get("amount",0))
                    if typ in ["收入","报销类收入"]:
                        inc += amt
                    elif typ in ["支出","报销类支出"]:
                        exp += amt
            return inc, exp
        row = 0
        col = (first_weekday + 6) % 7
        total_slots = col + days_in_month
        row_count = (total_slots + 6) // 7
        for r in range(row_count):
            grid.grid_rowconfigure(r, weight=1)
        for d in range(1, days_in_month+1):
            f = ttk.Frame(grid)
            f.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            ttk.Label(f, text=str(d), anchor="center", font=("Microsoft YaHei", 12)).pack()
            inc, exp = day_summary(d)
            if exp > 0:
                ttk.Label(f, text=f"-{int(round(exp))}", foreground="#FF0000", anchor="center", font=("Microsoft YaHei", 8)).pack()
            else:
                ttk.Label(f, text="").pack()
            if inc > 0:
                ttk.Label(f, text=f"+{int(round(inc))}", foreground="#00FF00", anchor="center", font=("Microsoft YaHei", 8)).pack()
            else:
                ttk.Label(f, text="").pack()
            try:
                f.bind("<Button-3>", lambda e, yy=y, mm=m, dd=d: self._on_day_right_click(e, yy, mm, dd))
                for ch in f.winfo_children():
                    ch.bind("<Button-3>", lambda e, yy=y, mm=m, dd=d: self._on_day_right_click(e, yy, mm, dd))
            except Exception:
                pass
            col += 1
            if col == 7:
                col = 0
                row += 1

    def _render_list(self, y, m, txs):
        rows = []
        try:
            mk = f"{y:04d}-{m:02d}"
            q = query_transactions({"month": mk, "order_col": "time", "order_desc": True})
            for t in q:
                dt = parse_datetime(t.get("time",""))
                rtime = t.get("record_time")
                try:
                    rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M") if rtime else ""
                except Exception:
                    rtime_str = str(rtime) if rtime else ""
                rows.append([
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
                    t.get("id",""),
                ])
        except Exception:
            for t in txs:
                dt = parse_datetime(t.get("time",""))
                if dt.year == y and dt.month == m:
                    rtime = t.get("record_time")
                    rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M") if rtime else ""
                    rows.append([
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
                        t.get("id",""),
                    ])
        self.list_view.set_rows(rows)

    def _open_cols(self):
        self.list_view.open_columns_manager()

    def _on_day_right_click(self, e, y, m, d):
        mnu = tk.Menu(self, tearoff=0)
        mnu.add_command(label="记录当日账单", command=lambda: self._record_for_day(y, m, d))
        try:
            mnu.tk_popup(e.x_root, e.y_root)
        finally:
            mnu.grab_release()

    def _record_for_day(self, y, m, d):
        try:
            s = load_state()
            accounts = get_account_names(s)
            initial = {"time": f"{y:04d}-{m:02d}-{d:02d}T12:00:00", "ttype": "支出"}
            dlg = AddTransactionDialog(self, accounts, initial=initial)
            self.wait_window(dlg)
            if getattr(dlg, "result", None):
                new = dict(dlg.result)
                new["id"] = gen_id()
                try:
                    cat = (new.get("category") or "").strip()
                    typ = normalize_ttype(new.get("ttype"))
                    if cat and typ in ["收入","报销类收入","支出","报销类支出"]:
                        add_category(s, "收入" if typ in ["收入","报销类收入"] else "支出", cat)
                except Exception:
                    pass
                try:
                    new["record_time"] = datetime.now().isoformat()
                    new["record_source"] = "首页右键"
                except Exception:
                    pass
                try:
                    apply_transaction_delta(s, new, 1)
                except Exception:
                    pass
                try:
                    s.setdefault("transactions", []).append(new)
                except Exception:
                    pass
                try:
                    save_state(s)
                except Exception:
                    pass
                try:
                    self.set_period_cb(f"{y:04d}-{m:02d}")
                except Exception:
                    pass
        except Exception:
            pass

class MonthlyModule(ttk.Frame):
    def __init__(self, master, get_period_cb, set_period_cb):
        super().__init__(master)
        self.get_period_cb = get_period_cb
        self.set_period_cb = set_period_cb
        self.year_var = tk.StringVar()
        self.header = ttk.Frame(self)
        self.header.pack(fill=tk.X, padx=8, pady=8)
        self.title_lbl = ttk.Label(self.header, text="", font=("Microsoft YaHei", 12))
        self.title_lbl.pack(side=tk.LEFT)
        self.grid_frame = ttk.Frame(self)
        self.grid_frame.pack(fill=tk.X, padx=8, pady=8)
        self.detail_frame = ttk.Frame(self)
        self.detail_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.detail_top = ttk.Label(self.detail_frame, text="")
        self.detail_top.pack(anchor=tk.W)
        tools = ttk.Frame(self.detail_frame)
        tools.pack(fill=tk.X)
        ttk.Button(tools, text="列管理", command=self._open_cols).pack(side=tk.RIGHT)
        self.list_view = DashboardListView(self.detail_frame)
        self.list_view.pack(fill=tk.BOTH, expand=True)

    def refresh(self, period_val, txs):
        try:
            y = int(period_val.strip())
        except Exception:
            now = datetime.now()
            y = now.year
        self.title_lbl.configure(text=f"{y:04d}年")
        for w in self.grid_frame.winfo_children():
            w.destroy()
        for i in range(6):
            self.grid_frame.grid_columnconfigure(i, weight=1, uniform="month")
        sums = {}
        months_with_data = []
        for m in range(1,13):
            inc = 0.0
            exp = 0.0
            for t in txs:
                dt = parse_datetime(t.get("time",""))
                if dt.year == y and dt.month == m:
                    typ = normalize_ttype(t.get("ttype"))
                    amt = float(t.get("amount",0))
                    if typ in ["收入","报销类收入"]:
                        inc += amt
                    elif typ in ["支出","报销类支出"]:
                        exp += amt
            sums[m] = (inc, exp)
            if inc > 0 or exp > 0:
                months_with_data.append(m)
        sel_month = max(months_with_data) if months_with_data else None
        for r in range((12 + 5)//6):
            self.grid_frame.grid_rowconfigure(r, weight=1)
        for i in range(12):
            r = i // 6
            c = i % 6
            m = i + 1
            f = ttk.Frame(self.grid_frame, relief="solid", borderwidth=1)
            f.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            ttk.Label(f, text=f"{m}月", font=("Microsoft YaHei", 10, 'bold')).pack()
            inc, exp = sums.get(m, (0.0, 0.0))
            ttk.Label(f, text=str(int(round(exp))), foreground="#FF0000", font=("Microsoft YaHei", 8)).pack()
            ttk.Label(f, text=str(int(round(inc))), foreground="#00FF00", font=("Microsoft YaHei", 8)).pack()
            f.bind("<Button-1>", lambda e, mm=m: self._on_month_click(y, mm, txs))
            for ch in f.winfo_children():
                ch.bind("<Button-1>", lambda e, mm=m: self._on_month_click(y, mm, txs))
        if sel_month:
            self._on_month_click(y, sel_month, txs)
        else:
            self.detail_top.configure(text="无数据")
            self.tree_detail.delete(*self.tree_detail.get_children())

    def _on_month_click(self, y, m, txs):
        month_txs = []
        for t in txs:
            dt = parse_datetime(t.get("time",""))
            if dt.year == y and dt.month == m:
                month_txs.append(t)
        exp_total = 0.0
        for t in month_txs:
            typ = normalize_ttype(t.get("ttype"))
            amt = float(t.get("amount",0))
            if typ in ["支出","报销类支出"]:
                exp_total += amt
        self.detail_top.configure(text=f"支:{format_amount(exp_total)}")
        rows = []
        for t in sorted(month_txs, key=lambda x: parse_datetime(x.get("time","")), reverse=True):
            dt = parse_datetime(t.get("time",""))
            rtime = t.get("record_time")
            rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M") if rtime else ""
            rows.append([
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
                t.get("id",""),
            ])
        self.list_view.set_rows(rows)

    def _open_cols(self):
        self.list_view.open_columns_manager()

class YearlyModule(ttk.Frame):
    def __init__(self, master, get_period_cb, set_period_cb):
        super().__init__(master)
        self.get_period_cb = get_period_cb
        self.set_period_cb = set_period_cb
        self.header = ttk.Frame(self)
        self.header.pack(fill=tk.X, padx=8, pady=8)
        self.title_lbl = ttk.Label(self.header, text="年份", font=("Microsoft YaHei", 12))
        self.title_lbl.pack(side=tk.LEFT)
        self.grid_frame = ttk.Frame(self)
        self.grid_frame.pack(fill=tk.X, padx=8, pady=8)
        self.detail_frame = ttk.Frame(self)
        self.detail_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.detail_top = ttk.Label(self.detail_frame, text="")
        self.detail_top.pack(anchor=tk.W)
        tools = ttk.Frame(self.detail_frame)
        tools.pack(fill=tk.X)
        ttk.Button(tools, text="列管理", command=self._open_cols).pack(side=tk.RIGHT)
        self.list_view = DashboardListView(self.detail_frame)
        self.list_view.pack(fill=tk.BOTH, expand=True)

    def refresh(self, period_val, txs):
        years = sorted({parse_datetime(t.get("time","")).year for t in load_state().get("transactions", [])})
        for w in self.grid_frame.winfo_children():
            w.destroy()
        for i in range(6):
            self.grid_frame.grid_columnconfigure(i, weight=1, uniform="year")
        sums = {}
        years_with_data = []
        for y in years:
            inc = 0.0
            exp = 0.0
            for t in txs:
                dt = parse_datetime(t.get("time",""))
                if dt.year == y:
                    typ = normalize_ttype(t.get("ttype"))
                    amt = float(t.get("amount",0))
                    if typ in ["收入","报销类收入"]:
                        inc += amt
                    elif typ in ["支出","报销类支出"]:
                        exp += amt
            sums[y] = (inc, exp)
            if inc > 0 or exp > 0:
                years_with_data.append(y)
        sel_year = max(years_with_data) if years_with_data else (years[-1] if years else None)
        cols_per_row = 6
        idx = 0
        row_count = (len(years) + cols_per_row - 1) // cols_per_row
        for r in range(row_count):
            self.grid_frame.grid_rowconfigure(r, weight=1)
        for y in years:
            r = idx // cols_per_row
            c = idx % cols_per_row
            idx += 1
            f = ttk.Frame(self.grid_frame, relief="solid", borderwidth=1)
            f.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            ttk.Label(f, text=f"{y}年", font=("Microsoft YaHei", 10, 'bold')).pack()
            inc, exp = sums.get(y, (0.0, 0.0))
            ttk.Label(f, text=str(int(round(exp))), foreground="#FF0000", font=("Microsoft YaHei", 8)).pack()
            ttk.Label(f, text=str(int(round(inc))), foreground="#00FF00", font=("Microsoft YaHei", 8)).pack()
            f.bind("<Button-1>", lambda e, yy=y: self._on_year_click(yy, txs))
            for ch in f.winfo_children():
                ch.bind("<Button-1>", lambda e, yy=y: self._on_year_click(yy, txs))
        if sel_year:
            self._on_year_click(sel_year, txs)
        else:
            self.detail_top.configure(text="无数据")
            self.tree_detail.delete(*self.tree_detail.get_children())

    def _on_year_click(self, y, txs):
        year_txs = []
        for t in txs:
            dt = parse_datetime(t.get("time",""))
            if dt.year == y:
                year_txs.append(t)
        exp_total = 0.0
        for t in year_txs:
            typ = normalize_ttype(t.get("ttype"))
            amt = float(t.get("amount",0))
            if typ in ["支出","报销类支出"]:
                exp_total += amt
        self.detail_top.configure(text=f"支:{format_amount(exp_total)}")
        rows = []
        for t in sorted(year_txs, key=lambda x: parse_datetime(x.get("time","")), reverse=True):
            dt = parse_datetime(t.get("time",""))
            rtime = t.get("record_time")
            rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M") if rtime else ""
            rows.append([
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
                t.get("id",""),
            ])
        self.list_view.set_rows(rows)

    def _open_cols(self):
        self.list_view.open_columns_manager()

class DashboardListView(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.all_columns = [
            "交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注","记账时间","记账来源","id"
        ]
        self.visible_columns = list(self.all_columns)
        try:
            s = load_state()
            saved = (s.get("prefs", {}) or {}).get("dashboard_list", {}).get("visible_columns")
            if isinstance(saved, list) and saved:
                self.visible_columns = [c for c in self.all_columns if c in saved]
        except Exception:
            pass
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(table_frame, columns=self.all_columns, show="headings")
        self.tree["displaycolumns"] = tuple(self.visible_columns)
        self.sort_states = {c: 'asc' for c in self.all_columns}
        self.sort_states["交易时间"] = 'desc'
        self.current_sort_col = "交易时间"
        self.current_sort_desc = True
        for c in self.all_columns:
            self.tree.heading(c, text=f"{c} ▾", command=lambda col=c: self._on_heading_click(col))
            self.tree.column(c, width=(200 if c == "备注" else 140), stretch=False)
        self._apply_saved_widths()
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.vbar.set)
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=self.hbar.set)
        self.hbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<ButtonRelease-1>", self._on_release)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑", command=self._on_edit)
        self.menu.add_command(label="删除", command=self._on_delete)
        self.menu.add_separator()
        self.menu.add_command(label="删除选中", command=self._delete_selected)
        self.menu.add_separator()
        self.menu.add_command(label="批量改为收入", command=self._bulk_change_to_income)
        self.menu.add_command(label="批量改为支出", command=self._bulk_change_to_expense)
        self.menu.add_command(label="批量改为转账", command=self._bulk_change_to_transfer)
        self.menu_batch = tk.Menu(self.menu, tearoff=0)
        self.menu_batch.add_command(label="批量修改账户", command=self._bulk_modify_accounts)
        self.menu_batch.add_command(label="批量修改消费类别", command=self._bulk_modify_category)
        self.menu_batch.add_command(label="批量修改记账来源", command=self._bulk_modify_record_source)
        self.menu.add_cascade(label="批量修改", menu=self.menu_batch)
        self.menu.add_command(label="AI预填消费类别", command=self._ai_prefill_category)

    def set_rows(self, rows):
        self.tree.delete(*self.tree.get_children())
        for vals in rows:
            self.tree.insert("", tk.END, values=vals)
        try:
            if getattr(self, "current_sort_col", None):
                self._sort_by(self.current_sort_col, bool(getattr(self, "current_sort_desc", False)))
        except Exception:
            pass

    def _on_heading_click(self, col):
        dir = self.sort_states.get(col, 'asc')
        new_dir = 'desc' if dir == 'asc' else 'asc'
        self.sort_states[col] = new_dir
        desc = (new_dir == 'desc')
        self.current_sort_col = col
        self.current_sort_desc = desc
        self._sort_by(col, desc)

    def _sort_by(self, col, descending=False):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        def keyfunc(v):
            val = v[0]
            if col in ("交易时间","记账时间"):
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
        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, pady=8)
        def ok():
            chosen = [c for c, v in vars.items() if v.get()]
            self._set_visible_columns(chosen)
            win.destroy()
        ttk.Button(btns, text="确定", command=ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    def _set_visible_columns(self, cols):
        keep = [c for c in self.all_columns if c in cols] or [self.all_columns[0]]
        self.visible_columns = keep
        self.tree["displaycolumns"] = tuple(self.visible_columns)
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {}).setdefault("dashboard_list", {})
            prefs["visible_columns"] = list(self.visible_columns)
            save_state(s)
        except Exception:
            pass
        self._save_column_widths()

    def _apply_saved_widths(self):
        try:
            s = load_state()
            widths = (s.get("prefs", {}) or {}).get("dashboard_list", {}).get("column_widths", {})
            for c in self.all_columns:
                default = 200 if c == "备注" else 140
                w = int(widths.get(c, default))
                self.tree.column(c, width=w, stretch=False)
        except Exception:
            pass

    def _save_column_widths(self):
        try:
            s = load_state()
            prefs = s.setdefault("prefs", {}).setdefault("dashboard_list", {})
            widths = {}
            for c in self.all_columns:
                try:
                    widths[c] = int(self.tree.column(c, 'width'))
                except Exception:
                    pass
            prefs["column_widths"] = widths
            save_state(s)
        except Exception:
            pass

    def _on_release(self, e):
        try:
            self.after(0, self._save_column_widths)
        except Exception:
            pass

    def _on_right_click(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _selected_tx_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], 'values')
        return vals[-1] if vals else None

    def _selected_tx_ids(self):
        ids = []
        for iid in self.tree.selection():
            vals = self.tree.item(iid, 'values')
            if vals:
                ids.append(vals[-1])

        return ids

    def _row_values_from_tx(self, t):
        dt = parse_datetime(t.get("time",""))
        rtime = t.get("record_time")
        try:
            rtime_str = parse_datetime(rtime).strftime("%Y-%m-%d %H:%M") if rtime else ""
        except Exception:
            rtime_str = str(rtime) if rtime else ""
        return [
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
            t.get("id",""),
        ]

    def _on_edit(self):
        tx_id = self._selected_tx_id()
        if not tx_id:
            return
        state = load_state()
        t = get_transaction(state, tx_id)
        dlg = AddTransactionDialog(self, get_account_names(state), initial=t)
        self.wait_window(dlg)
        if getattr(dlg, 'result', None):
            old = get_transaction(state, tx_id)
            apply_transaction_delta(state, old, -1)
            new = dict(old)
            new.update(dlg.result)
            new["id"] = tx_id
            typ = normalize_ttype(new.get("ttype"))
            if typ in ["收入","报销类收入","支出","报销类支出"]:
                sc = "收入" if typ in ["收入","报销类收入"] else "支出"
                cat = (new.get("category") or "").strip()
                if cat:
                    add_category(state, sc, cat)
            update_transaction(state, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
            apply_transaction_delta(state, new, 1)
            save_state(state)
            iid = self.tree.selection()[0]
            self.tree.item(iid, values=self._row_values_from_tx(new))

    def _on_delete(self):
        tx_id = self._selected_tx_id()
        if not tx_id:
            return
        state = load_state()
        t = get_transaction(state, tx_id)
        apply_transaction_delta(state, t, -1)
        remove_transaction(state, tx_id)
        save_state(state)
        for iid in list(self.tree.selection()) or []:
            try:
                self.tree.delete(iid)
            except Exception:
                pass

    def _delete_selected(self):
        ids = self._selected_tx_ids()
        if not ids:
            return
        state = load_state()
        for tx_id in ids:
            t = get_transaction(state, tx_id)
            if t:
                apply_transaction_delta(state, t, -1)
                remove_transaction(state, tx_id)
        save_state(state)
        for iid in list(self.tree.selection()) or []:
            try:
                self.tree.delete(iid)
            except Exception:
                pass

    def _refresh_selection_rows(self, state_obj, ids):
        id_set = set(ids)
        for iid in self.tree.get_children(""):
            vals = self.tree.item(iid, 'values')
            if not vals:
                continue
            if vals[-1] in id_set:
                t = get_transaction(state_obj, vals[-1])
                if t:
                    self.tree.item(iid, values=self._row_values_from_tx(t))

    def _bulk_change_to_income(self):
        ids = self._selected_tx_ids()
        if not ids:
            return
        s = load_state()
        count = 0
        for tx_id in ids:
            old = get_transaction(s, tx_id)
            if not old:
                continue
            new = dict(old)
            new["ttype"] = "收入"
            try:
                apply_transaction_delta(s, old, -1)
                update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
                apply_transaction_delta(s, new, 1)
                count += 1
            except Exception:
                pass
        save_state(s)
        messagebox.showinfo("批量修改完成", f"已改为收入: {count} 条")
        self._refresh_selection_rows(s, ids)

    def _bulk_change_to_expense(self):
        ids = self._selected_tx_ids()
        if not ids:
            return
        s = load_state()
        count = 0
        for tx_id in ids:
            old = get_transaction(s, tx_id)
            if not old:
                continue
            new = dict(old)
            new["ttype"] = "支出"
            try:
                apply_transaction_delta(s, old, -1)
                update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
                apply_transaction_delta(s, new, 1)
                count += 1
            except Exception:
                pass
        save_state(s)
        messagebox.showinfo("批量修改完成", f"已改为支出: {count} 条")
        self._refresh_selection_rows(s, ids)

    def _bulk_change_to_transfer(self):
        ids = self._selected_tx_ids()
        if not ids:
            return
        s = load_state()
        count = 0
        for tx_id in ids:
            old = get_transaction(s, tx_id)
            if not old:
                continue
            try:
                apply_transaction_delta(s, old, -1)
                new = dict(old)
                new["ttype"] = "转账"
                new["category"] = "转账"
                new["account"] = ""
                new["to_account"] = None
                new["from_account"] = None
                update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
                apply_transaction_delta(s, new, 1)
                count += 1
            except Exception:
                pass
        save_state(s)
        messagebox.showinfo("批量修改完成", f"已修改为转账: {count} 条")
        self._refresh_selection_rows(s, ids)

    def _bulk_modify_accounts(self):
        ids = self._selected_tx_ids()
        if not ids:
            return
        names = get_account_names(load_state())
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
        s = load_state()
        count = 0
        for tx_id in ids:
            old = get_transaction(s, tx_id)
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
                apply_transaction_delta(s, old, -1)
                update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
                apply_transaction_delta(s, new, 1)
                count += 1
            except Exception:
                pass
        save_state(s)
        messagebox.showinfo("批量修改完成", f"已更新账户信息: {count} 条")
        self._refresh_selection_rows(s, ids)

    def _bulk_modify_category(self):
        ids = self._selected_tx_ids()
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
        s = load_state()
        add_category(s, sc, cat_final)
        count = 0
        for tx_id in ids:
            old = get_transaction(s, tx_id)
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
                apply_transaction_delta(s, old, -1)
                update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
                apply_transaction_delta(s, new, 1)
                count += 1
            except Exception:
                pass
        save_state(s)
        messagebox.showinfo("批量修改完成", f"已更新消费类别: {count} 条")
        self._refresh_selection_rows(s, ids)

    def _bulk_modify_record_source(self):
        ids = self._selected_tx_ids()
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
            s_val = e_src.get().strip()
            res["src"] = s_val if s_val else cb.get().strip()
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
        s = load_state()
        count = 0
        for tx_id in ids:
            old = get_transaction(s, tx_id)
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
                apply_transaction_delta(s, old, -1)
                update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
                apply_transaction_delta(s, new, 1)
                count += 1
            except Exception:
                pass
        save_state(s)
        messagebox.showinfo("批量修改完成", f"已更新记账来源: {count} 条")
        self._refresh_selection_rows(s, ids)

    def _ai_prefill_category(self):
        ids = self._selected_tx_ids()
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
            pred = self._predict_category_for_dashboard(text, scene, s)
            if not pred:
                skipped += 1
                continue
            new = dict(t)
            new["category"] = pred
            add_category(s, scene, pred)
            update_transaction(s, tx_id, type('DummyTx', (), {'to_dict': lambda self2: new})())
            filled += 1
        save_state(s)
        messagebox.showinfo("AI预填完成", f"已预填: {filled} 条\n跳过: {skipped} 条")
        self._refresh_selection_rows(s, ids)

    def _predict_category_for_dashboard(self, text: str, scene: str, state) -> str:
        s_val = (text or "").lower()
        try:
            rules = get_category_rules(state, scene)
            for it in rules:
                kw = (it.get("keyword") or "").lower()
                cat = (it.get("category") or "").strip()
                if kw and cat and kw in s_val:
                    return cat
        except Exception:
            pass
        if scene == "支出":
            if any(k in s_val for k in ["早餐","午餐","晚餐","外卖","餐厅","饭店","奶茶","咖啡"]):
                return "三餐"
            if any(k in s_val for k in ["公交","地铁","打车","出租","滴滴","出行","高铁","火车","机票"]):
                return "交通"
            if any(k in s_val for k in ["电影","娱乐","网游","游戏","剧场","ktv","音乐"]):
                return "娱乐"
            if any(k in s_val for k in ["医院","医疗","看病","药店","药品","体检"]):
                return "医疗"
            if any(k in s_val for k in ["学习","课程","培训","书籍","教材"]):
                return "学习"
            if any(k in s_val for k in ["纸巾","清洁","生活","用品","日用品"]):
                return "日用品"
            if any(k in s_val for k in ["房租","租金","物业","水费","电费","燃气","煤气"]):
                return "水电煤"
            if any(k in s_val for k in ["化妆","美妆","美容","护肤"]):
                return "美妆"
            if any(k in s_val for k in ["孩子","幼儿园","课外","辅导","教育"]):
                return "子女教育"
        else:
            if any(k in s_val for k in ["工资","薪资","薪水","发薪"]):
                return "工资"
            if any(k in s_val for k in ["生活费","零用","家人汇款"]):
                return "生活费"
            if any(k in s_val for k in ["红包","收红包","礼金"]):
                return "收红包"
            if any(k in s_val for k in ["外快","兼职","劳务","项目款","佣金"]):
                return "外快"
            if any(k in s_val for k in ["基金","股票","理财","分红"]):
                return "股票基金"
        return ""
