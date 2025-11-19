import tkinter as tk
from ui_main import MainApp
from theme import setup_theme

def main():
    root = tk.Tk()
    root.title("个人记账本")
    setup_theme(root)
    app = MainApp(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.geometry("1100x700")
    root.mainloop()

if __name__ == "__main__":
    main()
