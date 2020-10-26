from LSP.plugin.core.typing import Generator
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.diagnostics import DiagnosticsCursor
from LSP.plugin.core.protocol import DiagnosticSeverity
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

        # Check that the cursor is in its initial empty state.
        cursor = self.wm._cursor
        self.assertIsInstance(cursor, DiagnosticsCursor)
        self.assertFalse(cursor.has_value)

        # Let's go to the next diagnostic. The cursor should have advanced to the first diagnostic.
        self.wm.window().run_command("lsp_next_diagnostic")
        yield lambda: cursor.has_value
        self.assertTrue(cursor.has_value)
        file_name, diag = cursor.value
        self.assertEqual(file_name, self.view.file_name())
        self.assertEqual(diag.severity, DiagnosticSeverity.Error)
        self.assertEqual(diag.message, "foo")
        self.assertEqual(diag.source, "qux")

        # Now the second diagnostic.
        self.wm.window().run_command("lsp_next_diagnostic")
        yield lambda: cursor.value[1].severity != diag.severity
        file_name, diag = cursor.value
        self.assertEqual(file_name, self.view.file_name())
        self.assertEqual(diag.severity, DiagnosticSeverity.Warning)
        self.assertEqual(diag.message, "bar")
        self.assertEqual(diag.source, "qux")

        # Now the third diagnostic.
        self.wm.window().run_command("lsp_next_diagnostic")
        yield lambda: cursor.value[1].severity != diag.severity
        file_name, diag = cursor.value
        self.assertEqual(file_name, self.view.file_name())
        self.assertEqual(diag.severity, DiagnosticSeverity.Information)
        self.assertEqual(diag.message, "baz")
        self.assertEqual(diag.source, "qux")

        # Move forward one more time and check that wrap-around works.
        self.wm.window().run_command("lsp_next_diagnostic")
        yield lambda: cursor.value[1].severity != diag.severity
        file_name, diag = cursor.value
        self.assertEqual(file_name, self.view.file_name())
        self.assertEqual(diag.severity, DiagnosticSeverity.Error)
        self.assertEqual(diag.message, "foo")
        self.assertEqual(diag.source, "qux")

        # Move backwards and check that wrap-around in the other direction works.
        self.wm.window().run_command("lsp_previous_diagnostic")
        yield lambda: cursor.value[1].severity != diag.severity
        file_name, diag = cursor.value
        self.assertEqual(file_name, self.view.file_name())
        self.assertEqual(diag.severity, DiagnosticSeverity.Information)
        self.assertEqual(diag.message, "baz")
        self.assertEqual(diag.source, "qux")
