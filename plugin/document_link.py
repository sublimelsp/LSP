from __future__ import annotations

from ..protocol import DocumentLink
from ..protocol import URI
from .core.logging import debug
from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
import sublime


class LspOpenLinkCommand(LspTextCommand):
    capability = 'documentLinkProvider'

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
        if not super().is_enabled(event, point):
            return False
        if position := get_position(self.view, event):
            if session := self.best_session(self.capability, position):
                if sv := session.session_view_for_view_async(self.view):
                    return sv.session_buffer.get_document_link_at_point(self.view, position) is not None
        return False

    def run(self, edit: sublime.Edit, event: dict | None = None) -> None:
        if position := get_position(self.view, event):
            if session := self.best_session(self.capability, position):
                if sv := session.session_view_for_view_async(self.view):
                    if link := sv.session_buffer.get_document_link_at_point(self.view, position):
                        if (target := link.get("target")) is not None:
                            self.open_target(target)
                        elif session.has_capability("documentLinkProvider.resolveProvider"):
                            request = Request.resolveDocumentLink(link, self.view)
                            session.send_request_async(request, self._on_resolved_async)
                        else:
                            debug("DocumentLink.target is missing, but the server doesn't support documentLink/resolve")

    def _on_resolved_async(self, response: DocumentLink) -> None:
        if target := response.get("target"):
            self.open_target(target)

    def open_target(self, target: URI) -> None:
        if target.startswith("file:"):
            if window := self.view.window():
                open_file_uri(window, target)
        else:
            open_in_browser(target)
