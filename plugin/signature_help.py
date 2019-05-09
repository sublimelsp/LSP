import mdpopups
import sublime
import sublime_plugin
import webbrowser

try:
    from typing import Any, List, Dict, Optional
    assert Any and List and Dict and Optional
except ImportError:
    pass

from .core.configurations import is_supported_syntax
from .core.registry import config_for_scope, session_for_view, client_for_view
from .core.documents import get_document_position
from .core.events import global_events
from .core.protocol import Request
from .core.popups import popup_css, popup_class
from .core.settings import client_configs
from .core.signature_help import create_signature_help, SignatureHelp, ScopeRenderer
assert SignatureHelp


class ColorSchemeScopeRenderer(ScopeRenderer):
    def __init__(self, view) -> None:
        self._scope_styles = {}  # type: dict
        for scope in ["entity.name.function", "variable.parameter", "punctuation"]:
            self._scope_styles[scope] = mdpopups.scope2style(view, scope)

    def render_function(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "entity.name.function")

    def render_punctuation(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "punctuation")

    def render_parameter(self, content: str, emphasize: bool = False) -> str:
        return self._wrap_with_scope_style(content, "variable.parameter", emphasize)

    def _wrap_with_scope_style(self, content: str, scope: str, emphasize: bool = False) -> str:
        color = self._scope_styles[scope]["color"]
        weight_style = ';font-weight: bold' if emphasize else ''
        return '<span style="color: {}{}">{}</span>'.format(color, weight_style, content)


class SignatureHelpListener(sublime_plugin.ViewEventListener):

    def __init__(self, view):
        self.view = view
        self._initialized = False
        self._signature_help_triggers = []  # type: List[str]
        self._visible = False
        self._language_id = ""
        self._help = None  # type: Optional[SignatureHelp]
        self._renderer = ColorSchemeScopeRenderer(self.view)

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax, client_configs.all)

    def initialize(self):
        session = session_for_view(self.view)
        if session:
            signatureHelpProvider = session.get_capability(
                'signatureHelpProvider')
            if signatureHelpProvider:
                self._signature_help_triggers = signatureHelpProvider.get(
                    'triggerCharacters')

        config = config_for_scope(self.view)
        if config:
            self._language_id = self._view_language(self.view, config.name)

        self._initialized = True

    def on_modified_async(self):
        pos = self.view.sel()[0].begin()
        # TODO: this will fire too often, narrow down using scopes or regex
        if not self._initialized:
            self.initialize()

        if self._signature_help_triggers:
            last_char = self.view.substr(pos - 1)
            if last_char in self._signature_help_triggers:
                self.request_signature_help(pos)
            elif self._visible:
                if last_char.isspace():
                    # Peek behind to find the last non-whitespace character.
                    last_char = self.view.substr(self.view.find_by_class(pos, False, ~0) - 1)
                if last_char not in self._signature_help_triggers:
                    self.view.hide_popup()

    def request_signature_help(self, point) -> None:
        client = client_for_view(self.view)
        if client:
            global_events.publish("view.on_purge_changes", self.view)
            document_position = get_document_position(self.view, point)
            if document_position:
                client.send_request(
                    Request.signatureHelp(document_position),
                    lambda response: self.handle_response(response, point))

    def handle_response(self, response: 'Optional[Dict]', point) -> None:
        self._help = create_signature_help(response, self._renderer)
        if self._help:
            if self._visible:
                self._update_popup()
            else:
                self._show_popup(point)

    def on_query_context(self, key, _, operand, __):
        if key != "lsp.signature_help":
            return False  # Let someone else handle this keybinding.
        elif not self._visible:
            if operand == 0:
                self.request_signature_help(self.view.sel()[0].begin())
                return True
            else:
                return False  # Let someone else handle this keybinding.
        elif self._help and self._help.has_overloads():

            # We use the "operand" for the number -1 or +1. See the keybindings.
            self._help.select_signature(operand)
            self._update_popup()

            return True  # We handled this keybinding.

        return False

    def _build_popup_content(self) -> str:
        if self._help:
            return self._help.build_popup_content()
        return ""

    def _show_popup(self, point: int) -> None:
        mdpopups.show_popup(self.view,
                            self._build_popup_content(),
                            css=popup_css,
                            md=True,
                            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                            location=point,
                            wrapper_class=popup_class,
                            max_width=800,
                            on_hide=self._on_hide,
                            on_navigate=self._on_hover_navigate)
        self._visible = True

    def _update_popup(self) -> None:
        mdpopups.update_popup(self.view,
                              self._build_popup_content(),
                              css=popup_css,
                              md=True,
                              wrapper_class=popup_class)

    def _view_language(self, view: sublime.View, config_name: str) -> 'Optional[str]':
        languages = view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def _on_hide(self):
        self._visible = False

    def _on_hover_navigate(self, href):
        webbrowser.open_new_tab(href)
