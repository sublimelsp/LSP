#!/usr/bin/env python
import gi
import sys
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Gdk

color_chooser_dialog = Gtk.ColorChooserDialog(show_editor=True)
color_chooser_dialog.set_title('LSP Color Picker')

if len(sys.argv) > 1: # sys.argv[1] looks like '1,0.2,1,0.5'
    r, g, b, a = sys.argv[1].split(',')
    r = float(r or 0)
    g = float(g or 0)
    b = float(b or 0)
    a = float(a or 0)
    preselect_color = Gdk.RGBA(r, g, b, a)
    color_chooser_dialog.set_rgba(preselect_color)


def on_select_color():
    color = color_chooser_dialog.get_rgba()
    red = int(color.red * 255)
    green = int(color.green * 255)
    blue = int(color.blue * 255)
    alpha = int(color.alpha * 255)
    if alpha < 255:
        print('#%02x%02x%02x%02x' % (red, green, blue, alpha))
    else:
        print('#%02x%02x%02x' % (red, green, blue))

if color_chooser_dialog.run() == Gtk.ResponseType.OK:
    on_select_color()

color_chooser_dialog.destroy()
