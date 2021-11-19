from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .core.logging import debug
from .core.promise import Promise
from .core.protocol import Diagnostic
from .core.protocol import Error
from .core.protocol import Hover
from .core.protocol import Position
from .core.protocol import RangeLsp
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.typing import List, Optional, Dict, Tuple, Sequence, Union
from .core.views import diagnostic_severity
from .core.views import first_selection_region
from .core.views import format_diagnostic_for_html
from .core.views import FORMAT_MARKED_STRING, FORMAT_MARKUP_CONTENT, minihtml
from .core.views import is_location_href
from .core.views import make_command_link
from .core.views import make_link
from .core.views import show_lsp_popup
from .core.views import text_document_position_params
from .core.views import text_document_range_params
from .core.views import unpack_href_location
from .core.views import update_lsp_popup
from .core.windows import AbstractViewListener
from urllib.parse import unquote, urlparse
import functools
import re
import sublime
import webbrowser


SUBLIME_WORD_MASK = 515
SessionName = str
ResolvedHover = Union[Hover, Error]

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
        temp_point = point
        if temp_point is None:
            region = first_selection_region(self.view)
            if region is not None:
                temp_point = region.begin()
        if temp_point is None:
            return
        window = self.view.window()
        if not window:
            return
        hover_point = temp_point
        wm = windows.lookup(window)
        self._base_dir = wm.get_project_path(self.view.file_name() or "")
        self._hover_responses = []  # type: List[Hover]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = []  # type: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]]
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_symbol_hover_async(listener, hover_point)
            self._diagnostics_by_config, covering = listener.diagnostics_touching_point_async(
                hover_point, userprefs().show_diagnostics_severity_level)
            if self._diagnostics_by_config:
                self.show_hover(listener, hover_point, only_diagnostics)
            if not only_diagnostics and userprefs().show_code_actions_in_hover:
                actions_manager.request_for_region_async(
                    self.view, covering, self._diagnostics_by_config,
                    functools.partial(self.handle_code_actions, listener, hover_point))

        sublime.set_timeout_async(run_async)

    def request_symbol_hover_async(self, listener: AbstractViewListener, point: int) -> None:
        hover_promises = []  # type: List[Promise[ResolvedHover]]
        for session in listener.sessions_async('hoverProvider'):
            range_hover_provider = session.get_capability('experimental.rangeHoverProvider')
            if range_hover_provider:
                region = first_selection_region(self.view)
                if region is not None:
                    if region.contains(point):  # when hovering selection send the selection as range
                        document_position = text_document_range_params(self.view, region)
                    else:  # there is selection but ignored
                        document_position = text_document_range_params(self.view, region)
                else:  # nothing selected
                    document_position = text_document_position_params(self.view, point)
            else:
                document_position = text_document_position_params(self.view, point)
            hover_promises.append(session.send_request_task(
                Request("textDocument/hover", document_position, self.view)
            ))

        Promise.all(hover_promises).then(lambda responses: self._on_all_settled(responses, listener, point))

    def _on_all_settled(self, responses: List[ResolvedHover], listener: AbstractViewListener, point: int) -> None:
        hovers = []  # type: List[Hover]
        errors = []  # type: List[Error]
        for response in responses:
            if isinstance(response, Error):
                errors.append(response)
                continue
            if response:
                hovers.append(response)
        if errors:
            error_messages = ", ".join(str(error) for error in errors)
            sublime.status_message('Hover error: {}'.format(error_messages))
        self._hover_responses = hovers
        self.show_hover(listener, point, only_diagnostics=False)

    def handle_code_actions(
        self,
        listener: AbstractViewListener,
        point: int,
        responses: Dict[str, List[CodeActionOrCommand]]
    ) -> None:
        self._actions_by_config = responses
        self.show_hover(listener, point, only_diagnostics=False)

    def provider_exists(self, listener: AbstractViewListener, link: LinkKind) -> bool:
        return bool(listener.session_async('{}Provider'.format(link.lsp_name)))

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
                    format_diagnostic_for_html(self.view, sb.session.config, diagnostic, self._base_dir))
            for items in by_severity.values():
                formatted.extend(items)
            formatted.append("</div>")
        return "".join(formatted)

    def code_actions_content(self) -> str:
        formatted = []
        for config_name, actions in self._actions_by_config.items():
            action_count = len(actions)
            if action_count > 0:
                href = "{}:{}".format('code-actions', config_name)
                if action_count > 1:
                    text = "choose code action ({} available)".format(action_count)
                else:
                    text = actions[0].get('title', 'code action')
                formatted.append('<div class="actions">[{}] Code action: {}</div>'.format(
                    config_name, make_link(href, text)))
        return "".join(formatted)

    def hover_content(self) -> str:
        contents = []
        for hover_response in self._hover_responses:
            content = (hover_response.get('contents') or '') if isinstance(hover_response, dict) else ''
            contents.append(minihtml(self.view, content, allowed_formats=FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT))
        return '<hr>'.join(contents)

    def show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        sublime.set_timeout(lambda: self._show_hover(listener, point, only_diagnostics))

    def _show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        hover_content = self.hover_content()
        contents = self.diagnostics_content() + hover_content + self.code_actions_content()
        if contents and not only_diagnostics and hover_content:
            contents += self.symbol_actions_content(listener, point)

        _test_contents.clear()
        _test_contents.append(contents)  # for testing only

        if contents:
            # The previous popup could be in a different location from the next one
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
        elif href.startswith("file:"):
            window = self.view.window()
            if window:
                decoded = unquote(href)  # decode percent-encoded characters
                parsed = urlparse(decoded)
                filepath = parsed.path
                if sublime.platform() == "windows":
                    filepath = re.sub(r"^/([a-zA-Z]:)", r"\1", filepath)  # remove slash preceding drive letter
                fn = "{}:{}".format(filepath, parsed.fragment) if parsed.fragment else filepath
                window.open_file(fn, flags=sublime.ENCODED_POSITION)
        elif href.startswith('code-actions:'):
            _, config_name = href.split(":")
            titles = [command["title"] for command in self._actions_by_config[config_name]]
            self.view.run_command("lsp_selection_set", {"regions": [(point, point)]})
            if len(titles) > 1:
                window = self.view.window()
                if window:
                    window.show_quick_panel(titles, lambda i: self.handle_code_action_select(config_name, i),
                                            placeholder="Code actions")
            else:
                self.handle_code_action_select(config_name, 0)
        elif is_location_href(href):
            session_name, uri, row, col_utf16 = unpack_href_location(href)
            session = self.session_by_name(session_name)
            if session:
                position = {"line": row, "character": col_utf16}  # type: Position
                r = {"start": position, "end": position}  # type: RangeLsp
                sublime.set_timeout_async(functools.partial(session.open_uri_async, uri, r))
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
