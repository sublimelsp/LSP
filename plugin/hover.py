import mdpopups
import sublime
import sublime_plugin
import webbrowser
from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .code_actions import run_code_action_or_command
from .core.css import css
from .core.logging import debug
from .core.protocol import Request, Diagnostic
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.settings import userprefs
from .core.typing import List, Optional, Any, Dict
from .core.views import format_diagnostic_for_html
from .core.views import FORMAT_MARKED_STRING, FORMAT_MARKUP_CONTENT, minihtml
from .core.views import make_command_link
from .core.views import make_link
from .core.views import offset_to_point
from .core.views import text_document_position_params
from .diagnostics import filter_by_point, view_diagnostics


SUBLIME_WORD_MASK = 515


_test_contents = []  # type: List[str]


class LinkKind:

    __slots__ = ("lsp_name", "label", "subl_cmd_name", "supports_side_by_side")

    def __init__(self, lsp_name: str, label: str, subl_cmd_name: str, supports_side_by_side: bool) -> None:
        self.lsp_name = lsp_name
        self.label = label
        self.subl_cmd_name = subl_cmd_name
        self.supports_side_by_side = supports_side_by_side


link_kinds = [
    LinkKind("definition", "Definition", "lsp_symbol_definition", True),
    LinkKind("typeDefinition", "Type Definition", "lsp_symbol_type_definition", True),
    LinkKind("declaration", "Declaration", "lsp_symbol_declaration", True),
    LinkKind("implementation", "Implementation", "lsp_symbol_implementation", True),
    LinkKind("references", "References", "lsp_symbol_references", False),
    LinkKind("rename", "Rename", "lsp_symbol_rename", False),
]


class LspHoverCommand(LspTextCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._base_dir = None   # type: Optional[str]

    def is_likely_at_symbol(self, point: int) -> bool:
        word_at_sel = self.view.classify(point)
        return bool(word_at_sel & SUBLIME_WORD_MASK)

    def run(self, edit: sublime.Edit, point: Optional[int] = None, event: Optional[dict] = None) -> None:
        hover_point = point or self.view.sel()[0].begin()
        window = self.view.window()
        if not window:
            return
        self._base_dir = windows.lookup(window).get_project_path(self.view.file_name() or "")

        self._hover = None  # type: Optional[Any]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = {}  # type: Dict[str, List[Diagnostic]]

        if self.is_likely_at_symbol(hover_point):
            self.request_symbol_hover(hover_point)

        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.
        request_point = offset_to_point(self.view, hover_point)
        self._diagnostics_by_config, code_actions_range = filter_by_point(view_diagnostics(self.view), request_point)
        if self._diagnostics_by_config:
            actions_manager.request_with_diagnostics(
                self.view, code_actions_range, self._diagnostics_by_config,
                lambda response: self.handle_code_actions(response, hover_point))
            self.show_hover(hover_point)

    def request_symbol_hover(self, point: int) -> None:
        session = self.best_session('hoverProvider', point)
        if session:
            document_position = text_document_position_params(self.view, point)
            session.send_request(
                Request.hover(document_position),
                lambda response: self.handle_response(response, point))

    def handle_code_actions(self, responses: Dict[str, List[CodeActionOrCommand]], point: int) -> None:
        self._actions_by_config = responses
        self.show_hover(point)

    def handle_response(self, response: Optional[Any], point: int) -> None:
        self._hover = response
        self.show_hover(point)

    def symbol_actions_content(self, point: int) -> str:
        if userprefs().show_symbol_action_links:
            actions = []
            for link_kind in link_kinds:
                if self.best_session('{}Provider'.format(link_kind.lsp_name)):
                    command = 'lsp_run_command_from_point'
                    args = {
                        'command_name': link_kind.subl_cmd_name,
                        'point': point,
                    }
                    link = make_command_link(command, link_kind.label, args)
                    if link_kind.supports_side_by_side:
                        args['command_args'] = {'side_by_side': True}
                        link += ' ' + make_command_link(command, '◨', args, 'icon')
                    actions.append(link)
            if actions:
                return "<p class='actions'>" + " | ".join(actions) + "</p>"
        return ""

    def diagnostics_content(self) -> str:
        formatted = []
        for config_name in self._diagnostics_by_config:
            by_severity = {}  # type: Dict[int, List[str]]
            formatted.append("<div class='diagnostics'>")
            for diagnostic in self._diagnostics_by_config[config_name]:
                by_severity.setdefault(diagnostic.severity, []).append(
                    format_diagnostic_for_html(diagnostic, self._base_dir))

            for severity, items in by_severity.items():
                formatted.append("<div>")
                formatted.extend(items)
                formatted.append("</div>")

            if config_name in self._actions_by_config:
                action_count = len(self._actions_by_config[config_name])
                if action_count > 0:
                    href = "{}:{}".format('code-actions', config_name)
                    text = "{} ({})".format('Code Actions', action_count)
                    formatted.append("<div class=\"actions\">{}</div>".format(make_link(href, text)))

            formatted.append("</div>")

        return "".join(formatted)

    def hover_content(self) -> str:
        content = (self._hover.get('contents') or '') if isinstance(self._hover, dict) else ''
        return minihtml(self.view, content, allowed_formats=FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT)

    def show_hover(self, point: int) -> None:
        sublime.set_timeout(lambda: self._show_hover(point))

    def _show_hover(self, point: int) -> None:
        contents = self.diagnostics_content() + self.hover_content()
        if contents:
            contents += self.symbol_actions_content(point)

        _test_contents.clear()
        _test_contents.append(contents)  # for testing only

        if contents:
            if self.view.is_popup_visible():
                mdpopups.update_popup(
                    self.view,
                    contents,
                    css=css().popups,
                    md=False,
                    wrapper_class=css().popups_classname)
            else:
                mdpopups.show_popup(
                    self.view,
                    contents,
                    css=css().popups,
                    md=False,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    wrapper_class=css().popups_classname,
                    max_width=800,
                    on_navigate=lambda href: self._on_navigate(href, point))

    def _on_navigate(self, href: str, point: int) -> None:
        if href.startswith("subl:"):
            pass
        elif href.startswith('code-actions:'):
            _, config_name = href.split(":")
            titles = [command["title"] for command in self._actions_by_config[config_name]]
            sel = self.view.sel()
            sel.clear()
            sel.add(sublime.Region(point, point))
            self.view.show_popup_menu(titles, lambda i: self.handle_code_action_select(config_name, i))
        elif href.startswith("file://"):
            window = self.view.window()
            if window:
                window.open_file(href[len("file://"):], flags=sublime.ENCODED_POSITION)
        else:
            if not (href.lower().startswith("http://") or href.lower().startswith("https://")):
                href = "http://" + href
            if not webbrowser.open(href):
                debug("failed to open:", href)

    def handle_code_action_select(self, config_name: str, index: int) -> None:
        if index > -1:
            selected = self._actions_by_config[config_name][index]
            run_code_action_or_command(self.view, config_name, selected)


class LspRunCommandFromPointCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, point: int, command_name: str, command_args: Optional[dict] = None) -> None:
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command(command_name, command_args)
