from .core.protocol import InlayHintLabelPart, MarkupContent, Point, InlayHint, Request
from .core.registry import LspTextCommand, LspWindowCommand
from .core.sessions import Session
from .core.settings import userprefs
from .core.typing import Optional, Union
from .core.views import point_to_offset
from .formatting import apply_text_edits_to_view
import html
import sublime
import uuid


class LspToggleCapabilityCommand(LspWindowCommand):
    def run(self, capability: str) -> None:
        if capability == "inlayHintProvider":
            self.window.run_command('lsp_toggle_inlay_hints')


class LspToggleInlayHintsCommand(LspWindowCommand):
    capability = 'inlayHintProvider'

    def run(self) -> None:
        self.toggle(self.window)
        status = "on" if self.are_enabled(self.window) else "off"
        sublime.status_message("Inlay Hints are {}".format(status))
        for session in self.sessions():
            for sv in session.session_views_async():
                sv.session_buffer.do_inlay_hints_async(sv.view)

    @classmethod
    def are_enabled(cls, w: Optional[sublime.Window]) -> bool:
        if not w:
            return userprefs().show_inlay_hints
        return bool(w.settings().get('lsp_show_inlay_hints', userprefs().show_inlay_hints))

    @classmethod
    def toggle(cls, w: sublime.Window) -> None:
        w.settings().set('lsp_show_inlay_hints', not cls.are_enabled(w))


class LspInlayHintClickCommand(LspTextCommand):
    capability = 'inlayHintProvider'

    def run(self, _edit: sublime.Edit, session_name: str, inlay_hint: InlayHint, phantom_uuid: str,
            event: Optional[dict] = None, label_part: Optional[InlayHintLabelPart] = None) -> None:
        # Insert textEdits for the given inlay hint.
        # If a InlayHintLabelPart was clicked, label_part will be passed as an argument to the LspInlayHintClickCommand
        # and InlayHintLabelPart.command will be executed.
        session = self.session_by_name(session_name, 'inlayHintProvider')
        if session and session.has_capability('inlayHintProvider.resolveProvider'):
            request = Request.resolveInlayHint(inlay_hint, self.view)
            session.send_request_async(
                request,
                lambda response: self.handle(session_name, response, phantom_uuid, label_part))
            return
        self.handle(session_name, inlay_hint, phantom_uuid, label_part)

    def handle(self, session_name: str, inlay_hint: InlayHint, phantom_uuid: str,
               label_part: Optional[InlayHintLabelPart] = None) -> None:
        self.handle_inlay_hint_text_edits(session_name, inlay_hint, phantom_uuid)
        self.handle_label_part_command(session_name, label_part)

    def handle_inlay_hint_text_edits(self, session_name: str, inlay_hint: InlayHint, phantom_uuid: str) -> None:
        session = self.session_by_name(session_name, 'inlayHintProvider')
        if not session:
            return
        text_edits = inlay_hint.get('textEdits')
        if not text_edits:
            return
        for sb in session.session_buffers_async():
            sb.remove_inlay_hint_phantom(phantom_uuid)
        apply_text_edits_to_view(text_edits, self.view)

    def handle_label_part_command(self, session_name: str, label_part: Optional[InlayHintLabelPart] = None) -> None:
        if not label_part:
            return
        command = label_part.get('command')
        if not command:
            return
        args = {
            "session_name": session_name,
            "command_name": command["command"],
            "command_args": command["arguments"]
        }
        self.view.run_command("lsp_execute", args)


def inlay_hint_to_phantom(view: sublime.View, inlay_hint: InlayHint, session: Session) -> sublime.Phantom:
    position = inlay_hint["position"]  # type: ignore
    region = sublime.Region(point_to_offset(Point.from_lsp(position), view))
    phantom_uuid = str(uuid.uuid4())
    content = get_inlay_hint_html(view, inlay_hint, session, phantom_uuid)
    p = sublime.Phantom(region, content, sublime.LAYOUT_INLINE)
    setattr(p, 'lsp_uuid', phantom_uuid)
    return p


def get_inlay_hint_html(view: sublime.View, inlay_hint: InlayHint, session: Session, phantom_uuid: str) -> str:
    tooltip = format_inlay_hint_tooltip(inlay_hint.get("tooltip"))
    label = format_inlay_hint_label(inlay_hint, session, phantom_uuid)
    font = view.settings().get('font_face') or "monospace"
    html = """
    <body id="lsp-inlay-hint">
        <style>
            .inlay-hint {{
                color: color(var(--foreground) alpha(0.6));
                background-color: color(var(--foreground) alpha(0.08));
                border-radius: 4px;
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
            {label}
        </div>
    </body>
    """.format(
        tooltip=tooltip,
        font=font,
        label=label
    )
    return html


def format_inlay_hint_tooltip(tooltip: Optional[Union[str, MarkupContent]]) -> str:
    if isinstance(tooltip, str):
        return tooltip
    if isinstance(tooltip, dict):  # MarkupContent
        return tooltip.get('value') or ""
    return ""


def format_inlay_hint_label(inlay_hint: InlayHint, session: Session, phantom_uuid: str) -> str:
    result = ""
    can_resolve_inlay_hint = session.has_capability('inlayHintProvider.resolveProvider')
    label = inlay_hint['label']  # type: ignore
    is_clickable = bool(inlay_hint.get('textEdits')) or can_resolve_inlay_hint
    if isinstance(label, str):
        if is_clickable:
            inlay_hint_click_command = sublime.command_url('lsp_inlay_hint_click', {
                'session_name': session.config.name,
                'inlay_hint': inlay_hint,
                'phantom_uuid': phantom_uuid
            })
            result += '<a href="{command}">'.format(command=inlay_hint_click_command)
        result += html.escape(label)
        if is_clickable:
            result += "</a>"
        return result

    for label_part in label:
        value = ""
        is_clickable = is_clickable or bool(label_part.get('command'))
        if is_clickable:
            inlay_hint_click_command = sublime.command_url('lsp_inlay_hint_click', {
                'session_name': session.config.name,
                'inlay_hint': inlay_hint,
                'phantom_uuid': phantom_uuid,
                'label_part': label_part
            })
            value += '<a href="{command}">'.format(command=inlay_hint_click_command)
        value += html.escape(label_part.get('value') or "")
        if is_clickable:
            value += "</a>"
        # InlayHintLabelPart.location is not supported
        result += "<div title=\"{tooltip}\">{value}</div>".format(
            tooltip=format_inlay_hint_tooltip(label_part.get("tooltip")),
            value=value
        )
    return result
