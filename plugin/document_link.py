from __future__ import annotations

from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.settings import userprefs
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

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
        if not super().is_enabled(event, point):
            return False
        if userprefs().link_highlight_style == 'underline':
            if (position := get_position(self.view, event, point)) is not None:
                if session := self.best_session(self.capability, position):
                    if sv := session.session_view_for_view_async(self.view):
                        return sv.session_buffer.get_document_link_at_point(self.view, position) is not None
            return False
        return True

    def run(self, edit: sublime.Edit, event: dict | None = None, point: int | None = None) -> None:
        sublime.set_timeout_async(lambda: self._run_async(event, point))

    def _run_async(self, event: dict | None, point: int | None) -> None:
        if (position := get_position(self.view, event, point)) is not None:
            if session := self.best_session(self.capability, position):
                session.send_request_async(
                    Request.documentLink({'textDocument': text_document_identifier(self.view)}, self.view),
                    partial(self._on_response_async, session, position)
                )

    def _on_response_async(self, session: Session, point: int, response: list[DocumentLink] | None) -> None:
        for link in response or []:
            if range_to_region(link['range'], self.view).contains(point):
                if (uri := link.get('target')) is not None:
                    self._open_uri_async(session, uri)
                elif session.has_capability('documentLinkProvider.resolveProvider'):
                    request = Request.resolveDocumentLink(link, self.view)
                    session.send_request_async(request, partial(self._on_resolved_async, session))
                return
        if window := self.view.window():
            window.status_message('No link available')

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
