import sublime
from .core.protocol import Request
from .core.registry import LSPViewEventListener
from .core.settings import settings
from .core.types import debounced
from .core.typing import List, Optional
from .core.views import document_color_params
from .core.views import lsp_color_to_phantom


class LspColorListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_point = -1
        self.initialized = False
        self.enabled = False
        self._phantoms = sublime.PhantomSet(self.view, "lsp_color")

    def __del__(self) -> None:
        self._stored_point = -1  # Prevent a debounced request to alter the phantoms again
        self._phantoms.update([])

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'colorProvider' in settings.disabled_capabilities:
            return False
        return cls.has_supported_syntax(view_settings)

    def on_activated_async(self) -> None:
        if not self.initialized:
            self.initialize()

    def initialize(self, is_retry: bool = False) -> None:
        if self.session('colorProvider'):
            self.initialized = True
            self.enabled = True
            self.fire_request()
        elif not is_retry:
            # session may be starting, try again once in a second.
            sublime.set_timeout_async(lambda: self.initialize(is_retry=True), 1000)
        else:
            self.initialized = True  # we retried but still no session available.

    def on_modified_async(self) -> None:
        if self.enabled:
            sel = self.view.sel()
            if len(sel) < 1:
                return
            current_point = sel[0].b
            if self._stored_point != current_point:
                self._stored_point = current_point
                debounced(self.fire_request, 800, lambda: self._stored_point == current_point, async_thread=True)

    def fire_request(self) -> None:
        session = self.session('colorProvider')
        if session:
            session.send_request(Request.documentColor(document_color_params(self.view)), self.handle_response)

    def handle_response(self, response: Optional[List[dict]]) -> None:
        color_infos = response if response else []
        self._phantoms.update([lsp_color_to_phantom(self.view, color_info) for color_info in color_infos])
