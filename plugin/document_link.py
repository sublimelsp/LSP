from __future__ import annotations

from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.url import parse_uri
from .core.views import range_to_region
from .core.views import text_document_identifier
from functools import partial
from typing import TYPE_CHECKING
import sublime

if TYPE_CHECKING:
    from ..protocol import DocumentLink
    from ..protocol import URI
    from .core.sessions import Session


class LspOpenLinkCommand(LspTextCommand):

    capability = 'documentLinkProvider'

    def run(self, edit: sublime.Edit, event: dict | None = None) -> None:
        sublime.set_timeout_async(lambda: self._run_async(event))

    def _run_async(self, event: dict | None) -> None:
        if (position := get_position(self.view, event)) is not None:
            if session := self.best_session(self.capability, position):
                session.send_request_async(
                    Request.documentLink({'textDocument': text_document_identifier(self.view)}, self.view),
                    partial(self._on_response_async, session, position)
                )

    def _on_response_async(self, session: Session, point: int, response: list[DocumentLink] | None) -> None:
        if not response:
            return
        for link in response:
            if range_to_region(link['range'], self.view).contains(point):
                if (uri := link.get('target')) is not None:
                    self._open_uri_async(session, uri)
                elif session.has_capability('documentLinkProvider.resolveProvider'):
                    request = Request.resolveDocumentLink(link, self.view)
                    session.send_request_async(request, partial(self._on_resolved_async, session))
                return

    def _on_resolved_async(self, session: Session, response: DocumentLink) -> None:
        if uri := response.get('target'):
            self._open_uri_async(session, uri)

    def _open_uri_async(self, session: Session, uri: URI) -> None:
        scheme = parse_uri(uri)[0]
        if scheme == 'file':
            if window := self.view.window():
                open_file_uri(window, uri)
        elif scheme.lower() in {'http', 'https'} or (not scheme and uri.startswith('www.')):
            open_in_browser(uri)
        else:
            session.open_uri_async(uri)
