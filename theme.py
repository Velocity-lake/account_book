from tkinter import ttk
import tkinter as tk

def setup_theme(root, mode: str = 'light'):
    style = ttk.Style(root)
    try:
        style.theme_use(style.theme_use())
    except Exception:
        pass
    light = {
        'bg': '#ffffff',
        'fg': '#1d1d1f',
        'muted': '#6e6e73',
        'btn_hover': '#e5e5ea',
        'primary': '#34c759',
        'primary_active': '#2fb34f',
        'surface': '#f5f5f7',
        'input_bg': '#ffffff',
        'border': '#d9d9de',
        'canvas_bg': '#ffffff',
        'tree_bg': '#ffffff',
        'tree_fg': '#1d1d1f',
        'tree_field': '#ffffff',
        'tree_sel_bg': '#dde7ff',
        'tree_sel_fg': '#1d1d1f'
    }
    dark = {
        'bg': '#1e1e1e',
        'fg': '#e5e5ea',
        'muted': '#a1a1a6',
        'btn_hover': '#2a2a2a',
        'primary': '#34c759',
        'primary_active': '#2fb34f',
        'surface': '#232323',
        'input_bg': '#2b2b2b',
        'border': '#3a3a3a',
        'canvas_bg': '#1e1e1e',
        'tree_bg': '#2b2b2b',
        'tree_fg': '#e5e5ea',
        'tree_field': '#2b2b2b',
        'tree_sel_bg': '#3a5ba0',
        'tree_sel_fg': '#ffffff'
    }
    pal = dark if (mode or 'light') == 'dark' else light
    try:
        root.configure(bg=pal['bg'])
    except Exception:
        pass
    style.configure('TLabel', font=('Segoe UI', 11), foreground=pal['fg'], background=pal['bg'])
    style.configure('Header.TLabel', font=('Segoe UI', 18), foreground=pal['fg'], background=pal['bg'])
    style.configure('TFrame', background=pal['bg'])
    style.configure('TLabelframe', background=pal['bg'])
    style.configure('TLabelframe.Label', foreground=pal['fg'], background=pal['bg'])
    style.configure('Sidebar.TButton', font=('Segoe UI', 11), padding=(12,8), anchor='w')
    style.map('Sidebar.TButton', background=[('active', pal['btn_hover'])])
    style.configure('Primary.TButton', font=('Segoe UI', 11), padding=(10,6))
    style.map('Primary.TButton', foreground=[('active','#ffffff')], background=[('!disabled', pal['primary']),('active', pal['primary_active'])])
    style.configure('Secondary.TButton', font=('Segoe UI', 11), padding=(10,6))
    style.map('Secondary.TButton', background=[('active', pal['btn_hover'])])
    style.configure('TButton', font=('Segoe UI', 11))
    style.map('TButton', foreground=[('disabled', pal['muted'])])
    style.configure('TCombobox', foreground=pal['fg'], fieldbackground=pal['input_bg'], background=pal['bg'])
    style.map('TCombobox', fieldbackground=[('readonly', pal['input_bg'])])
    style.configure('TEntry', foreground=pal['fg'], fieldbackground=pal['input_bg'], background=pal['bg'])
    style.configure('TScrollbar', background=pal['bg'])
    style.configure('TPanedwindow', background=pal['bg'])
    style.configure('Treeview', background=pal['tree_bg'], fieldbackground=pal['tree_field'], foreground=pal['tree_fg'])
    style.configure('Treeview.Heading', font=('Segoe UI', 11), foreground=pal['fg'], background=pal['bg'])
    style.map('Treeview', background=[('selected', pal['tree_sel_bg'])], foreground=[('selected', pal['tree_sel_fg'])])
    def _apply_widget_backgrounds(w):
        try:
            for ch in w.winfo_children():
                try:
                    if isinstance(ch, tk.Canvas):
                        ch.configure(bg=pal.get('canvas_bg', pal['bg']))
                    elif isinstance(ch, tk.Toplevel):
                        ch.configure(bg=pal['bg'])
                except Exception:
                    pass
                _apply_widget_backgrounds(ch)
        except Exception:
            pass
    _apply_widget_backgrounds(root)
