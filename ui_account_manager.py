import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime
from storage import load_state, save_state, add_account, remove_account, rename_account, find_account, get_account_types, get_account_names, apply_transaction_delta, add_category
from models import Account
from utils import format_amount, gen_id, normalize_ttype
from ui_add_dialog import AddTransactionDialog

class AccountManagerPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.state = load_state()
        self.build_ui()
        self.refresh()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_net = ttk.Label(top, text="净资产：0.00")
        self.lbl_assets = ttk.Label(top, text="总资产：0.00")
        self.lbl_debt = ttk.Label(top, text="总负债：0.00")
        self.lbl_net.pack(side=tk.LEFT, padx=12)
        self.lbl_assets.pack(side=tk.LEFT, padx=12)
        self.lbl_debt.pack(side=tk.LEFT, padx=12)
        self.btn_edit = ttk.Button(top, text="编辑模式", command=self.toggle_edit_mode)
        self.btn_edit.pack(side=tk.RIGHT, padx=4)
        self.btn_freeze = ttk.Button(top, text="冻结资产", command=self.toggle_freeze_assets)
        self.btn_freeze.pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="下载账户模板", command=self.download_account_template).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="导出账户", command=self.export_accounts).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="导入账户", command=self.import_accounts).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="新增账户", command=self.on_add).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="删除账户", command=self.on_delete).pack(side=tk.RIGHT, padx=4)
        cols = ["账户名","余额","备注"]
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=200 if c != "备注" else 260)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree.tag_configure('negative', foreground='#ff3b30')
        self.tree.tag_configure('group', foreground='#000000', font=('Segoe UI', 11, 'bold'))
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="编辑", command=self.on_edit)
        self.edit_mode = False
        self._editor = None

    def refresh(self):
        self.state = load_state()
        self.tree.delete(*self.tree.get_children())
        net = 0.0
        pos = 0.0
        neg = 0.0
        groups = {}
        types = get_account_types(self.state)
        sums = {t: 0.0 for t in types}
        counts = {t: 0 for t in types}
        for a in self.state.get("accounts", []):
            t = (a.get("type") or "")
            bal = float(a.get("balance",0))
            sums[t] = sums.get(t, 0.0) + bal
            counts[t] = counts.get(t, 0) + 1
        for typ in types:
            label = f"{typ} - {counts.get(typ,0)}个账户"
            sumv = sums.get(typ, 0.0)
            node = self.tree.insert("", tk.END, text=label, values=[label, format_amount(sumv), ""], open=True, tags=('group',))
            groups[typ] = node
        for a in self.state.get("accounts", []):
            bal = float(a.get("balance",0))
            net += bal
            if bal >= 0:
                pos += bal
            else:
                neg += bal
            node = groups.get(a.get("type") or "")
            self.tree.insert(node if node else "", tk.END, text=a.get("name"), values=[a.get("name"), format_amount(bal), a.get("note","")], tags=(('negative',) if bal < 0 else ()))
        self.lbl_net.configure(text=f"净资产：{format_amount(net)}")
        self.lbl_assets.configure(text=f"总资产：{format_amount(pos)}")
        self.lbl_debt.configure(text=f"总负债：{format_amount(neg)}")
        fr = bool((self.state.get("prefs", {}) or {}).get("freeze_assets"))
        try:
            self.btn_freeze.configure(text=("解除冻结" if fr else "冻结资产"))
            self.btn_edit.configure(text=("退出编辑模式" if self.edit_mode else "编辑模式"))
        except Exception:
            pass

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        self.refresh()

    def toggle_freeze_assets(self):
        s = load_state()
        prefs = s.setdefault("prefs", {})
        cur = bool((prefs or {}).get("freeze_assets"))
        prefs["freeze_assets"] = (not cur)
        save_state(s)
        self.refresh()

    def on_double_click(self, event):
        if not self.edit_mode:
            iid = self.tree.identify_row(event.y)
            if not iid:
                return
            parent = self.tree.parent(iid)
            if parent == "":
                return
            vals = self.tree.item(iid, 'values')
            if not vals:
                return
            name = vals[0]
            try:
                from ui_bill_list import BillListDialog
                BillListDialog(self, initial_filters={"account_related": name})
            except Exception:
                pass
            return
        region = self.tree.identify_region(event.x, event.y)
        if region not in ('cell','tree'):
            return
        iid = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not iid or not col_id:
            return
        vals = self.tree.item(iid, 'values')
        text = self.tree.item(iid, 'text')
        parent = self.tree.parent(iid)
        if not vals:
            return
        if parent == "":
            return
        x, y, w, h = self.tree.bbox(iid, col_id)
        absx = self.tree.winfo_rootx() + x
        absy = self.tree.winfo_rooty() + y
        if self._editor:
            try:
                self._editor.destroy()
            except Exception:
                pass
        col_index = int(col_id.replace('#',''))
        val = vals[col_index-1] if col_index-1 < len(vals) else ""
        if col_index == 0:
            e = ttk.Entry()
            e.insert(0, str(text))
            def commit_tree():
                new_name = e.get().strip()
                if not new_name:
                    return
                old_name = text
                if new_name != old_name:
                    if messagebox.askyesno("同步账单", "是否同步修改账单中的账户名称？"):
                        rename_account(self.state, old_name, new_name)
                        a = find_account(self.state, new_name) or {}
                        save_state(self.state)
                    else:
                        a = find_account(self.state, old_name) or {}
                        if a:
                            a["name"] = new_name
                            save_state(self.state)
                self.refresh()
                e.destroy()
            e.bind("<Return>", lambda ev: commit_tree())
            e.bind("<Escape>", lambda ev: e.destroy())
            e.place(x=absx, y=absy, width=w, height=h)
            e.focus_set()
            self._editor = e
            return
        if col_index == 1:
            e = ttk.Entry()
            e.insert(0, str(val))
            def commit():
                new_name = e.get().strip()
                if not new_name:
                    return
                old_name = vals[0]
                if new_name != old_name:
                    if messagebox.askyesno("同步账单", "是否同步修改账单中的账户名称？"):
                        rename_account(self.state, old_name, new_name)
                        a = find_account(self.state, new_name) or {}
                        save_state(self.state)
                    else:
                        a = find_account(self.state, old_name) or {}
                        if a:
                            a["name"] = new_name
                            save_state(self.state)
                self.refresh()
                e.destroy()
            e.bind("<Return>", lambda ev: commit())
            e.bind("<Escape>", lambda ev: e.destroy())
            e.place(x=absx, y=absy, width=w, height=h)
            e.focus_set()
            self._editor = e
        elif col_index == 2:
            e = ttk.Entry()
            e.insert(0, str(val))
            def commit():
                try:
                    bal = float(e.get().strip())
                except Exception:
                    return
                name = vals[0]
                a = find_account(self.state, name)
                if a:
                    a["balance"] = bal
                    save_state(self.state)
                self.refresh()
                e.destroy()
            e.bind("<Return>", lambda ev: commit())
            e.bind("<Escape>", lambda ev: e.destroy())
            e.place(x=absx, y=absy, width=w, height=h)
            e.focus_set()
            self._editor = e
        elif col_index == 3:
            e = ttk.Entry()
            e.insert(0, str(val))
            def commit():
                name = vals[0]
                a = find_account(self.state, name)
                if a:
                    a["note"] = e.get().strip()
                    save_state(self.state)
                self.refresh()
                e.destroy()
            e.bind("<Return>", lambda ev: commit())
            e.bind("<Escape>", lambda ev: e.destroy())
            e.place(x=absx, y=absy, width=w, height=h)
            e.focus_set()
            self._editor = e

    def on_add(self):
        dlg = AccountDialog(self, None)
        self.wait_window(dlg)
        if dlg.result:
            a = Account(**dlg.result)
            add_account(self.state, a)
            save_state(self.state)
            self.refresh()

    def selected_account_name(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def on_delete(self):
        name = self.selected_account_name()
        if not name:
            return
        if not messagebox.askyesno("确认", "删除该账户？删除后账单中的引用不会自动移除"):
            return
        remove_account(self.state, name)
        save_state(self.state)
        self.refresh()

    def export_accounts(self):
        dir_path = filedialog.askdirectory(title="选择导出位置")
        if not dir_path:
            return
        try:
            cols = ["名称","类型","余额","备注"]
            rows = []
            for a in load_state().get("accounts", []):
                rows.append([a.get("name",""), a.get("type",""), str(a.get("balance",0)), a.get("note","")])
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"导出账户_{ts}.xlsx"
            path = os.path.join(dir_path, fname)
            self._write_xlsx(path, cols, rows)
            if messagebox.askyesno("导出成功", "账户已导出，是否打开所在文件夹？"):
                try:
                    os.startfile(dir_path)
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def download_account_template(self):
        dir_path = filedialog.askdirectory(title="选择保存位置")
        if not dir_path:
            return
        cols = ["名称","类型","余额","备注"]
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        fname = f"账户标准模板_{ts}.xlsx"
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

    def import_accounts(self):
        paths = filedialog.askopenfilenames(title="选择账户文件", filetypes=[("所有文件","*.*"), ("Excel 文件","*.xlsx"), ("CSV 文件","*.csv")])
        if not paths:
            return
        try:
            from importers import read_csv
            from xlsx_reader import read_xlsx
            s = load_state()
            # 备份
            from storage import backup_state
            bpath = backup_state()
            rows_import = []
            for p in paths:
                if p.lower().endswith('.csv'):
                    raw = read_csv(p)
                else:
                    raw = read_xlsx(p)
                # 允许非标准文件，尝试从键映射到账户字段
                for r in raw:
                    name = str(r.get("名称", r.get("账户名", r.get("name","")))).strip()
                    typ = str(r.get("类型", r.get("账户类型", r.get("type","")))).strip()
                    bal_raw = r.get("余额", r.get("balance", "0"))
                    try:
                        bal = float(str(bal_raw).strip() or "0")
                    except Exception:
                        bal = None
                    note = str(r.get("备注", r.get("note",""))).strip()
                    rows_import.append({"name": name, "type": typ, "balance": bal, "note": note})
            # 去除空行与重复（名称为空或全空跳过），重复保留最后一条
            merged = {}
            for it in rows_import:
                if not it.get("name"):
                    continue
                if all(((str(it.get(k,"")) or "").strip() == "") for k in ["type","note"]) and (it.get("balance") in (None, 0)):
                    continue
                merged[it["name"]] = it
            # 全量覆盖模式选择
            full_override = messagebox.askyesno("覆盖模式", "是否启用全量覆盖模式？\n启用后，未出现在导入文件中的账户将被移除。")
            added = 0
            updated = 0
            errors = 0
            # 应用 upsert
            for name, it in merged.items():
                a = find_account(s, name)
                # 类型处理：未知类型自动加入
                if it.get("type"):
                    types = get_account_types(s)
                    if it["type"] not in types:
                        types.append(it["type"])
                        s["account_types"] = list(types)
                if a:
                    if it.get("balance") is None:
                        errors += 1
                        continue
                    a["type"] = it.get("type", a.get("type",""))
                    a["balance"] = float(it.get("balance", a.get("balance",0)))
                    a["note"] = it.get("note", a.get("note",""))
                    updated += 1
                else:
                    if it.get("balance") is None:
                        errors += 1
                        continue
                    add_account(s, Account(name=name, balance=float(it.get("balance",0)), type=it.get("type",""), note=it.get("note","")))
                    added += 1
            if full_override:
                keep_names = set(merged.keys())
                s["accounts"] = [a for a in s.get("accounts", []) if a.get("name") in keep_names]
            save_state(s)
            msg = [
                f"导入完成",
                f"新增: {added} 条",
                f"更新: {updated} 条",
            ]
            if full_override:
                msg.append("已启用全量覆盖模式")
            if errors:
                msg.append(f"错误: {errors} 条（余额非数字或缺失）")
            msg.append(f"已自动备份: {bpath}")
            messagebox.showinfo("导入结果", "\n".join(msg))
            self.refresh()
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _write_xlsx(self, path, header, rows):
        import zipfile
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

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            parent = self.tree.parent(iid)
            try:
                self.menu.delete(0, tk.END)
            except Exception:
                pass
            if parent == "":
                self.menu.add_command(label="新增账户", command=lambda: self.on_add_in_group(iid))
            else:
                self.menu.add_command(label="编辑", command=self.on_edit)
                self.menu.add_command(label="新增记账", command=self.on_add_transaction_for_account)
            self.menu.post(event.x_root, event.y_root)

    def on_add_in_group(self, group_iid):
        label = self.tree.item(group_iid, 'text') or ""
        if '（' in label:
            typ = label.split('（')[0].strip()
        else:
            typ = label.split('-')[0].strip()
        dlg = AccountDialog(self, {"name": "", "balance": 0.0, "type": typ, "note": ""})
        self.wait_window(dlg)
        if dlg.result:
            a = Account(**dlg.result)
            add_account(self.state, a)
            save_state(self.state)
            self.refresh()

    def on_edit(self):
        name = self.selected_account_name()
        if not name:
            return
        a = find_account(self.state, name)
        dlg = AccountDialog(self, a)
        self.wait_window(dlg)
        if dlg.result:
            new = dlg.result
            if new["name"] != name:
                rename_account(self.state, name, new["name"])
                a = find_account(self.state, new["name"]) or {}
                a.update(new)
            else:
                a.update(new)
            save_state(self.state)
            self.refresh()

    def on_add_transaction_for_account(self):
        name = self.selected_account_name()
        if not name:
            return
        initial = {"account": name, "ttype": "支出"}
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
            apply_transaction_delta(self.state, new, 1)
            try:
                self.state.setdefault("transactions", []).append(new)
            except Exception:
                pass
            save_state(self.state)
            self.refresh()

class AccountDialog(tk.Toplevel):
    def __init__(self, master, initial):
        super().__init__(master)
        self.result = None
        self.title("账户编辑")
        self.grab_set()
        f = ttk.Frame(self)
        f.pack(padx=16, pady=16)
        ttk.Label(f, text="账户名").grid(row=0, column=0)
        self.e_name = ttk.Entry(f)
        self.e_name.grid(row=0, column=1)
        ttk.Label(f, text="余额").grid(row=1, column=0)
        self.e_balance = ttk.Entry(f)
        self.e_balance.grid(row=1, column=1)
        ttk.Label(f, text="类型").grid(row=2, column=0)
        self.cb_type = ttk.Combobox(f, values=get_account_types(load_state()), state="normal")
        self.cb_type.grid(row=2, column=1)
        ttk.Label(f, text="备注").grid(row=3, column=0)
        self.e_note = ttk.Entry(f)
        self.e_note.grid(row=3, column=1)
        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(b, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(b, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=4)
        f.columnconfigure(1, weight=1)
        if initial:
            self.e_name.insert(0, initial.get("name",""))
            self.e_balance.insert(0, str(initial.get("balance",0)))
            self.cb_type.set(initial.get("type",""))
            self.e_note.insert(0, initial.get("note",""))
        else:
            self.cb_type.set(get_account_types(load_state())[0])

    def on_ok(self):
        try:
            name = self.e_name.get().strip()
            bal = float(self.e_balance.get().strip() or "0")
            typ = self.cb_type.get().strip() or "现金"
            note = self.e_note.get().strip()
            if not name:
                raise ValueError("账户名不能为空")
            self.result = {"name": name, "balance": bal, "type": typ, "note": note}
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))
