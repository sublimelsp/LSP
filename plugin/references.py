from .core.protocol import Location
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.sessions import Session
from .core.typing import List, Optional
from .core.views import text_document_position_params
from .locationpicker import LocationPicker
import functools
import sublime
import weakref


class LspSymbolReferencesCommand(LspTextCommand):

    capability = 'referencesProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._picker = None  # type: Optional[LocationPicker]

    def run(self, _: sublime.Edit, event: Optional[dict] = None, point: Optional[int] = None) -> None:
        session = self.best_session(self.capability)
        file_path = self.view.file_name()
        pos = get_position(self.view, event, point)
        if session and file_path and pos is not None:
            self.weaksession = weakref.ref(session)
            params = text_document_position_params(self.view, pos)
            params['context'] = {"includeDeclaration": False}
            request = Request("textDocument/references", params, self.view, progress=True)
            session.send_request(request, functools.partial(self._handle_response_async, session))

    def _handle_response_async(self, session: Session, response: Optional[List[Location]]) -> None:
        sublime.set_timeout(lambda: self._handle_response(session, response))

    def _handle_response(self, session: Session, response: Optional[List[Location]]) -> None:
        if response:
            self._picker = LocationPicker(self.view, session, response, side_by_side=False)
        else:
            window = self.view.window()
            if window:
                window.status_message("No references found")
