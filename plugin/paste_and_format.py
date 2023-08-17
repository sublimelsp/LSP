from .core.registry import LspTextCommand
from .core.typing import Optional
from .core.views import first_selection_region
import sublime


class LspPasteAndFormatCommand(LspTextCommand):
    capability = 'documentRangeFormattingProvider'

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        clipboard_text = sublime.get_clipboard()
        region = first_selection_region(self.view)
        if region is None:
            return
        sel = self.view.sel()
        number_of_cursors = len(sel)
        split_clipboard_text = clipboard_text.split('\n')
        for index, region in enumerate(sel):
            insert_text = clipboard_text
            # mimic copy/paste behavior of ST when there are multiple cursors
            if len(split_clipboard_text) == number_of_cursors:
                insert_text = split_clipboard_text[index]
            self.view.replace(edit, region, insert_text)
        # if we don't delay execution self.format with set_timeout_async,
        # on_text_changed_async will not pick up the change
        # thus a call to listener.purge_changes_async will not see new text changes.
        sublime.set_timeout_async(self.format, 1)

    def format(self) -> None:
        listener = self.get_listener()
        if listener:
            listener.purge_changes_async()
        self.view.run_command('lsp_format_document_range')
