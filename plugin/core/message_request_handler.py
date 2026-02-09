from __future__ import annotations
from ...protocol import MessageActionItem
from ...protocol import MessageType
from ...protocol import ShowMessageRequestParams
from .promise import PackagedTask, Promise, ResolveFunc
from .views import show_lsp_popup
from .views import text2html
import sublime


ICONS: dict[MessageType, str] = {
    MessageType.Error: '❗',
    MessageType.Warning: '⚠️',
    MessageType.Info: 'ℹ️',
    MessageType.Log: '📝',
    MessageType.Debug: '🐛'
}


class MessageRequestHandler:
    def __init__(self, view: sublime.View, params: ShowMessageRequestParams, source: str) -> None:
        self.view = view
        self.actions = params.get("actions", [])
        self.action_titles = list(action.get("title") for action in self.actions)
        self.message = params['message']
        self.message_type = params.get('type', 4)
        self.source = source

    def show(self) -> Promise[MessageActionItem | None]:
        task: PackagedTask[MessageActionItem | None] = Promise.packaged_task()
        promise, resolve = task
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
            location=self.view.layout_to_text(self.view.viewport_position()),
            css=sublime.load_resource("Packages/LSP/notification.css"),
            wrapper_class='notification',
            on_navigate=lambda href: self._send_user_choice(resolve, href),
            on_hide=lambda href: self._send_user_choice(resolve, href))
        return promise

    def _send_user_choice(self, resolve: ResolveFunc[MessageActionItem | None], href: int = -1) -> None:
        self.view.hide_popup()
        index = int(href)
        resolve(self.actions[index] if index != -1 else None)
