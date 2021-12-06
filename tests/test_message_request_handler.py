import unittest
from test_mocks import MockSession
from LSP.plugin.core.windows import WindowManager
import sublime


class MessageRequestHandlerTest(unittest.TestCase):
    def test_show_popup(self):
        window = sublime.active_window()
        view = window.active_view()
        session = MockSession()
        params = {
            'type': 1,
            'message': 'hello',
            'actions': [
                {'title': "abc"},
                {'title': "def"}
            ]
        }
        manager = WindowManager(window, None, None)
        manager.handle_message_request(session, params, "1")
        self.assertEquals(view.element(), "input:input")
