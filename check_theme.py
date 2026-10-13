"""Diagnostic: print the current theme mode and resolved colors."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.theme import theme
t = theme()
print("mode:      ", t.mode)
print("bg:        ", t.color("bg"))
print("surface:   ", t.color("surface"))
print("nav_bg:    ", t.color("nav_bg"))
print("topbar_bg: ", t.color("topbar_bg"))
print("text:      ", t.color("text"))
print("border:    ", t.color("border"))