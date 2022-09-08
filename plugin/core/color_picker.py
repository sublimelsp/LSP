from abc import ABCMeta
import threading
import subprocess

import os

from .protocol import Color
from .typing import Callable, Union, Optional
import sublime
import sublime_plugin

ColorPickResult = Union[Color, None]  # str - if a color is selected, else None
OnPickCallback = Callable[[ColorPickResult], None]


class ColorPickerPlugin(metaclass=ABCMeta):
    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        ...

    def normalize_color(self, color: str) -> Optional[Color]:
        ...

    def close(self) -> None:
        ...



class LinuxColorPicker(ColorPickerPlugin):
    process = None  # type: Optional[subprocess.Popen]

    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        t = threading.Thread(target=self._open_picker, args=(on_pick, preselect_color))
        t.start()

    def _open_picker(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        color_arg = ""
        if preselect_color:
            color_arg = "{},{},{},{}".format(preselect_color['red'], preselect_color['green'], preselect_color['blue'], preselect_color['alpha'])
        picker_cmd = [os.path.join(sublime.packages_path(), "LSP", "color_pickers", "linux_executable.py"), color_arg]
        self.process = subprocess.Popen(picker_cmd, stdout=subprocess.PIPE)
        output = self.process.communicate()[0].strip().decode('utf-8')
        on_pick(self.normalize_color(output))

    def normalize_color(self, color: str) -> Optional[Color]:
        if not color:
            return None
        r, g, b, a = color.split(',')
        r = float(r)
        g = float(g)
        b = float(b)
        a = float(a)
        return {
            "red": r,
            "green": g,
            "blue": b,
            "alpha": a,
        }

    def close(self) -> None:
        if self.process:
            self.process.kill()
            self.process = None


class WindowsColorPicker(ColorPickerPlugin):
    process = None  # type: Optional[subprocess.Popen]

    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        t = threading.Thread(target=self._open_picker, args=(on_pick, preselect_color))
        t.start()

    def _open_picker(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        color_arg = ""
        if preselect_color:
            color_arg = "{},{},{},{}".format(preselect_color['red'], preselect_color['green'], preselect_color['blue'], preselect_color['alpha'])
        picker_cmd = [os.path.join(sublime.packages_path(), "LSP", "color_pickers", "win_colorpicker.exe"), color_arg]
        self.process = subprocess.Popen(picker_cmd, stdout=subprocess.PIPE)
        output = self.process.communicate()[0].strip().decode('utf-8')
        on_pick(self.normalize_color(output))

    def normalize_color(self, color: str) -> Optional[Color]:
        return {
            "red": 1,
            "green": 1,
            "blue": 1,
            "alpha": 1
        }

    def close(self) -> None:
        if self.process:
            self.process.kill()
            self.process = None


def get_color_picker() -> Optional[ColorPickerPlugin]:
    if sublime.platform() == "linux":
        return LinuxColorPicker()
    if sublime.platform() == "windows":
        return WindowsColorPicker()
    if sublime.platform() == "osx":
        return None
    return None


color_picker = get_color_picker()


class CloseColorPickerOnBlur(sublime_plugin.EventListener):
    def on_activated(self, view: sublime.View) -> None:
        if color_picker:
            color_picker.close()

    def on_exit(self) -> None:
        if color_picker:
            color_picker.close()
