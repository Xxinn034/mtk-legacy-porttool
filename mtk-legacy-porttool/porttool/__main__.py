#!/usr/bin/env python3
from tkinterdnd2 import TkinterDnD
from .ui import MainApp
from os import name

if name == 'nt':
    import ctypes
    from multiprocessing.dummy import freeze_support
    freeze_support()

def main():
    root = TkinterDnD.Tk()
    if name == 'nt':
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0)
        root.tk.call('tk', 'scaling', scale_factor / 75)
    app = MainApp(root)
    root.mainloop()