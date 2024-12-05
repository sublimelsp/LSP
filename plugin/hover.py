from __future__ import annotations
from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .code_actions import CodeActionsByConfigName
from .core.constants import HOVER_ENABLED_KEY
from .core.constants import RegionKey
from .core.constants import SHOW_DEFINITIONS_KEY
from .core.open import lsp_range_from_uri_fragment
from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.promise import Promise
from .core.protocol import Diagnostic
from .core.protocol import DocumentLink
from .core.protocol import Error
from .core.protocol import Hover
from .core.protocol import Position
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import AbstractViewListener
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.url import parse_uri
from .core.views import diagnostic_severity
from .core.views import format_code_actions_for_quick_panel
from .core.views import format_diagnostic_for_html
from .core.views import FORMAT_MARKED_STRING
from .core.views import FORMAT_MARKUP_CONTENT
from .core.views import is_location_href
from .core.views import make_command_link
from .core.views import make_link
from .core.views import MarkdownLangMap
from .core.views import minihtml
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import text_document_position_params
from .core.views import unpack_href_location
from .core.views import update_lsp_popup
from functools import partial
from typing import Sequence, Union
from urllib.parse import urlparse
import html
import mdpopups
import sublime
import sublime_plugin


SessionName = str
ResolvedHover = Union[Hover, Error]


_test_contents: list[str] = []


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


def code_actions_content(actions_by_config: list[CodeActionsByConfigName], lightbulb: bool = True) -> str:
    formatted = []
    for config_name, actions in actions_by_config:
        action_count = len(actions)
        if action_count == 0:
            continue
        if action_count > 1:
            text = f"choose ({action_count} available)"
        else:
            text = actions[0].get('title', 'code action')
        href = "{}:{}".format('code-actions', config_name)
        link = make_link(href, text)
        lightbulb_html = '<span class="lightbulb"><img src="res://Packages/LSP/icons/lightbulb_colored.png"></span>' \
            if lightbulb else ''
        formatted.append(
            f'<div class="actions">{lightbulb_html}{link} <span class="color-muted">{config_name}</span></div>')
    return "".join(formatted)


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
        self._actions_by_config: list[CodeActionsByConfigName] = []
        self._diagnostics_by_config: Sequence[tuple[SessionBufferProtocol, Sequence[Diagnostic]]] = []
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_symbol_hover_async(listener, hover_point)
                if userprefs().link_highlight_style in ("underline", "none"):
                    self.request_document_link_async(listener, hover_point)
            self._diagnostics_by_config, covering = listener.diagnostics_touching_point_async(
                hover_point, userprefs().show_diagnostics_severity_level)
            if self._diagnostics_by_config:
                self.show_hover(listener, hover_point, only_diagnostics)
            if not only_diagnostics and userprefs().show_code_actions_in_hover:
                actions_manager \
                    .request_for_region_async(self.view, covering, self._diagnostics_by_config, manual=False) \
                    .then(lambda results: self._handle_code_actions(listener, hover_point, results))

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
        link_promises: list[Promise[DocumentLink]] = []
        for sv in listener.session_views_async():
            if not sv.has_capability_async("documentLinkProvider"):
                continue
            link = sv.session_buffer.get_document_link_at_point(sv.view, point)
            if link is None:
                continue
            target = link.get("target")
            if target:
                link_promises.append(Promise.resolve(link))
            elif sv.has_capability_async("documentLinkProvider.resolveProvider"):
                link_promises.append(
                    sv.session.send_request_task(Request.resolveDocumentLink(link, sv.view))
                    .then(lambda link: self._on_resolved_link(sv.session_buffer, link))
                )
        if link_promises:
            Promise.all(link_promises).then(partial(self._on_all_document_links_resolved, listener, point))

    def _on_resolved_link(self, session_buffer: SessionBufferProtocol, link: DocumentLink) -> DocumentLink:
        session_buffer.update_document_link(link)
        return link

    def _on_all_document_links_resolved(
        self, listener: AbstractViewListener, point: int, links: list[DocumentLink]
    ) -> None:
        self._document_links = links
        self.show_hover(listener, point, only_diagnostics=False)

    def _handle_code_actions(
        self,
        listener: AbstractViewListener,
        point: int,
        responses: list[CodeActionsByConfigName]
    ) -> None:
        self._actions_by_config = responses
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
            else:
                return "Follow Link…", combined_region
        elif len(self._document_links) == 1:
            link = self._document_links[0]
            target = link.get("target")
            label = "Follow Link" if link.get("target", "file:").startswith("file:") else "Open in Browser"
            title = link.get("tooltip")
            tooltip = f' title="{html.escape(title)}"' if title else ""
            region = range_to_region(link["range"], self.view)
            return f'<a href="{html.escape(target)}"{tooltip}>{label}</a>' if target else label, region
        else:
            return "", None

    def diagnostics_content(self) -> str:
        formatted = []
        for sb, diagnostics in self._diagnostics_by_config:
            by_severity: dict[int, list[str]] = {}
            formatted.append('<div class="diagnostics">')
            for diagnostic in diagnostics:
                by_severity.setdefault(diagnostic_severity(diagnostic), []).append(
                    format_diagnostic_for_html(sb.session.config, diagnostic, self._base_dir))
            for items in by_severity.values():
                formatted.extend(items)
            formatted.append("</div>")
        return "".join(formatted)

    def hover_content(self) -> str:
        contents = []
        for hover, language_map in self._hover_responses:
            content = (hover.get('contents') or '') if isinstance(hover, dict) else ''
            allowed_formats = FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT
            contents.append(minihtml(self.view, content, allowed_formats, language_map))
        return '<hr>'.join(contents)

    def hover_range(self) -> sublime.Region | None:
        for hover, _ in self._hover_responses:
            hover_range = hover.get('range')
            if hover_range:
                return range_to_region(hover_range, self.view)
        else:
            return None

    def show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        sublime.set_timeout(lambda: self._show_hover(listener, point, only_diagnostics))

    def _show_hover(self, listener: AbstractViewListener, point: int, only_diagnostics: bool) -> None:
        hover_content = self.hover_content()
        prefs = userprefs()
        diagnostics_content = self.diagnostics_content() if only_diagnostics or prefs.show_diagnostics_in_hover else ""
        contents = diagnostics_content + hover_content + code_actions_content(self._actions_by_config)
        link_content, link_range = self.link_content_and_range()
        only_link_content = not bool(contents) and link_range is not None
        if prefs.show_symbol_action_links and contents and not only_diagnostics and hover_content:
            symbol_actions_content = self.symbol_actions_content(listener, point)
            if link_content:
                if symbol_actions_content:
                    symbol_actions_content += ' | '
                symbol_actions_content += link_content
            if symbol_actions_content:
                contents += '<div class="actions">' + symbol_actions_content + '</div>'
        elif link_content:
            contents += '<div class="{}">{}</div>'.format('link with-padding' if contents else 'link', link_content)

        _test_contents.clear()
        _test_contents.append(contents)  # for testing only

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
                    on_navigate=lambda href: self._on_navigate(href, point),
                    on_hide=lambda: self.view.erase_regions(RegionKey.HOVER_HIGHLIGHT))
            self._image_resolver = mdpopups.resolve_images(
                contents, mdpopups.worker_thread_resolver, partial(self._on_images_resolved, contents))

    def _on_images_resolved(self, original_contents: str, contents: str) -> None:
        self._image_resolver = None
        if contents != original_contents and self.view.is_popup_visible():
            update_lsp_popup(self.view, contents)

    def _on_navigate(self, href: str, point: int) -> None:
        if href.startswith("subl:"):
            pass
        elif href.startswith("file:"):
            window = self.view.window()
            if window:
                open_file_uri(window, href)
        elif href.startswith('code-actions:'):
            self.view.run_command("lsp_selection_set", {"regions": [(point, point)]})
            _, config_name = href.split(":")
            actions = next(actions for name, actions in self._actions_by_config if name == config_name)
            if len(actions) > 1:
                window = self.view.window()
                if window:
                    items, selected_index = format_code_actions_for_quick_panel(
                        map(lambda action: (config_name, action), actions))
                    window.show_quick_panel(
                        items,
                        lambda i: self.handle_code_action_select(config_name, actions, i),
                        selected_index=selected_index,
                        placeholder="Code actions")
            else:
                self.handle_code_action_select(config_name, actions, 0)
        elif href == "quick-panel:DocumentLink":
            window = self.view.window()
            if window:
                targets = [link["target"] for link in self._document_links]  # pyright: ignore

                def on_select(targets: list[str], idx: int) -> None:
                    if idx > -1:
                        self._on_navigate(targets[idx], 0)

                window.show_quick_panel(
                    [parse_uri(target)[1] for target in targets], partial(on_select, targets), placeholder="Open Link")
        elif is_location_href(href):
            session_name, uri, row, col_utf16 = unpack_href_location(href)
            session = self.session_by_name(session_name)
            if session:
                position: Position = {"line": row, "character": col_utf16}
                r: Range = {"start": position, "end": position}
                sublime.set_timeout_async(partial(session.open_uri_async, uri, r))
        elif parse_uri(href)[0].lower() in ("", "http", "https"):
            open_in_browser(href)
        else:
            sublime.set_timeout_async(partial(self.try_open_custom_uri_async, href))

    def handle_code_action_select(self, config_name: str, actions: list[CodeActionOrCommand], index: int) -> None:
        if index == -1:
            return

        def run_async() -> None:
            session = self.session_by_name(config_name)
            if session:
                session.run_code_action_async(actions[index], progress=True, view=self.view)

        sublime.set_timeout_async(run_async)

    def try_open_custom_uri_async(self, href: str) -> None:
        r = lsp_range_from_uri_fragment(urlparse(href).fragment)
        for session in self.sessions():
            if session.try_open_uri_async(href, r) is not None:
                return


class LspToggleHoverPopupsCommand(sublime_plugin.WindowCommand):

    def is_enabled(self) -> bool:
        view = self.window.active_view()
        if view:
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
        window_manager = windows.lookup(self.window)
        if not window_manager:
            return
        for session in window_manager.get_sessions():
            for session_view in session.session_views_async():
                if enable:
                    session_view.view.settings().set(SHOW_DEFINITIONS_KEY, False)
                else:
                    session_view.reset_show_definitions()
