import mdpopups
import sublime
import html
import webbrowser

try:
    from typing import Any, List, Dict, Optional
    assert Any and List and Dict and Optional
except ImportError:
    pass

from .core.configurations import is_supported_syntax
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.documents import get_document_position
from .core.protocol import Request
from .core.popups import popups
from .core.settings import client_configs, settings
from .core.signature_help import create_signature_help, SignatureHelp
assert SignatureHelp


class ColorSchemeScopeRenderer(object):
    def __init__(self, view: sublime.View) -> None:
        self._scope_styles = {}  # type: dict
        self._view = view
        for scope in ["entity.name.function", "variable.parameter", "punctuation"]:
            self._scope_styles[scope] = mdpopups.scope2style(view, scope)

    def function(self, content: str, escape: bool = True) -> str:
        return self._wrap_with_scope_style(content, "entity.name.function", escape=escape)

    def punctuation(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "punctuation")

    def parameter(self, content: str, emphasize: bool = False) -> str:
        return self._wrap_with_scope_style(content, "variable.parameter", emphasize)

    def markdown(self, content: str) -> str:
        return mdpopups.md2html(self._view, content)

    def _wrap_with_scope_style(self, content: str, scope: str, emphasize: bool = False, escape: bool = True) -> str:
        color = self._scope_styles[scope]["color"]
        additional_styles = 'font-weight: bold; text-decoration: underline;' if emphasize else ''
        content = html.escape(content, quote=False) if escape else content
        return '<span style="color: {};{}">{}</span>'.format(color, additional_styles, content)


class SignatureHelpListener(LSPViewEventListener):

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._initialized = False
        self._signature_help_triggers = []  # type: List[str]
        self._signature_help_selector = view.settings().get("auto_complete_selector", "") or ""  # type: str
        self._visible = False
        self._help = None  # type: Optional[SignatureHelp]
        self._renderer = ColorSchemeScopeRenderer(self.view)

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'signatureHelp' in settings.disabled_capabilities:
            return False
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        else:
            return False

    def initialize(self) -> None:
        session = session_for_view(self.view, 'signatureHelpProvider')
        if session:
            signatureHelpProvider = session.get_capability(
                'signatureHelpProvider')
            if signatureHelpProvider:
                self._signature_help_triggers = signatureHelpProvider.get(
                    'triggerCharacters')

        self._initialized = True

    def on_modified_async(self) -> None:
        pos = self.view.sel()[0].begin()
        # TODO: this will fire too often, narrow down using scopes or regex
        if not self._initialized:
            self.initialize()

        if not self.view.match_selector(pos, self._signature_help_selector):
            return

        if self._signature_help_triggers:
            last_char = self.view.substr(pos - 1)
            if last_char in self._signature_help_triggers:
                self.request_signature_help(pos)
            elif self._visible:
                if last_char.isspace():
                    # Peek behind to find the last non-whitespace character.
                    last_non_white_space_position = self.view.find_by_class(pos, False, ~0)
                    last_char = self.view.substr(last_non_white_space_position - 1)
                if last_char not in self._signature_help_triggers:
                    self.view.hide_popup()

    def request_signature_help(self, point: int) -> None:
        self.requested_position = point
        client = client_from_session(session_for_view(self.view, 'signatureHelpProvider', point))
        if client:
            self.manager.documents.purge_changes(self.view)
            document_position = get_document_position(self.view, point)
            if document_position:
                client.send_request(
                    Request.signatureHelp(document_position),
                    lambda response: self.handle_response(response, point))

    def handle_response(self, response: 'Optional[Dict]', point: int) -> None:
        if self.view.sel()[0].begin() == self.requested_position:
            self._help = create_signature_help(response)
            if self._help:
                content = self._help.build_popup_content(self._renderer)
                if self._visible:
                    self._update_popup(content)
                else:
                    self._show_popup(content, point)

    def on_query_context(self, key: str, _operator: int, operand: int, _match_all: bool) -> bool:
        if key != "lsp.signature_help":
            return False  # Let someone else handle this keybinding.
        elif not self._visible:
            if operand == 0:
                self.request_signature_help(self.view.sel()[0].begin())
                return True
            else:
                return False  # Let someone else handle this keybinding.
        elif self._help and self._help.has_multiple_signatures():

            # We use the "operand" for the number -1 or +1. See the keybindings.
            self._help.select_signature(operand)
            self._update_popup(self._help.build_popup_content(self._renderer))

            return True  # We handled this keybinding.

        return False

    def _show_popup(self, content: str, point: int) -> None:
        mdpopups.show_popup(self.view,
                            content,
                            css=popups.stylesheet,
                            md=True,
                            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                            location=point,
                            wrapper_class=popups.classname,
                            max_width=800,
                            on_hide=self._on_hide,
                            on_navigate=self._on_hover_navigate)
        self._visible = True

    def _update_popup(self, content: str) -> None:
        mdpopups.update_popup(self.view,
                              content,
                              css=popups.stylesheet,
                              md=True,
                              wrapper_class=popups.classname)

    def _on_hide(self) -> None:
        self._visible = False

    def _on_hover_navigate(self, href: str) -> None:
        webbrowser.open_new_tab(href)
