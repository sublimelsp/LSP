from __future__ import annotations
from .core.constants import RegionKey
from .core.protocol import Location
from .core.protocol import Point
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.types import ClientConfig
from .core.views import get_line
from .core.views import get_symbol_kind_from_scope
from .core.views import get_uri_and_position_from_location
from .core.views import position_to_offset
from .core.views import text_document_position_params
from .locationpicker import LocationPicker
from typing import Literal
import functools
import linecache
import os
import sublime


OutputMode = Literal['output_panel', 'quick_panel']


class LspSymbolReferencesCommand(LspTextCommand):

    capability = 'referencesProvider'

    def is_enabled(
        self,
        event: dict | None = None,
        point: int | None = None,
        side_by_side: bool = False,
        force_group: bool = True,
        fallback: bool = False,
        group: int = -1,
        include_declaration: bool = False,
        output_mode: OutputMode | None = None,
    ) -> bool:
        return fallback or super().is_enabled(event, point)

    def is_visible(
        self,
        event: dict | None = None,
        point: int | None = None,
        side_by_side: bool = False,
        force_group: bool = True,
        fallback: bool = False,
        group: int = -1,
        include_declaration: bool = False,
        output_mode: OutputMode | None = None,
    ) -> bool:
        # We include "output panel" and "quick panel" variants of `LSP: Find References` in the Command Palette
        # but we only show the one that is not the same as the default one (per the `show_references_in_quick_panel`
        # setting).
        if output_mode == 'output_panel' and not userprefs().show_references_in_quick_panel or \
                output_mode == 'quick_panel' and userprefs().show_references_in_quick_panel:
            return False
        if self.applies_to_context_menu(event):
            return self.is_enabled(
                event, point, side_by_side, force_group, fallback, group, include_declaration, output_mode)
        return True

    def run(
        self,
        _: sublime.Edit,
        event: dict | None = None,
        point: int | None = None,
        side_by_side: bool = False,
        force_group: bool = True,
        fallback: bool = False,
        group: int = -1,
        include_declaration: bool = False,
        output_mode: OutputMode | None = None,
    ) -> None:
        session = self.best_session(self.capability)
        file_path = self.view.file_name()
        pos = get_position(self.view, event, point)
        if session and file_path and pos is not None:
            position_params = text_document_position_params(self.view, pos)
            params = {
                'textDocument': position_params['textDocument'],
                'position': position_params['position'],
                'context': {
                    "includeDeclaration": include_declaration,
                },
            }
            request = Request("textDocument/references", params, self.view, progress=True)
            word_range = self.view.word(pos)
            session.send_request(
                request,
                functools.partial(
                    self._handle_response_async,
                    self.view.substr(word_range),
                    session,
                    side_by_side,
                    force_group,
                    fallback,
                    group,
                    output_mode,
                    event,
                    word_range.begin()
                )
            )
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_response_async(
        self,
        word: str,
        session: Session,
        side_by_side: bool,
        force_group: bool,
        fallback: bool,
        group: int,
        output_mode: OutputMode | None,
        event: dict | None,
        position: int,
        response: list[Location] | None
    ) -> None:
        sublime.set_timeout(lambda: self._handle_response(
            word, session, side_by_side, force_group, fallback, group, output_mode, event, position, response))

    def _handle_response(
        self,
        word: str,
        session: Session,
        side_by_side: bool,
        force_group: bool,
        fallback: bool,
        group: int,
        output_mode: OutputMode | None,
        event: dict | None,
        position: int,
        response: list[Location] | None
    ) -> None:
        if not response:
            self._handle_no_results(fallback, side_by_side)
            return
        modifier_keys = (event or {}).get('modifier_keys', {})
        if output_mode is None:
            show_in_quick_panel = userprefs().show_references_in_quick_panel
            if modifier_keys.get('shift'):
                show_in_quick_panel = not show_in_quick_panel
        else:
            show_in_quick_panel = output_mode == 'quick_panel'
        if show_in_quick_panel:
            if modifier_keys.get('primary'):
                side_by_side = True
            self._show_references_in_quick_panel(word, session, response, side_by_side, force_group, group, position)
        else:
            self._show_references_in_output_panel(word, session, response)

    def _handle_no_results(self, fallback: bool = False, side_by_side: bool = False) -> None:
        window = self.view.window()
        if not window:
            return
        if fallback:
            window.run_command("goto_reference", {"side_by_side": side_by_side})
        else:
            window.status_message("No references found")

    def _show_references_in_quick_panel(
        self,
        word: str,
        session: Session,
        locations: list[Location],
        side_by_side: bool,
        force_group: bool,
        group: int,
        position: int
    ) -> None:
        selection = self.view.sel()
        self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in selection]})
        placeholder = "References to " + word
        kind = get_symbol_kind_from_scope(self.view.scope_name(position))
        index = 0
        locations.sort(key=lambda location: (location['uri'], Point.from_lsp(location['range']['start'])))
        if len(selection):
            pt = selection[0].b
            view_filename = self.view.file_name()
            for idx, location in enumerate(locations):
                if view_filename != session.config.map_server_uri_to_client_path(location['uri']):
                    continue
                index = idx
                if position_to_offset(location['range']['start'], self.view) > pt:
                    break
        LocationPicker(self.view, session, locations, side_by_side, force_group, group, placeholder, kind, index)

    def _show_references_in_output_panel(self, word: str, session: Session, locations: list[Location]) -> None:
        wm = windows.lookup(session.window)
        if not wm:
            return
        panel = wm.panel_manager and wm.panel_manager.ensure_references_panel()
        if not panel:
            return
        base_dir = wm.get_project_path(self.view.file_name() or "")
        to_render: list[str] = []
        references_count = 0
        references_by_file = _group_locations_by_uri(wm.window, session.config, locations)
        for file, references in references_by_file.items():
            to_render.append(f'{_get_relative_path(base_dir, file)}:')
            for reference in references:
                references_count += 1
                point, line = reference
                to_render.append(f" {point.row + 1:>4}:{point.col + 1:<4} {line}")
            to_render.append("")  # add spacing between filenames
        characters = "\n".join(to_render)
        panel.settings().set("result_base_dir", base_dir)
        panel.run_command("lsp_clear_panel")
        wm.window.run_command("show_panel", {"panel": "output.references"})
        panel.run_command('append', {
            'characters': f"{references_count} references for '{word}'\n\n{characters}",
            'force': True,
            'scroll_to_end': False
        })
        # highlight all word occurrences
        regions = panel.find_all(rf"\b{word}\b")
        panel.add_regions(
            RegionKey.REFERENCE_HIGHLIGHT,
            regions,
            'comment',
            flags=sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO
        )


def _get_relative_path(base_dir: str | None, file_path: str) -> str:
    if base_dir:
        try:
            return os.path.relpath(file_path, base_dir)
        except ValueError:
            # On Windows, ValueError is raised when path and start are on different drives.
            pass
    return file_path


def _group_locations_by_uri(
    window: sublime.Window,
    config: ClientConfig,
    locations: list[Location]
) -> dict[str, list[tuple[Point, str]]]:
    """Return a dictionary that groups locations by the URI it belongs."""
    grouped_locations: dict[str, list[tuple[Point, str]]] = {}
    for location in locations:
        uri, position = get_uri_and_position_from_location(location)
        file_path = config.map_server_uri_to_client_path(uri)
        point = Point.from_lsp(position)
        # get line of the reference, to showcase its use
        reference_line = get_line(window, file_path, point.row)
        if grouped_locations.get(file_path) is None:
            grouped_locations[file_path] = []
        grouped_locations[file_path].append((point, reference_line))
    # we don't want to cache the line, we always want to get fresh data
    linecache.clearcache()
    return grouped_locations
