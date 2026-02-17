from __future__ import annotations

from ..protocol import SelectionRange
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.views import range_to_region
from .core.views import selection_range_params
from typing import Any
import sublime


class LspExpandSelectionCommand(LspTextCommand):

    capability = 'selectionRangeProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._regions: list[sublime.Region] = []
        self._change_count = 0

    def is_enabled(self, event: dict | None = None, point: int | None = None, fallback: bool = False) -> bool:
        return fallback or super().is_enabled(event, point)

    def is_visible(self, event: dict | None = None, point: int | None = None, fallback: bool = False) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point, fallback)
        return True

    def run(self, edit: sublime.Edit, event: dict | None = None, fallback: bool = False) -> None:
        position = get_position(self.view, event)
        if position is None:
            return
        if session := self.best_session(self.capability, position):
            self._regions.extend(self.view.sel())
            self._change_count = self.view.change_count()
            params = selection_range_params(self.view)
            session.send_request(Request.selectionRange(params), self.on_result, self.on_error)
        elif fallback:
            self._run_builtin_expand_selection(f"No {self.capability} found")

    def on_result(self, params: list[SelectionRange] | None) -> None:
        if self._change_count != self.view.change_count():
            return
        if params:
            self.view.run_command("lsp_selection_set", {"regions": [
                self._smallest_containing(region, param) for region, param in zip(self._regions, params)]})
        else:
            self._status_message("Nothing to expand")
        self._regions.clear()

    def on_error(self, params: Any) -> None:
        self._regions.clear()
        self._run_builtin_expand_selection("Error: {}".format(params["message"]))

    def _status_message(self, msg: str) -> None:
        if window := self.view.window():
            window.status_message(msg)

    def _run_builtin_expand_selection(self, fallback_reason: str) -> None:
        self._status_message(f"{fallback_reason}, reverting to built-in Expand Selection")
        self.view.run_command("expand_selection", {"to": "smart"})

    def _smallest_containing(self, region: sublime.Region, param: SelectionRange) -> tuple[int, int]:
        r = range_to_region(param["range"], self.view)
        # Test for *strict* containment
        if r.contains(region) and (r.a < region.a or r.b > region.b):
            return r.a, r.b
        if parent := param.get("parent"):
            return self._smallest_containing(region, parent)
        return region.a, region.b
