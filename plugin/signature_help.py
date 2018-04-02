import mdpopups
import sublime
import sublime_plugin
import webbrowser
import re
import html

try:
    from typing import Any, List, Dict
    assert Any and List and Dict
except ImportError:
    pass


from .core.clients import client_for_view
from .core.documents import get_document_position, purge_did_change
from .core.configurations import is_supported_syntax, config_for_scope
from .core.protocol import Request
from .core.logging import debug
from .core.popups import popup_css, popup_class
from .core.settings import settings


class SignatureHelpListener(sublime_plugin.ViewEventListener):

    def __init__(self, view):
        self.view = view
        self._initialized = False
        self._signature_help_triggers = []  # type: List[str]
        self._visible = False
        self._language_id = ""
        self._signatures = []  # type: List[Any]
        self._active_signature = -1
        self._active_parameter = -1

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
                self._signature_help_triggers = signatureHelpProvider.get(
                    'triggerCharacters')

        config = config_for_scope(self.view)
        if config:
            self._language_id = config.languageId

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

    def request_signature_help(self, point):
        client = client_for_view(self.view)
        if client:
            purge_did_change(self.view.buffer_id())
            document_position = get_document_position(self.view, point)
            if document_position:
                client.send_request(
                    Request.signatureHelp(document_position),
                    lambda response: self.handle_response(response, point))

    def handle_response(self, response, point):
        if response is not None:
            self._signatures = response.get("signatures", [])
            self._active_signature = response.get("activeSignature", -1)
            self._active_parameter = response.get("activeParameter", -1)

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
                self._update_popup()

            return True  # We handled this keybinding.

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

    def _build_popup_content(self) -> str:
        if settings.highlight_active_signature_parameter:
            return self._build_popup_content_style_vscode()
        else:
            # Default to "sublime".
            return self._build_popup_content_style_sublime()

    def _on_hide(self):
        self._visible = False

    def _on_hover_navigate(self, href):
        webbrowser.open_new_tab(href)

    def _build_overload_selector(self) -> str:
        return "**{}** of **{}** overloads (use the ↑ ↓ keys to navigate):\n".format(
            str(self._active_signature + 1), str(len(self._signatures)))

    def _build_popup_content_style_sublime(self) -> str:
        signature = self._signatures[self._active_signature]
        formatted = []

        if len(self._signatures) > 1:
            formatted.append(self._build_overload_selector())

        signature_label = signature.get('label')
        if len(signature_label) > 400:
            label = "```{} ...```".format(signature_label[0:400])  # long code blocks = hangs
        else:
            label = "```{}\n{}\n```\n".format(self._language_id, signature_label)
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
        return "\n".join(formatted)

    def _build_popup_content_style_vscode(self) -> str:
        # Fetch all the relevant data.
        signature_label = ""
        signature_documentation = ""
        parameter_label = ""
        parameter_documentation = ""
        if self._active_signature in range(0, len(self._signatures)):
            signature = self._signatures[self._active_signature]
            signature_label = html.escape(signature["label"], quote=False)
            signature_documentation = signature.get("documentation", "")  # Optional.
            parameters = signature.get("parameters", None)
            if parameters and self._active_parameter in range(0, len(parameters)):
                parameter = parameters[self._active_parameter]
                parameter_label = html.escape(parameter["label"], quote=False)
                parameter_documentation = parameter.get("documentation", "")  # Optional.

        formatted = []

        if len(self._signatures) > 1:
            formatted.append(self._build_overload_selector())

        # Write the active signature and give special treatment to the active parameter (if found).
        # Note that this <div> class and the extra <pre> are copied from mdpopups' HTML output. When mdpopups changes
        # its output style, we must update this literal string accordingly.
        formatted.append('<div class="highlight"><pre>')
        if parameter_label:
            signature_label = self._replace_active_parameter(signature_label, parameter_label)
        formatted.append(signature_label)
        formatted.append("</pre></div>")

        if parameter_documentation:
            formatted.append(parameter_documentation)

        if signature_documentation:
            formatted.append(signature_documentation)

        return "\n".join(formatted)

    def _replace_active_parameter(self, signature: str, parameter: str) -> str:
        if parameter[0].isalnum() and parameter[-1].isalnum():
            pattern = r'\b{}\b'.format(re.escape(parameter))
        else:
            # If the left or right boundary of the parameter string is not an alphanumeric character, the \b check will
            # never match. In this case, it's probably safe to assume the parameter string itself will be a good pattern
            # to search for.
            pattern = re.escape(parameter)
        replacement = '<span style="font-weight: bold; text-decoration: underline">{}</span>'.format(parameter)
        # FIXME: This is somewhat language-specific to look for an opening parenthesis. Most languages use parentheses
        # for their parameter lists though.
        start_of_param_list_pos = signature.find('(')
        # Note that this works even when we don't find an opening parenthesis, because .find returns -1 in that case.
        start_of_param_list = signature[start_of_param_list_pos + 1:]
        return signature[:start_of_param_list_pos + 1] + re.sub(pattern, replacement, start_of_param_list, 1)
