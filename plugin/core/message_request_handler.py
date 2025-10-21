from __future__ import annotations
from ...protocol import MessageType
from ...protocol import ShowMessageRequestParams
from .protocol import Response
from .sessions import Session
from .views import show_lsp_popup
from .views import text2html
from typing import Any
import sublime


ICONS: dict[MessageType, str] = {
    MessageType.Error: '❗',
    MessageType.Warning: '⚠️',
    MessageType.Info: 'ℹ️',
    MessageType.Log: '📝'
}


class MessageRequestHandler:
    def __init__(
        self, view: sublime.View, session: Session, request_id: Any, params: ShowMessageRequestParams, source: str
    ) -> None:
        self.session = session
        self.request_id = request_id
        self.request_sent = False
        self.view = view
        self.actions = params.get("actions", [])
        self.action_titles = list(action.get("title") for action in self.actions)
        self.message = params['message']
        self.message_type = params.get('type', 4)
        self.source = source

    def show(self) -> None:
        formatted: list[str] = []
        formatted.append(f"<h2>{self.source}</h2>")
        icon = ICONS.get(self.message_type, '')
        formatted.append(f"<div class='message'>{icon} {text2html(self.message)}</div>")
        if self.action_titles:
            buttons: list[str] = []
            for idx, title in enumerate(self.action_titles):
                buttons.append(f"<a href='{idx}'>{text2html(title)}</a>")
            formatted.append("<div class='actions'>" + " ".join(buttons) + "</div>")
        show_lsp_popup(
            self.view,
            "".join(formatted),
            css=sublime.load_resource("Packages/LSP/notification.css"),
            wrapper_class='notification',
            on_navigate=self._send_user_choice,
            on_hide=self._send_user_choice)

    def _send_user_choice(self, href: int = -1) -> None:
        if self.request_sent:
            return
        self.request_sent = True
        self.view.hide_popup()
        index = int(href)
        param = self.actions[index] if index != -1 else None
        response = Response(self.request_id, param)
        self.session.send_response(response)
