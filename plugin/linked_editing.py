from __future__ import annotations

from .core.aio import run_on_main_thread
from .core.constants import ChangeEventAction
from .core.constants import LINKED_EDITING_FLAGS
from .core.constants import LINKED_EDITING_SCOPE
from .core.constants import RegionKey
from .core.logging import debug
from .core.protocol import Error
from .core.protocol import Request
from .core.type_converters import range_to_region
from .core.views import text_document_position_params
from typing import TYPE_CHECKING
import re
import sublime
import sublime_plugin

if TYPE_CHECKING:
    from ..protocol import LinkedEditingRangeParams
    from ..protocol import LinkedEditingRanges
    from .core.sessions import CancellableRequest
    from .core.sessions import Session


# Used when the language server doesn't provide a word pattern. It rejects whitespace and common delimiters, so that
# for example typing a space after an HTML tag name ends linked editing instead of mirroring the space.
DEFAULT_WORD_PATTERN = re.compile(r"[^\s<>/\\'\"`=(){}\[\],;]*")


class LinkedEditing:
    """
    Tracks the linked editing ranges of a view and mirrors edits made in one of the ranges into the other ranges.

    The ranges are tracked manually from the text changes instead of with `View.add_regions`, because regions added
    that way don't grow when text is inserted at their boundaries.

    All edits made while linked editing is active, including the mirrored edits, are glued into a single undo group,
    so that undo restores all ranges at once, and typing a word is undone in one step like in regular typing. The undo
    groups are marked when linked editing starts, and glued when it stops, before an undo or redo, and before saving.
    This uses the undocumented built-in commands `mark_undo_groups_for_gluing`, `glue_marked_undo_groups` and
    `unmark_undo_groups_for_gluing`, which are also used by the Vintage package that ships with Sublime Text.

    Unless noted otherwise, the methods of this class must be called on the main thread.
    """

    def __init__(self, view: sublime.View) -> None:
        self._view = view
        self._ranges: tuple[sublime.Region, ...] = ()
        self._word_pattern: re.Pattern[str] = DEFAULT_WORD_PATTERN
        # Indices into `_ranges` of the ranges that were edited since the last sync. The edited range is the one whose
        # content gets mirrored into the other ranges, so mirroring is only done if exactly one range was edited.
        self._touched: set[int] = set()
        self._sync_pending = False
        # The selection after the last edit, or when the undo groups were last marked. A different selection means that
        # the caret was moved without an edit.
        self._selection: list[sublime.Region] = []
        # The request that is in flight, if any, with its point and version. Only used on the asyncio thread.
        self._pending_request: CancellableRequest[LinkedEditingRanges | None] | None = None
        self._pending_position: tuple[int, int] | None = None

    def is_active(self) -> bool:
        """Whether there are linked editing ranges. Safe to call from any thread."""
        return bool(self._ranges)

    def contains(self, point: int) -> bool:
        """Whether the point is inside of or at the boundary of a linked editing range. Safe to call from any thread."""
        return any(r.contains(point) for r in self._ranges)

    def contains_selection(self) -> bool:
        """Whether all selections of the view are inside of the linked editing ranges. Safe to call from any thread."""
        return all(any(r.contains(s) for r in self._ranges) for s in self._view.sel())

    @property
    def ranges(self) -> tuple[sublime.Region, ...]:
        return self._ranges

    def clear(self, *, glue: bool = True) -> None:
        """
        Stop linked editing.

        :param      glue:  Whether to glue the undo groups of the edits made while linked editing was active. Must be
                           `False` after an undo or redo, because the marked undo groups were undone.
        """
        if not self._ranges:
            return
        self._ranges = ()
        self._touched.clear()
        if self._view.is_valid():
            self._view.erase_regions(RegionKey.LINKED_EDITING)
            if glue:
                self._view.run_command("glue_marked_undo_groups")
            self._view.run_command("unmark_undo_groups_for_gluing")

    def glue(self) -> None:
        """Glue the undo groups of the edits made so far, and keep gluing later edits into a new undo group."""
        if self._ranges and self._view.is_valid():
            self._view.run_command("glue_marked_undo_groups")
            self._view.run_command("mark_undo_groups_for_gluing")
            self._selection = list(self._view.sel())

    def on_selection_modified(self) -> None:
        """Stop linked editing if a caret left the ranges, or start a new undo group if the caret moved within them."""
        if not self._ranges or not self._view.is_valid():
            return
        if not self.contains_selection():
            self.clear()
        elif list(self._view.sel()) != self._selection:
            # Undo restores the selection from when the undo groups were marked, so mark them again at the new caret
            # position. Otherwise undoing edits made here would move the caret back to where linked editing started.
            self.glue()

    async def request(self, session: Session, point: int, version: int) -> None:
        """
        Request the linked editing ranges at the given point. Must be called on the asyncio thread.

        :param      version:  The change count of the view before the pending changes were sent to the server. The
                              response is ignored if the view changed since then.
        """
        if self._pending_request and self._pending_position == (point, version):
            # Sublime Text can report the same selection change more than once, for example three times for one undo.
            return
        params: LinkedEditingRangeParams = {**text_document_position_params(self._view, point)}
        request = session.request(Request.linkedEditingRange(params, self._view))
        # The response of a previous request is obsolete, because it was for a different caret position or version.
        previous_request, self._pending_request = self._pending_request, request
        self._pending_position = (point, version)
        if previous_request:
            await previous_request.cancel()
        response = await request
        if self._pending_request is request:
            self._pending_request = None
        if request.cancelled:
            return
        if isinstance(response, Error):
            debug("linkedEditingRange request failed:", response)
            response = None
        await run_on_main_thread(self._on_response, version, point, response)

    def _on_response(self, version: int, point: int, response: LinkedEditingRanges | None) -> None:
        view = self._view
        if not view.is_valid() or view.change_count() != version:
            return
        selection = view.sel()
        if len(selection) != 1 or selection[0].b != point:
            return
        self.clear()
        if not response:
            return
        regions = sorted((range_to_region(view, r) for r in response['ranges']), key=lambda r: r.begin())
        if len(regions) < 2:
            return
        if any(prev.end() >= curr.begin() for prev, curr in zip(regions, regions[1:])):
            # Touching ranges are rejected too, because an insertion at their shared boundary would grow both ranges.
            debug("ignoring overlapping or touching linked editing ranges")
            return
        if len({view.substr(r) for r in regions}) != 1:
            debug("ignoring linked editing ranges with different content")
            return
        if not any(r.contains(point) for r in regions):
            return
        self._word_pattern = DEFAULT_WORD_PATTERN
        if word_pattern := response.get('wordPattern'):
            try:
                self._word_pattern = re.compile(word_pattern)
            except re.error as ex:
                debug("cannot use word pattern", word_pattern, "for linked editing:", ex)
        self._ranges = tuple(regions)
        self._touched.clear()
        self._draw()
        view.run_command("mark_undo_groups_for_gluing")
        self._selection = list(view.sel())

    def on_text_changed(self, changes: list[sublime.TextChange], action: ChangeEventAction) -> None:
        """Update the linked editing ranges for the given changes and schedule mirroring of the edits."""
        if not self._ranges:
            return
        if action in {ChangeEventAction.UNDO, ChangeEventAction.REDO}:
            self.clear(glue=False)
            return
        ranges = list(self._ranges)
        for change in changes:
            start = change.a.pt
            end = change.b.pt
            delta = len(change.str) - (end - start)
            for i, r in enumerate(ranges):
                if end < r.a or (end == r.a and start < end):
                    # The change is before this range.
                    ranges[i] = sublime.Region(r.a + delta, r.b + delta)
                elif start > r.b or (start == r.b and start < end):
                    # The change is after this range.
                    continue
                elif r.a <= start and end <= r.b:
                    # The change is inside of this range. An insertion at a boundary of the range is considered to be
                    # inside, so that the range grows.
                    ranges[i] = sublime.Region(r.a, r.b + delta)
                    self._touched.add(i)
                else:
                    # The change partially overlaps this range.
                    self.clear()
                    return
        self._ranges = tuple(ranges)
        self._selection = list(self._view.sel())
        self._draw()
        if not self._sync_pending:
            self._sync_pending = True
            # Running a text command from within `TextChangeListener.on_text_changed` would cause the changes of the
            # current callback to be reported again, so we defer it.
            sublime.set_timeout(self._sync)

    def _draw(self) -> None:
        self._view.add_regions(
            RegionKey.LINKED_EDITING, list(self._ranges), scope=LINKED_EDITING_SCOPE, flags=LINKED_EDITING_FLAGS)

    def _sync(self) -> None:
        touched = self._touched
        self._touched = set()
        view = self._view
        if not self._ranges or not view.is_valid():
            self._sync_pending = False
            return
        if not self.contains_selection():
            # An edit moved a caret out of the ranges, or there is another caret elsewhere. Caret movement caused by an
            # edit doesn't trigger `on_selection_modified`, so this needs to be checked here.
            self._sync_pending = False
            self.clear()
            return
        texts = [view.substr(r) for r in self._ranges]
        if len(set(texts)) > 1:
            if len(touched) != 1:
                self._sync_pending = False
                self.clear()
                return
            primary = touched.pop()
            text = texts[primary]
            if text and not self._word_pattern.fullmatch(text):
                # Linked editing stops when the content doesn't match the word pattern.
                self._sync_pending = False
                self.clear()
                return
            regions = [(r.a, r.b) for i, r in enumerate(self._ranges) if i != primary and texts[i] != text]
            # The ranges get updated through `on_text_changed`, which ST calls synchronously while the command runs.
            # Keep `_sync_pending` set in the meantime, so that the mirrored edits don't schedule another sync.
            view.run_command("lsp_apply_linked_edits", {"regions": regions, "text": text})
            self._touched.clear()
        self._sync_pending = False
        self._selection = list(view.sel())


class LspApplyLinkedEditsCommand(sublime_plugin.TextCommand):
    """Internal command that replaces the given regions with the same text."""

    def run(self, edit: sublime.Edit, regions: list[tuple[int, int]], text: str) -> None:
        for a, b in sorted(regions, reverse=True):
            self.view.replace(edit, sublime.Region(a, b), text)
