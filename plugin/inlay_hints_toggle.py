from .core.settings import userprefs
from .core.typing import Literal, Union
import sublime

ToggleInlayHintStrategy = Literal["current_view", "current_window", "all_windows"]


class InlayHints:
    toggle_strategy = "current_view"  # type: ToggleInlayHintStrategy
    global_show_inlay_hints = False

    @staticmethod
    def get_target(v: sublime.View) -> Union[sublime.View, sublime.Window]:
        if InlayHints.toggle_strategy == 'current_window':
            w = v.window()
            if not w:
                raise Exception('no window')
            return w
        return v

    @staticmethod
    def are_enabled(v: sublime.View) -> bool:
        if InlayHints.toggle_strategy == 'all_windows':
            return InlayHints.global_show_inlay_hints
        target = InlayHints.get_target(v)
        return target.settings().get('lsp_show_inlay_hints') or userprefs().show_inlay_hints

    @staticmethod
    def toggle(v: sublime.View) -> None:
        if InlayHints.toggle_strategy == 'all_windows':
            InlayHints.global_show_inlay_hints = not InlayHints.global_show_inlay_hints
            return
        target = InlayHints.get_target(v)
        target.settings().set('lsp_show_inlay_hints', not InlayHints.are_enabled(v))
