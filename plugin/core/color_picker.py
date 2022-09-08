import threading
import subprocess

import os

from .protocol import ColorInformation
from .typing import Callable, Union, Optional
import sublime
import sublime_plugin

ColorPickResult = Union[str, None]  # str - if a color is selected, else None
OnPickCallback = Callable[[ColorPickResult], None]


class ColorPicker:
    process = None  # type: Optional[subprocess.Popen]

    @classmethod
    def pick(cls,on_pick: OnPickCallback, preselect_color: Optional[ColorInformation] = None) -> None:
        t = threading.Thread(target=cls._open_picker, args=(on_pick, preselect_color))
        t.start()

    @classmethod
    def _open_picker(cls, on_pick: OnPickCallback, color_information: Optional[ColorInformation] = None) -> None:
        preselect_color = ""
        if color_information:
            color = color_information['color']
            preselect_color = "{},{},{},{}".format(color['red'], color['green'], color['blue'], color['alpha'])
        picker_cmd = [os.path.join(sublime.packages_path(), "LSP", "color_pickers", "linux.py"), preselect_color]
        cls.process = subprocess.Popen(picker_cmd, stdout=subprocess.PIPE)
        color = cls.process.communicate()[0].strip().decode('utf-8')
        on_pick(color or None)

    @classmethod
    def close(cls):
        if cls.process:
            cls.process.kill()
            cls.process = None


class CloseColorPickerOnBlur(sublime_plugin.EventListener):
    def on_activated(self, view: sublime.View):
        ColorPicker.close()

    def on_exit(self):
        ColorPicker.close()