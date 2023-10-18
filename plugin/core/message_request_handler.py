from .protocol import MessageType
from .protocol import Response
from .protocol import ShowMessageRequestParams
from .sessions import Session
from .typing import Any, Dict, List
from .views import show_lsp_popup
from .views import text2html
import sublime


ICONS = {
    MessageType.Error: '❗',
    MessageType.Warning: '⚠️',
    MessageType.Info: 'ℹ️',
    MessageType.Log: '📝'
}  # type: Dict[MessageType, str]


class MessageRequestHandler():
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
        formatted = []  # type: List[str]
        formatted.append("<h2>{}</h2>".format(self.source))
        icon = ICONS.get(self.message_type, '')
        formatted.append("<div class='message'>{} {}</div>".format(icon, text2html(self.message)))
        if self.action_titles:
            buttons = []  # type: List[str]
            for idx, title in enumerate(self.action_titles):
                buttons.append("<a href='{}'>{}</a>".format(idx, text2html(title)))
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
