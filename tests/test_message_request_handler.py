from __future__ import annotations
from LSP.plugin.core.message_request_handler import MessageRequestHandler
from test_mocks import MockSession
import sublime
import unittest


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
