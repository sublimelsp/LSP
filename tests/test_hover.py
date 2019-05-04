from LSP.plugin.hover import _test_contents
from setup import TextDocumentTestCase

ORIGINAL_CONTENT = """Hello Wrld"""

EXPECTED_CONTENT = """<dom-module id="some-thing">
<template>
    <style></style>
</template>
</dom-module>"""


class LspHoverCommandTests(TextDocumentTestCase):

    def test_hover_info(self):
        self.client.responses['textDocument/hover'] = {"contents": "greeting"}

        yield 100  # wait for file to be open
        self.view.run_command('insert', {"characters": ORIGINAL_CONTENT})
        self.view.run_command('lsp_hover', {'point': 3})

        yield 100  # popup should be visible eventually
        self.assertTrue(self.view.is_popup_visible())

        last_content = _test_contents[-1]
        self.assertTrue("greeting" in last_content)
