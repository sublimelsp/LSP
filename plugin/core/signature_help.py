from .logging import debug
from .protocol import SignatureHelp
from .protocol import SignatureHelpContext
from .protocol import SignatureInformation
from .typing import Optional, List
from .views import FORMAT_MARKUP_CONTENT
from .views import FORMAT_STRING
from .views import minihtml
import html
import sublime


class SigHelp:
    """
    A quasi state-machine object that maintains which signature (a.k.a. overload) is active. The active signature is
    determined by what the end-user is doing.
    """

    def __init__(self, state: SignatureHelp) -> None:
        self._state = state
        self._signatures = self._state["signatures"]
        self._active_signature_index = self._state.get("activeSignature") or 0
        self._active_parameter_index = self._state.get("activeParameter") or 0

    @classmethod
    def from_lsp(cls, sighelp: Optional[SignatureHelp]) -> "Optional[SigHelp]":
        """Create a SigHelp state object from a server's response to textDocument/signatureHelp."""
        if sighelp is None or not sighelp.get("signatures"):
            return None
        return cls(sighelp)

    def render(self, view: sublime.View) -> str:
        """Render the signature help content as minihtml."""
        try:
            signature = self._signatures[self._active_signature_index]
        except IndexError:
            return ""
        formatted = []  # type: List[str]
        intro = self._render_intro()
        if intro:
            formatted.append(intro)
        formatted.extend(self._render_label(view, signature))
        formatted.extend(self._render_docs(view, signature))
        return "".join(formatted)

    def context(self, trigger_kind: int, trigger_character: str, is_retrigger: bool) -> SignatureHelpContext:
        """
        Extract the state out of this state machine to send back to the language server.

        XXX: Currently unused. Revisit this some time in the future.
        """
        self._state["activeSignature"] = self._active_signature_index
        return {
            "triggerKind": trigger_kind,
            "triggerCharacter": trigger_character,
            "isRetrigger": is_retrigger,
            "activeSignatureHelp": self._state
        }

    def has_multiple_signatures(self) -> bool:
        """Does the current signature help state contain more than one overload?"""
        return len(self._signatures) > 1

    def select_signature(self, direction: int) -> None:
        """Increment or decrement the active overload; purely chosen by the end-user."""
        new_index = self._active_signature_index + direction
        self._active_signature_index = max(0, min(new_index, len(self._signatures) - 1))

    def active_signature(self) -> SignatureInformation:
        return self._signatures[self._active_signature_index]

    def _render_intro(self) -> Optional[str]:
        if len(self._signatures) > 1:
            fmt = '<p><div style="font-size: 0.9rem"><b>{}</b> of <b>{}</b> overloads ' + \
                  "(use ↑ ↓ to navigate, press Esc to hide):</div></p>"
            return fmt.format(
                self._active_signature_index + 1,
                len(self._signatures),
            )
        return None

    def _render_label(self, view: sublime.View, signature: SignatureInformation) -> List[str]:
        formatted = []  # type: List[str]
        # Note that this <div> class and the extra <pre> are copied from mdpopups' HTML output. When mdpopups changes
        # its output style, we must update this literal string accordingly.
        formatted.append('<div class="highlight"><pre>')
        label = signature["label"]
        parameters = signature.get("parameters")
        if parameters:
            prev, start, end = 0, 0, 0
            for i, param in enumerate(parameters):
                rawlabel = param["label"]
                if isinstance(rawlabel, list):
                    # TODO: UTF-16 offsets
                    start, end = rawlabel[0], rawlabel[1]
                else:
                    # Note that this route is from an earlier spec. It is a bad way of doing things because this
                    # route relies on the client being smart enough to figure where the parameter is inside of
                    # the signature label. The above case where the label is a tuple of (start, end) positions is much
                    # more robust.
                    start = label[prev:].find(rawlabel)
                    if start == -1:
                        debug("no match found for {}".format(rawlabel))
                        continue
                    start += prev
                    end = start + len(rawlabel)
                if prev < start:
                    formatted.append(_function(view, label[prev:start]))
                formatted.append(_parameter(view, label[start:end], i == self._active_parameter_index))
                prev = end
            if end < len(label):
                formatted.append(_function(view, label[end:]))
        else:
            formatted.append(_function(view, label))
        formatted.append("</pre></div>")
        return formatted

    def _render_docs(self, view: sublime.View, signature: SignatureInformation) -> List[str]:
        formatted = []  # type: List[str]
        docs = self._parameter_documentation(view, signature)
        if docs:
            formatted.append(docs)
        docs = _signature_documentation(view, signature)
        if docs:
            if formatted:
                formatted.append("<hr/>")
            formatted.append('<div style="font-size: 0.9rem">')
            formatted.append(docs)
            formatted.append('</div>')
        return formatted

    def _parameter_documentation(self, view: sublime.View, signature: SignatureInformation) -> Optional[str]:
        parameters = signature.get("parameters")
        if not parameters:
            return None
        try:
            parameter = parameters[self._active_parameter_index]
        except IndexError:
            return None
        documentation = parameter.get("documentation")
        if documentation:
            return minihtml(view, documentation, allowed_formats=FORMAT_STRING | FORMAT_MARKUP_CONTENT)
        return None


def _function(view: sublime.View, content: str) -> str:
    return _wrap_with_scope_style(view, content, "entity.name.function", False)


def _parameter(view: sublime.View, content: str, emphasize: bool) -> str:
    return _wrap_with_scope_style(view, content, "variable.parameter", emphasize)


def _wrap_with_scope_style(view: sublime.View, content: str, scope: str, emphasize: bool) -> str:
    return '<span style="color: {}{}">{}</span>'.format(
        view.style_for_scope(scope)["foreground"],
        '; font-weight: bold; text-decoration: underline' if emphasize else '',
        html.escape(content, quote=False)
    )


def _signature_documentation(view: sublime.View, signature: SignatureInformation) -> Optional[str]:
    documentation = signature.get("documentation")
    if documentation:
        return minihtml(view, documentation, allowed_formats=FORMAT_STRING | FORMAT_MARKUP_CONTENT)
    return None
