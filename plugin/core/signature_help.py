import html
from .logging import debug
try:
    from typing_extensions import Protocol
    from typing import Tuple, Optional, Dict, List, Union, Any
    assert Tuple and Optional and Dict and List and Union and Any
except ImportError:
    pass
    Protocol = object  # type: ignore


class ScopeRenderer(Protocol):

    def function(self, content: str, escape: bool = True) -> str:
        ...

    def punctuation(self, content: str) -> str:
        ...

    def parameter(self, content: str, emphasize: bool = False) -> str:
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


def parse_signature_label(signature_label: str, parameters: 'List[ParameterInformation]') -> 'Tuple[int, int]':
    current_index = -1

    # assumption - if there are parens, the first paren starts arguments
    # (note: self argument in pyls-returned method calls not included in params!)
    # if no parens, start detecting from first parameter instead.
    # if paren, extract and highlight
    open_paren_index = signature_label.find('(')
    params_start_index = open_paren_index + 1
    current_index = params_start_index

    for parameter in parameters:

        if parameter.label:
            range_start = signature_label.find(parameter.label, current_index)
            range_end = range_start + len(parameter.label)
            parameter.range = (range_start, range_end)
        elif parameter.range:
            parameter.label = signature_label[parameter.range[0]:parameter.range[1]]

        if parameter.range:
            current_index = parameter.range[1]

    close_paren_index = signature_label.find(')', current_index)

    return open_paren_index, close_paren_index


def parse_parameter_information(parameter: 'Dict') -> 'ParameterInformation':
    label_or_range = parameter['label']
    label_range = None
    label = None
    if isinstance(label_or_range, str):
        label = label_or_range
    else:
        label_range = label_or_range
    return ParameterInformation(label, label_range, get_documentation(parameter))


def parse_signature_information(signature: 'Dict') -> 'SignatureInformation':
    signature_label = signature['label']
    param_infos = []  # type: 'List[ParameterInformation]'
    parameters = signature.get('parameters')
    paren_bounds = (-1, -1)
    if parameters:
        param_infos = list(parse_parameter_information(param) for param in parameters)
        paren_bounds = parse_signature_label(signature_label, param_infos)

    return SignatureInformation(signature_label, get_documentation(signature), paren_bounds, param_infos)


class ParameterInformation(object):

    def __init__(self, label: 'Optional[str]', label_range: 'Optional[Tuple[int, int]]',
                 documentation: 'Optional[str]') -> None:
        self.label = label
        self.range = label_range
        self.documentation = documentation


class SignatureInformation(object):

    def __init__(self, label: str, documentation: 'Optional[str]', paren_bounds: 'Tuple[int, int]',
                 parameters: 'List[ParameterInformation]' = []) -> None:
        self.label = label
        self.documentation = documentation
        self.parameters = parameters
        [self.open_paren_index, self.close_paren_index] = paren_bounds


def create_signature_help(response: 'Optional[Dict]') -> 'Optional[SignatureHelp]':
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

        return SignatureHelp(signatures, active_signature, active_parameter)
    else:
        return None


def render_signature_label(renderer: ScopeRenderer, sig_info: SignatureInformation,
                           active_parameter_index: int = -1) -> str:

    if sig_info.parameters:
        label = sig_info.label

        # replace with styled spans in reverse order

        if sig_info.close_paren_index > -1:
            start = sig_info.close_paren_index
            end = start+1
            label = label[:start] + renderer.punctuation(label[start:end]) + html.escape(label[end:], quote=False)

        max_param_index = len(sig_info.parameters) - 1
        for index, param in enumerate(reversed(sig_info.parameters)):
            if param.range:
                start, end = param.range
                is_current = active_parameter_index == max_param_index - index
                rendered_param = renderer.parameter(html.escape(label[start:end], quote=False), is_current)
                label = label[:start] + rendered_param + label[end:]

                # todo: highlight commas between parameters as punctuation.

        if sig_info.open_paren_index > -1:
            start = sig_info.open_paren_index
            end = start+1
            label = html.escape(label[:start], quote=False) + renderer.punctuation(label[start:end]) + label[end:]

        # todo: only render up to first parameter as function scope.
        return renderer.function(label, escape=False)
    else:
        return renderer.function(sig_info.label)


class SignatureHelp(object):

    def __init__(self, signatures: 'List[SignatureInformation]',
                 active_signature=0, active_parameter=0) -> None:
        self._signatures = signatures
        self._active_signature_index = active_signature
        self._active_parameter_index = active_parameter

    def build_popup_content(self, renderer: ScopeRenderer) -> str:
        parameter_documentation = None  # type: Optional[str]

        formatted = []

        if len(self._signatures) > 1:
            formatted.append(self._build_overload_selector())

        signature = self._signatures[self._active_signature_index]  # type: SignatureInformation

        # Write the active signature and give special treatment to the active parameter (if found).
        # Note that this <div> class and the extra <pre> are copied from mdpopups' HTML output. When mdpopups changes
        # its output style, we must update this literal string accordingly.
        formatted.append('<div class="highlight"><pre>')
        formatted.append(render_signature_label(renderer, signature, self._active_parameter_index))
        formatted.append("</pre></div>")

        if signature.documentation:
            formatted.append("<p>{}</p>".format(signature.documentation))

        if signature.parameters and self._active_parameter_index in range(0, len(signature.parameters)):
            parameter = signature.parameters[self._active_parameter_index]
            parameter_label = html.escape(parameter.label, quote=False)
            parameter_documentation = parameter.documentation
            if parameter_documentation:
                formatted.append("<p><b>{}</b>: {}</p>".format(parameter_label, parameter_documentation))

        return "\n".join(formatted)

    def has_multiple_signatures(self) -> bool:
        return len(self._signatures) > 1

    def select_signature(self, direction: int) -> None:
        new_index = self._active_signature_index + direction

        # clamp signature index
        self._active_signature_index = max(0, min(new_index, len(self._signatures) - 1))

    def active_signature(self) -> 'SignatureInformation':
        return self._signatures[self._active_signature_index]

    def _build_overload_selector(self) -> str:
        return "**{}** of **{}** overloads (use the ↑ ↓ keys to navigate):\n".format(
            str(self._active_signature_index + 1), str(len(self._signatures)))
