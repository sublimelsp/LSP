import os
import sublime
import sublime_plugin

from .url import uri_to_filename
from .protocol import Range
from .settings import log
from .workspace import get_project_path


def apply_workspace_edit(window, params):
    edit = params.get('edit', dict())
    window.run_command('lsp_apply_workspace_edit', {'changes': edit.get('changes')})


class LspApplyWorkspaceEditCommand(sublime_plugin.WindowCommand):
    def run(self, changes=None):
        # log(2, 'workspace edit %s', changes)
        if changes:
            for uri, file_changes in changes.items():
                path = uri_to_filename(uri)
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
                    log(2, 'view not found to apply %s %s', path, file_changes)
            message = 'Applied changes to {} documents'.format(len(changes))
            self.window.status_message(message)
        else:
            self.window.status_message('No changes to apply to workspace')


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):
    def run(self, edit, changes=None, show_status=True):
        regions = list(self.create_region(change) for change in changes)
        replacements = list(change.get('newText') for change in changes)

        # TODO why source.python here?
        self.view.add_regions('lsp_edit', regions, "source.python")

        index = 0
        last_region_count = len(regions)
        for newText in replacements:
            # refresh updated regions after each edit.
            updated_regions = self.view.get_regions('lsp_edit')
            region = updated_regions[index]  #
            self.apply_change(region, newText, edit)
            if len(self.view.get_regions('lsp_edit')) == last_region_count:
                index += 1  # no regions lost, move to next region.
            else:
                # current region was removed, don't advance index.
                last_region_count = len(self.view.get_regions('lsp_edit'))

        self.view.erase_regions('lsp_edit')
        if show_status:
            window = self.view.window()
            if window:
                base_dir = get_project_path(window)
                file_path = self.view.file_name()
                relative_file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                message = 'Applied {} change(s) to {}'.format(len(changes), relative_file_path)
                window.status_message(message)

    def create_region(self, change):
        return Range.from_lsp(change['range']).to_region(self.view)

    def apply_change(self, region, newText, edit):
        if region.empty():
            self.view.insert(edit, region.a, newText)
        else:
            if len(newText) > 0:
                self.view.replace(edit, region, newText)
            else:
                self.view.erase(edit, region)
