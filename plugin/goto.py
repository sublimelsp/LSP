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

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None, side_by_side: bool = False) -> bool:
        return super().is_enabled(event, point)

    def run(
        self,
        _: sublime.Edit,
        event: Optional[dict] = None,
        point: Optional[int] = None,
        side_by_side: bool = False
    ) -> None:
        session = self.best_session(self.capability)
        if session:
            params = text_document_position_params(self.view, get_position(self.view, event, point))
            request = Request(self.method, params, self.view, progress=True)
            session.send_request(request, functools.partial(self._handle_response_async, session, side_by_side))

    def _handle_response_async(
        self,
        session: Session,
        side_by_side: bool,
        response: Union[None, Location, List[Location], List[LocationLink]]
    ) -> None:
        if isinstance(response, dict):
            open_location_async(session, response, side_by_side)
        elif isinstance(response, list):
            if len(response) == 0:
                window = self.view.window()
                if window:
                    window.status_message("No results found")
            elif len(response) == 1:
                open_location_async(session, response[0], side_by_side)
            else:
                sublime.set_timeout(functools.partial(LocationPicker, self.view, session, response, side_by_side))
        else:
            window = self.view.window()
            if window:
                window.status_message("No results found")


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
