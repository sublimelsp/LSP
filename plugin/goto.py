import sublime
from .core.logging import debug
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.sessions import method_to_capability
from .core.typing import List, Optional, Any
from .core.views import location_to_encoded_filename
from .core.views import text_document_position_params
from .documents import is_at_word


def process_response_list(responses: list) -> List[str]:
    return [location_to_encoded_filename(x) for x in responses]


def open_location(window: sublime.Window, location: str, side_by_side: bool = True) -> None:
    debug("opening location", location)
    flags = sublime.ENCODED_POSITION
    if side_by_side:
        flags |= sublime.ADD_TO_SELECTION_SEMI_TRANSIENT
    window.open_file(location, flags)


def select_entry(window: Optional[sublime.Window], locations: List[str], idx: int, orig_view: sublime.View,
                 side_by_side: bool) -> None:
    if not window:
        return
    if idx >= 0:
        open_location(window, locations[idx], side_by_side)
    elif orig_view:
        window.focus_view(orig_view)


def highlight_entry(window: Optional[sublime.Window], locations: List[str], idx: int) -> None:
    if not window:
        return
    window.open_file(locations[idx], group=window.active_group(), flags=sublime.TRANSIENT | sublime.ENCODED_POSITION)


class LspGotoCommand(LspTextCommand):

    method = ''

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        return super().is_enabled(event) and is_at_word(self.view, event)

    def run(self, edit: sublime.Edit, event: Optional[dict] = None, side_by_side: bool = False) -> None:
        session = self.best_session(self.capability)
        if session:
            pos = get_position(self.view, event)
            request = Request(self.method, text_document_position_params(self.view, pos), self.view)
            session.send_request(request, lambda response: self.handle_response(response, side_by_side))

    def handle_response(self, response: Any, side_by_side: bool) -> None:
        window = self.view.window()
        view = self.view
        if window is None:
            return
        if response:
            if len(view.sel()) > 0:
                view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in view.sel()]})
            if isinstance(response, dict):
                locations = [location_to_encoded_filename(response)]
            else:
                locations = process_response_list(response)
            if len(locations) == 1:
                open_location(window, locations[0], side_by_side)
            elif len(locations) > 1:
                window.show_quick_panel(
                    items=locations,
                    on_select=lambda x: select_entry(window, locations, x, view, side_by_side),
                    on_highlight=lambda x: highlight_entry(window, locations, x),
                    flags=sublime.KEEP_OPEN_ON_FOCUS_LOST)
            # TODO: can add region here.
        else:
            sublime.status_message("Empty response from language server, "
                                   "reverting to Sublime's built-in Goto Definition")
            window.run_command("goto_definition", {"side_by_side": side_by_side})


class LspSymbolDefinitionCommand(LspGotoCommand):
    method = "textDocument/definition"
    capability = method_to_capability(method)[0]


class LspSymbolTypeDefinitionCommand(LspGotoCommand):
    method = "textDocument/typeDefinition"
    capability = method_to_capability(method)[0]


class LspSymbolDeclarationCommand(LspGotoCommand):
    method = "textDocument/declaration"
    capability = method_to_capability(method)[0]


class LspSymbolImplementationCommand(LspGotoCommand):
    method = "textDocument/implementation"
    capability = method_to_capability(method)[0]
