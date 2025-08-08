import tkinter as tk
from PIL import Image, ImageTk
from interface import TelloGUI

root = tk.Tk()
app = TelloGUI(root)
root.mainloop()