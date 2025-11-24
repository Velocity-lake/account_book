import tkinter as tk
from tkinter import ttk
import importlib
import help_content


class HelpPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self._toc_index_map = {}
        self._build()

    def _build(self):
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        paned = ttk.PanedWindow(container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # TOC (left)
        self.toc_frame = ttk.Frame(paned)
        self.toc = ttk.Treeview(self.toc_frame, show="tree")
        self.toc.pack(fill=tk.BOTH, expand=True)
        self.toc.bind("<<TreeviewSelect>>", self._on_toc_select)

        # Content (right)
        self.content_frame = ttk.Frame(paned)
        self.text = tk.Text(self.content_frame, wrap="word")
        self.text.pack(fill=tk.BOTH, expand=True)
        self._configure_text_tags()

        paned.add(self.toc_frame, weight=1)
        paned.add(self.content_frame, weight=3)

        # Shortcuts
        self.text.bind("<Control-f>", self._open_find_dialog)

    def refresh(self):
        try:
            importlib.reload(help_content)
        except Exception:
            pass
        self._render_document(help_content.get_help_content())

    def _configure_text_tags(self):
        try:
            self.text.tag_configure("h1", font=("Microsoft YaHei", 16, "bold"), spacing3=6)
            self.text.tag_configure("h2", font=("Microsoft YaHei", 14, "bold"), spacing3=4)
            self.text.tag_configure("h3", font=("Microsoft YaHei", 12, "bold"), spacing3=2)
            self.text.tag_configure("p", font=("Microsoft YaHei", 11))
            self.text.tag_configure("code", font=("Consolas", 10), background="#f5f5f7")
            self.text.tag_configure("quote", font=("Microsoft YaHei", 11, "italic"), foreground="#555555")
        except Exception:
            pass

    def _clear(self):
        for i in self.toc.get_children(""):
            self.toc.delete(i)
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.configure(state="disabled")
        self._toc_index_map.clear()

    def _render_document(self, nodes):
        self._clear()
        self.text.configure(state="normal")
        def add_nodes(parent_id, items, level=1):
            for node in items:
                title = (node.get("title") or "").strip()
                content = node.get("content") or ""
                children = node.get("children") or []
                tag = "h1" if level == 1 else ("h2" if level == 2 else "h3")

                # Record start index
                start_index = self.text.index(tk.END)
                # Heading
                if title:
                    self.text.insert(tk.END, title + "\n", (tag,))
                # Body
                if content:
                    self.text.insert(tk.END, content.rstrip() + "\n\n", ("p",))
                # Map for TOC jump
                item_id = self.toc.insert(parent_id, tk.END, text=title or "(无标题)")
                self._toc_index_map[item_id] = start_index
                # Children
                if children:
                    add_nodes(item_id, children, level + 1)
        add_nodes("", nodes, 1)
        self.text.configure(state="disabled")

    def _on_toc_select(self, _evt):
        cur = self.toc.selection()
        if not cur:
            return
        idx = self._toc_index_map.get(cur[0])
        if not idx:
            return
        self.text.configure(state="normal")
        try:
            self.text.see(idx)
            self.text.mark_set("insert", idx)
        finally:
            self.text.configure(state="disabled")

    def _open_find_dialog(self, _evt=None):
        dlg = tk.Toplevel(self)
        dlg.title("查找")
        dlg.transient(self)
        dlg.grab_set()
        ttk.Label(dlg, text="关键字").grid(row=0, column=0, padx=8, pady=8)
        e = ttk.Entry(dlg)
        e.grid(row=0, column=1, padx=8, pady=8)
        result = {"last": "1.0"}
        def find_next():
            patt = e.get().strip()
            if not patt:
                return
            self.text.configure(state="normal")
            try:
                pos = self.text.search(patt, result["last"], nocase=True, stopindex=tk.END)
                if pos:
                    self.text.see(pos)
                    self.text.tag_remove("sel", "1.0", tk.END)
                    end_pos = f"{pos}+{len(patt)}c"
                    self.text.tag_add("sel", pos, end_pos)
                    result["last"] = end_pos
            finally:
                self.text.configure(state="disabled")
        ttk.Button(dlg, text="查找下一个", command=find_next).grid(row=1, column=0, columnspan=2, pady=8)
        e.focus_set()
