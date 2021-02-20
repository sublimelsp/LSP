from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .core.logging import debug
from .core.protocol import Diagnostic
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.typing import List, Optional, Any, Dict, Tuple, Sequence
from .core.views import diagnostic_severity
from .core.views import format_diagnostic_for_html
from .core.views import FORMAT_MARKED_STRING, FORMAT_MARKUP_CONTENT, minihtml
from .core.views import make_command_link
from .core.views import make_link
from .core.views import show_lsp_popup
from .core.views import text_document_position_params
from .core.views import update_lsp_popup
from .core.windows import AbstractViewListener
import functools
import sublime
import webbrowser


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

    def run(
        self,
        edit: sublime.Edit,
        only_diagnostics: bool = False,
        point: Optional[int] = None,
        event: Optional[dict] = None
    ) -> None:
        hover_point = point or self.view.sel()[0].begin()
        window = self.view.window()
        if not window:
            return
        wm = windows.lookup(window)
        self._base_dir = wm.get_project_path(self.view.file_name() or "")
        self._hover = None  # type: Optional[Any]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = []  # type: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]]
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_symbol_hover(listener, hover_point)
            self._diagnostics_by_config, covering = listener.diagnostics_touching_point_async(hover_point)
            if self._diagnostics_by_config:
                if not only_diagnostics:
                    actions_manager.request_with_diagnostics_async(
                        self.view, covering, self._diagnostics_by_config,
                        functools.partial(self.handle_code_actions, listener, hover_point))
                self.show_hover(listener, hover_point, only_diagnostics)

        sublime.set_timeout_async(run_async)

    def request_symbol_hover(self, listener: AbstractViewListener, point: int) -> None:
        session = listener.session('hoverProvider', point)
        if session:
            document_position = text_document_position_params(self.view, point)
            session.send_request(
                Request("textDocument/hover", document_position, self.view),
                lambda response: self.handle_response(listener, response, point))

    def handle_code_actions(
        self,
        listener: AbstractViewListener,
        point: int,
        responses: Dict[str, List[CodeActionOrCommand]]
    ) -> None:
        self._actions_by_config = responses
        self.show_hover(listener, point, only_diagnostics=False)

    def handle_response(self, listener: AbstractViewListener, response: Optional[Any], point: int) -> None:
        self._hover = response
        self.show_hover(listener, point, only_diagnostics=False)

    def provider_exists(self, listener: AbstractViewListener, link: LinkKind) -> bool:
        return bool(listener.session('{}Provider'.format(link.lsp_name)))

    def symbol_actions_content(self, listener: AbstractViewListener, point: int) -> str:
        if userprefs().show_symbol_action_links:
            actions = [lk.link(point, self.view) for lk in link_kinds if self.provider_exists(listener, lk)]
            if actions:
                return '<div class="actions">' + " | ".join(actions) + "</div>"
        return ""

    def diagnostics_content(self) -> str:
        formatted = []
        for sb, diagnostics in self._diagnostics_by_config:
            by_severity = {}  # type: Dict[int, List[str]]
            formatted.append('<div class="diagnostics">')
            for diagnostic in diagnostics:
                by_severity.setdefault(diagnostic_severity(diagnostic), []).append(
                    format_diagnostic_for_html(self.view, diagnostic, self._base_dir))
            for items in by_severity.values():
                formatted.extend(items)
            config_name = sb.session.config.name
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

    def show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        sublime.set_timeout(lambda: self._show_hover(listener, point, only_diagnostics))

    def _show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        contents = self.diagnostics_content() + self.hover_content()
        if contents and not only_diagnostics:
            contents += self.symbol_actions_content(listener, point)

        _test_contents.clear()
        _test_contents.append(contents)  # for testing only

        if contents:
            if self.view.is_popup_visible():
                update_lsp_popup(self.view, contents)
            else:
                show_lsp_popup(
                    self.view,
                    contents,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
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
                    session.run_code_action_async(self._actions_by_config[config_name][index], progress=True)

            sublime.set_timeout_async(run_async)
