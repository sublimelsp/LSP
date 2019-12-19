import sublime

from setup import TextDocumentTestCase

try:
    from typing import Dict, Optional, List
    assert Dict and Optional and List
except ImportError:
    pass

OPEN_DOCUMENT_DELAY = 100
DID_CHANGE_PURGE_DELAY = 500


class DocumentFormattingTests(TextDocumentTestCase):

    def test_formats_on_save(self):
        self.transport.responses['textDocument/formatting'] = [{
            'newText': "BBB",
            'range': {
                'start': {
                    'line': 0,
                    'character': 0
                },
                'end': {
                    'line': 0,
                    'character': 3
                }
            }
        }]

        yield OPEN_DOCUMENT_DELAY*3
        self.view.settings().set("lsp_format_on_save", True)

        self.assertEquals(self.transport.sent[0]["method"], "initialize")
        self.assertEquals(self.transport.sent[1]["method"], "initialized")
        self.assertEquals(self.transport.sent[2]["method"], "textDocument/didOpen")

        self.view.run_command("insert", {"characters": "A"})

        yield 100

        self.view.run_command("save")

        yield 100

        self.assertEquals(self.transport.sent[3]["method"], "textDocument/didChange")
        self.assertEquals(self.transport.sent[4]["method"], "textDocument/formatting")
        self.assertEquals(self.transport.sent[5]["method"], "textDocument/didSave")
        self.assertEquals(self.transport.sent[6]["method"], "textDocument/didChange")
        self.assertEquals(self.transport.sent[7]["method"], "textDocument/didSave")

        text = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals("BBB", text)

    def tearDown(self) -> None:
        # revert
        # self.wm._handle_post_exit("textls")
        self.view.settings().set("lsp_format_on_save", False)
        self.view.run_command("select_all")
        self.view.run_command("left_delete")
        self.view.run_command("save")
        print("saving cleaned")
        super().tearDown()


class WillSaveWaitUntilTests(TextDocumentTestCase):

    def test_will_save_wait_until(self):
        self.transport.responses['textDocument/willSaveWaitUntil'] = [{
            'newText': "BBB",
            'range': {
                'start': {
                    'line': 0,
                    'character': 0
                },
                'end': {
                    'line': 0,
                    'character': 3
                }
            }
        }]

        yield OPEN_DOCUMENT_DELAY*3
        self.session.capabilities['textDocumentSync']['willSaveWaitUntil'] = True
        self.view.settings().set("lsp_format_on_save", False)

        self.assertEquals(self.transport.sent[0]["method"], "initialize")
        self.assertEquals(self.transport.sent[1]["method"], "initialized")
        self.assertEquals(self.transport.sent[2]["method"], "textDocument/didOpen")

        self.view.run_command("insert", {"characters": "A"})

        yield 100

        self.view.run_command("save")

        yield 100

        self.assertEquals(self.transport.sent[3]["method"], "textDocument/didChange")
        self.assertEquals(self.transport.sent[4]["method"], "textDocument/willSaveWaitUntil")
        self.assertEquals(self.transport.sent[5]["method"], "textDocument/didSave")
        self.assertEquals(self.transport.sent[6]["method"], "textDocument/didChange")
        self.assertEquals(self.transport.sent[7]["method"], "textDocument/didSave")

        text = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals("BBB", text)

    def tearDown(self) -> None:
        self.session.capabilities['textDocumentSync']['willSaveWaitUntil'] = False
        self.view.run_command("select_all")
        self.view.run_command("left_delete")
        self.view.run_command("save")
        super().tearDown()
