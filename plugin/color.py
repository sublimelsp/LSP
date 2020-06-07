import sublime
from .core.documents import is_transient_view
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import LSPViewEventListener
from .core.settings import settings
from .core.typing import List, Dict, Optional
from .core.url import filename_to_uri
from .core.views import range_to_region
from .core.windows import debounced


color_phantoms_by_view = dict()  # type: Dict[int, sublime.PhantomSet]


class LspColorListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_point = -1
        self.initialized = False
        self.enabled = False

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'colorProvider' in settings.disabled_capabilities:
            return False
        return cls.has_supported_syntax(view_settings)

    @property
    def phantom_set(self) -> sublime.PhantomSet:
        return color_phantoms_by_view.setdefault(self.view.id(), sublime.PhantomSet(self.view, "lsp_color"))

    def on_activated_async(self) -> None:
        if not self.initialized:
            self.initialize()

    def initialize(self, is_retry: bool = False) -> None:
        if self.session('colorProvider'):
            self.initialized = True
            self.enabled = True
            self.send_color_request()
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
            current_point = sel[0].begin()
            if self._stored_point != current_point:
                self._stored_point = current_point
                debounced(self.send_color_request, 800, lambda: self._stored_point == current_point, async_thread=True)

    def send_color_request(self) -> None:
        if is_transient_view(self.view):
            return

        session = self.session('colorProvider')
        if session:
            file_path = self.view.file_name()
            if file_path:
                params = {
                    "textDocument": {
                        "uri": filename_to_uri(file_path)
                    }
                }
                session.send_request(
                    Request.documentColor(params),
                    self.handle_response
                )

    def handle_response(self, response: Optional[List[dict]]) -> None:
        color_infos = response if response else []
        phantoms = []
        for color_info in color_infos:
            color = color_info['color']
            red = color['red'] * 255
            green = color['green'] * 255
            blue = color['blue'] * 255
            alpha = color['alpha']

            content = """
            <style>html {{padding: 0}}</style>
            <div style='padding: 0.4em;
                        margin-top: 0.2em;
                        border: 1px solid color(var(--foreground) alpha(0.25));
                        background-color: rgba({}, {}, {}, {})'>
            </div>""".format(red, green, blue, alpha)

            range = Range.from_lsp(color_info['range'])
            region = range_to_region(range, self.view)

            phantoms.append(sublime.Phantom(region, content, sublime.LAYOUT_INLINE))

        self.phantom_set.update(phantoms)


def remove_color_boxes(view: sublime.View) -> None:
    phantom_set = color_phantoms_by_view.get(view.id())
    if phantom_set:
        phantom_set.update([])
