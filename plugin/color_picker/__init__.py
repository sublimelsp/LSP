from ..core.protocol import Color, TextEdit, ColorInformation
from ..core.typing import Callable, Optional, List, Any
from ..core.views import lsp_color_to_hex
from ..formatting import apply_text_edits_to_view
from abc import ABCMeta
import sublime
import sublime_plugin
import subprocess
import threading
import os

OnPickCallback = Callable[[Optional[Color]], None]


class ColorPickerPlugin(metaclass=ABCMeta):
    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        ...

    def normalize_color(self, color: Any) -> Optional[Color]:
        ...

    def close(self) -> None:
        ...


class LinuxColorPicker(ColorPickerPlugin):
    process = None  # type: Optional[subprocess.Popen]

    def pick(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
        t = threading.Thread(target=self._open_picker, args=(on_pick, preselect_color))
        t.start()

    def _open_picker(self, on_pick: OnPickCallback, color: Optional[Color] = None) -> None:
        preselect_color_arg = ""
        if color:
            preselect_color_arg = "{},{},{},{}".format(
                color['red'], color['green'], color['blue'], color['alpha']
            )
        picker_cmd = [
            os.path.join(sublime.packages_path(), "LSP", "plugin", "color_picker", "linux_executable.py"),
            preselect_color_arg
        ]
        self.process = subprocess.Popen(picker_cmd, stdout=subprocess.PIPE)
        output = self.process.communicate()[0].strip().decode('utf-8')
        on_pick(self.normalize_color(output))

    def normalize_color(self, color: Any) -> Optional[Color]:
        if isinstance(color, str):
            r, g, b, a = map(float, color.split(','))
            return {
                "red": r,
                "green": g,
                "blue": b,
                "alpha": a,
            }
        return None

    def close(self) -> None:
        if self.process:
            self.process.kill()
            self.process = None


if sublime.platform() == "windows":
    import ctypes

    class CHOOSECOLOR(ctypes.Structure):
        _fields_ = [
            ("lStructSize", ctypes.c_uint32),
            ("hwndOwner", ctypes.c_void_p),
            ("hInstance", ctypes.c_void_p),
            ("rgbResult", ctypes.c_uint32),
            ("lpCustColors", ctypes.POINTER(ctypes.c_uint32)),
            ("Flags", ctypes.c_uint32),
            ("lCustData", ctypes.c_void_p),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", ctypes.c_wchar_p)]

    CC_SOLIDCOLOR = 0x80
    CC_RGBINIT = 0x01
    CC_FULLOPEN = 0x02
    ChooseColorW = ctypes.windll.Comdlg32.ChooseColorW
    ChooseColorW.argtypes = [ctypes.POINTER(CHOOSECOLOR)]
    ChooseColorW.restype = ctypes.c_int32


    class WindowsColorPicker(ColorPickerPlugin):
        process = None  # type: Optional[subprocess.Popen]

        def pick(self, on_pick: OnPickCallback, preselect_color: Optional[Color] = None) -> None:
            t = threading.Thread(target=self._open_picker, args=(on_pick, preselect_color))
            t.start()

        def _open_picker(self, on_pick: OnPickCallback, color: Optional[Color] = None) -> None:
            default_color = (255 << 16) | (255 << 8) | (255)
            if color:
                default_color = (round(255*color['blue']) << 16) | (round(255*color['green']) << 8) | round(255*color['red'])
            cc = CHOOSECOLOR()
            ctypes.memset(ctypes.byref(cc), 0, ctypes.sizeof(cc))
            cc.lStructSize = ctypes.sizeof(cc)
            cc.hwndOwner = sublime.active_window().hwnd()
            CustomColors = ctypes.c_uint32 * 16
            cc.lpCustColors = CustomColors() # uses 0 (black) for all 16 predefined custom colors
            cc.rgbResult = ctypes.c_uint32(default_color)
            cc.Flags = CC_SOLIDCOLOR | CC_FULLOPEN | CC_RGBINIT

            # ST window will become unresponsive until color picker dialog is closed
            output = ChooseColorW(ctypes.byref(cc))

            if output == 1: # user clicked OK
                on_pick(self.normalize_color(cc.rgbResult))
            else:
                on_pick(None)

        def normalize_color(self, bgr_color: Any) -> Optional[Color]:

            def bgr2color(bgr) -> Color:
                # 0x00BBGGRR
                byte_table = list(["{0:02X}".format(b) for b in range(256)])
                b_hex = byte_table[(bgr >> 16) & 0xff]
                g_hex = byte_table[(bgr >> 8) & 0xff]
                r_hex = byte_table[(bgr) & 0xff]

                r = int(r_hex, 16) / 255
                g = int(g_hex, 16) / 255
                b = int(b_hex, 16) / 255
                return {
                    "red": r,
                    "green": g,
                    "blue": b,
                    "alpha": 1  # windows picker doesn't support alpha, so fallback to 1
                }

            if bgr_color:
                return bgr2color(bgr_color)
            return None

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


class LspChooseColorPicker(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, color_information: ColorInformation, file_name: str) -> None:
        if not color_picker:
            sublime.status_message('Your platform does not support a ColorPicker yet.')
            return
        window = self.view.window()
        if not window:
            return

        def on_select(color: Optional[Color]) -> None:
            self.on_pick_color(color, color_information, file_name)

        color_picker.pick(on_select, color_information['color'])

    def on_pick_color(
        self, selected_color: Optional[Color], color_information: ColorInformation, file_name: str
    ) -> None:
        if not selected_color:
            return
        window = self.view.window()
        if not window:
            return
        view = window.find_open_file(file_name)
        new_text = lsp_color_to_hex(selected_color)
        text_edits = [{
            "newText": new_text,
            "range": color_information['range']
        }]  # type: List[TextEdit]
        if view:
            apply_text_edits_to_view(text_edits, view)
