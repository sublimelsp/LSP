from .core.panels import ensure_panel
from .core.protocol import Location
from .core.protocol import Point
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.sessions import Session
from .core.settings import PLUGIN_NAME
from .core.settings import userprefs
from .core.types import ClientConfig
from .core.types import PANEL_FILE_REGEX
from .core.types import PANEL_LINE_REGEX
from .core.typing import Dict, List, Optional, Tuple
from .core.views import get_line
from .core.views import get_uri_and_position_from_location
from .core.views import text_document_position_params
from .locationpicker import LocationPicker
import functools
import linecache
import os
import sublime


def ensure_references_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, "references", PANEL_FILE_REGEX, PANEL_LINE_REGEX,
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/References.sublime-syntax")


class LspSymbolReferencesCommand(LspTextCommand):

    capability = 'referencesProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._picker = None  # type: Optional[LocationPicker]

    def run(self, _: sublime.Edit, event: Optional[dict] = None, point: Optional[int] = None) -> None:
        session = self.best_session(self.capability)
        file_path = self.view.file_name()
        pos = get_position(self.view, event, point)
        if session and file_path and pos is not None:
            params = text_document_position_params(self.view, pos)
            params['context'] = {"includeDeclaration": False}
            request = Request("textDocument/references", params, self.view, progress=True)
            session.send_request(
                request,
                functools.partial(
                    self._handle_response_async,
                    self.view.substr(self.view.word(pos)),
                    session
                )
            )

    def _handle_response_async(self, word: str, session: Session, response: Optional[List[Location]]) -> None:
        sublime.set_timeout(lambda: self._handle_response(word, session, response))

    def _handle_response(self, word: str, session: Session, response: Optional[List[Location]]) -> None:
        if response:
            if userprefs().show_references_in_quick_panel:
                self._show_references_in_quick_panel(session, response)
            else:
                self._show_references_in_output_panel(word, session, response)
        else:
            window = self.view.window()
            if window:
                window.status_message("No references found")

    def _show_references_in_quick_panel(self, session: Session, locations: List[Location]) -> None:
        self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
        LocationPicker(self.view, session, locations, side_by_side=False)

    def _show_references_in_output_panel(self, word: str, session: Session, locations: List[Location]) -> None:
        window = session.window
        panel = ensure_references_panel(window)
        if not panel:
            return
        manager = session.manager()
        if not manager:
            return
        base_dir = manager.get_project_path(self.view.file_name() or "")
        to_render = []  # type: List[str]
        references_count = 0
        references_by_file = _group_locations_by_uri(window, session.config, locations)
        for file, references in references_by_file.items():
            to_render.append('{}:'.format(_get_relative_path(base_dir, file)))
            for reference in references:
                references_count += 1
                point, line = reference
                to_render.append('{:>5}:{:<4} {}'.format(point.row + 1, point.col + 1, line))
            to_render.append("")  # add spacing between filenames
        characters = "\n".join(to_render)
        panel.settings().set("result_base_dir", base_dir)
        panel.run_command("lsp_clear_panel")
        window.run_command("show_panel", {"panel": "output.references"})
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
        return os.path.relpath(file_path, base_dir)
    else:
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
