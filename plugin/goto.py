import sublime

from .core.registry import LspTextCommand
from .core.protocol import Request, Point
from .core.documents import get_document_position, get_position, is_at_word
from .core.url import uri_to_filename
from .core.logging import debug
from Default.history_list import get_jump_history_for_view

try:
    from typing import List, Dict, Optional, Any
    assert List and Dict and Optional and Any
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
        window = sublime.active_window()
        if response:
            # Save to jump back history.
            get_jump_history_for_view(self.view).push_selection(self.view)
            # TODO: DocumentLink support.
            location = response if isinstance(response, dict) else response[0]
            if "targetUri" in location:
                # TODO: Do something clever with originSelectionRange and targetRange.
                file_path = uri_to_filename(location["targetUri"])
                start = Point.from_lsp(location["targetSelectionRange"]["start"])
            else:
                file_path = uri_to_filename(location["uri"])
                start = Point.from_lsp(location["range"]["start"])
            file_location = "{}:{}:{}".format(file_path, start.row + 1, start.col + 1)
            debug("opening location", location)
            window.open_file(file_location, sublime.ENCODED_POSITION)
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
