from __future__ import annotations

from .core.aio import run_coroutine
from .core.logging import exception_log
from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.settings import userprefs
from .core.url import parse_uri
from .core.views import range_to_region
from .core.views import text_document_identifier
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protocol import URI
    from .core.sessions import Session
    import sublime


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
        run_coroutine(self._run(event, point))

    async def _run(self, event: dict | None, point: int | None) -> None:
        if (position := get_position(self.view, event, point)) is not None:
            if session := self.best_session(self.capability, position):
                response = await session.request(
                    Request.documentLink({'textDocument': text_document_identifier(self.view)}, self.view)
                )
                if isinstance(response, Error):
                    return
                for link in response or []:
                    if range_to_region(link['range'], self.view).contains(position):
                        if (uri := link.get('target')) is not None:
                            await self._open_uri(session, uri)
                        elif session.has_capability('documentLinkProvider.resolveProvider'):
                            link = await session.request(Request.resolveDocumentLink(link, self.view))
                            if isinstance(link, Error):
                                exception_log("error resolving link", link)
                                continue
                            if uri := link.get('target'):
                                await self._open_uri(session, uri)
                        return
                if window := self.view.window():
                    window.status_message('No link available')

    async def _open_uri(self, session: Session, uri: URI) -> None:
        scheme = parse_uri(uri)[0]
        if scheme == 'file':
            if window := self.view.window():
                await open_file_uri(window, uri)
        elif scheme.lower() in {'http', 'https'} or (not scheme and uri.startswith('www.')):
            open_in_browser(uri)
        else:
            await session.open_uri(uri)
