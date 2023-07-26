from .core.protocol import FoldingRange
from .core.protocol import FoldingRangeKind
from .core.protocol import FoldingRangeParams
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import UINT_MAX
from .core.registry import LspTextCommand
from .core.typing import List, Optional
from .core.views import range_to_region
from .core.views import text_document_identifier
from functools import partial
import sublime


def folding_range_to_range(folding_range: FoldingRange) -> Range:
    return {
        'start': {
            'line': folding_range['startLine'],
            'character': folding_range.get('startCharacter', UINT_MAX)
        },
        'end': {
            'line': folding_range['endLine'],
            'character': folding_range.get('endCharacter', UINT_MAX)
        }
    }


class LspFoldCommand(LspTextCommand):

    capability = 'foldingRangeProvider'
    folding_ranges = []  # type: List[FoldingRange]
    change_count = -1
    folding_region = None  # type: Optional[sublime.Region]

    def is_visible(
        self, manual: bool = True, hidden: bool = False, event: Optional[dict] = None, point: Optional[int] = None
    ) -> bool:
        if manual:
            return True
        # There should be a single empty selection in the view, otherwise this functionality would be misleading
        selection = self.view.sel()
        if len(selection) != 1 or not selection[0].empty():
            return False
        if hidden:  # This is our dummy menu item, with the purpose to run the request when the "Edit" menu gets opened
            view_change_count = self.view.change_count()
            # If the stored change_count matches the view's actual change count, the request has already been run for
            # this document state (i.e. "Edit" menu was opened before) and the results are still valid - no need to send
            # another request.
            if self.change_count == view_change_count:
                return False
            self.change_count = -1
            session = self.best_session(self.capability)
            if session:
                params = {'textDocument': text_document_identifier(self.view)}  # type: FoldingRangeParams
                session.send_request_async(
                    Request.foldingRange(params, self.view),
                    partial(self._handle_response_async, view_change_count)
                )
            return False
        return self.folding_region is not None  # Already set or unset by self.description

    def _handle_response_async(self, change_count: int, response: Optional[List[FoldingRange]]) -> None:
        self.change_count = change_count
        self.folding_ranges = response or []

    def description(
        self, manual: bool = True, hidden: bool = False, event: Optional[dict] = None, point: Optional[int] = None
    ) -> str:
        if manual:
            return "LSP: Fold"
        # Implementation detail of Sublime Text: TextCommand.description is called *before* TextCommand.is_visible
        self.folding_region = None
        if self.change_count != self.view.change_count():  # Ensure that the response has already arrived
            return "LSP <debug>"  # is_visible will return False
        if point is not None:
            pt = point
        else:
            selection = self.view.sel()
            if len(selection) != 1 or not selection[0].empty():
                return "LSP <debug>"  # is_visible will return False
            pt = selection[0].b
        for folding_range in sorted(self.folding_ranges, key=lambda r: r['startLine'], reverse=True):
            region = range_to_region(folding_range_to_range(folding_range), self.view)
            if region.contains(pt):
                # Store the relevant folding region, so that we don't need to do the same computation again in
                # self.is_visible and self.run
                self.folding_region = region
                return {
                    FoldingRangeKind.Comment: "LSP: Fold this comment",
                    FoldingRangeKind.Imports: "LSP: Fold imports",
                    FoldingRangeKind.Region: "LSP: Fold this region",
                    'array': "LSP: Fold this array",  # used by LSP-json
                    'object': "LSP: Fold this object",  # used by LSP-json
                }.get(folding_range.get('kind', ''), "LSP: Fold")
        return "LSP <debug>"  # is_visible will return False

    def run(
        self,
        edit: sublime.Edit,
        manual: bool = True,
        hidden: bool = False,
        event: Optional[dict] = None,
        point: Optional[int] = None
    ) -> None:
        if manual:
            if point is not None:
                pt = point
            else:
                selection = self.view.sel()
                if len(selection) != 1 or not selection[0].empty():
                    self.view.run_command('fold_unfold')
                    return
                pt = selection[0].b
            session = self.best_session(self.capability)
            if session:
                params = {'textDocument': text_document_identifier(self.view)}  # type: FoldingRangeParams
                session.send_request_async(
                    Request.foldingRange(params, self.view),
                    partial(self._handle_response_manual_async, pt)
                )
        elif self.folding_region is not None:
            self.view.fold(self.folding_region)

    def _handle_response_manual_async(self, point: int, response: Optional[List[FoldingRange]]) -> None:
        if not response:
            window = self.view.window()
            if window:
                window.status_message("Code Folding not available")
            return
        for folding_range in sorted(response, key=lambda r: r['startLine'], reverse=True):
            region = range_to_region(folding_range_to_range(folding_range), self.view)
            if region.contains(point):
                self.view.fold(region)
                return
        else:
            window = self.view.window()
            if window:
                window.status_message("Code Folding not available")
