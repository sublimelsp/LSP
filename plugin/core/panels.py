from .typing import Dict, Optional, List, Generator, Tuple
from contextlib import contextmanager
import sublime
import sublime_plugin


# about 80 chars per line implies maintaining a buffer of about 40kb per window
LOG_PANEL_MAX_LINES = 500

OUTPUT_PANEL_SETTINGS = {
    "auto_indent": False,
    "draw_indent_guides": False,
    "draw_unicode_white_space": "none",
    "draw_white_space": "none",
    "fold_buttons": True,
    "gutter": True,
    "is_widget": True,
    "line_numbers": False,
    "lsp_active": True,
    "margin": 3,
    "match_brackets": False,
    "rulers": [],
    "scroll_past_end": False,
    "show_definitions": False,
    "tab_size": 4,
    "translate_tabs_to_spaces": False,
    "word_wrap": False
}


class PanelName:
    Diagnostics = "diagnostics"
    References = "references"
    Rename = "rename"
    Log = "LSP Log Panel"


@contextmanager
def mutable(view: sublime.View) -> Generator:
    view.set_read_only(False)
    yield
    view.set_read_only(True)


def clear_undo_stack(view: sublime.View) -> None:
    clear_undo_stack = getattr(view, "clear_undo_stack", None)
    if not callable(clear_undo_stack):
        return
    # The clear_undo_stack method cannot be called from within a text command...
    sublime.set_timeout(clear_undo_stack)


class WindowPanelListener(sublime_plugin.EventListener):

    server_log_map = {}  # type: Dict[int, List[Tuple[str, str]]]

    def on_init(self, views: List[sublime.View]) -> None:
        for window in sublime.windows():
            self.server_log_map[window.id()] = []

    def on_new_window(self, window: sublime.Window) -> None:
        self.server_log_map[window.id()] = []

    def on_pre_close_window(self, window: sublime.Window) -> None:
        self.server_log_map.pop(window.id())

    def on_window_command(self, window: sublime.Window, command_name: str, args: Dict) -> None:
        if command_name in ('show_panel', 'hide_panel'):
            sublime.set_timeout(lambda: self.maybe_update_log_panel(window))

    def maybe_update_log_panel(self, window: sublime.Window) -> None:
        if is_log_panel_open(window):
            panel = ensure_log_panel(window)
            if panel:
                update_log_panel(panel, window.id())


def create_output_panel(window: sublime.Window, name: str) -> Optional[sublime.View]:
    panel = window.create_output_panel(name)
    settings = panel.settings()
    for key, value in OUTPUT_PANEL_SETTINGS.items():
        settings.set(key, value)
    return panel


def destroy_output_panels(window: sublime.Window) -> None:
    for field in filter(lambda a: not a.startswith('__'), PanelName.__dict__.keys()):
        panel_name = getattr(PanelName, field)
        panel = window.find_output_panel(panel_name)
        if panel and panel.is_valid():
            panel.settings().set("syntax", "Packages/Text/Plain text.tmLanguage")
            window.destroy_output_panel(panel_name)


def create_panel(window: sublime.Window, name: str, result_file_regex: str, result_line_regex: str,
                 syntax: str, context_menu: Optional[str] = None) -> Optional[sublime.View]:
    panel = create_output_panel(window, name)
    if not panel:
        return None
    settings = panel.settings()
    if result_file_regex:
        settings.set("result_file_regex", result_file_regex)
    if result_line_regex:
        settings.set("result_line_regex", result_line_regex)
    if context_menu:
        settings.set("context_menu", context_menu)
    panel.assign_syntax(syntax)
    # Call create_output_panel a second time after assigning the above settings, so that it'll be picked up
    # as a result buffer. See: Packages/Default/exec.py#L228-L230
    panel = window.create_output_panel(name)
    if panel:
        # All our panels are read-only
        panel.set_read_only(True)
    return panel


def ensure_panel(window: sublime.Window, name: str, result_file_regex: str, result_line_regex: str,
                 syntax: str, context_menu: Optional[str] = None) -> Optional[sublime.View]:
    return window.find_output_panel(name) or \
        create_panel(window, name, result_file_regex, result_line_regex, syntax, context_menu)


class LspClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """
    def run(self, edit: sublime.Edit) -> None:
        with mutable(self.view):
            self.view.erase(edit, sublime.Region(0, self.view.size()))


class LspUpdatePanelCommand(sublime_plugin.TextCommand):
    """
    A update_panel command to update the error panel with new text.
    """

    def run(self, edit: sublime.Edit, characters: Optional[str] = "") -> None:
        # Clear folds
        self.view.unfold(sublime.Region(0, self.view.size()))

        with mutable(self.view):
            self.view.replace(edit, sublime.Region(0, self.view.size()), characters or "")

        # Clear the selection
        selection = self.view.sel()
        selection.clear()
        clear_undo_stack(self.view)


def ensure_log_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, PanelName.Log, "", "", "Packages/LSP/Syntaxes/ServerLog.sublime-syntax",
                        "Context LSP Log Panel.sublime-menu")


def is_log_panel_open(window: sublime.Window) -> bool:
    return window.is_valid() and window.active_panel() == "output.{}".format(PanelName.Log)


def log_server_message(window: sublime.Window, prefix: str, message: str) -> None:
    window_id = window.id()
    if not window.is_valid() or window_id not in WindowPanelListener.server_log_map:
        return
    WindowPanelListener.server_log_map[window_id].append((prefix, message))
    list_len = len(WindowPanelListener.server_log_map[window_id])
    if list_len >= LOG_PANEL_MAX_LINES:
        # Trim leading items in the list, leaving only the max allowed count.
        del WindowPanelListener.server_log_map[window_id][:list_len - LOG_PANEL_MAX_LINES]
    panel = ensure_log_panel(window)
    if is_log_panel_open(window) and panel:
        update_log_panel(panel, window_id)


def update_log_panel(panel: sublime.View, window_id: int) -> None:
    panel.run_command("lsp_update_log_panel", {"window_id": window_id})


class LspUpdateLogPanelCommand(sublime_plugin.TextCommand):

    def run(self, edit: sublime.Edit, window_id: int) -> None:
        to_process = WindowPanelListener.server_log_map.get(window_id) or []
        WindowPanelListener.server_log_map[window_id] = []
        with mutable(self.view):
            new_lines = []
            for prefix, message in to_process:
                message = message.replace("\r\n", "\n")  # normalize Windows eol
                new_lines.append("{}: {}\n".format(prefix, message))
            if new_lines:
                self.view.insert(edit, self.view.size(), ''.join(new_lines))
                last_region_end = 0  # Starting from point 0 in the panel ...
                total_lines, _ = self.view.rowcol(self.view.size())
                for _ in range(0, max(0, total_lines - LOG_PANEL_MAX_LINES)):
                    # ... collect all regions that span an entire line ...
                    region = self.view.full_line(last_region_end)
                    last_region_end = region.b
                erase_region = sublime.Region(0, last_region_end)
                if not erase_region.empty():
                    self.view.erase(edit, erase_region)
        clear_undo_stack(self.view)


class LspClearLogPanelCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        window = self.view.window()
        if not window:
            return
        panel = ensure_log_panel(window)
        if panel:
            panel.run_command("lsp_clear_panel")

    def is_visible(self) -> bool:
        window = self.view.window()
        if not window:
            return False
        return ensure_log_panel(window) == self.view
