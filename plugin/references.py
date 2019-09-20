import os
import sublime
import linecache

from .core.documents import is_at_word, get_position, get_document_position
from .core.panels import ensure_panel
from .core.protocol import Request, Point
from .core.registry import LspTextCommand, windows
from .core.settings import PLUGIN_NAME, settings
from .core.url import uri_to_filename

try:
    from typing import List, Dict, Optional, Callable, Tuple
    from mypy_extensions import TypedDict
    assert List and Dict and Optional and Callable and Tuple and TypedDict
    ReferenceDict = TypedDict('ReferenceDict', {'uri': str, 'range': dict})
except ImportError:
    pass


def ensure_references_panel(window: sublime.Window) -> 'Optional[sublime.View]':
    return ensure_panel(window, "references", r"^\s*\S\s+(\S.*):$", r"^\s+([0-9]+):?([0-9]+).*$",
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/References.sublime-syntax")


class LspSymbolReferencesCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.reflist = []  # type: List[List[str]]

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        if self.has_client_with_capability('referencesProvider'):
            return is_at_word(self.view, event)
        return False

    def run(self, edit: sublime.Edit, event: 'Optional[dict]' = None) -> None:
        client = self.client_with_capability('referencesProvider')
        if client:
            pos = get_position(self.view, event)
            document_position = get_document_position(self.view, pos)
            if document_position:
                document_position['context'] = {
                    "includeDeclaration": False
                }
                request = Request.references(document_position)
                client.send_request(
                    request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response: 'Optional[List[ReferenceDict]]', pos: int) -> None:
        window = self.view.window()

        if response is None:
            response = []

        references_count = len(response)
        # return if there are no references
        if references_count < 1:
            window.run_command("hide_panel", {"panel": "output.references"})
            window.status_message("No references found")
            return

        word_region = self.view.word(pos)
        word = self.view.substr(word_region)

        base_dir = windows.lookup(window).get_project_path()
        formatted_references = self._get_formatted_references(response, base_dir)

        if settings.show_references_in_quick_panel:
            flags = sublime.KEEP_OPEN_ON_FOCUS_LOST
            if settings.quick_panel_monospace_font:
                flags |= sublime.MONOSPACE_FONT
            window.show_quick_panel(
                self.reflist,
                lambda index: self.on_ref_choice(base_dir, index),
                flags,
                self.get_current_ref(base_dir, word_region.begin()),
                lambda index: self.on_ref_highlight(base_dir, index)
            )
        else:
            panel = ensure_references_panel(window)
            if not panel:
                return
            panel.settings().set("result_base_dir", base_dir)

            panel.set_read_only(False)
            panel.run_command("lsp_clear_panel")
            window.run_command("show_panel", {"panel": "output.references"})
            panel.run_command('append', {
                'characters': "{} references for '{}'\n\n{}".format(references_count, word, formatted_references),
                'force': True,
                'scroll_to_end': False
            })

            # highlight all word occurrences
            regions = panel.find_all(r"\b{}\b".format(word))
            panel.add_regions('ReferenceHighlight', regions, 'comment', flags=sublime.DRAW_OUTLINED)
            panel.set_read_only(True)

    def get_current_ref(self, base_dir: 'Optional[str]', pos: int) -> 'Optional[int]':
        row, col = self.view.rowcol(pos)
        row, col = row + 1, col + 1

        def find_matching_ref(condition: 'Callable[[int, int], bool]') -> 'Optional[int]':
            for i, ref in enumerate(self.reflist):
                file = ref[0]
                filename, filerow, filecol = file.rsplit(':', 2)

                row, col = int(filerow), int(filecol)
                filepath = filename
                if base_dir:
                    filepath = os.path.join(base_dir, filename)

                if not os.path.exists(filepath):
                    continue

                if os.path.samefile(filepath, self.view.file_name()) and condition(row, col):
                    return i
            return None

        ref = find_matching_ref(lambda r, c: row == r and col == c)
        if ref is not None:
            return ref

        ref = find_matching_ref(lambda r, c: row == r)
        if ref is not None:
            return ref

        return 0

    def on_ref_choice(self, base_dir: 'Optional[str]', index: int) -> None:
        window = self.view.window()
        if index != -1:
            window.open_file(self.get_selected_file_path(base_dir, index), sublime.ENCODED_POSITION)

    def on_ref_highlight(self, base_dir: 'Optional[str]', index: int) -> None:
        window = self.view.window()
        if index != -1:
            window.open_file(self.get_selected_file_path(base_dir, index), sublime.ENCODED_POSITION | sublime.TRANSIENT)

    def get_selected_file_path(self, base_dir: 'Optional[str]', index: int) -> str:
        file_path = self.reflist[index][0]
        if base_dir:
            file_path = os.path.join(base_dir, file_path)
        return file_path

    def want_event(self) -> bool:
        return True

    def _get_formatted_references(self, references: 'List[ReferenceDict]', base_dir: 'Optional[str]') -> str:
        grouped_references = self._group_references_by_file(references, base_dir)
        return self._format_references(grouped_references)

    def _group_references_by_file(self, references: 'List[ReferenceDict]',
                                  base_dir: 'Optional[str]'
                                  ) -> 'Dict[str, List[Tuple[Point, str]]]':
        """ Return a dictionary that groups references by the file it belongs. """
        grouped_references = {}  # type: Dict[str, List[Tuple[Point, str]]]
        for reference in references:
            file_path = uri_to_filename(reference["uri"])
            point = Point.from_lsp(reference['range']['start'])

            # get line of the reference, to showcase its use
            reference_line = linecache.getline(file_path, point.row + 1).strip()

            if base_dir:
                file_path = os.path.relpath(file_path, base_dir)

            if grouped_references.get(file_path) is None:
                grouped_references[file_path] = []
            grouped_references[file_path].append((point, reference_line))

        # we don't want to cache the line, we always want to get fresh data
        linecache.clearcache()

        return grouped_references

    def _format_references(self, grouped_references: 'Dict[str, List[Tuple[Point, str]]]') -> str:
        text = ''
        refs = []  # type: List[List[str]]
        for file, references in grouped_references.items():
            text += '◌ {}:\n'.format(file)
            for reference in references:
                point, line = reference
                text += '\t{:>8}:{:<4} {}\n'.format(point.row + 1, point.col + 1, line)
                refs.append(['{}:{}:{}'.format(file, point.row + 1, point.col + 1), line])
            # append a new line after each file name
            text += '\n'
        self.reflist = refs
        return text
