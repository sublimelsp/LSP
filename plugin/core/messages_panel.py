from __future__ import annotations

from .constants import MESSAGE_TYPE_LEVELS
from .panels import buttons_html
from .panels import PanelManager
from .panels import PanelName
from .promise import Promise
from .promise import ResolveFunc
from datetime import datetime
from itertools import count
from typing import TYPE_CHECKING
import sublime

if TYPE_CHECKING:
    from ...protocol import MessageActionItem
    from ...protocol import MessageType
    from ...protocol import ShowMessageParams
    from ...protocol import ShowMessageRequestParams

MAX_MESSAGES = 100
INDENT = "    "

DISMISS_HREF = "dismiss"


class MessageEntry:

    _ids = count()

    def __init__(
        self,
        config_name: str,
        message_type: MessageType,
        message: str,
        actions: list[MessageActionItem] | None = None,
        resolve: ResolveFunc[MessageActionItem | None] | None = None
    ) -> None:
        self.id = next(self._ids)
        self.config_name = config_name
        self.message_type = message_type
        self.message = message
        self.timestamp = datetime.now()
        self.actions = actions or []
        self.resolve = resolve
        # Text describing the outcome of a request. Only relevant for requests that are no longer pending.
        self.outcome: str | None = None

    @property
    def is_pending(self) -> bool:
        return self.resolve is not None

    def conclude(self, outcome: str, response: MessageActionItem | None = None, *, notify: bool = True) -> None:
        resolve = self.resolve
        if resolve is None:
            return
        self.resolve = None
        self.outcome = outcome
        if notify:
            resolve(response)

    def render(self) -> str:
        level = MESSAGE_TYPE_LEVELS.get(self.message_type, "INFO")
        lines = [f"{self.timestamp.strftime('%H:%M:%S')} {self.config_name} {level}"]
        message = self.message.replace("\r\n", "\n").rstrip() or "<empty message>"
        lines.extend(f"{INDENT}{line}".rstrip() for line in message.split("\n"))
        if self.outcome:
            lines.append(f"{INDENT}{self.outcome}")
        return "\n".join(lines)

    def render_buttons(self) -> str:
        buttons = [(str(idx), action['title'], idx == 0) for idx, action in enumerate(self.actions)]
        buttons.append((DISMISS_HREF, "Dismiss", False))
        return buttons_html(buttons)


class MessagesPanel:
    """
    Shows `window/showMessage` notifications and `window/showMessageRequest` requests in a dedicated output panel.

    Requests are rendered with buttons for each of the actions provided by the server. A request stays pending until
    the user chooses one of the actions or dismisses it, or until the server that sent it exits.

    All the state is only accessed and modified on the main thread.
    """

    def __init__(self, window: sublime.Window, panel_manager: PanelManager) -> None:
        self._window = window
        self._panel_manager = panel_manager
        self._entries: list[MessageEntry] = []
        self._phantom_set: sublime.PhantomSet | None = None

    def add_message(self, config_name: str, params: ShowMessageParams, show_panel: bool) -> None:
        entry = MessageEntry(config_name, params['type'], params['message'])
        sublime.set_timeout(lambda: self._add_entry(entry, show_panel))

    def add_request(self, config_name: str, params: ShowMessageRequestParams) -> Promise[MessageActionItem | None]:
        promise, resolve = Promise.packaged_task()
        entry = MessageEntry(config_name, params['type'], params['message'], params.get('actions'), resolve)
        sublime.set_timeout(lambda: self._add_entry(entry, show_panel=True))
        return promise

    def expire_requests(self, config_name: str) -> None:
        """Mark pending requests from the given server as no longer answerable, for example because it has exited."""
        def run() -> None:
            changed = False
            for entry in self._entries:
                if entry.is_pending and entry.config_name == config_name:
                    entry.conclude("(expired - the server has exited)", notify=False)
                    changed = True
            if changed:
                self._render()

        sublime.set_timeout(run)

    def clear(self) -> None:
        """Remove all entries except the requests that still await a response."""
        self._entries = [entry for entry in self._entries if entry.is_pending]
        self._render()

    def toggle(self) -> None:
        if not self._panel_manager.get_panel(PanelName.Messages):
            self._render()
        self._panel_manager.toggle_output_panel(PanelName.Messages)

    def destroy(self) -> None:
        self._entries.clear()
        self._phantom_set = None

    def _add_entry(self, entry: MessageEntry, show_panel: bool) -> None:
        self._entries.append(entry)
        self._trim_entries()
        self._render()
        if show_panel and not self._panel_manager.is_panel_open(PanelName.Messages):
            self._window.run_command("show_panel", {"panel": f"output.{PanelName.Messages}"})

    def _trim_entries(self) -> None:
        excess = len(self._entries) - MAX_MESSAGES
        if excess <= 0:
            return
        kept: list[MessageEntry] = []
        for entry in self._entries:
            if excess > 0 and not entry.is_pending:
                excess -= 1
                continue
            kept.append(entry)
        self._entries = kept

    def _on_navigate(self, entry: MessageEntry, href: str) -> None:
        if not entry.is_pending:
            return
        if href == DISMISS_HREF:
            entry.conclude("(dismissed)")
        else:
            action = entry.actions[int(href)]
            entry.conclude(f"(selected: {action['title']})", action)
        self._render()

    def _render(self) -> None:
        panel = self._panel_manager.ensure_messages_panel()
        if not panel:
            return
        if self._phantom_set is None or self._phantom_set.view != panel:
            self._phantom_set = sublime.PhantomSet(panel, "lsp_message_actions")
        chunks: list[str] = []
        pending: list[tuple[int, MessageEntry]] = []
        offset = 0
        # Show the newest entries at the top.
        for entry in reversed(self._entries):
            text = entry.render()
            if entry.is_pending:
                pending.append((offset + len(text), entry))
            chunks.append(text)
            offset += len(text) + 2  # Account for the empty line between entries.
        panel.run_command("lsp_update_panel", {"characters": "\n\n".join(chunks)})
        self._phantom_set.update([
            sublime.Phantom(
                sublime.Region(point),
                entry.render_buttons(),
                sublime.PhantomLayout.BLOCK,
                on_navigate=lambda href, entry=entry: self._on_navigate(entry, href)
            ) for point, entry in pending
        ])
        panel.show(0, animate=False)
