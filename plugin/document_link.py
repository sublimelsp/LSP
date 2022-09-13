from .core.logging import debug
from .core.open import open_file_uri
from .core.open import open_in_browser
from .core.protocol import DocumentLink, Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.typing import Optional
import sublime


class LspOpenLinkCommand(LspTextCommand):
    capability = 'documentLinkProvider'

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if not super().is_enabled(event, point):
            return False
        position = get_position(self.view, event)
        if not position:
            return False
        session = self.best_session(self.capability, position)
        if not session:
            return False
        sv = session.session_view_for_view_async(self.view)
        if not sv:
            return False
        link = sv.session_buffer.get_document_link_at_point(self.view, position)
        return link is not None

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        point = get_position(self.view, event)
        if not point:
            return
        session = self.best_session(self.capability, point)
        if not session:
            return
        sv = session.session_view_for_view_async(self.view)
        if not sv:
            return
        link = sv.session_buffer.get_document_link_at_point(self.view, point)
        if not link:
            return
        target = link.get("target")

        if target is not None:
            self.open_target(target)
        else:
            if not session.has_capability("documentLinkProvider.resolveProvider"):
                debug("DocumentLink.target is missing, but the server doesn't support documentLink/resolve")
                return
            session.send_request_async(Request.resolveDocumentLink(link, self.view), self._on_resolved_async)

    def _on_resolved_async(self, response: DocumentLink) -> None:
        self.open_target(response["target"])

    def open_target(self, target: str) -> None:
        if target.startswith("file:"):
            window = self.view.window()
            if window:
                open_file_uri(window, target)
        else:
            open_in_browser(target)
