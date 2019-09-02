import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional
    assert Any and List and Dict and Callable and Optional
except ImportError:
    pass

from .core.protocol import Request
from .core.url import filename_to_uri
from .core.registry import session_for_view, config_for_scope
from .core.settings import settings, client_configs
from .core.views import range_to_region
from .core.protocol import Range
from .core.configurations import is_supported_syntax
from .core.events import global_events


class LspColorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.color_phantom_set = None  # type: Optional[sublime.PhantomSet]
        self._stored_point = -1
        self.enabled = False
        self.session = None

    @classmethod
    def is_applicable(cls, _settings):
        syntax = _settings.get('syntax')
        is_supported = syntax and is_supported_syntax(syntax, client_configs.all)
        disabled = 'colorProvider' in settings.disabled_capabilities
        return is_supported and not disabled

    def on_activated_async(self):
        self.session = session_for_view(self.view)
        if not self.session:
            self.initialize_session()
            return

        self.enabled = self.session.has_capability('colorProvider')
        if self.enabled:
            self.schedule_request()

    def on_modified_async(self):
        if self.enabled:
            self.schedule_request()

    def initialize_session(self):
        config = config_for_scope(self.view)
        if config:
            print('add listener', "initialized.{}".format(config.name))
            global_events.subscribe("initialized.{}".format(config.name), self.on_session_initialized)

    def on_session_initialized(self, session):
        print('remove listener', 'initialized.{}'.format(session.config.name))
        global_events.unsubscribe('initialized.{}'.format(session.config.name), self.on_session_initialized)

        self.enabled = session.has_capability('colorProvider')
        if self.enabled:
            self.session = session
            self.send_color_request()

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
        params = {
            "textDocument": {
                "uri": filename_to_uri(self.view.file_name())
            }
        }
        self.session.client.send_request(
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
                        margin-top: 0.1em;
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
