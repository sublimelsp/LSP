import mdpopups
import sublime
import webbrowser
from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .core.css import css
from .core.logging import debug
from .core.protocol import Diagnostic
from .core.protocol import Request
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

    def link(self, point: int, view: sublime.View) -> str:
        args = {'point': point}
        link = make_command_link(self.subl_cmd_name, self.label, args, None, view)
        if self.supports_side_by_side:
            args['side_by_side'] = True
            link += ' ' + make_command_link(self.subl_cmd_name, '◨', args, 'icon', view)
        return link


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

    def run(self, edit: sublime.Edit, point: Optional[int] = None, event: Optional[dict] = None) -> None:
        hover_point = point or self.view.sel()[0].begin()
        window = self.view.window()
        if not window:
            return
        self._base_dir = windows.lookup(window).get_project_path(self.view.file_name() or "")
        self._hover = None  # type: Optional[Any]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = {}  # type: Dict[str, List[Diagnostic]]
        self.request_symbol_hover(hover_point)
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.
        request_point = offset_to_point(self.view, hover_point)

        def run_async() -> None:
            self._diagnostics_by_config, code_actions_range = filter_by_point(
                view_diagnostics(self.view), request_point)
            if self._diagnostics_by_config:
                actions_manager.request_with_diagnostics_async(
                    self.view, code_actions_range, self._diagnostics_by_config,
                    lambda response: self.handle_code_actions(response, hover_point))
                self.show_hover(hover_point)

        sublime.set_timeout_async(run_async)

    def request_symbol_hover(self, point: int) -> None:
        session = self.best_session('hoverProvider', point)
        if session:
            document_position = text_document_position_params(self.view, point, session.config)
            session.send_request(
                Request.hover(document_position, self.view),
                lambda response: self.handle_response(response, point))

    def handle_code_actions(self, responses: Dict[str, List[CodeActionOrCommand]], point: int) -> None:
        self._actions_by_config = responses
        self.show_hover(point)

    def handle_response(self, response: Optional[Any], point: int) -> None:
        self._hover = response
        self.show_hover(point)

    def provider_exists(self, link: LinkKind) -> bool:
        return bool(self.best_session('{}Provider'.format(link.lsp_name)))

    def symbol_actions_content(self, point: int) -> str:
        if userprefs().show_symbol_action_links:
            actions = [lk.link(point, self.view) for lk in link_kinds if self.provider_exists(lk)]
            if actions:
                return '<div class="actions">' + " | ".join(actions) + "</div>"
        return ""

    def diagnostics_content(self) -> str:
        formatted = []
        for config_name in self._diagnostics_by_config:
            by_severity = {}  # type: Dict[int, List[str]]
            formatted.append('<div class="diagnostics">')
            for diagnostic in self._diagnostics_by_config[config_name]:
                by_severity.setdefault(diagnostic.severity, []).append(
                    format_diagnostic_for_html(self.view, diagnostic, self._base_dir))
            for items in by_severity.values():
                formatted.extend(items)
            if config_name in self._actions_by_config:
                action_count = len(self._actions_by_config[config_name])
                if action_count > 0:
                    href = "{}:{}".format('code-actions', config_name)
                    text = "choose code action ({} available)".format(action_count)
                    formatted.append('<div class="actions">[{}] {}</div>'.format(config_name, make_link(href, text)))
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
            self.view.run_command("lsp_selection_set", {"regions": [(point, point)]})
            self.view.show_popup_menu(titles, lambda i: self.handle_code_action_select(config_name, i))
        elif href.startswith("location:"):
            window = self.view.window()
            if window:
                window.open_file(href[len("location:"):], flags=sublime.ENCODED_POSITION)
        else:
            # NOTE: Remove this check when on py3.8.
            if not (href.lower().startswith("http://") or href.lower().startswith("https://")):
                href = "http://" + href
            if not webbrowser.open(href):
                debug("failed to open:", href)

    def handle_code_action_select(self, config_name: str, index: int) -> None:
        if index > -1:

            def run_async() -> None:
                session = self.session_by_name(config_name)
                if session:
                    session.run_code_action_async(self._actions_by_config[config_name][index])

            sublime.set_timeout_async(run_async)
