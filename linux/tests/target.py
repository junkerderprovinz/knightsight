"""A plain coloured window that writes down every click, wheel turn and key it gets."""

import sys
import tkinter as tk

log_path, title, color, place = sys.argv[1:5]
log = open(log_path, "a", buffering=1)
root = tk.Tk()
root.title(title)
root.geometry("400x300" + place)
tk.Canvas(root, bg=color, highlightthickness=0).pack(fill="both", expand=True)
root.bind("<ButtonPress>", lambda e: log.write(f"{title} button {e.num} {e.x} {e.y}\n"))
root.bind("<KeyPress>", lambda e: log.write(f"{title} key {e.keysym}{' ctrl' if e.state & 4 else ''}\n"))
root.mainloop()
