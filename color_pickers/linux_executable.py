#!/usr/bin/env python
import gi
import sys
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Gdk

color_chooser_dialog = Gtk.ColorChooserDialog(show_editor=True)
color_chooser_dialog.set_title('LSP Color Picker')

if len(sys.argv) > 1: # sys.argv[1] looks like '1,0.2,1,0.5'
    r, g, b, a = map(lambda color: float(color or 0), sys.argv[1].split(','))
    preselect_color = Gdk.RGBA(r, g, b, a)
    color_chooser_dialog.set_rgba(preselect_color)

def on_select_color():
    color = color_chooser_dialog.get_rgba()
    print('{},{},{},{}'.format(color.red, color.green, color.blue, color.alpha))

if color_chooser_dialog.run() == Gtk.ResponseType.OK:
    on_select_color()

color_chooser_dialog.destroy()
