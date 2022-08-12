from .core.protocol import InlayHintLabelPart, MarkupContent, Point, InlayHint, Request
from .core.registry import LspTextCommand
from .core.typing import List, Optional, Union
from .core.views import FORMAT_MARKUP_CONTENT, point_to_offset, minihtml
from .formatting import apply_text_edits_to_view
import html
import sublime


class LspToggleInlayHintsCommand(LspTextCommand):
    capability = 'inlayHintProvider'

    def run(self, _edit: sublime.Edit, _event: Optional[dict] = None) -> None:
        settings = sublime.load_settings("LSP.sublime-settings")
        show_inlay_hints = settings.get("show_inlay_hints", False)
        settings.set("show_inlay_hints", not show_inlay_hints)
        sublime.save_settings("LSP.sublime-settings")


class LspInlayHintClickCommand(LspTextCommand):
    capability = 'inlayHintProvider'

    def run(self, _edit: sublime.Edit, session_name: str, inlay_hint: InlayHint, event: Optional[dict] = None) -> None:
        session = self.session_by_name(session_name, 'inlayHintProvider.resolveProvider')
        if session:
            request = Request.resolveInlayHint(inlay_hint, self.view)
            session.send_request_async(request, lambda response: self.handle(session_name, response))
            return
        self.handle(session_name, inlay_hint)

    def handle(self, session_name: str, inlay_hint: InlayHint) -> None:
        self.handle_inlay_hint_text_edits(inlay_hint)
        self.handle_inlay_hint_command(session_name, inlay_hint)

    def handle_inlay_hint_text_edits(self, inlay_hint: InlayHint) -> None:
        text_edits = inlay_hint.get('textEdits')
        if text_edits:
            apply_text_edits_to_view(text_edits, self.view)

    def handle_inlay_hint_command(self, session_name: str, inlay_hint: InlayHint) -> None:
        label_parts = inlay_hint.get('label')
        if not isinstance(label_parts, list):
            return
        for label_part in label_parts:
            command = label_part.get('command')
            if not command:
                continue
            args = {
                "session_name": session_name,
                "command_name": command["command"],
                "command_args": command["arguments"]
            }
            self.view.run_command("lsp_execute", args)


INLAY_HINT_HTML = """
<body id="lsp-inlay-hint">
    <style>
        .inlay-hint {{
            background-color: color(var(--foreground) alpha(0.08));
            border-radius: 4px;
            margin-left: {margin_left};
            margin-right: {margin_right};
            padding: 0.05em 4px;
            font-size: 0.9em;
            font-family: monospace;
        }}

        .inlay-hint a {{
            color: color(var(--foreground) alpha(0.6));
            text-decoration: none;
        }}
    </style>
    <div class="inlay-hint" title="{tooltip}">
            <a href="{command}">{label}</a>
    </div>
</body>
"""


def format_inlay_hint_tooltip(view: sublime.View, tooltip: Optional[Union[str, MarkupContent]]) -> str:
    if isinstance(tooltip, str):
        return html.escape(tooltip)
    elif isinstance(tooltip, dict):  # MarkupContent
        return minihtml(view, tooltip, allowed_formats=FORMAT_MARKUP_CONTENT)
    else:
        return ""


def format_inlay_hint_label(view: sublime.View, label: Union[str, List[InlayHintLabelPart]]) -> str:
    if isinstance(label, str):
        return html.escape(label)
    else:
        return "".join("<div title=\"{tooltip}\">{value}</div>".format(
            tooltip=format_inlay_hint_tooltip(view, label_part.get("tooltip")),
            value=label_part.get("value")
        ) for label_part in label)


def inlay_hint_to_phantom(view: sublime.View, inlay_hint: InlayHint, session_name: str) -> sublime.Phantom:
    region = sublime.Region(point_to_offset(Point.from_lsp(inlay_hint["position"]), view))
    tooltip = format_inlay_hint_tooltip(view, inlay_hint.get("tooltip"))
    label = format_inlay_hint_label(view, inlay_hint["label"])
    margin_left = "0.6rem" if inlay_hint.get("paddingLeft", False) else "0"
    margin_right = "0.6rem" if inlay_hint.get("paddingRight", False) else "0"
    command = sublime.command_url('lsp_inlay_hint_click', {'session_name': session_name, 'inlay_hint': inlay_hint})
    content = INLAY_HINT_HTML.format(
        margin_left=margin_left,
        margin_right=margin_right,
        tooltip=tooltip,
        label=label,
        command=command)
    return sublime.Phantom(region, content, sublime.LAYOUT_INLINE)
