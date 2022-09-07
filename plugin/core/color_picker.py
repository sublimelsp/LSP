try:
    from ColorPicker.sublimecp import ColorPicker as Picker
except ImportError:
    Picker = None

import threading
from .typing import Callable, Union
import sublime

ColorPickResult = Union[str, None]  # str - if a color is selected, else None
OnPickCallback = Callable[[ColorPickResult], None]


class ColorPicker:
    @classmethod
    def is_enabled(cls) -> bool:
        return bool(Picker)

    @classmethod
    def pick(cls, window: sublime.Window, on_pick: OnPickCallback) -> None:
        t = threading.Thread(target=open_picker, args=(on_pick, window))
        t.start()


def open_picker(on_pick, window):
    if not Picker:
        return
    color_picker = Picker()
    color = color_picker.pick(window)
    if sublime.platform() == 'linux' and isinstance(color, str):
        color = '#' + color
    on_pick(color or None)