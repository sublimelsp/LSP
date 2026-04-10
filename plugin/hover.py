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
from .core.sessions import AbstractViewListener
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.url import CODE_ACTION_SCHEME
from .core.url import decode_code_action_uri
from .core.url import parse_uri
from .core.views import format_diagnostics_for_html
from .core.views import FORMAT_MARKED_STRING
from .core.views import FORMAT_MARKUP_CONTENT
from .core.views import html_wrapper
from .core.views import is_location_href
from .core.views import make_command_link
from .core.views import MarkdownLangMap
from .core.views import minihtml
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import text_document_position_params
from .core.views import unpack_href_location
from .core.views import update_lsp_popup
from functools import partial
from typing import Sequence
from typing import Union
from urllib.parse import urlparse
import html
import mdpopups
import sublime
import sublime_plugin

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
        self._document_links: list[DocumentLink] = []
        self._actions_by_config: dict[str, list[Command | CodeAction]] = {}
        self._diagnostics_by_config: Sequence[tuple[SessionBufferProtocol, Sequence[Diagnostic]]] = []
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_symbol_hover_async(listener, hover_point)
                if userprefs().link_highlight_style in {"underline", "none"}:
                    self.request_document_link_async(listener, hover_point)
            self._diagnostics_by_config = listener.get_diagnostics_async(
                hover_point, userprefs().show_diagnostics_severity_level)
            if self._diagnostics_by_config:
                self.show_hover(listener, hover_point, only_diagnostics)
            if userprefs().show_code_actions_in_hover:
                region = sublime.Region(hover_point, hover_point)
                kinds = [CodeActionKind.QuickFix]
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
        for session in listener.sessions_async('hoverProvider'):
            hover_promises.append(session.send_request_task(
                Request("textDocument/hover", text_document_position_params(self.view, point), self.view)
            ))
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
        link_promises: list[Promise[DocumentLink | None]] = []
        for sv in listener.session_views_async():
            if not sv.has_capability_async("documentLinkProvider"):
                continue
            link = sv.session_buffer.get_document_link_at_point(sv.view, point)
            if link is None:
                continue
            if link.get("target"):
                link_promises.append(Promise.resolve(link))
            elif sv.has_capability_async("documentLinkProvider.resolveProvider"):
                link_promises.append(
                    sv.session.send_request_task(Request.resolveDocumentLink(link, sv.view))
                    .then(partial(self._on_resolved_link, sv.session_buffer)))
        if link_promises:
            Promise.all(link_promises).then(partial(self._on_all_document_links_resolved, listener, point))

    def _on_resolved_link(
        self, session_buffer: SessionBufferProtocol, link: DocumentLink | Error
    ) -> DocumentLink | None:
        if isinstance(link, Error):
            return None
        session_buffer.update_document_link(link)
        return link

    def _on_all_document_links_resolved(
        self, listener: AbstractViewListener, point: int, links: list[DocumentLink | None]
    ) -> None:
        if document_links := list(filter(None, links)):
            self._document_links = document_links
            self.show_hover(listener, point, only_diagnostics=False)

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
        if len(self._document_links) > 1:
            combined_region = range_to_region(self._document_links[0]["range"], self.view)
            for link in self._document_links[1:]:
                combined_region = combined_region.cover(range_to_region(link["range"], self.view))
            if all(link.get("target") for link in self._document_links):
                return '<a href="quick-panel:DocumentLink">Follow Link…</a>', combined_region
            return "Follow Link…", combined_region
        if len(self._document_links) == 1:
            link = self._document_links[0]
            target = link.get("target")
            label = "Follow Link" if link.get("target", "file:").startswith("file:") else "Open in Browser"
            title = link.get("tooltip")
            tooltip = f' title="{html.escape(title)}"' if title else ""
            region = range_to_region(link["range"], self.view)
            return f'<a href="{html.escape(target)}"{tooltip}>{label}</a>' if target else label, region
        return "", None

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

    def _on_navigate(self, href: str) -> None:
        scheme = parse_uri(href)[0]
        if scheme == 'subl':
            pass
        elif scheme == 'file':
            if window := self.view.window():
                open_file_uri(window, href)
        elif scheme == CODE_ACTION_SCHEME:
            session_name, version, action = decode_code_action_uri(href)
            if version == self.view.change_count() and (session := self.session_by_name(session_name)):
                sublime.set_timeout_async(lambda: session.run_code_action_async(action, progress=True, view=self.view))
                self.view.hide_popup()
        elif href == "quick-panel:DocumentLink":
            if window := self.view.window():
                targets = [link["target"] for link in self._document_links]  # pyright: ignore

                def on_select(targets: list[str], idx: int) -> None:
                    if idx > -1:
                        self._on_navigate(targets[idx])

                window.show_quick_panel(
                    [parse_uri(target)[1] for target in targets], partial(on_select, targets), placeholder="Open Link")
        elif is_location_href(href):
            session_name, uri, row, col_utf16 = unpack_href_location(href)
            if session := self.session_by_name(session_name):
                position: Position = {"line": row, "character": col_utf16}
                r: Range = {"start": position, "end": position}
                sublime.set_timeout_async(partial(session.open_uri_async, uri, r))
        elif scheme.lower() in {"http", "https"} or (not scheme and href.startswith('www.')):
            open_in_browser(href)
        elif scheme:
            sublime.set_timeout_async(partial(self.try_open_custom_uri_async, href))

    def try_open_custom_uri_async(self, href: str) -> None:
        r = lsp_range_from_uri_fragment(urlparse(href).fragment)
        for session in self.sessions():
            if session.try_open_uri_async(href, r) is not None:
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
