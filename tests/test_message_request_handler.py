import unittest
from test_mocks import MockClient
from LSP.plugin.core.message_request_handler import MessageRequestHandler
import sublime


class MessageRequestHandlerTest(unittest.TestCase):
    def test_show_popup(self):
        window = sublime.active_window()
        view = window.active_view()
        client = MockClient()
        params = {
            'type': 1,
            'message': 'hello',
            'actions': [
                {'title': "abc"},
                {'title': "def"}
            ]
        }
        handler = MessageRequestHandler(view, client, "1", params)
        handler.show()
        self.assertTrue(view.is_popup_visible())
