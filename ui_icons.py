import tkinter as tk

def _make_icon(color: str, size: int = 16):
    img = tk.PhotoImage(width=size, height=size)
    for y in range(size):
        img.put(color, to=(0, y, size, y+1))
    return img

def create_icons(root):
    # Create small, consistent 16x16 solid icons with semantic colors
    # Keep references on caller to avoid GC
    return {
        'dashboard': _make_icon('#0a84ff'),   # blue
        'bills': _make_icon('#8e8e93'),       # gray
        'record': _make_icon('#34c759'),      # green
        'import': _make_icon('#5e5ce6'),      # purple
        'import_ai': _make_icon('#ff9f0a'),   # orange
        'accounts': _make_icon('#5856d6'),    # indigo
        'export': _make_icon('#64d2ff'),      # light blue
        'template': _make_icon('#6e6e73'),    # slate
        'backup': _make_icon('#ffd60a'),      # yellow
        'refresh': _make_icon('#8e8e93'),     # gray
    }
