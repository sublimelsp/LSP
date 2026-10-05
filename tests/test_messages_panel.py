from __future__ import annotations

from LSP.plugin.core.messages_panel import MessagesPanel
from LSP.plugin.core.panels import PanelManager
from LSP.plugin.core.panels import PanelName
from LSP.protocol import MessageType
from typing import Any
from typing import Generator
from unittesting import DeferrableTestCase
import sublime


class WindowStub:
    """Records `show_panel` calls instead of running them, so that the UnitTesting output panel stays visible."""

    def __init__(self) -> None:
        self.shown_panels: list[str] = []

    def run_command(self, command: str, args: dict[str, Any]) -> None:
        if command == "show_panel":
            self.shown_panels.append(args["panel"])


class MessagesPanelTests(DeferrableTestCase):

    def setUp(self) -> None:
        super().setUp()
        window = sublime.active_window()
        self.window = window
        self.window_stub = WindowStub()
        self.panel_manager = PanelManager(window)
        self.messages = MessagesPanel(self.window_stub, self.panel_manager)  # type: ignore
        self.results: list[Any] = []

    def tearDown(self) -> None:
        self.messages.destroy()
        self.window.destroy_output_panel(PanelName.Messages)
        super().tearDown()

    def panel_text(self) -> str:
        panel = self.panel_manager.get_panel(PanelName.Messages)
        self.assertIsNotNone(panel)
        assert panel
        return panel.substr(sublime.Region(0, panel.size()))

    def phantom_count(self) -> int:
        phantom_set = self.messages._phantom_set
        return len(phantom_set.phantoms) if phantom_set else 0

    def test_show_message(self) -> Generator:
        self.messages.add_message("server", {"type": MessageType.Error, "message": "first\nsecond"}, show_panel=False)
        yield lambda: self.panel_manager.get_panel(PanelName.Messages) is not None
        text = self.panel_text()
        self.assertRegex(text, r"^\d{2}:\d{2}:\d{2} server ERROR\n    first\n    second$")
        self.assertEqual(self.phantom_count(), 0)
        self.assertEqual(self.window_stub.shown_panels, [])
        self.messages.add_message("server", {"type": MessageType.Info, "message": "third"}, show_panel=True)
        yield lambda: self.window_stub.shown_panels == [f"output.{PanelName.Messages}"]
        self.assertTrue(self.panel_text().endswith(" server INFO\n    third"))

    def test_show_message_request_action(self) -> Generator:
        actions = [{"title": "Yes"}, {"title": "No", "extra": 1}]
        params = {"type": MessageType.Warning, "message": "Sure?", "actions": actions}
        promise = self.messages.add_request("server", params)
        promise.then(self.results.append)
        yield lambda: self.phantom_count() == 1
        self.assertEqual(self.window_stub.shown_panels, [f"output.{PanelName.Messages}"])
        entry = self.messages._entries[0]
        self.messages._on_navigate(entry, "1")
        yield lambda: len(self.results) == 1
        self.assertEqual(self.results, [{"title": "No", "extra": 1}])
        self.assertEqual(self.phantom_count(), 0)
        self.assertTrue(self.panel_text().endswith("    Sure?\n    (selected: No)"))
        # Further clicks are ignored once the request is concluded.
        self.messages._on_navigate(entry, "0")
        self.assertEqual(len(self.results), 1)

    def test_show_message_request_dismiss(self) -> Generator:
        promise = self.messages.add_request("server", {"type": MessageType.Info, "message": "Hello"})
        promise.then(self.results.append)
        yield lambda: self.phantom_count() == 1
        self.messages._on_navigate(self.messages._entries[0], "dismiss")
        yield lambda: len(self.results) == 1
        self.assertEqual(self.results, [None])
        self.assertTrue(self.panel_text().endswith("    Hello\n    (dismissed)"))

    def test_expire_and_clear(self) -> Generator:
        self.messages.add_message("server", {"type": MessageType.Info, "message": "note"}, show_panel=False)
        self.messages.add_request("server", {"type": MessageType.Info, "message": "a", "actions": [{"title": "A"}]})
        self.messages.add_request("other", {"type": MessageType.Info, "message": "b", "actions": [{"title": "B"}]})
        yield lambda: self.phantom_count() == 2
        self.messages.expire_requests("server")
        yield lambda: self.phantom_count() == 1
        self.assertIn("    a\n    (expired - the server has exited)", self.panel_text())
        self.messages.clear()
        self.assertEqual([entry.message for entry in self.messages._entries], ["b"])
        self.assertEqual(self.phantom_count(), 1)
