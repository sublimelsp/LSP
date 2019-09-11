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
    from typing import List, Dict, Optional
    assert List and Dict and Optional
except ImportError:
    pass


def ensure_references_panel(window: sublime.Window) -> 'Optional[sublime.View]':
    return ensure_panel(window, "references", r"^\s*\S\s+(\S.*):$", r"^\s+([0-9]+):?([0-9]+).*$",
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/References.sublime-syntax")


class LspSymbolReferencesCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)
        self.reflist = []  # type: List[List[str]]

    def is_enabled(self, event=None):
        if self.has_client_with_capability('referencesProvider'):
            return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
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

    def handle_response(self, response: 'Optional[List[Dict]]', pos) -> None:
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

    def get_current_ref(self, base_dir, pos: int) -> 'Optional[int]':
        row, col = self.view.rowcol(pos)
        row, col = row + 1, col + 1

        def find_matching_ref(condition):
            for i, ref in enumerate(self.reflist):
                file = ref[0]
                filename, filerow, filecol = file.rsplit(':', 2)

                row, col = int(filerow), int(filecol)
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

    def on_ref_choice(self, base_dir, index: int) -> None:
        window = self.view.window()
        if index != -1:
            filepath = os.path.join(base_dir, self.reflist[index][0])
            window.open_file(filepath, sublime.ENCODED_POSITION)

    def on_ref_highlight(self, base_dir, index: int) -> None:
        window = self.view.window()
        if index != -1:
            filepath = os.path.join(base_dir, self.reflist[index][0])
            window.open_file(filepath, sublime.ENCODED_POSITION | sublime.TRANSIENT)

    def want_event(self):
        return True

    def _get_formatted_references(self, references: 'List[Dict]', base_dir) -> str:
        grouped_references = self._group_references_by_file(references, base_dir)
        return self._format_references(grouped_references)

    def _group_references_by_file(self, references, base_dir):
        """ Return a dictionary that groups references by the file it belongs. """
        grouped_references = {}  # type: Dict[str, List[Dict]]
        for reference in references:
            file_path = uri_to_filename(reference.get("uri"))
            relative_file_path = os.path.relpath(file_path, base_dir)

            point = Point.from_lsp(reference.get('range').get('start'))
            # get line of the reference, to showcase its use
            reference_line = linecache.getline(file_path, point.row + 1).strip()

            if grouped_references.get(relative_file_path) is None:
                grouped_references[relative_file_path] = []
            grouped_references[relative_file_path].append({'point': point, 'text': reference_line})

        # we don't want to cache the line, we always want to get fresh data
        linecache.clearcache()

        return grouped_references

    def _format_references(self, grouped_references) -> str:
        text = ''
        refs = []
        for file in grouped_references:
            text += '◌ {}:\n'.format(file)
            references = grouped_references.get(file)
            for reference in references:
                point = reference.get('point')
                text += '\t{:>8}:{:<4} {}\n'.format(point.row + 1, point.col + 1, reference.get('text'))
                refs.append(['{}:{}:{}'.format(file, point.row + 1, point.col + 1), reference.get('text')])
            # append a new line after each file name
            text += '\n'
        self.reflist = refs
        return text
