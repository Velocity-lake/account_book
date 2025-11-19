from tkinter import ttk

def setup_theme(root):
    style = ttk.Style(root)
    try:
        style.theme_use(style.theme_use())
    except Exception:
        pass
    style.configure('TLabel', font=('Segoe UI', 11), foreground='#1d1d1f')
    style.configure('Header.TLabel', font=('Segoe UI', 18), foreground='#1d1d1f')
    style.configure('Sidebar.TButton', font=('Segoe UI', 11), padding=(12,8), anchor='w')
    style.map('Sidebar.TButton', background=[('active','#e5e5ea')])
    style.configure('Primary.TButton', font=('Segoe UI', 11), padding=(10,6))
    style.map('Primary.TButton', foreground=[('active','#ffffff')], background=[('!disabled','#34c759'),('active','#2fb34f')])
    style.configure('Secondary.TButton', font=('Segoe UI', 11), padding=(10,6))
    style.map('Secondary.TButton', background=[('active','#e5e5ea')])
    style.configure('Treeview.Heading', font=('Segoe UI', 11))
