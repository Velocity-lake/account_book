import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from datetime import datetime
from storage import load_state, save_state, backup_state, add_transaction, apply_transaction_delta, get_account_names, add_category, BASE_DIR
from utils import normalize_ttype
from storage import load_state, get_category_rules
from models import Transaction
from utils import gen_id, parse_datetime
from ui_bill_list import BillListPage
from ui_account_manager import AccountManagerPage
from ui_add_dialog import AddTransactionDialog
from importers import try_import
from ui_dashboard import DashboardPage
from ui_settings import SettingsPage
from ui_icons import create_icons
from import_ai import process_images, export_failures
import zipfile

class MainApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.state = load_state()
        try:
            self.menu_layout_mode = (self.state.get("prefs", {}) or {}).get("menu_layout", 'classic')
        except Exception:
            self.menu_layout_mode = 'classic'
        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        ttk.Label(top, text="个人记账本", style='Header.TLabel').pack(side=tk.LEFT, padx=12, pady=8)
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)
        self.sidebar = ttk.Frame(body)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.icons = create_icons(self)
        self.build_sidebar()
        self.content = ttk.Frame(body)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        from ui_record_page import RecordPage
        self.pages = {
            "dashboard": DashboardPage(self.content),
            "bills": BillListPage(self.content, controller=self),
            "accounts": AccountManagerPage(self.content),
            "record": RecordPage(self.content),
            "settings": SettingsPage(self.content, controller=self),
            "import": self.ImportPanel(self.content, controller=self),
        }
        for p in self.pages.values():
            p.pack_forget()
        self.show_dashboard()

    def build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        ttk.Button(self.sidebar, text="首页总览", image=self.icons['dashboard'], compound='left', style='Sidebar.TButton', command=self.show_dashboard).pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(self.sidebar, text="账单列表", image=self.icons['bills'], compound='left', style='Sidebar.TButton', command=self.show_bills).pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(self.sidebar, text="记录账单", image=self.icons['record'], compound='left', style='Sidebar.TButton', command=self.show_record_page).pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(self.sidebar, text="账户管理", image=self.icons['accounts'], compound='left', style='Sidebar.TButton', command=self.show_accounts).pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(self.sidebar, text="软件设置", style='Sidebar.TButton', command=self.show_settings).pack(fill=tk.X, padx=8, pady=4)
        if self.menu_layout_mode == 'classic':
            ttk.Separator(self.sidebar).pack(fill=tk.X, padx=8, pady=6)
            ttk.Button(self.sidebar, text="导入账单", image=self.icons['import'], compound='left', style='Sidebar.TButton', command=self.show_import_panel).pack(fill=tk.X, padx=8, pady=4)
            ttk.Button(self.sidebar, text="智能导入（截图）", image=self.icons['import_ai'], compound='left', style='Sidebar.TButton', command=self.import_ai_images).pack(fill=tk.X, padx=8, pady=4)
            ttk.Button(self.sidebar, text="导出账单", image=self.icons['export'], compound='left', style='Sidebar.TButton', command=self.export_records).pack(fill=tk.X, padx=8, pady=4)
            ttk.Button(self.sidebar, text="下载标准模板", image=self.icons['template'], compound='left', style='Sidebar.TButton', command=self.download_template).pack(fill=tk.X, padx=8, pady=4)
            ttk.Button(self.sidebar, text="备份数据", image=self.icons['backup'], compound='left', style='Sidebar.TButton', command=self.backup).pack(fill=tk.X, padx=8, pady=4)
            ttk.Button(self.sidebar, text="刷新数据", image=self.icons['refresh'], compound='left', style='Sidebar.TButton', command=self.refresh_all).pack(fill=tk.X, padx=8, pady=4)

    def set_menu_layout(self, mode: str):
        self.menu_layout_mode = mode if mode in ('classic','compact') else 'classic'
        self.build_sidebar()

    def show_bills(self):
        for p in self.pages.values():
            p.pack_forget()
        self.pages["bills"].pack(fill=tk.BOTH, expand=True)
        self.pages["bills"].refresh()

    def show_dashboard(self):
        for p in self.pages.values():
            p.pack_forget()
        self.pages["dashboard"].pack(fill=tk.BOTH, expand=True)
        self.pages["dashboard"].refresh()

    def show_accounts(self):
        for p in self.pages.values():
            p.pack_forget()
        self.pages["accounts"].pack(fill=tk.BOTH, expand=True)
        self.pages["accounts"].refresh()

    def show_settings(self):
        for p in self.pages.values():
            p.pack_forget()
        self.pages["settings"].pack(fill=tk.BOTH, expand=True)

    def refresh_all(self):
        self.state = load_state()
        self.pages["bills"].refresh()
        self.pages["accounts"].refresh()

    def show_record_page(self):
        for p in self.pages.values():
            p.pack_forget()
        self.pages["record"].pack(fill=tk.BOTH, expand=True)
        self.pages["record"].refresh()

    def show_import_panel(self):
        for p in self.pages.values():
            p.pack_forget()
        self.pages["import"].pack(fill=tk.BOTH, expand=True)

    class ImportPanel(ttk.Frame):
        def __init__(self, master, controller):
            super().__init__(master)
            self.controller = controller
            self.build()
        def build(self):
            frm = ttk.Frame(self)
            frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            ttk.Label(frm, text="导入账单", font=("Microsoft YaHei", 16)).pack(anchor=tk.W)
            ttk.Label(frm, text="请选择导入类型", font=("Microsoft YaHei", 12)).pack(anchor=tk.W, pady=8)
            row = ttk.Frame(frm)
            row.pack(fill=tk.X)
            ttk.Button(row, text="支付宝账单导入", command=self.controller._import_alipay).pack(side=tk.LEFT, padx=6, pady=6)
            ttk.Button(row, text="微信账单导入", command=self.controller._import_wechat).pack(side=tk.LEFT, padx=6, pady=6)
            ttk.Button(row, text="标准模版导入", command=self.controller._import_standard).pack(side=tk.LEFT, padx=6, pady=6)
            ttk.Button(row, text="其它导入", command=self.controller._import_other).pack(side=tk.LEFT, padx=6, pady=6)

    def import_records(self):
        self.show_import_panel()

    def _handle_import_rows(self, rows, source_label, stats):
        s = load_state()
        account_names = get_account_names(s)
        if not account_names:
            raise ValueError("请先新增账户再导入")
        now_iso = datetime.now().isoformat()
        for r in rows:
            r["record_time"] = now_iso
            r["record_source"] = source_label
            cat_sync = (r.get("category") or "").strip()
            typ_sync = normalize_ttype(r.get("ttype"))
            if cat_sync and typ_sync in ["收入","报销类收入","支出","报销类支出"]:
                sc_sync = "收入" if typ_sync in ["收入","报销类收入"] else "支出"
                add_category(s, sc_sync, cat_sync)
        use_ai = messagebox.askyesno("预填消费类别", "是否让系统进行预填消费类别？")
        ai_prefill = 0
        if use_ai:
            for r in rows:
                cat = (r.get("category") or "").strip()
                typ = normalize_ttype(r.get("ttype"))
                if not cat and typ in ["收入","报销类收入","支出","报销类支出"]:
                    text = " ".join([str(r.get("note","")), str(r.get("record_source","")), str(r.get("account",""))]).lower()
                    sc = "收入" if typ in ["收入","报销类收入"] else "支出"
                    pred = self._predict_category(text, sc)
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
        from utils import tx_signature
        existing = {tx_signature(t) for t in s.get("transactions", [])}
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
        total = len(rows)
        skipped = total - success
        msg = f"导入完成\n总计: {total} 条\n成功: {success} 条"
        if dup:
            msg += f"\n重复: {dup} 条"
        skipped_no_io = int((stats or {}).get("skipped_no_io", 0))
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
        self.refresh_all()

    def _import_alipay(self):
        paths = filedialog.askopenfilenames(title="选择支付宝账单文件", filetypes=[("CSV 文件","*.csv"), ("Excel 文件","*.xlsx"), ("所有文件","*.*")])
        if not paths:
            return
        from importers import read_csv, read_xlsx, map_alipay
        s = load_state()
        account_names = get_account_names(s)
        rows_all = []
        stats_total = {"skipped_no_io": 0}
        for p in paths:
            raw = read_csv(p) if p.lower().endswith('.csv') else read_xlsx(p)
            rows, stats = map_alipay(raw, account_names)
            rows_all.extend(rows)
            stats_total["skipped_no_io"] += int(stats.get("skipped_no_io", 0))
        self._handle_import_rows(rows_all, "支付宝", stats_total)

    def _import_wechat(self):
        paths = filedialog.askopenfilenames(title="选择微信账单文件", filetypes=[("CSV 文件","*.csv"), ("Excel 文件","*.xlsx"), ("所有文件","*.*")])
        if not paths:
            return
        from importers import read_csv, read_xlsx, map_wechat
        s = load_state()
        account_names = get_account_names(s)
        rows_all = []
        for p in paths:
            raw = read_csv(p) if p.lower().endswith('.csv') else read_xlsx(p)
            rows = map_wechat(raw, account_names)
            rows_all.extend(rows)
        self._handle_import_rows(rows_all, "微信", {"skipped_no_io": 0})

    def _import_standard(self):
        paths = filedialog.askopenfilenames(title="选择标准模版文件", filetypes=[("CSV 文件","*.csv"), ("Excel 文件","*.xlsx"), ("所有文件","*.*")])
        if not paths:
            return
        from importers import read_csv, read_xlsx, import_standard_rows
        s = load_state()
        account_names = get_account_names(s)
        rows_all = []
        for p in paths:
            raw = read_csv(p) if p.lower().endswith('.csv') else read_xlsx(p)
            rows = import_standard_rows(raw, account_names)
            rows_all.extend(rows)
        self._handle_import_rows(rows_all, "模版导入", {"skipped_no_io": 0})

    def _import_other(self):
        paths = filedialog.askopenfilenames(title="选择账单文件", filetypes=[("CSV 文件","*.csv"), ("Excel 文件","*.xlsx"), ("所有文件","*.*")])
        if not paths:
            return
        s = load_state()
        account_names = get_account_names(s)
        rows_all = []
        stats_total = {"skipped_no_io": 0}
        from importers import try_import
        for p in paths:
            res = try_import(p, account_names)
            rows_all.extend(res.get("rows", []))
            stats_total["skipped_no_io"] += int(res.get("stats", {}).get("skipped_no_io", 0))
        self._handle_import_rows(rows_all, "其它导入", stats_total)

    def export_records(self):
        path = filedialog.asksaveasfilename(title="导出账单", defaultextension=".xlsx", filetypes=[("Excel 文件","*.xlsx"), ("CSV 文件","*.csv")])
        if not path:
            return
        s = load_state()
        cols = ["交易时间","金额","消费类别","所属类别","账户","转入账户","转出账户","备注"]
        try:
            if path.lower().endswith('.csv'):
                import csv
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(cols)
                    for t in s.get("transactions", []):
                        w.writerow([
                            t.get("time")[:19].replace("T"," "),
                            t.get("amount"),
                            t.get("category",""),
                            t.get("ttype",""),
                            t.get("account",""),
                            t.get("to_account",""),
                            t.get("from_account",""),
                            t.get("note",""),
                        ])
            else:
                rows = []
                for t in s.get("transactions", []):
                    rows.append([
                        t.get("time")[:19].replace("T"," "),
                        str(t.get("amount")),
                        t.get("category",""),
                        t.get("ttype",""),
                        t.get("account",""),
                        t.get("to_account",""),
                        t.get("from_account",""),
                        t.get("note",""),
                    ])
                self._write_xlsx(path, cols, rows)
            messagebox.showinfo("导出成功", "账单已导出")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def backup(self):
        p = backup_state()
        messagebox.showinfo("备份成功", f"已创建备份\n{p}")

    def download_template(self):
        dir_path = filedialog.askdirectory(title="选择保存位置")
        if not dir_path:
            return
        cols = ["交易时间","金额","消费大类","消费小类","所属类别","账户","转入账户","转出账户","备注"]
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"标准账单模版_{ts}.xlsx"
        path = os.path.join(dir_path, fname)
        try:
            self._write_xlsx(path, cols, [])
            if messagebox.askyesno("已生成模板", "是否打开该文件夹？"):
                try:
                    os.startfile(dir_path)
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

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

    def _predict_category(self, text: str, scene: str) -> str:
        s = (text or "").lower()
        try:
            rules = get_category_rules(load_state(), scene)
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
    def import_ai_images(self):
        paths = filedialog.askopenfilenames(title="选择订单截图", filetypes=[("图片","*.png;*.jpg;*.jpeg"), ("所有文件","*.*")])
        if not paths:
            return
        try:
            s = load_state()
            account_names = get_account_names(s)
            if not account_names:
                raise ValueError("请先新增账户")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results, failures = process_images(paths, account_names, parse_datetime(now_str), s.get("transactions", []))
            now_iso = datetime.now().isoformat()
            for r in results:
                r["record_time"] = now_iso
                r["record_source"] = "智能导入"
            if any((not r.get("account")) for r in results):
                acc = self.ask_default_account(account_names)
                if not acc:
                    raise ValueError("未选择默认账户，无法完成导入")
                for r in results:
                    if not r.get("account"):
                        r["account"] = acc
            from utils import tx_signature
            existing = {tx_signature(t) for t in s.get("transactions", [])}
            success = 0
            dup = 0
            for r in results:
                sig = tx_signature(r)
                if sig in existing:
                    dup += 1
                    continue
                existing.add(sig)
                s["transactions"].append(r)
                apply_transaction_delta(s, r, 1)
                success += 1
            save_state(s)
            import os
            fail_path = export_failures(failures, os.path.dirname(os.path.abspath(__file__))) if failures else None
            msg = f"智能导入完成\n总计: {len(results)} 条\n成功: {success} 条"
            if failures:
                msg += f"\n失败: {len(failures)} 条"
            if dup:
                msg += f"\n重复: {dup} 条"
            messagebox.showinfo("智能导入", msg)
            if fail_path:
                messagebox.showinfo("失败清单已生成", fail_path)
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("导入失败", str(e))
    def ask_default_account(self, account_names):
        from storage import list_accounts_by_type, get_account_types, load_state
        s = load_state()
        by_type = list_accounts_by_type(s)
        types = get_account_types(s)
        dlg = tk.Toplevel(self)
        dlg.title("选择默认账户")
        dlg.grab_set()
        ttk.Label(dlg, text="部分记录无法匹配账户，请选择默认账户：").pack(padx=12, pady=8)
        frame = ttk.Frame(dlg)
        frame.pack(padx=12, pady=8)
        ttk.Label(frame, text="分类").grid(row=0, column=0)
        cb_group = ttk.Combobox(frame, values=types, state="readonly")
        cb_group.grid(row=0, column=1)
        ttk.Label(frame, text="账户").grid(row=1, column=0)
        cb_acc = ttk.Combobox(frame, state="readonly")
        cb_acc.grid(row=1, column=1)
        chosen = {"value": None}
        def on_group():
            t = cb_group.get().strip()
            cb_acc["values"] = by_type.get(t, [])
            if by_type.get(t):
                cb_acc.set(by_type[t][0])
        cb_group.bind("<<ComboboxSelected>>", lambda e: on_group())
        cb_group.set(types[0])
        on_group()
        def ok():
            chosen["value"] = cb_acc.get().strip()
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
