from abc import ABCMeta
import threading
import subprocess

import os

from .protocol import ColorInformation
from .typing import Callable, Union, Optional
import sublime
import sublime_plugin

ColorPickResult = Union[str, None]  # str - if a color is selected, else None
OnPickCallback = Callable[[ColorPickResult], None]


class ColorPickerPlugin(metaclass=ABCMeta):
    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[ColorInformation] = None) -> None:
        ...

    def close(self) -> None:
        ...


class LinuxColorPicker(ColorPickerPlugin):
    process = None  # type: Optional[subprocess.Popen]

    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[ColorInformation] = None) -> None:
        t = threading.Thread(target=self._open_picker, args=(on_pick, preselect_color))
        t.start()

    def _open_picker(self, on_pick: OnPickCallback, color_information: Optional[ColorInformation] = None) -> None:
        preselect_color = ""
        if color_information:
            value = color_information['color']
            preselect_color = "{},{},{},{}".format(value['red'], value['green'], value['blue'], value['alpha'])
        picker_cmd = [os.path.join(sublime.packages_path(), "LSP", "color_pickers", "linux.py"), preselect_color]
        self.process = subprocess.Popen(picker_cmd, stdout=subprocess.PIPE)
        color = self.process.communicate()[0].strip().decode('utf-8')
        on_pick(color or None)

    def close(self) -> None:
        if self.process:
            self.process.kill()
            self.process = None


def get_color_picker() -> Optional[ColorPickerPlugin]:
    if sublime.platform() == "linux":
        return LinuxColorPicker()
    if sublime.platform() == "windows":
        return None
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
