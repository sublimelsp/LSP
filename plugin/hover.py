from __future__ import annotations

from ..protocol import CodeAction
from ..protocol import CodeActionKind
from ..protocol import Command
from ..protocol import Diagnostic
from ..protocol import DocumentLink
from ..protocol import Hover
from ..protocol import Position
from ..protocol import Range
from .code_actions import filter_quickfix_actions
from .core.constants import HOVER_ENABLED_KEY
from .core.constants import MarkdownLangMap
from .core.constants import RegionKey
from .core.constants import SHOW_DEFINITIONS_KEY
from .core.open import lsp_range_from_uri_fragment
from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.promise import Promise
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.settings import userprefs
from .core.url import CODE_ACTION_SCHEME
from .core.url import decode_code_action_uri
from .core.url import decode_document_link_uri
from .core.url import DOCUMENT_LINK_SCHEME
from .core.url import encode_document_link_uri
from .core.url import parse_uri
from .core.views import format_diagnostics_for_html
from .core.views import FORMAT_MARKED_STRING
from .core.views import FORMAT_MARKUP_CONTENT
from .core.views import html_wrapper
from .core.views import is_location_href
from .core.views import make_command_link
from .core.views import minihtml
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import text_document_identifier
from .core.views import text_document_position_params
from .core.views import unpack_href_location
from .core.views import update_lsp_popup
from functools import partial
from typing import Sequence
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import urlsplit
from urllib.parse import urlunsplit
import html
import mdpopups
import sublime
import sublime_plugin

if TYPE_CHECKING:
    from .core.sessions import AbstractViewListener
    from .core.sessions import SessionBufferProtocol

SessionName = str
ResolvedHover = Union[Hover, Error]


class LinkKind:

    __slots__ = ("lsp_name", "label", "subl_cmd_name", "supports_side_by_side")

    def __init__(self, lsp_name: str, label: str, subl_cmd_name: str, supports_side_by_side: bool) -> None:
        self.lsp_name = lsp_name
        self.label = label
        self.subl_cmd_name = subl_cmd_name
        self.supports_side_by_side = supports_side_by_side

    def link(self, point: int, view: sublime.View) -> str:
        args = {'point': point}
        link = make_command_link(self.subl_cmd_name, self.label, args, None, None, view.id())
        if self.supports_side_by_side:
            args['side_by_side'] = True
            link += ' ' + make_command_link(self.subl_cmd_name, '◨', args, 'icon', None, view.id())
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
        self._base_dir: str | None = None
        self._image_resolver = None
        self._document_link_cache: tuple[str, int, list[DocumentLink]] = ('', -1, [])

    def run(
        self,
        edit: sublime.Edit,
        only_diagnostics: bool = False,
        point: int | None = None,
        event: dict | None = None
    ) -> None:
        hover_point = get_position(self.view, event, point)
        if hover_point is None:
            return
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        self._base_dir = wm.get_project_path(self.view.file_name() or "")
        self._hover_responses: list[tuple[Hover, MarkdownLangMap | None]] = []
        self._document_link: tuple[str, int, DocumentLink] | None = None
        self._actions_by_config: dict[str, list[Command | CodeAction]] = {}
        self._diagnostics_by_config: Sequence[tuple[SessionBufferProtocol, Sequence[Diagnostic]]] = []
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_document_link_async(listener, hover_point)
                self.request_symbol_hover_async(listener, hover_point)
            self._diagnostics_by_config = listener.get_diagnostics_async(
                hover_point, userprefs().show_diagnostics_severity_level)
            if self._diagnostics_by_config:
                self.show_hover(listener, hover_point, only_diagnostics)
            if userprefs().show_code_actions_in_hover:
                region = sublime.Region(hover_point, hover_point)
                kinds: list[str | CodeActionKind] = [CodeActionKind.QuickFix]
                code_action_promises = [
                    sb.request_code_actions_async(self.view, region, diagnostics, kinds)
                        .then(partial(filter_quickfix_actions, len(diagnostics) > 1))
                        .then(lambda result, config_name=sb.session.config.name: (config_name, result))
                    for sb, diagnostics in self._diagnostics_by_config
                    if sb.has_capability('codeActionProvider')
                ]
                Promise.all(code_action_promises).then(partial(self._handle_code_actions, listener, hover_point))

        sublime.set_timeout_async(run_async)

    def request_symbol_hover_async(self, listener: AbstractViewListener, point: int) -> None:
        hover_promises: list[Promise[ResolvedHover]] = []
        language_maps: list[MarkdownLangMap | None] = []
        request = Request('textDocument/hover', text_document_position_params(self.view, point), self.view)
        for session in listener.sessions_async('hoverProvider'):
            hover_promises.append(session.send_request_task(request))
            language_maps.append(session.markdown_language_id_to_st_syntax_map())
        Promise.all(hover_promises).then(partial(self._on_all_settled, listener, point, language_maps))

    def _on_all_settled(
        self,
        listener: AbstractViewListener,
        point: int,
        language_maps: list[MarkdownLangMap | None],
        responses: list[ResolvedHover]
    ) -> None:
        hovers: list[tuple[Hover, MarkdownLangMap | None]] = []
        errors: list[Error] = []
        for response, language_map in zip(responses, language_maps):
            if isinstance(response, Error):
                errors.append(response)
                continue
            if response:
                hovers.append((response, language_map))
        if errors:
            error_messages = ", ".join(str(error) for error in errors)
            sublime.status_message(f'Hover error: {error_messages}')
        self._hover_responses = hovers
        self.show_hover(listener, point, only_diagnostics=False)

    def request_document_link_async(self, listener: AbstractViewListener, point: int) -> None:
        if session := self.best_session('documentLinkProvider', point):
            if sv := session.session_view_for_view_async(self.view):
                session_name = session.config.name
                version = self.view.change_count()
                if userprefs().link_highlight_style == 'underline':
                    # If underline for links is enabled, textDocument/documentLink is requested after each buffer change
                    if link := sv.session_buffer.get_document_link_at_point(self.view, point):
                        self._document_link = (session_name, version, link)
                elif self._document_link_cache[0] == session_name and self._document_link_cache[1] == version:
                    # Use cache from previous hover if the result is not outdated
                    self._process_cached_document_links_async(point)
                else:
                    session.send_request_async(
                        Request.documentLink({'textDocument': text_document_identifier(self.view)}, self.view),
                        partial(self._on_document_link_response_async, listener, point, version, session_name)
                    )

    def _on_document_link_response_async(
        self,
        listener: AbstractViewListener,
        point: int,
        version: int,
        session_name: str,
        response: list[DocumentLink] | None
    ) -> None:
        self._document_link_cache = (session_name, version, response or [])
        self._process_cached_document_links_async(point)
        self.show_hover(listener, point, only_diagnostics=False)

    def _process_cached_document_links_async(self, point: int) -> None:
        for link in self._document_link_cache[2]:
            if range_to_region(link['range'], self.view).contains(point):
                session_name = self._document_link_cache[0]
                version = self._document_link_cache[1]
                self._document_link = (session_name, version, link)
                return

    def _on_link_resolved_async(self, link: DocumentLink) -> None:
        if uri := link.get('target'):
            self._on_navigate(uri)

    def _handle_code_actions(
        self,
        listener: AbstractViewListener,
        point: int,
        responses: list[tuple[str, list[Command | CodeAction]]]
    ) -> None:
        if actions := {config_name: code_actions for config_name, code_actions in responses if code_actions}:
            self._actions_by_config = actions
            self.show_hover(listener, point, only_diagnostics=False)

    def provider_exists(self, listener: AbstractViewListener, link: LinkKind) -> bool:
        return bool(listener.session_async(f'{link.lsp_name}Provider'))

    def symbol_actions_content(self, listener: AbstractViewListener, point: int) -> str:
        actions = [lk.link(point, self.view) for lk in link_kinds if self.provider_exists(listener, lk)]
        return " | ".join(actions) if actions else ""

    def link_content_and_range(self) -> tuple[str, sublime.Region | None]:
        if self._document_link is None:
            return "", None
        session_name, version, link = self._document_link
        region = range_to_region(link['range'], self.view)
        title = link.get('tooltip')
        tooltip = f' title="{html.escape(title)}"' if title else ""
        if (uri := link.get('target')) is not None:
            label = "Open in Browser" if uri.startswith(('http:', 'https:')) else "Open Link"
            uri = html.escape(uri)
        else:
            label = "Open Link"
            uri = encode_document_link_uri(session_name, version, link)
        return f'<a href="{uri}"{tooltip}>{label}</a>', region

    def hover_content(self) -> str:
        contents: list[str] = []
        for hover, language_map in self._hover_responses:
            content = (hover.get('contents') or '') if isinstance(hover, dict) else ''
            allowed_formats = FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT
            if parsed := minihtml(self.view, content, allowed_formats, language_map):
                contents.append(html_wrapper(parsed))
        return '<hr class="m-0">'.join(contents)

    def hover_range(self) -> sublime.Region | None:
        for hover, _ in self._hover_responses:
            if hover_range := hover.get('range'):
                return range_to_region(hover_range, self.view)
        return None

    def show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        sublime.set_timeout(lambda: self._show_hover(listener, point, only_diagnostics))

    def _show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        # TODO: clean up this method, it is a total mess currently with all that conditional logic
        contents = ''
        prefs = userprefs()
        if only_diagnostics or prefs.show_diagnostics_in_hover:
            contents += format_diagnostics_for_html(
                self.view,
                self._diagnostics_by_config,
                self._actions_by_config,
                listener.lightbulb_color,
                self._base_dir
            )
        hover_content = self.hover_content()
        contents += hover_content
        link_content, link_range = self.link_content_and_range()
        only_link_content = not bool(contents) and link_range is not None
        if prefs.show_symbol_action_links and contents and not only_diagnostics and hover_content:
            symbol_actions_content = self.symbol_actions_content(listener, point)
            if link_content:
                if symbol_actions_content:
                    symbol_actions_content += ' | '
                symbol_actions_content += link_content
            if symbol_actions_content:
                contents += html_wrapper(symbol_actions_content, class_name='actions')
        elif link_content:
            contents += html_wrapper(link_content)

        if contents:
            if prefs.hover_highlight_style:
                hover_range = link_range if only_link_content else self.hover_range()
                if hover_range:
                    _, flags = prefs.highlight_style_region_flags(prefs.hover_highlight_style)
                    self.view.add_regions(
                        RegionKey.HOVER_HIGHLIGHT,
                        regions=[hover_range],
                        scope="region.cyanish markup.highlight.hover.lsp",
                        flags=flags)
            if self.view.is_popup_visible():
                update_lsp_popup(self.view, contents)
            else:
                show_lsp_popup(
                    self.view,
                    contents,
                    flags=sublime.PopupFlags.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    on_navigate=self._on_navigate,
                    on_hide=lambda: self.view.erase_regions(RegionKey.HOVER_HIGHLIGHT))
            self._image_resolver = mdpopups.resolve_images(
                contents, mdpopups.worker_thread_resolver, partial(self._on_images_resolved, contents))

    def _on_images_resolved(self, original_contents: str, contents: str) -> None:
        self._image_resolver = None
        if contents != original_contents and self.view.is_popup_visible():
            update_lsp_popup(self.view, contents)

    def _on_navigate(self, uri: str) -> None:
        scheme = parse_uri(uri)[0]
        if scheme == 'subl':
            pass
        elif scheme == 'file':
            if window := self.view.window():
                open_file_uri(window, uri).then(lambda view: window.focus_view(view) if view else None)
        elif scheme == CODE_ACTION_SCHEME:
            session_name, version, action = decode_code_action_uri(uri)
            if version == self.view.change_count() and (session := self.session_by_name(session_name)):
                sublime.set_timeout_async(lambda: session.run_code_action_async(action, progress=True, view=self.view))
                self.view.hide_popup()
        elif scheme == DOCUMENT_LINK_SCHEME:
            session_name, version, link = decode_document_link_uri(uri)
            if version == self.view.change_count() and (session := self.session_by_name(session_name)) and \
                    session.has_capability('documentLinkProvider.resolveProvider'):
                request = Request.resolveDocumentLink(link, self.view)
                sublime.set_timeout_async(lambda: session.send_request_async(request, self._on_link_resolved_async))
        elif is_location_href(uri):
            session_name, uri, row, col_utf16 = unpack_href_location(uri)
            if session := self.session_by_name(session_name):
                position: Position = {"line": row, "character": col_utf16}
                r: Range = {"start": position, "end": position}
                sublime.set_timeout_async(partial(session.open_uri_async, uri, r))
        elif scheme.lower() in {"http", "https"} or (not scheme and uri.startswith('www.')):
            open_in_browser(uri)
        elif scheme:
            sublime.set_timeout_async(partial(self.try_open_custom_uri_async, uri))

    def try_open_custom_uri_async(self, uri: str) -> None:
        uri_parts = urlsplit(uri)
        r = lsp_range_from_uri_fragment(uri_parts.fragment)
        if r:
            uri = urlunsplit(uri_parts._replace(fragment=''))
        for session in self.sessions():
            if session.try_open_uri_async(uri, r) is not None:
                return


class LspToggleHoverPopupsCommand(sublime_plugin.WindowCommand):

    def is_enabled(self) -> bool:
        if view := self.window.active_view():
            return self._has_hover_provider(view)
        return False

    def is_checked(self) -> bool:
        return bool(self.window.settings().get(HOVER_ENABLED_KEY, True))

    def run(self) -> None:
        enable = not self.is_checked()
        self.window.settings().set(HOVER_ENABLED_KEY, enable)
        sublime.set_timeout_async(partial(self._update_views_async, enable))

    def _has_hover_provider(self, view: sublime.View) -> bool:
        listener = windows.listener_for_view(view)
        return listener.hover_provider_count > 0 if listener else False

    def _update_views_async(self, enable: bool) -> None:
        if window_manager := windows.lookup(self.window):
            for session in window_manager.get_sessions():
                for session_view in session.session_views_async():
                    if enable:
                        session_view.view.settings().set(SHOW_DEFINITIONS_KEY, False)
                    else:
                        session_view.reset_show_definitions()


class LspCopyTextCommand(sublime_plugin.WindowCommand):

    def run(self, text: str) -> None:
        sublime.set_clipboard(text)
        text_length = len(text)
        self.window.status_message(f"Copied {text_length} characters")
