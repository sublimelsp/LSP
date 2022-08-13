from .core.sessions import Session
from .core.protocol import InlayHintLabelPart, MarkupContent, Point, InlayHint, Request
from .core.registry import LspTextCommand
from .core.typing import List, Optional, Union
from .core.views import FORMAT_MARKUP_CONTENT, point_to_offset, minihtml
from .formatting import apply_text_edits_to_view
import html
import sublime
import uuid
from .core.types import TemporarySettings


class LspToggleInlayHintsCommand(LspTextCommand):
    capability = 'inlayHintProvider'

    def run(self, _edit: sublime.Edit, _event: Optional[dict] = None) -> None:
        sessions = self.sessions('inlayHintProvider')
        TemporarySettings.SHOW_INLAY_HINTS = not TemporarySettings.SHOW_INLAY_HINTS
        for session in sessions:
            for sv in session.session_views_async():
                sv.session_buffer.do_inlay_hints_async(sv.view)


class LspInlayHintApplyTextEditsCommand(LspTextCommand):
    capability = 'inlayHintProvider'

    def run(self, _edit: sublime.Edit, session_name: str, inlay_hint: InlayHint, phantom_uuid: str,
            event: Optional[dict] = None) -> None:
        session = self.session_by_name(session_name, 'inlayHintProvider')
        if session and session.has_capability('inlayHintProvider.resolveProvider'):
            request = Request.resolveInlayHint(inlay_hint, self.view)
            session.send_request_async(request, lambda response: self.handle(session_name, response, phantom_uuid))
            return
        self.handle(session_name, inlay_hint, phantom_uuid)

    def handle(self, session_name: str, inlay_hint: InlayHint, phantom_uuid: str) -> None:
        self.handle_inlay_hint_text_edits(session_name, inlay_hint, phantom_uuid)

    def handle_inlay_hint_text_edits(self, session_name: str, inlay_hint: InlayHint, phantom_uuid: str) -> None:
        session = self.session_by_name(session_name, 'inlayHintProvider')
        if not session:
            return
        text_edits = inlay_hint.get('textEdits')
        if not text_edits:
            return
        for sv in session.session_views_async():
            sv.remove_inlay_hint_phantom(phantom_uuid)
        apply_text_edits_to_view(text_edits, self.view)


def get_inlay_hint_html(view: sublime.View, inlay_hint: InlayHint, session: Session, phantom_uuid: str) -> str:
    tooltip = format_inlay_hint_tooltip(view, inlay_hint.get("tooltip"))
    label = format_inlay_hint_label(view, inlay_hint["label"])
    margin_left = "0.6rem" if inlay_hint.get("paddingLeft", False) else "0"
    margin_right = "0.6rem" if inlay_hint.get("paddingRight", False) else "0"
    font = view.settings().get('font_face') or "monospace"
    html = """
    <body id="lsp-inlay-hint">
        <style>
            .inlay-hint {{
                color: color(var(--foreground) alpha(0.6));
                background-color: color(var(--foreground) alpha(0.08));
                border-radius: 4px;
                margin-left: {margin_left};
                margin-right: {margin_right};
                padding: 0.05em 4px;
                font-size: 0.9em;
                font-family: {font};
            }}

            .inlay-hint a {{
                color: color(var(--foreground) alpha(0.6));
                text-decoration: none;
            }}
        </style>
        <div class="inlay-hint" title="{tooltip}">
    """.format(
        margin_left=margin_left,
        margin_right=margin_right,
        tooltip=tooltip,
        font=font
    )
    can_resolve_inlay_hint = session.has_capability('inlayHintProvider.resolveProvider')
    apply_text_edits_command = sublime.command_url('lsp_inlay_hint_apply_text_edits', {
        'session_name': session.config.name,
        'inlay_hint': inlay_hint,
        'phantom_uuid': phantom_uuid
    })
    can_apply_text_edits = inlay_hint.get('textEdits') or (not inlay_hint.get('textEdits') and can_resolve_inlay_hint)
    if can_apply_text_edits:
        html += '<a href="{apply_text_edits_command}">'.format(apply_text_edits_command=apply_text_edits_command)
    html += label
    if can_apply_text_edits:
        html += '</a>'
    html += """
        </div>
    </body>
    """
    return html


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


def inlay_hint_to_phantom(view: sublime.View, inlay_hint: InlayHint, session: Session) -> sublime.Phantom:
    region = sublime.Region(point_to_offset(Point.from_lsp(inlay_hint["position"]), view))
    phantom_uuid = str(uuid.uuid4())
    content = get_inlay_hint_html(view, inlay_hint, session, phantom_uuid)
    p = sublime.Phantom(region, content, sublime.LAYOUT_INLINE)
    setattr(p, 'lsp_uuid', phantom_uuid)
    return p
