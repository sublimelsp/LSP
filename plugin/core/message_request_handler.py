from .protocol import Response
from .protocol import ShowMessageRequestParams
from .sessions import Session
from .typing import Any, List, Callable
from .views import show_lsp_popup
from .views import text2html
import sublime


class MessageRequestHandler():
    def __init__(
        self, view: sublime.View, session: Session, request_id: Any, params: ShowMessageRequestParams, source: str
    ) -> None:
        self.session = session
        self.request_id = request_id
        self.request_sent = False
        self.view = view
        self.actions = params.get("actions", [])
        self.titles = list(action.get("title") for action in self.actions)
        self.message = text2html(params['message'])
        self.message_type = params.get('type', 4)
        self.source = source

    def _send_user_choice(self, href: int = -1) -> None:
        if not self.request_sent:
            self.request_sent = True
            self.view.hide_popup()
            index = int(href)
            param = self.actions[index] if index != -1 else None
            response = Response(self.request_id, param)
            self.session.send_response(response)

    def show(self) -> None:
        show_notification(
            self.view,
            self.source,
            self.message_type,
            self.message,
            self.titles,
            self._send_user_choice,
            self._send_user_choice
        )


def show_notification(
    view: sublime.View,
    source: str,
    message_type: int,
    message: str,
    titles: List[str],
    on_navigate: Callable[[int], None],
    on_hide: Callable[[int], None]
) -> None:
    stylesheet = sublime.load_resource("Packages/LSP/notification.css")
    contents = message_content(source, message_type, message, titles)
    show_lsp_popup(
        view,
        contents,
        css=stylesheet,
        wrapper_class='notification',
        on_navigate=on_navigate,
        on_hide=on_hide)


def message_content(source: str, message_type: int, message: str, titles: List[str]) -> str:
    formatted = []  # type: List[str]
    icons = {
        1: '❗',
        2: '⚠️',
        3: 'ℹ️',
        4: '📝'
    }
    icon = icons.get(message_type, '')
    formatted.append("<h2>{}</h2>".format(source))
    formatted.append("<div class='message'>{} {}</div>".format(icon, message))
    if titles:
        buttons = []  # type: List[str]
        for idx, title in enumerate(titles):
            buttons.append("<a href='{}'>{}</a>".format(idx, title))
        formatted.append("<div class='actions'>" + " ".join(buttons) + "</div>")
    return "".join(formatted)
