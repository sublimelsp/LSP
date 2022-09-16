from LSP.plugin.core.panels import PanelName
from LSP.plugin.core.protocol import DiagnosticSeverity
from LSP.plugin.core.protocol import DiagnosticTag
from LSP.plugin.core.protocol import PublishDiagnosticsParams
from LSP.plugin.core.typing import Generator
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
import sublime
import time


class ServerNotifications(TextDocumentTestCase):

    def test_publish_diagnostics(self) -> Generator:
        self.insert_characters("a b c\n")
        params = {
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
        }  # type: PublishDiagnosticsParams
        yield from self.await_client_notification("textDocument/publishDiagnostics", params)
        yield lambda: len(self.view.get_regions("lspTESTds1")) > 0
        yield lambda: len(self.view.get_regions("lspTESTds2")) > 0
        yield lambda: len(self.view.get_regions("lspTESTds3")) > 0
        yield lambda: len(self.view.get_regions("lspTESTds3_tags")) == 0
        errors = self.view.get_regions("lspTESTds1")
        warnings = self.view.get_regions("lspTESTds2")
        info = self.view.get_regions("lspTESTds3")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], sublime.Region(0, 1))
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0], sublime.Region(2, 3))
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0], sublime.Region(4, 5))

        # Testing whether the popup with the diagnostic moves along with next_result

        self.view.window().run_command("show_panel", {"panel": "output.{}".format(PanelName.Diagnostics)})
        time.sleep(0.1)  # Give Diagnostics panel a bit of time to update its content (on async thread)
        # Make sure diagnostics panel has focus, so that "next_result" & "prev_result" commands don't
        # navigate between build results, find results, or find references
        self.view.window().focus_view(self.view.window().find_output_panel(PanelName.Diagnostics))

        self.view.window().run_command("next_result")
        yield self.view.is_popup_visible
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 0)

        self.view.window().run_command("next_result")
        yield self.view.is_popup_visible
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 2)

        self.view.window().run_command("next_result")
        yield self.view.is_popup_visible
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 4)

        # prev_result should work as well

        self.view.window().run_command("prev_result")
        yield self.view.is_popup_visible
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 2)

        self.view.window().run_command("prev_result")
        yield self.view.is_popup_visible
        self.assertEqual(self.view.sel()[0].a, self.view.sel()[0].b)
        self.assertEqual(self.view.sel()[0].b, 0)
