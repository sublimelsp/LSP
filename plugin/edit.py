import sublime
import sublime_plugin
from .core.edit import sort_by_application_order
from .core.logging import debug

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import List, Dict, Optional, Any, Iterable, Tuple
    TextEdit = Tuple[Tuple[int, int], Tuple[int, int], str]
    assert List and Dict and Optional and Any and Iterable


class LspApplyWorkspaceEditCommand(sublime_plugin.WindowCommand):
    def run(self, changes: 'Optional[Dict[str, List[TextEdit]]]' = None) -> None:
        documents_changed = 0
        if changes:
            for path, document_changes in changes.items():
                self.open_and_apply_edits(path, document_changes)
                documents_changed += 1

        if documents_changed > 0:
            message = 'Applied changes to {} documents'.format(documents_changed)
            self.window.status_message(message)
        else:
            self.window.status_message('No changes to apply to workspace')

    def open_and_apply_edits(self, path: str, file_changes: 'List[TextEdit]') -> None:
        view = self.window.open_file(path)
        if view:
            if view.is_loading():
                # TODO: wait for event instead.
                sublime.set_timeout_async(
                    lambda: view.run_command('lsp_apply_document_edit', {'changes': file_changes}),
                    500
                )
            else:
                view.run_command('lsp_apply_document_edit',
                                 {'changes': file_changes})
        else:
            debug('view not found to apply', path, file_changes)


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):

    def run(self, edit: 'Any', changes: 'Optional[List[TextEdit]]' = None) -> None:
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if changes:
            last_row, last_col = self.view.rowcol(self.view.size())
            for change in reversed(sort_by_application_order(changes)):
                start, end, newText = change
                region = sublime.Region(self.view.text_point(*start), self.view.text_point(*end))

                if start[0] > last_row and newText[0] != '\n':
                    # Handle when a language server (eg gopls) inserts at a row beyond the document
                    # some editors create the line automatically, sublime needs to have the newline prepended.
                    debug('adding new line for edit at line {}, document ended at line {}'.format(start[0], last_row))
                    self.apply_change(region, '\n' + newText, edit)
                    last_row, last_col = self.view.rowcol(self.view.size())
                else:
                    self.apply_change(region, newText, edit)

    def apply_change(self, region: 'sublime.Region', newText: str, edit: 'Any') -> None:
        if region.empty():
            self.view.insert(edit, region.a, newText)
        else:
            if len(newText) > 0:
                self.view.replace(edit, region, newText)
            else:
                self.view.erase(edit, region)
