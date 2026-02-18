from __future__ import annotations

from ..protocol import FoldingRange
from ..protocol import FoldingRangeKind
from ..protocol import FoldingRangeParams
from ..protocol import Range
from .core.protocol import Request
from .core.protocol import UINT_MAX
from .core.registry import LspTextCommand
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


def sorted_folding_ranges(folding_ranges: list[FoldingRange]) -> list[FoldingRange]:
    # Sort by reversed position and from innermost to outermost (if nested)
    return sorted(
        folding_ranges,
        key=lambda r: (
            r['startLine'],
            r.get('startCharacter', UINT_MAX),
            -r['endLine'],
            -r.get('endCharacter', UINT_MAX)
        ),
        reverse=True
    )


class LspFoldCommand(LspTextCommand):
    """A command to fold at the current caret position or at a given point.

    Optional command arguments:

    - `prefetch`:   Should usually be `false`, except for the built-in menu items under the "Edit" main menu, which
                    pre-run a request and cache the response to dynamically show or hide the item.
    - `hidden`:     Can be used for a hidden menu item with the purpose to run a request and store the response.
    - `strict`:     Allows to configure the folding behavior; `true` means to fold only when the caret is contained
                    within the folded region (like ST built-in `fold` command), and `false` will fold a region even if
                    the caret is anywhere else on the starting line.
    - `point`:      Can be used instead of the caret position, measured as character offset in the document.
    """

    capability = 'foldingRangeProvider'
    folding_ranges: list[FoldingRange] = []
    change_count = -1
    folding_region: sublime.Region | None = None

    def is_visible(
        self,
        prefetch: bool = False,
        hidden: bool = False,
        strict: bool = True,
        event: dict | None = None,
        point: int | None = None
    ) -> bool:
        if not prefetch:
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
                params: FoldingRangeParams = {'textDocument': text_document_identifier(self.view)}
                session.send_request_async(
                    Request.foldingRange(params, self.view),
                    partial(self._handle_response_async, view_change_count)
                )
            return False
        return self.folding_region is not None  # Already set or unset by self.description

    def _handle_response_async(self, change_count: int, response: list[FoldingRange] | None) -> None:
        self.change_count = change_count
        self.folding_ranges = response or []

    def description(
        self,
        prefetch: bool = False,
        hidden: bool = False,
        strict: bool = True,
        event: dict | None = None,
        point: int | None = None
    ) -> str:
        if not prefetch:
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
        for folding_range in sorted_folding_ranges(self.folding_ranges):
            region = range_to_region(folding_range_to_range(folding_range), self.view)
            if (strict and region.contains(pt) or
                    not strict and sublime.Region(self.view.line(region.a).a, region.b).contains(pt)) and \
                    not self.view.is_folded(region):
                # Store the relevant folding region, so that we don't need to do the same computation again in
                # self.is_visible and self.run
                self.folding_region = region
                kind = folding_range.get('kind')
                if kind == FoldingRangeKind.Imports:
                    return "LSP: Fold Imports"
                elif kind:
                    return f"LSP: Fold this {kind.title()}"
                else:
                    return "LSP: Fold"
        return "LSP <debug>"  # is_visible will return False

    def run(
        self,
        edit: sublime.Edit,
        prefetch: bool = False,
        hidden: bool = False,
        strict: bool = True,
        event: dict | None = None,
        point: int | None = None
    ) -> None:
        if prefetch:
            if self.folding_region is not None:
                self.view.fold(self.folding_region)
        else:
            if point is not None:
                pt = point
            else:
                selection = self.view.sel()
                if len(selection) != 1 or not selection[0].empty():
                    self.view.run_command('fold')
                    return
                pt = selection[0].b
            if session := self.best_session(self.capability):
                params: FoldingRangeParams = {'textDocument': text_document_identifier(self.view)}
                session.send_request_async(
                    Request.foldingRange(params, self.view),
                    partial(self._handle_response_manual_async, pt, strict)
                )

    def _handle_response_manual_async(self, point: int, strict: bool, response: list[FoldingRange] | None) -> None:
        if response:
            for folding_range in sorted_folding_ranges(response):
                region = range_to_region(folding_range_to_range(folding_range), self.view)
                if (strict and region.contains(point) or
                        not strict and sublime.Region(self.view.line(region.a).a, region.b).contains(point)) and \
                        not self.view.is_folded(region):
                    self.view.fold(region)
                    return
        if window := self.view.window():
            window.status_message("Code Folding not available")


class LspFoldAllCommand(LspTextCommand):

    capability = 'foldingRangeProvider'

    def run(self, edit: sublime.Edit, kind: str | None = None, event: dict | None = None) -> None:
        if session := self.best_session(self.capability):
            params: FoldingRangeParams = {'textDocument': text_document_identifier(self.view)}
            session.send_request_async(
                Request.foldingRange(params, self.view), partial(self._handle_response_async, kind))

    def _handle_response_async(self, kind: str | None, response: list[FoldingRange] | None) -> None:
        if not response:
            return
        regions = [
            range_to_region(folding_range_to_range(folding_range), self.view)
            for folding_range in response if not kind or kind == folding_range.get('kind')
        ]
        if not regions:
            return
        # Don't fold regions which contain the caret or selection
        selections = self.view.sel()
        regions = [region for region in regions if not any(region.intersects(selection) for selection in selections)]
        if regions:
            self.view.fold(regions)
