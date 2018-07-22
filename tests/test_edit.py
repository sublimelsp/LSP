from unittesting import DeferrableTestCase
import sublime
from os.path import dirname

test_file_path = dirname(__file__) + "/testfile.txt"

ORIGINAL_CONTENT = """<dom-module id="some-thing">
<style></style>
<template>
</template>
</dom-module>"""

EXPECTED_CONTENT = """<dom-module id="some-thing">
<template>
    <style></style>
</template>
</dom-module>"""


class ApplyDocumentEditTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().new_file()
        self.view.run_command('insert', {"characters": ORIGINAL_CONTENT})

    def test_apply(self):
        file_changes = [{
            'range': {
                'start': {'line': 0, 'character': 28},
                'end': {'line': 1, 'character': 0}
            },
            'newText': ''
        }, {
            'range': {
                'start': {'line': 1, 'character': 0},
                'end': {'line': 1, 'character': 15}
            },
            'newText': ''
        }, {
            'range': {
                'start': {'line': 2, 'character': 10},
                'end': {'line': 2, 'character': 10}
            },
            'newText': '\n    <style></style>'
        }]

        self.view.run_command('lsp_apply_document_edit', {'changes': file_changes, 'show_status': False})

        edited_content = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals(edited_content, EXPECTED_CONTENT)

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
