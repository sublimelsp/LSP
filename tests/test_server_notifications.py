from LSP.plugin.core.typing import Generator
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
import sublime


class ServerNotifications(TextDocumentTestCase):

    def test_publish_diagnostics(self) -> Generator:
        self.insert_characters("a b c\n")
        yield from self.await_client_notification("textDocument/publishDiagnostics", {
            'uri': filename_to_uri(self.view.file_name()),
            'diagnostics': [
                {
                    'message': "foo",
                    'severity': 1,
                    'source': 'qux',
                    'range': {'end': {'character': 1, 'line': 0}, 'start': {'character': 0, 'line': 0}}
                },
                {
                    'message': 'bar',
                    'severity': 2,
                    'source': 'qux',
                    'range': {'end': {'character': 3, 'line': 0}, 'start': {'character': 2, 'line': 0}}
                },
                {
                    'message': "baz",
                    'severity': 3,
                    'source': 'qux',
                    'range': {'end': {'character': 5, 'line': 0}, 'start': {'character': 4, 'line': 0}}
                }
            ]
        })
        yield lambda: len(self.view.get_regions("lspTESTd1")) > 0
        yield lambda: len(self.view.get_regions("lspTESTd2")) > 0
        yield lambda: len(self.view.get_regions("lspTESTd3")) > 0
        errors = self.view.get_regions("lspTESTd1")
        warnings = self.view.get_regions("lspTESTd2")
        info = self.view.get_regions("lspTESTd3")
        self.assertEqual(errors[0], sublime.Region(0, 1))
        self.assertEqual(warnings[0], sublime.Region(2, 3))
        self.assertEqual(info[0], sublime.Region(4, 5))
