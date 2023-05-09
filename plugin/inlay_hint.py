from .core.css import css
from .core.protocol import InlayHint
from .core.protocol import InlayHintLabelPart
from .core.protocol import MarkupContent
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.settings import userprefs
from .core.typing import cast, Optional, Union
from .core.views import position_to_offset
from .formatting import apply_text_edits_to_view
import html
import sublime
import uuid


class LspToggleInlayHintsCommand(LspWindowCommand):
    capability = 'inlayHintProvider'

    def run(self, enable: Optional[bool] = None) -> None:
        if not isinstance(enable, bool):
            enable = not self.are_enabled(self.window)
        self.window.settings().set('lsp_show_inlay_hints', enable)
        status = 'on' if enable else 'off'
        sublime.status_message('Inlay Hints are {}'.format(status))
        for session in self.sessions():
            for sv in session.session_views_async():
                sv.session_buffer.do_inlay_hints_async(sv.view)

    def is_checked(self) -> bool:
        return self.are_enabled(self.window)

    @classmethod
    def are_enabled(cls, window: Optional[sublime.Window]) -> bool:
        if not window:
            return userprefs().show_inlay_hints
        return bool(window.settings().get('lsp_show_inlay_hints', userprefs().show_inlay_hints))


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
            "command_args": command.get("arguments")
        }
        self.view.run_command("lsp_execute", args)


def inlay_hint_to_phantom(view: sublime.View, inlay_hint: InlayHint, session: Session) -> sublime.Phantom:
    position = inlay_hint["position"]
    region = sublime.Region(position_to_offset(position, view))
    phantom_uuid = str(uuid.uuid4())
    content = get_inlay_hint_html(view, inlay_hint, session, phantom_uuid)
    p = sublime.Phantom(region, content, sublime.LAYOUT_INLINE)
    setattr(p, 'lsp_uuid', phantom_uuid)
    return p


def get_inlay_hint_html(view: sublime.View, inlay_hint: InlayHint, session: Session, phantom_uuid: str) -> str:
    label = format_inlay_hint_label(inlay_hint, session, phantom_uuid)
    font = view.settings().get('font_face') or "monospace"
    html = """
    <body id="lsp-inlay-hint">
        <style>
            .inlay-hint {{
                font-family: {font};
            }}
            {css}
        </style>
        <div class="inlay-hint">
            {label}
        </div>
    </body>
    """.format(
        font=font,
        css=css().inlay_hints,
        label=label
    )
    return html


def format_inlay_hint_tooltip(tooltip: Optional[Union[str, MarkupContent]]) -> str:
    if isinstance(tooltip, str):
        return html.escape(tooltip)
    if isinstance(tooltip, dict):  # MarkupContent
        return html.escape(tooltip.get('value') or "")
    return ""


def format_inlay_hint_label(inlay_hint: InlayHint, session: Session, phantom_uuid: str) -> str:
    tooltip = format_inlay_hint_tooltip(inlay_hint.get("tooltip"))
    result = ""
    can_resolve_inlay_hint = session.has_capability('inlayHintProvider.resolveProvider')
    label = inlay_hint['label']
    has_text_edits = bool(inlay_hint.get('textEdits'))
    is_clickable = has_text_edits or can_resolve_inlay_hint
    if isinstance(label, str):
        if is_clickable:
            inlay_hint_click_command = sublime.command_url('lsp_on_double_click', {
                'command': 'lsp_inlay_hint_click',
                'args': {
                    'session_name': session.config.name,
                    'inlay_hint': cast(dict, inlay_hint),
                    'phantom_uuid': phantom_uuid
                }
            })
            result += '<a href="{command}">'.format(command=inlay_hint_click_command)
        instruction_text = '\nDouble-click to insert' if has_text_edits else ""
        result += '<span title="{tooltip}">{value}</span>'.format(
            tooltip=(tooltip + instruction_text).strip(),
            value=html.escape(label)
        )
        if is_clickable:
            result += "</a>"
        return result

    for label_part in label:
        value = ""
        tooltip = format_inlay_hint_tooltip(label_part.get("tooltip"))
        has_command = bool(label_part.get('command'))
        if has_command:
            inlay_hint_click_command = sublime.command_url('lsp_on_double_click', {
                'command': 'lsp_inlay_hint_click',
                'args': {
                    'session_name': session.config.name,
                    'inlay_hint': cast(dict, inlay_hint),
                    'phantom_uuid': phantom_uuid,
                    'label_part': cast(dict, label_part)
                }
            })
            value += '<a href="{command}">'.format(command=inlay_hint_click_command)
        value += html.escape(label_part['value'])
        if has_command:
            value += "</a>"
        # InlayHintLabelPart.location is not supported
        instruction_text = '\nDouble-click to execute' if has_command else ""
        result += "<span title=\"{tooltip}\">{value}</span>".format(
            tooltip=(tooltip + instruction_text).strip(),
            value=value
        )
    return result
