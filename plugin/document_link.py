from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.typing import Optional
from urllib.parse import unquote, urlparse
import re
import sublime
import webbrowser


class LspOpenLinkCommand(LspTextCommand):
    capability = 'documentLinkProvider'

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        point = get_position(self.view, event)
        if not point:
            return False
        session = self.best_session(self.capability, point)
        if not session:
            return False
        sv = session.session_view_for_view_async(self.view)
        if not sv:
            return False
        link = sv.session_buffer.get_document_link_at_point(self.view, point)
        return link is not None

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:

        def open_target(target: str) -> None:
            if target.startswith("file:"):
                window = self.view.window()
                if window:
                    decoded = unquote(target)  # decode percent-encoded characters
                    parsed = urlparse(decoded)
                    filepath = parsed.path
                    if sublime.platform() == "windows":
                        filepath = re.sub(r"^/([a-zA-Z]:)", r"\1", filepath)  # remove slash preceding drive letter
                    fn = "{}:{}".format(filepath, parsed.fragment) if parsed.fragment else filepath
                    window.open_file(fn, flags=sublime.ENCODED_POSITION)
            else:
                if not (target.lower().startswith("http://") or target.lower().startswith("https://")):
                    target = "http://" + target
                if not webbrowser.open(target):
                    sublime.status_message("failed to open: " + target)

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
            open_target(target)
        else:
            # TODO send documentLink/resolve request
            sublime.status_message("Links with unresolved target are currently not supported")
