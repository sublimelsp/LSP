import sublime

from .core.registry import LspTextCommand
from .core.protocol import Request, Point
from .core.documents import get_document_position, get_position, is_at_word
from .core.url import uri_to_filename
from .core.logging import debug
from Default.history_list import get_jump_history_for_view

try:
    from typing import List, Dict, Optional, Any, Tuple
    assert List and Dict and Optional and Any and Tuple
except ImportError:
    pass


class LspGotoCommand(LspTextCommand):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.goto_kind = "definition"

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        if self.has_client_with_capability(self.goto_kind + "Provider"):
            return is_at_word(self.view, event)
        return False

    def run(self, edit: sublime.Edit, event: 'Optional[dict]' = None) -> None:
        client = self.client_with_capability(self.goto_kind + "Provider")
        if client:
            pos = get_position(self.view, event)
            document_position = get_document_position(self.view, pos)
            if document_position:
                request_type = getattr(Request, self.goto_kind)
                if not request_type:
                    debug("unrecognized goto kind:", self.goto_kind)
                    return
                request = request_type(document_position)
                client.send_request(
                    request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response: 'Optional[Any]', position: int) -> None:
        def process_response_list(responses: list) -> 'List[Tuple[str, str, Tuple[int, int]]]':
            return [process_response(x) for x in responses]

        def process_response(response: dict) -> 'Tuple[str, str, Tuple[int, int]]':
            if "targetUri" in response:
                # TODO: Do something clever with originSelectionRange and targetRange.
                file_path = uri_to_filename(response["targetUri"])
                start = Point.from_lsp(response["targetSelectionRange"]["start"])
            else:
                file_path = uri_to_filename(response["uri"])
                start = Point.from_lsp(response["range"]["start"])
            row = start.row + 1
            col = start.col + 1
            file_path_and_row_col = "{}:{}:{}".format(file_path, row, col)
            return file_path, file_path_and_row_col, (row, col)

        def open_location(window: sublime.Window, location: 'Tuple[str, str, Tuple[int, int]]') -> None:
            fname, file_path_and_row_col, rowcol = location
            row, col = rowcol
            debug("opening location", file_path_and_row_col)
            window.open_file(
                file_path_and_row_col,
                sublime.ENCODED_POSITION | sublime.FORCE_GROUP)

        def select_entry(
                window: sublime.Window,
                locations: 'List[Tuple[str, str, Tuple[int, int]]]',
                idx: int,
                orig_view: sublime.View) -> None:
            if idx >= 0:
                open_location(window, locations[idx])
            else:
                if orig_view:
                    window.focus_view(orig_view)

        def highlight_entry(
                window: sublime.Window,
                locations: 'List[Tuple[str, str, Tuple[int, int]]]',
                idx: int) -> None:
            fname, file_path_and_row_col, rowcol = locations[idx]
            row, col = rowcol
            window.open_file(
                    file_path_and_row_col,
                    group=window.active_group(),
                    flags=sublime.TRANSIENT | sublime.ENCODED_POSITION | sublime.FORCE_GROUP)

        window = sublime.active_window()
        view = self.view
        if response:
            # Save to jump back history.
            get_jump_history_for_view(view).push_selection(view)
            # TODO: DocumentLink support.
            if isinstance(response, dict):
                locations = [process_response(response)]
            else:
                locations = process_response_list(response)
            if len(locations) == 1:
                open_location(window, locations[0])
            elif len(locations) > 1:
                window.show_quick_panel(
                    items=[display_name for file_path, display_name, rowcol in locations],
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
