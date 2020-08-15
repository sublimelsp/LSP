import os
import sublime
import linecache

from .core.panels import ensure_panel
from .core.protocol import Request, Point
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.settings import PLUGIN_NAME
from .core.settings import userprefs
from .core.typing import List, Dict, Optional, Tuple, TypedDict
from .core.url import uri_to_filename
from .core.views import get_line, text_document_position_params
from .documents import is_at_word

ReferenceDict = TypedDict('ReferenceDict', {'uri': str, 'range': dict})


def ensure_references_panel(window: sublime.Window) -> 'Optional[sublime.View]':
    return ensure_panel(window, "references", r"^\s*\S\s+(\S.*):$", r"^\s+([0-9]+):?([0-9]+).*$",
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/References.sublime-syntax")


class LspSymbolReferencesCommand(LspTextCommand):

    capability = 'referencesProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.reflist = []  # type: List[List[str]]
        self.word_region = None  # type: Optional[sublime.Region]
        self.word = ""
        self.base_dir = None  # type: Optional[str]

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        return super().is_enabled(event) and is_at_word(self.view, event)

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.best_session(self.capability)
        file_path = self.view.file_name()
        if session and file_path:
            pos = get_position(self.view, event)
            window = self.view.window()
            if not window:
                return
            self.word_region = self.view.word(pos)
            self.word = self.view.substr(self.word_region)

            # use relative paths if file on the same root.
            base_dir = windows.lookup(window).get_project_path(file_path)
            if base_dir:
                if os.path.commonprefix([base_dir, file_path]):
                    self.base_dir = base_dir

            document_position = text_document_position_params(self.view, pos)
            document_position['context'] = {"includeDeclaration": False}
            request = Request.references(document_position)
            session.send_request(request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response: Optional[List[ReferenceDict]], pos: int) -> None:
        window = self.view.window()

        if response is None:
            response = []

        if window:
            references_count = len(response)
            # return if there are no references
            if references_count < 1:
                window.run_command("hide_panel", {"panel": "output.references"})
                window.status_message("No references found")
                return

            references_by_file = self._group_references_by_file(response)

            if userprefs().show_references_in_quick_panel:
                self.show_quick_panel(references_by_file)
            else:
                self.show_references_panel(references_by_file)

    def show_quick_panel(self, references_by_file: Dict[str, List[Tuple[Point, str]]]) -> None:
        selected_index = -1
        current_file_path = self.view.file_name()
        self.reflist.clear()
        for file_path, references in references_by_file.items():
            for reference in references:
                point, line = reference
                item = ['{}:{}:{}'.format(self.get_relative_path(file_path), point.row + 1, point.col + 1), line]
                self.reflist.append(item)

                # pre-select a reference in the current file.
                if current_file_path == file_path and selected_index == -1:
                    selected_index = len(self.reflist) - 1

        flags = sublime.KEEP_OPEN_ON_FOCUS_LOST
        window = self.view.window()
        if window:
            window.show_quick_panel(
                self.reflist,
                self.on_ref_choice,
                flags,
                selected_index,
                self.on_ref_highlight
            )

    def on_ref_choice(self, index: int) -> None:
        self.open_ref_index(index)

    def on_ref_highlight(self, index: int) -> None:
        self.open_ref_index(index, transient=True)

    def open_ref_index(self, index: int, transient: bool = False) -> None:
        if index != -1:
            flags = sublime.ENCODED_POSITION | sublime.TRANSIENT if transient else sublime.ENCODED_POSITION
            window = self.view.window()
            if window:
                window.open_file(self.get_selected_file_path(index), flags)

    def show_references_panel(self, references_by_file: Dict[str, List[Tuple[Point, str]]]) -> None:
        window = self.view.window()
        if window:
            panel = ensure_references_panel(window)
            if not panel:
                return

            text = ''
            references_count = 0
            for file, references in references_by_file.items():
                text += '◌ {}:\n'.format(self.get_relative_path(file))
                for reference in references:
                    references_count += 1
                    point, line = reference
                    text += '\t{:>8}:{:<4} {}\n'.format(point.row + 1, point.col + 1, line)
                # append a new line after each file name
                text += '\n'

            base_dir = windows.lookup(window).get_project_path(self.view.file_name() or "")
            panel.settings().set("result_base_dir", base_dir)

            panel.run_command("lsp_clear_panel")
            window.run_command("show_panel", {"panel": "output.references"})
            panel.run_command('append', {
                'characters': "{} references for '{}'\n\n{}".format(references_count, self.word, text),
                'force': True,
                'scroll_to_end': False
            })

            # highlight all word occurrences
            regions = panel.find_all(r"\b{}\b".format(self.word))
            panel.add_regions('ReferenceHighlight', regions, 'comment', flags=sublime.DRAW_OUTLINED)

    def get_selected_file_path(self, index: int) -> str:
        return self.get_full_path(self.reflist[index][0])

    def get_relative_path(self, file_path: str) -> str:
        if self.base_dir:
            return os.path.relpath(file_path, self.base_dir)
        else:
            return file_path

    def get_full_path(self, file_path: str) -> str:
        if self.base_dir:
            return os.path.join(self.base_dir, file_path)
        return file_path

    def _group_references_by_file(self, references: List[ReferenceDict]
                                  ) -> Dict[str, List[Tuple[Point, str]]]:
        """ Return a dictionary that groups references by the file it belongs. """
        grouped_references = {}  # type: Dict[str, List[Tuple[Point, str]]]
        for reference in references:
            file_path = uri_to_filename(reference["uri"])
            point = Point.from_lsp(reference['range']['start'])

            # get line of the reference, to showcase its use
            reference_line = get_line(self.view.window(), file_path, point.row)

            if grouped_references.get(file_path) is None:
                grouped_references[file_path] = []
            grouped_references[file_path].append((point, reference_line))

        # we don't want to cache the line, we always want to get fresh data
        linecache.clearcache()

        return grouped_references
