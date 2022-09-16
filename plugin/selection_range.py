from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.sessions import method_to_capability
from .core.typing import Any, Dict, Optional, List, Tuple
from .core.views import range_to_region
from .core.views import selection_range_params
import sublime


class LspExpandSelectionCommand(LspTextCommand):
    method = 'textDocument/selectionRange'
    capability = method_to_capability(method)[0]

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._regions = []  # type: List[sublime.Region]
        self._change_count = 0

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        return True

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        position = get_position(self.view, event)
        if position is None:
            return
        session = self.best_session(self.capability, position)
        if session:
            params = selection_range_params(self.view)
            self._regions.extend(self.view.sel())
            self._change_count = self.view.change_count()
            session.send_request(Request(self.method, params), self.on_result, self.on_error)
        else:
            self._run_builtin_expand_selection("No {} found".format(self.capability))

    def on_result(self, params: Any) -> None:
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
        window = self.view.window()
        if window:
            window.status_message(msg)

    def _run_builtin_expand_selection(self, fallback_reason: str) -> None:
        self._status_message("{}, reverting to built-in Expand Selection".format(fallback_reason))
        self.view.run_command("expand_selection", {"to": "smart"})

    def _smallest_containing(self, region: sublime.Region, param: Dict[str, Any]) -> Tuple[int, int]:
        r = range_to_region(param["range"], self.view)
        # Test for *strict* containment
        if r.contains(region) and (r.a < region.a or r.b > region.b):
            return r.a, r.b
        parent = param.get("parent")
        if parent:
            return self._smallest_containing(region, parent)
        return region.a, region.b
