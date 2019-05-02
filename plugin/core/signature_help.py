import re
import html
from .logging import debug
from .types import Settings
try:
    from typing import Tuple, Optional, Dict, List, Union, Any
    assert Tuple and Optional and Dict and List and Union and Any
except ImportError:
    pass


def get_documentation(d: 'Dict[str, Any]') -> 'Optional[str]':
    docs = d.get('documentation', None)
    if docs is None:
        return None
    elif isinstance(docs, str):
        # In older version of the protocol, documentation was just a string.
        return docs
    elif isinstance(docs, dict):
        # This can be either "plaintext" or "markdown" format. For now, we can dump it into the popup box. It would
        # be nice to handle the markdown in a special way.
        return docs.get('value', None)
    else:
        debug('unknown documentation type:', str(d))
        return None


def create_signature_help(response: 'Optional[Dict]', language_id, settings: Settings) -> 'Optional[SignatureHelp]':
    signatures = []  # type: List[Dict]
    active_signature = -1
    active_parameter = -1
    if response is not None:
        signatures = response.get("signatures", [])
        active_signature = response.get("activeSignature", -1)
        active_parameter = response.get("activeParameter", -1)

        if len(signatures) > 0:
            if not 0 <= active_signature < len(signatures):
                debug("activeSignature {} not a valid index for signatures length {}".format(
                    active_signature, len(signatures)))
                active_signature = 0
        else:
            if active_signature != -1:
                debug("activeSignature should be -1 or null when no signatures are returned")
                active_signature = -1

    if signatures:
        return SignatureHelp(signatures, language_id, active_signature, active_parameter,
                             settings.highlight_active_signature_parameter)
    else:
        return None


class SignatureHelp(object):

    def __init__(self, signatures, language_id, active_signature=0, active_parameter=0, highlight_parameter=False):
        self._signatures = signatures
        self._language_id = language_id
        self._active_signature = active_signature
        self._active_parameter = active_parameter
        self._highlight_parameter = highlight_parameter

    def build_popup_content(self) -> str:
        if self._highlight_parameter:
            return self._build_popup_content_style_vscode()
        else:
            return self._build_popup_content_style_sublime()

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
                param_docs = get_documentation(parameter)
                if param_docs:
                    formatted.append("**{}**\n".format(parameter.get('label')))
                    formatted.append("* *{}*\n".format(param_docs))
        sigDocs = get_documentation(signature)
        if sigDocs:
            formatted.append(sigDocs)
        return "\n".join(formatted)

    def _build_popup_content_style_vscode(self) -> str:
        # Fetch all the relevant data.
        signature_label = ""
        signature_documentation = ""  # type: Optional[str]
        parameter_label = ""
        parameter_documentation = ""  # type: Optional[str]
        if self._active_signature in range(0, len(self._signatures)):
            signature = self._signatures[self._active_signature]
            signature_label = html.escape(signature["label"], quote=False)
            signature_documentation = get_documentation(signature)
            parameters = signature.get("parameters", None)
            if parameters and self._active_parameter in range(0, len(parameters)):
                parameter = parameters[self._active_parameter]
                parameter_label = html.escape(parameter["label"], quote=False)
                parameter_documentation = get_documentation(parameter)

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
