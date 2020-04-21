import mdpopups
from .rpc import Client
from .typing import Any, List, Callable
from .protocol import Response
from sublime import View


class MessageRequestHandler(object):
    def __init__(self, view: View, client: Client, request_id: Any, params: dict) -> None:
        self.client = client
        self.request_id = request_id
        self.request_sent = False
        self.view = view
        actions = params.get("actions", [])
        self.titles = list(action.get("title") for action in actions)
        self.message = params.get('message', '')
        self.message_type = params.get('type', 4)

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
            self.client.send_response(response)

    def show(self) -> None:
        show_notification(
            self.view,
            self.message_type,
            self.message,
            self.titles,
            self._send_user_choice,
            self._send_user_choice
        )


def message_content(message_type: int, message: str, titles: List[str]) -> str:
    formatted = []
    icons = {
      1: '❗',
      2: '⚠️',
      3: 'ℹ️',
      4: '📝'
    }
    icon = icons.get(message_type, '')
    formatted.append("<p class='message'>{} {}</p>".format(icon, message))

    buttons = []
    for idx, title in enumerate(titles):
        buttons.append("<a href='{}'>{}</a>".format(idx, title))

    formatted.append("<p class='actions'>" + " ".join(buttons) + "</p>")

    return "".join(formatted)


def show_notification(view: View, message_type: int, message: str, titles: List[str],
                      on_navigate: Callable, on_hide: Callable) -> None:
    myStyle = """
    .notification {
        margin: 0.5rem;
        padding: 1rem;
    }
    .notification .message {
        margin-bottom: 3rem;
    }

    .notification .actions a {
        text-decoration: none;
        padding: 0.5rem;
        border: 2px solid color(var(--foreground) alpha(0.25));
        color: var(--foreground);
    }
    """

    contents = message_content(message_type, message, titles)
    mdpopups.show_popup(
        view,
        contents,
        css=myStyle,
        md=False,
        location=-1,
        wrapper_class='notification',
        max_width=800,
        max_height=800,
        on_navigate=on_navigate,
        on_hide=on_hide
    )
