import mdpopups
import sublime
import sublime_plugin

try:
    from typing import Any, List
    assert Any and List
except ImportError:
    pass


from .core.clients import client_for_view
from .core.documents import get_document_position, purge_did_change
from .core.configurations import is_supported_syntax, config_for_scope
from .core.protocol import Request
from .core.logging import debug


class SignatureHelpListener(sublime_plugin.ViewEventListener):

    css = ".mdpopups .lsp_signature { margin: 4px; } .mdpopups p { margin: 0.1rem; }"
    wrapper_class = "lsp_signature"

    def __init__(self, view):
        self.view = view
        self._initialized = False
        self._signature_help_triggers = []  # type: List[str]
        self._visible = False
        self._language_id = ""
        self._signatures = []  # type: List[Any]
        self._active_signature = -1

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def initialize(self):
        client = client_for_view(self.view)
        if client:
            signatureHelpProvider = client.get_capability(
                'signatureHelpProvider')
            if signatureHelpProvider:
                self.signature_help_triggers = signatureHelpProvider.get(
                    'triggerCharacters')

        config = config_for_scope(self.view)
        if config:
            self._language_id = config.languageId

        self._initialized = True

    def on_modified_async(self):
        pos = self.view.sel()[0].begin()
        last_char = self.view.substr(pos - 1)
        # TODO: this will fire too often, narrow down using scopes or regex
        if not self._initialized:
            self.initialize()

        if self.signature_help_triggers:
            if last_char in self.signature_help_triggers:
                client = client_for_view(self.view)
                if client:
                    purge_did_change(self.view.buffer_id())
                    document_position = get_document_position(self.view, pos)
                    if document_position:
                        client.send_request(
                            Request.signatureHelp(document_position),
                            lambda response: self.handle_response(response, pos))
            else:
                # TODO: this hides too soon.
                if self._visible:
                    self.view.hide_popup()

    def handle_response(self, response, point):
        if response is not None:
            self._signatures = response.get("signatures", [])
            self._active_signature = response.get("activeSignature", -1)

            if self._signatures:
                if not 0 <= self._active_signature < len(self._signatures):
                    debug("activeSignature {} not a valid index for signatures length {}".format(
                        self._active_signature, len(self._signatures)))
                    self._active_signature = 0
            else:
                if self._active_signature != -1:
                    debug("activeSignature should be -1 or null when no signatures are returned")
                    self._active_signature = -1

            if len(self._signatures) > 0:
                mdpopups.show_popup(self.view,
                                    self._build_popup_content(),
                                    css=self.__class__.css,
                                    md=True,
                                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                                    location=point,
                                    wrapper_class=self.__class__.wrapper_class,
                                    max_width=800,
                                    on_hide=self._on_hide)
                self._visible = True

    def on_query_context(self, key, _, operand, __):
        if key != "lsp.signature_help":
            return False  # Let someone else handle this keybinding.
        elif not self._visible:
            return False  # Let someone else handle this keybinding.
        elif len(self._signatures) < 2:
            return False  # Let someone else handle this keybinding.
        else:
            # We use the "operand" for the number -1 or +1. See the keybindings.
            new_index = self._active_signature + operand

            # clamp signature index
            new_index = max(0, min(new_index, len(self._signatures) - 1))

            # only update when changed
            if new_index != self._active_signature:
                self._active_signature = new_index
                mdpopups.update_popup(self.view,
                                      self._build_popup_content(),
                                      css=self.__class__.css,
                                      md=True,
                                      wrapper_class=self.__class__.wrapper_class)

            return True  # We handled this keybinding.

    def _on_hide(self):
        self._visible = False

    def _build_popup_content(self) -> str:
        signature = self._signatures[self._active_signature]
        formatted = []

        if len(self._signatures) > 1:
            signature_navigation = "**{}** of **{}** overloads (use the arrow keys to navigate):\n".format(
                str(self._active_signature + 1), str(len(self._signatures)))
            formatted.append(signature_navigation)

        label = "```{}\n{}\n```".format(self._language_id, signature.get('label'))
        formatted.append(label)

        params = signature.get('parameters')
        if params:
            for parameter in params:
                paramDocs = parameter.get('documentation', None)
                if paramDocs:
                    formatted.append("**{}**\n".format(parameter.get('label')))
                    formatted.append("* *{}*\n".format(paramDocs))
        sigDocs = signature.get('documentation', None)
        if sigDocs:
            formatted.append(sigDocs)
        return preserve_whitespace("\n".join(formatted))


def preserve_whitespace(contents: str) -> str:
    """Preserve empty lines and whitespace for markdown conversion."""
    contents = contents.strip(' \t\r\n')
    contents = contents.replace('\t', '&nbsp;' * 4)
    contents = contents.replace('  ', '&nbsp;' * 2)
    contents = contents.replace('\n\n', '\n&nbsp;\n')
    return contents
