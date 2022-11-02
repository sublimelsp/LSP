from .core.protocol import Location
from .core.protocol import Point
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.types import ClientConfig
from .core.typing import Dict, List, Optional, Tuple
from .core.views import get_line
from .core.views import get_uri_and_position_from_location
from .core.views import text_document_position_params
from .core.views import word
from .locationpicker import LocationPicker
import functools
import linecache
import os
import sublime


class LspSymbolReferencesCommand(LspTextCommand):

    capability = 'referencesProvider'

    def is_enabled(
        self,
        event: Optional[dict] = None,
        point: Optional[int] = None,
        side_by_side: bool = False,
        fallback: bool = False,
    ) -> bool:
        return fallback or super().is_enabled(event, point)

    def run(
        self,
        _: sublime.Edit,
        event: Optional[dict] = None,
        point: Optional[int] = None,
        side_by_side: bool = False,
        fallback: bool = False,
    ) -> None:
        session = self.best_session(self.capability)
        file_path = self.view.file_name()
        pos = get_position(self.view, event, point)
        if session and file_path and pos is not None:
            position_params = text_document_position_params(self.view, pos)
            params = {
                'textDocument': position_params['textDocument'],
                'position': position_params['position'],
                'context': {"includeDeclaration": False},
            }
            request = Request("textDocument/references", params, self.view, progress=True)
            session.send_request(
                request,
                functools.partial(
                    self._handle_response_async,
                    word(self.view, pos),
                    session,
                    side_by_side,
                    fallback
                )
            )
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_response_async(
        self, word: str, session: Session, side_by_side: bool, fallback: bool, response: Optional[List[Location]]
    ) -> None:
        sublime.set_timeout(lambda: self._handle_response(word, session, side_by_side, fallback, response))

    def _handle_response(
        self, word: str, session: Session, side_by_side: bool, fallback: bool, response: Optional[List[Location]]
    ) -> None:
        if response:
            if userprefs().show_references_in_quick_panel:
                self._show_references_in_quick_panel(word, session, response, side_by_side)
            else:
                self._show_references_in_output_panel(word, session, response)
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_no_results(self, fallback: bool = False, side_by_side: bool = False) -> None:
        window = self.view.window()
        if not window:
            return
        if fallback:
            window.run_command("goto_reference", {"side_by_side": side_by_side})
        else:
            window.status_message("No references found")

    def _show_references_in_quick_panel(
            self, word: str, session: Session, locations: List[Location], side_by_side: bool
        ) -> None:
        self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
        LocationPicker(self.view, session, locations, side_by_side, placeholder="References to " + word)

    def _show_references_in_output_panel(self, word: str, session: Session, locations: List[Location]) -> None:
        wm = windows.lookup(session.window)
        if not wm:
            return
        panel = wm.panel_manager and wm.panel_manager.ensure_references_panel()
        if not panel:
            return
        base_dir = wm.get_project_path(self.view.file_name() or "")
        to_render = []  # type: List[str]
        references_count = 0
        references_by_file = _group_locations_by_uri(wm.window, session.config, locations)
        for file, references in references_by_file.items():
            to_render.append('{}:'.format(_get_relative_path(base_dir, file)))
            for reference in references:
                references_count += 1
                point, line = reference
                to_render.append(" {:>4}:{:<4} {}".format(point.row + 1, point.col + 1, line))
            to_render.append("")  # add spacing between filenames
        characters = "\n".join(to_render)
        panel.settings().set("result_base_dir", base_dir)
        panel.run_command("lsp_clear_panel")
        wm.window.run_command("show_panel", {"panel": "output.references"})
        panel.run_command('append', {
            'characters': "{} references for '{}'\n\n{}".format(references_count, word, characters),
            'force': True,
            'scroll_to_end': False
        })
        # highlight all word occurrences
        regions = panel.find_all(r"\b{}\b".format(word))
        panel.add_regions('ReferenceHighlight', regions, 'comment', flags=sublime.DRAW_OUTLINED)


def _get_relative_path(base_dir: Optional[str], file_path: str) -> str:
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
    locations: List[Location]
) -> Dict[str, List[Tuple[Point, str]]]:
    """Return a dictionary that groups locations by the URI it belongs."""
    grouped_locations = {}  # type: Dict[str, List[Tuple[Point, str]]]
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
