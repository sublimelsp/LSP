from __future__ import annotations

from .core.protocol import Error
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.views import range_to_region
from .core.views import selection_range_params
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protocol import SelectionRange
    import sublime


class LspExpandSelectionCommand(LspTextCommand):

    capability = 'selectionRangeProvider'

    def is_enabled(self, event: dict | None = None, point: int | None = None, fallback: bool = False) -> bool:
        return fallback or super().is_enabled(event, point)

    def is_visible(self, event: dict | None = None, point: int | None = None, fallback: bool = False) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point, fallback)
        return True

    async def run(self, event: dict | None = None, fallback: bool = False) -> None:
        position = get_position(self.view, event)
        if position is None:
            return
        session = self.best_session(self.capability, position)
        if not session:
            if fallback:
                self._run_builtin_expand_selection(f"No {self.capability} found")
            return
        regions = list(self.view.sel())
        change_count = self.view.change_count()
        params = selection_range_params(self.view)
        response = await session.request(Request.selectionRange(params))
        if isinstance(response, Error):
            self._run_builtin_expand_selection(f"Error: {response}")
            return
        if change_count != self.view.change_count():
            return
        if response:
            self.view.run_command("lsp_selection_set",
                                  {"regions": list(map(self._smallest_containing, regions, response))})
        else:
            self._status_message("Nothing to expand")

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
