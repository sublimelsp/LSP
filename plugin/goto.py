import sublime
from Default.history_list import get_jump_history_for_view
from .core.documents import get_position, is_at_word
from .core.logging import debug
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.typing import List, Optional, Any
from .core.views import location_to_encoded_filename
from .core.views import text_document_position_params


def process_response_list(responses: list) -> List[str]:
    return [location_to_encoded_filename(x) for x in responses]


def open_location(window: sublime.Window, location: str) -> None:
    debug("opening location", location)
    window.open_file(location, sublime.ENCODED_POSITION)


def select_entry(window: Optional[sublime.Window], locations: List[str], idx: int, orig_view: sublime.View) -> None:
    if not window:
        return
    if idx >= 0:
        open_location(window, locations[idx])
    elif orig_view:
        window.focus_view(orig_view)


def highlight_entry(window: Optional[sublime.Window], locations: List[str], idx: int) -> None:
    if not window:
        return
    window.open_file(locations[idx], group=window.active_group(), flags=sublime.TRANSIENT | sublime.ENCODED_POSITION)


class LspGotoCommand(LspTextCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.goto_kind = "definition"

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        if self.has_client_with_capability(self.goto_kind + "Provider"):
            return is_at_word(self.view, event)
        return False

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        client = self.client_with_capability(self.goto_kind + "Provider")
        if client:
            pos = get_position(self.view, event)
            document_position = text_document_position_params(self.view, pos)
            request_type = getattr(Request, self.goto_kind)
            if not request_type:
                debug("unrecognized goto kind:", self.goto_kind)
                return
            request = request_type(document_position)
            client.send_request(request, self.handle_response)

    def handle_response(self, response: Any) -> None:
        window = self.view.window()
        view = self.view
        if window is None:
            return
        if response:
            # Save to jump back history.
            get_jump_history_for_view(view).push_selection(view)
            # TODO: DocumentLink support.
            if isinstance(response, dict):
                locations = [location_to_encoded_filename(response)]
            else:
                locations = process_response_list(response)
            if len(locations) == 1:
                open_location(window, locations[0])
            elif len(locations) > 1:
                window.show_quick_panel(
                    items=locations,
                    on_select=lambda x: select_entry(window, locations, x, view),
                    on_highlight=lambda x: highlight_entry(window, locations, x),
                    flags=sublime.KEEP_OPEN_ON_FOCUS_LOST)
            # TODO: can add region here.
        else:
            sublime.status_message("Empty response from language server, "
                                   "reverting to Sublime's built-in Goto Definition")
            window.run_command("goto_definition")

    def want_event(self) -> bool:
        return True


class LspSymbolDefinitionCommand(LspGotoCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.goto_kind = "definition"


class LspSymbolTypeDefinitionCommand(LspGotoCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.goto_kind = "typeDefinition"


class LspSymbolDeclarationCommand(LspGotoCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.goto_kind = "declaration"


class LspSymbolImplementationCommand(LspGotoCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.goto_kind = "implementation"
