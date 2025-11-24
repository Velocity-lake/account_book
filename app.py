import tkinter as tk
from ui_main import MainApp
from theme import setup_theme
from storage import load_state

def main():
    root = tk.Tk()
    root.title("个人记账本")
    try:
        s = load_state()
        mode = (s.get("prefs", {}) or {}).get("theme", "light")
    except Exception:
        mode = "light"
    setup_theme(root, mode)
    app = MainApp(root)
    app.pack(fill=tk.BOTH, expand=True)
    try:
        setup_theme(root, mode)
    except Exception:
        pass
    root.geometry("1400x800")
    root.mainloop()

if __name__ == "__main__":
    main()
