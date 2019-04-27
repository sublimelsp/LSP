import sublime
import sublime_plugin

try:
    from typing import List, Dict, Optional, Any, Iterable
    assert List and Dict and Optional and Any
except ImportError:
    pass

from .url import uri_to_filename
from .protocol import Edit
from .logging import debug
from .views import range_to_region


class LspApplyWorkspaceEditCommand(sublime_plugin.WindowCommand):
    def run(self, changes: 'Optional[Dict[str, List[Edit]]]'=None):
        documents_changed = 0
        if changes:
            for (document_uri, document_changes) in changes.items():
                path = uri_to_filename(document_uri)
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


def sort_by_application_order(changes: 'Iterable[Edit]') -> 'List[Edit]':

    def get_start_position(change: Edit):
        start = change.range.start
        return (start.row, start.col)

    # The spec reads:
    # > However, it is possible that multiple edits have the same start position: multiple
    # > inserts, or any number of inserts followed by a single remove or replace edit. If
    # > multiple inserts have the same position, the order in the array defines the order in
    # > which the inserted strings appear in the resulting text.
    # So we sort by start position. But if multiple text edits start at the same position,
    # we use the index in the array as the key.

    # todo: removed array logic because sorted is stable, but does it work correctly with reverse?
    return sorted(changes, key=get_start_position, reverse=True)


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):
    def run(self, edit, changes: 'Optional[List[Edit]]'=None):
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if changes:
            sorted_changes = sort_by_application_order(changes)
            for change in sorted_changes:
                self.apply_change(range_to_region(change.range, self.view), change.newText, edit)

    def apply_change(self, region: 'sublime.Region', newText: str, edit):
        if region.empty():
            self.view.insert(edit, region.a, newText)
        else:
            if len(newText) > 0:
                self.view.replace(edit, region, newText)
            else:
                self.view.erase(edit, region)
