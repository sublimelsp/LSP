import sublime
import sublime_plugin
from .core.edit import sort_by_application_order
try:
    from typing import List, Dict, Optional, Any, Iterable, Tuple
    from .core.edit import TextEdit
    assert List and Dict and Optional and Any and Iterable and Tuple and TextEdit
except ImportError:
    pass
from .core.logging import debug


class LspApplyWorkspaceEditCommand(sublime_plugin.WindowCommand):
    def run(self, changes: 'Optional[Dict[str, List[TextEdit]]]'=None):
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

    def open_and_apply_edits(self, path, file_changes):
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
                                 {'changes': file_changes,
                                  'show_status': False})
        else:
            debug('view not found to apply', path, file_changes)


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):
    def run(self, edit, changes: 'Optional[List[TextEdit]]'=None):
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if changes:
            for change in sort_by_application_order(changes):
                start, end, newText = change
                region = sublime.Region(self.view.text_point(*start), self.view.text_point(*end))
                self.apply_change(region, newText, edit)

    def apply_change(self, region: 'sublime.Region', newText: str, edit):
        if region.empty():
            self.view.insert(edit, region.a, newText)
        else:
            if len(newText) > 0:
                self.view.replace(edit, region, newText)
            else:
                self.view.erase(edit, region)
