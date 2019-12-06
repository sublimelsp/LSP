import os

from setup import TextDocumentTestCase

try:
    from typing import Dict, Optional, List
    assert Dict and Optional and List
except ImportError:
    pass

OPEN_DOCUMENT_DELAY = 100
DID_CHANGE_PURGE_DELAY = 500
AFTER_INSERT_COMPLETION_DELAY = 1000 if os.getenv("TRAVIS") else 100


class DocumentSyncTests(TextDocumentTestCase):
    def test_sends_did_open(self):
        yield OPEN_DOCUMENT_DELAY*3

        self.assertEquals(self.transport.sent[0]["method"], "initialize")
        self.assertEquals(self.transport.sent[1]["method"], "initialized")
        self.assertEquals(self.transport.sent[2]["method"], "textDocument/didOpen")

        self.view.run_command("insert", {"characters": "A"})

        yield DID_CHANGE_PURGE_DELAY + 100

        self.assertEquals(self.transport.sent[3]["method"], "textDocument/didChange")

    def test_sends_save_with_purge(self):
        yield OPEN_DOCUMENT_DELAY*3

        self.assertEquals(self.transport.sent[0]["method"], "initialize")
        self.assertEquals(self.transport.sent[1]["method"], "initialized")
        self.assertEquals(self.transport.sent[2]["method"], "textDocument/didOpen")

        self.view.run_command("insert", {"characters": "A"})

        yield 100

        self.view.run_command("save")

        yield 100

        self.assertEquals(self.transport.sent[3]["method"], "textDocument/didChange")
        self.assertEquals(self.transport.sent[4]["method"], "textDocument/didSave")

    def tearDown(self) -> None:
        # revert
        self.view.run_command("select_all")
        self.view.run_command("left_delete")
        self.view.run_command("save")
        print("saving cleaned")
        super().tearDown()

