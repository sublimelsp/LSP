from __future__ import annotations

from LSP.plugin.core.url import filename_to_uri
from LSP.protocol import DiagnosticSeverity
from LSP.protocol import DiagnosticTag
from LSP.protocol import PublishDiagnosticsParams
from setup import TextDocumentTestCase
from typing import Generator
import sublime


class ServerNotifications(TextDocumentTestCase):

    def test_publish_diagnostics(self) -> Generator:
        self.insert_characters("a b c\n")
        yield from self.await_message('textDocument/didChange')
        params: PublishDiagnosticsParams = {
            'uri': filename_to_uri(self.view.file_name() or ''),
            'diagnostics': [
                {
                    'message': "foo",
                    'severity': DiagnosticSeverity.Error,
                    'source': 'qux',
                    'range': {'end': {'character': 1, 'line': 0}, 'start': {'character': 0, 'line': 0}}
                },
                {
                    'message': 'bar',
                    'severity': DiagnosticSeverity.Warning,
                    'source': 'qux',
                    'range': {'end': {'character': 3, 'line': 0}, 'start': {'character': 2, 'line': 0}}
                },
                {
                    'message': "baz",
                    'severity': DiagnosticSeverity.Information,
                    'source': 'qux',
                    'range': {'end': {'character': 5, 'line': 0}, 'start': {'character': 4, 'line': 0}},
                    'tags': [DiagnosticTag.Unnecessary]
                }
            ]
        }
        yield from self.await_client_notification("textDocument/publishDiagnostics", params)
        errors_icon_regions = self.view.get_regions("lspTESTds1_icon")
        errors_underline_regions = self.view.get_regions("lspTESTds1_underline")
        warnings_icon_regions = self.view.get_regions("lspTESTds2_icon")
        warnings_underline_regions = self.view.get_regions("lspTESTds2_underline")
        info_icon_regions = self.view.get_regions("lspTESTds3_icon")
        info_underline_regions = self.view.get_regions("lspTESTds3_underline")
        yield lambda: len(errors_icon_regions) == len(errors_underline_regions) == 1
        yield lambda: len(warnings_icon_regions) == len(warnings_underline_regions) == 1
        yield lambda: len(info_icon_regions) == len(info_underline_regions) == 1
        yield lambda: len(self.view.get_regions("lspTESTds3_tags")) == 0
        self.assertEqual(errors_underline_regions[0], sublime.Region(0, 1))
        self.assertEqual(warnings_underline_regions[0], sublime.Region(2, 3))
        self.assertEqual(info_underline_regions[0], sublime.Region(4, 5))

        # Testing whether the cursor position moves along with lsp_next_diagnostic

        self.view.window().run_command("lsp_next_diagnostic")
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 0)

        self.view.window().run_command("lsp_next_diagnostic")
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 2)

        self.view.window().run_command("lsp_next_diagnostic")
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 4)

        # lsp_prev_diagnostic should work as well

        self.view.window().run_command("lsp_prev_diagnostic")
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 2)

        self.view.window().run_command("lsp_prev_diagnostic")
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 0)

        # Testing to wrap around if there are no more diagnostics in the direction

        self.view.window().run_command("lsp_prev_diagnostic")
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 4)
