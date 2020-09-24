import unittest
from test_mocks import MockSession
from LSP.plugin.core.message_request_handler import MessageRequestHandler
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
        handler = MessageRequestHandler(view, session, "1", params, 'lsp server')
        handler.show()
        self.assertTrue(view.is_popup_visible())
