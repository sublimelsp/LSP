from .protocol import Response
from .sessions import Session
from .typing import Any, List, Callable
import mdpopups
import sublime


class MessageRequestHandler():
    def __init__(self, view: sublime.View, session: Session, request_id: Any, params: dict, source: str) -> None:
        self.session = session
        self.request_id = request_id
        self.request_sent = False
        self.view = view
        actions = params.get("actions", [])
        self.titles = list(action.get("title") for action in actions)
        self.message = params.get('message', '')
        self.message_type = params.get('type', 4)
        self.source = source

    def _send_user_choice(self, href: int = -1) -> None:
        if not self.request_sent:
            self.request_sent = True
            self.view.hide_popup()
            # when noop; nothing was selected e.g. the user pressed escape
            param = None
            index = int(href)
            if index != -1:
                param = {"title": self.titles[index]}
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


def message_content(source: str, message_type: int, message: str, titles: List[str]) -> str:
    formatted = []
    icons = {
        1: '❗',
        2: '⚠️',
        3: 'ℹ️',
        4: '📝'
    }
    icon = icons.get(message_type, '')
    formatted.append("<h2>{}</h2>".format(source))
    formatted.append("<p class='message'>{} {}</p>".format(icon, message))

    buttons = []
    for idx, title in enumerate(titles):
        buttons.append("<a href='{}'>{}</a>".format(idx, title))

    formatted.append("<p class='actions'>" + " ".join(buttons) + "</p>")

    return "".join(formatted)


def show_notification(view: sublime.View, source: str, message_type: int, message: str, titles: List[str],
                      on_navigate: Callable, on_hide: Callable) -> None:
    stylesheet = sublime.load_resource("Packages/LSP/notification.css")
    contents = message_content(source, message_type, message, titles)
    mdpopups.show_popup(
        view,
        contents,
        css=stylesheet,
        md=False,
        location=-1,
        wrapper_class='notification',
        max_width=800,
        max_height=800,
        on_navigate=on_navigate,
        on_hide=on_hide
    )
