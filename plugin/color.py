import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional
    assert Any and List and Dict and Callable and Optional
except ImportError:
    pass

from .core.protocol import Request
from .core.url import filename_to_uri
from .core.registry import session_for_view, sessions_for_view, client_from_session, configs_for_scope
from .core.settings import settings, client_configs
from .core.views import range_to_region
from .core.protocol import Range
from .core.configurations import is_supported_syntax
from .core.documents import is_transient_view


class LspColorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.color_phantom_set = None  # type: Optional[sublime.PhantomSet]
        self._stored_point = -1
        self.initialized = False
        self.enabled = False

    @classmethod
    def is_applicable(cls, _settings):
        syntax = _settings.get('syntax')
        is_supported = syntax and is_supported_syntax(syntax, client_configs.all)
        disabled_by_user = 'colorProvider' in settings.disabled_capabilities
        return is_supported and not disabled_by_user

    def on_activated_async(self):
        if not self.initialized:
            self.initialize()

    def initialize(self, is_retry=False):
        configs = configs_for_scope(self.view)
        if not configs:
            self.initialized = True  # no server enabled, re-open file to activate feature.
        sessions = list(sessions_for_view(self.view))
        if sessions:
            self.initialized = True
            if any(session.has_capability('colorProvider') for session in sessions):
                self.enabled = True
                self.send_color_request()
        elif not is_retry:
            # session may be starting, try again once in a second.
            sublime.set_timeout_async(lambda: self.initialize(is_retry=True), 1000)
        else:
            self.initialized = True  # we retried but still no session available.

    def on_modified_async(self):
        if self.enabled:
            self.schedule_request()

    def schedule_request(self):
        sel = self.view.sel()
        if len(sel) < 1:
            return

        current_point = sel[0].begin()
        if self._stored_point != current_point:
            self._stored_point = current_point
            sublime.set_timeout_async(lambda: self.fire_request(current_point), 800)

    def fire_request(self, current_point: int) -> None:
        if current_point == self._stored_point:
            self.send_color_request()

    def send_color_request(self):
        if is_transient_view(self.view):
            return

        client = client_from_session(session_for_view(self.view, 'colorProvider'))
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                }
            }
            client.send_request(
                Request.documentColor(params),
                self.handle_response
            )

    def handle_response(self, response) -> None:
        phantoms = []
        for val in response:
            color = val['color']
            red = color['red'] * 255
            green = color['green'] * 255
            blue = color['blue'] * 255
            alpha = color['alpha']

            content = """
            <div style='padding: 0.4em;
                        margin-top: 0.2em;
                        border: 1px solid color(var(--foreground) alpha(0.25));
                        background-color: rgba({}, {}, {}, {})'>
            </div>""".format(red, green, blue, alpha)

            range = Range.from_lsp(val['range'])
            region = range_to_region(range, self.view)

            phantoms.append(sublime.Phantom(region, content, sublime.LAYOUT_INLINE))

        if phantoms:
            if not self.color_phantom_set:
                self.color_phantom_set = sublime.PhantomSet(self.view, "lsp_color")
            self.color_phantom_set.update(phantoms)
        else:
            self.color_phantom_set = None


def remove_color_boxes(view):
    view.erase_phantoms('lsp_color')
