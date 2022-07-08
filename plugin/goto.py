from .core.protocol import Location
from .core.protocol import LocationLink
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.sessions import Session, method_to_capability
from .core.typing import List, Optional, Union
from .core.views import text_document_position_params
from .locationpicker import LocationPicker
from .locationpicker import open_location_async
import functools
import sublime


class LspGotoCommand(LspTextCommand):

    method = ''
    fallback_command = ''

    def is_enabled(
        self,
        event: Optional[dict] = None,
        point: Optional[int] = None,
        side_by_side: bool = False,
        fallback: bool = False
    ) -> bool:
        return fallback or super().is_enabled(event, point)

    def run(
        self,
        _: sublime.Edit,
        event: Optional[dict] = None,
        point: Optional[int] = None,
        side_by_side: bool = False,
        fallback: bool = False
    ) -> None:
        session = self.best_session(self.capability)
        position = get_position(self.view, event, point)
        if session and position is not None:
            params = text_document_position_params(self.view, position)
            request = Request(self.method, params, self.view, progress=True)
            session.send_request(
                request, functools.partial(self._handle_response_async, session, side_by_side, fallback)
            )
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_response_async(
        self,
        session: Session,
        side_by_side: bool,
        fallback: bool,
        response: Union[None, Location, List[Location], List[LocationLink]]
    ) -> None:
        if isinstance(response, dict):
            self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
            open_location_async(session, response, side_by_side)
        elif isinstance(response, list):
            if len(response) == 0:
                self._handle_no_results(fallback, side_by_side)
            elif len(response) == 1:
                self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
                open_location_async(session, response[0], side_by_side)
            else:
                self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
                sublime.set_timeout(functools.partial(LocationPicker, self.view, session, response, side_by_side))
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_no_results(self, fallback: bool = False, side_by_side: bool = False) -> None:
        window = self.view.window()

        if not window:
            return

        if fallback and self.fallback_command:
            window.run_command(self.fallback_command, {"side_by_side": side_by_side})
        else:
            window.status_message("No results found")


class LspSymbolDefinitionCommand(LspGotoCommand):
    method = "textDocument/definition"
    capability = method_to_capability(method)[0]
    fallback_command = "goto_definition"


class LspSymbolTypeDefinitionCommand(LspGotoCommand):
    method = "textDocument/typeDefinition"
    capability = method_to_capability(method)[0]


class LspSymbolDeclarationCommand(LspGotoCommand):
    method = "textDocument/declaration"
    capability = method_to_capability(method)[0]


class LspSymbolImplementationCommand(LspGotoCommand):
    method = "textDocument/implementation"
    capability = method_to_capability(method)[0]
