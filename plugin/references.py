import os
import sublime
import linecache

from .core.panels import create_output_panel
from .core.settings import PLUGIN_NAME
from .core.registry import client_for_view, LspTextCommand
from .core.documents import is_at_word, get_position, get_document_position
from .core.workspace import get_project_path
from .core.protocol import Request, Point
from .core.url import uri_to_filename

try:
    from typing import List, Dict, Optional
    assert List and Dict and Optional
except ImportError:
    pass


def ensure_references_panel(window: sublime.Window):
    return window.find_output_panel("references") or create_references_panel(window)


def create_references_panel(window: sublime.Window):
    panel = create_output_panel(window, "references")
    panel.settings().set("result_file_regex", r"^\s*\S\s+(\S.*):$")
    panel.settings().set("result_line_regex", r"^\s+([0-9]+):?([0-9]+).*$")
    panel.assign_syntax("Packages/" + PLUGIN_NAME +
                        "/Syntaxes/References.sublime-syntax")
    # Call create_output_panel a second time after assigning the above
    # settings, so that it'll be picked up as a result buffer
    # see: Packages/Default/exec.py#L228-L230
    panel = window.create_output_panel("references")
    return panel


class LspSymbolReferencesCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        if self.has_client_with_capability('referencesProvider'):
            return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
        client = client_for_view(self.view)
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

        word = self.view.substr(self.view.word(pos))

        base_dir = get_project_path(window)
        formatted_references = self._get_formatted_references(response, base_dir)

        panel = ensure_references_panel(window)
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

    def want_event(self):
        return True

    def _get_formatted_references(self, references: 'List[Dict]', base_dir) -> str:
        grouped_references = self._group_references_by_file(references, base_dir)
        formatted_references = self._format_references(grouped_references)
        return formatted_references

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
        for file in grouped_references:
            text += '◌ {}:\n'.format(file)
            references = grouped_references.get(file)
            for reference in references:
                point = reference.get('point')
                text += '\t{:>8}:{:<4} {}\n'.format(point.row + 1, point.col + 1, reference.get('text'))
            # append a new line after each file name
            text += '\n'
        return text
