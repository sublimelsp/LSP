import html
from .logging import debug
try:
    from typing_extensions import Protocol
    from typing import Tuple, Optional, Dict, List, Union, Any
    assert Tuple and Optional and Dict and List and Union and Any
except ImportError:
    pass


class ScopeRenderer(Protocol):

    def render_function(self, content: str) -> str:
        ...

    def render_punctuation(self, content: str) -> str:
        ...

    def render_parameter(self, content: str, emphasize: bool = False) -> str:
        ...


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


def parse_signature_information(signature: 'Dict') -> 'SignatureInformation':
    param_infos = []  # type: 'List[ParameterInformation]'
    parameters = signature.get('parameters')
    if parameters:
        # todo: if we advertise labelOffsetSupport, we can get [int,int] ranges in "label"
        param_infos = list(ParameterInformation(param['label'], get_documentation(param)) for param in parameters)
    return SignatureInformation(signature['label'], get_documentation(signature), param_infos)


class ParameterInformation(object):

    def __init__(self, label: str, documentation: 'Optional[str]') -> None:
        self.label = label
        self.documentation = documentation


class SignatureInformation(object):

    def __init__(self, label: str, documentation: 'Optional[str]',
                 parameters: 'List[ParameterInformation]' = []) -> None:
        self.label = label
        self.documentation = documentation
        self.parameters = parameters


def create_signature_help(response: 'Optional[Dict]', renderer: ScopeRenderer) -> 'Optional[SignatureHelp]':
    if response is None:
        return None

    signatures = list(parse_signature_information(signature) for signature in response.get("signatures", []))
    active_signature = response.get("activeSignature", -1)
    active_parameter = response.get("activeParameter", -1)

    if signatures:
        if not 0 <= active_signature < len(signatures):
            debug("activeSignature {} not a valid index for signatures length {}".format(
                active_signature, len(signatures)))
            active_signature = 0

        return SignatureHelp(signatures, renderer, active_signature, active_parameter)
    else:
        return None


class SignatureHelp(object):

    def __init__(self, signatures: 'List[SignatureInformation]', renderer: ScopeRenderer,
                 active_signature=0, active_parameter=0) -> None:
        self._signatures = signatures
        self._active_signature_index = active_signature
        self._active_parameter = active_parameter
        self._renderer = renderer

    def build_popup_content(self) -> str:
        parameter_documentation = None  # type: Optional[str]

        signature = self._signatures[self._active_signature_index]  # type: SignatureInformation
        signature_label = self._highlight_signature(signature.label)
        debug('LABEL:', signature_label)

        # signature_label = html.escape(signature.label, quote=False)
        if signature.parameters and self._active_parameter in range(0, len(signature.parameters)):
            parameter = signature.parameters[self._active_parameter]
            parameter_label = html.escape(parameter.label, quote=False)
            parameter_documentation = parameter.documentation

        formatted = []

        if len(self._signatures) > 1:
            formatted.append(self._build_overload_selector())

        # Write the active signature and give special treatment to the active parameter (if found).
        # Note that this <div> class and the extra <pre> are copied from mdpopups' HTML output. When mdpopups changes
        # its output style, we must update this literal string accordingly.
        formatted.append('<div class="highlight"><pre>')
        formatted.append(signature_label)
        formatted.append("</pre></div>")

        if signature.documentation:
            formatted.append("<p>{}</p>".format(signature.documentation))

        if parameter_documentation:
            formatted.append("<p><b>{}</b>: {}</p>".format(parameter_label, parameter_documentation))

        return "\n".join(formatted)

    def has_overloads(self) -> bool:
        return len(self._signatures) > 1

    def select_signature(self, direction: int) -> None:
        new_index = self._active_signature_index + direction

        # clamp signature index
        self._active_signature_index = max(0, min(new_index, len(self._signatures) - 1))

    def _active_signature(self) -> 'SignatureInformation':
        return self._signatures[self._active_signature_index]

    def _build_overload_selector(self) -> str:
        return "**{}** of **{}** overloads (use the ↑ ↓ keys to navigate):\n".format(
            str(self._active_signature_index + 1), str(len(self._signatures)))

    def _read_parameter(self, signature_label: str, param_info: ParameterInformation,
                        start_at: int) -> 'Tuple[str, str, int]':
        param_index = signature_label.find(param_info.label, start_at)
        param_end = param_index + len(param_info.label)

        comma_index = signature_label.find(',', param_end)
        if comma_index > -1:
            return signature_label[start_at:comma_index], ', ', comma_index + 2
        else:
            close_paren_index = signature_label.find(')', param_end)
            if close_paren_index > -1:
                return signature_label[start_at:close_paren_index], ')', close_paren_index + 1
            else:
                # we have no delimiters, just return param label.
                return param_info.label, ' ', start_at

    def _highlight_signature(self, signature_label: str) -> str:

        rendered_signature = []  # type: List[str]
        sig_info = self._active_signature()
        # assumption - if there are parens, the first paren starts arguments
        # (note: self argument in pyls-returned method calls not included in params!)
        # if no parens, start detecting from first parameter instead.
        # if paren, extract and highlight
        first_paren_index = signature_label.find('(')
        if first_paren_index > -1:
            rendered_signature.append(
                self._renderer.render_function(signature_label[:first_paren_index])
            )
            rendered_signature.append(
                self._renderer.render_punctuation('(')
            )
        current_pos = first_paren_index + 1
        if sig_info.parameters:
            for index, param_info in enumerate(sig_info.parameters):
                parameter, delimiter, current_pos = self._read_parameter(signature_label, param_info, current_pos)

                # append parameter and punctuation
                rendered_signature.append(
                    self._renderer.render_parameter(parameter, index == self._active_parameter)
                )
                rendered_signature.append(
                    self._renderer.render_punctuation(delimiter)
                )

        # append remainder
        rendered_signature.append(
            self._renderer.render_function(signature_label[current_pos:])
        )

        return "".join(rendered_signature)
