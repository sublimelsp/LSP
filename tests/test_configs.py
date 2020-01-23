from unittesting import DeferrableTestCase
import unittest
import sublime
from os.path import dirname
from LSP.plugin.core.settings import client_configs, read_client_config, update_client_config
from LSP.plugin.core.registry import windows

test_file_path = dirname(__file__) + "/testfile.txt"


class ConfigParsingTests(DeferrableTestCase):

    def test_can_parse_old_client_settings(self):
        settings = {
            "command": ["pyls"],
            "scopes": ["source.python"],
            "syntaxes": ["Packages/Python/Python.sublime-syntax"],
            "languageId": "python"
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(len(config.languages), 1)
        self.assertEqual(config.languages[0].scopes, ["source.python"])

    def test_can_parse_client_settings_with_languages(self):
        settings = {
            "command": ["pyls"],
            "languages": [{
                "scopes": ["source.python"],
                "syntaxes": ["Packages/Python/Python.sublime-syntax"],
                "languageId": "python"
            }]
        }
        config = read_client_config("pyls", settings)
        self.assertEqual(len(config.languages), 1)
        self.assertEqual(config.languages[0].scopes, ["source.python"])

    def test_can_update_config(self):
        settings = {
            "command": ["pyls"],
            "scopes": ["source.python"],
            "syntaxes": ["Packages/Python/Python.sublime-syntax"],
            "languageId": "python"
        }
        config = read_client_config("pyls", settings)
        config = update_client_config(config, {"enabled": True})
        self.assertEqual(config.enabled, True)


class ConfigTests(DeferrableTestCase):

    @unittest.skip('only at develop-time')
    def test_defaults(self):
        self.assertEqual(len(client_configs.all), 15)
        for config in client_configs.all:
            self.assertFalse(config.enabled)
            self.assertEqual(1, len(config.languages))


class WindowConfigTests(DeferrableTestCase):

    def setUp(self):
        super().setUp()
        w, windows._windows = windows._windows, {}
        for window_id, wm in w.items():
            wm.end_sessions()
            yield lambda: len(wm._sessions) == 0
        self.view = sublime.active_window().open_file(test_file_path)

    def test_window_without_configs(self):
        yield 100
        wm = windows.lookup(sublime.active_window())
        self.assertFalse(wm._configs.syntax_supported(self.view))

    def test_window_with_config(self):
        pass

    def doCleanups(self):
        if hasattr(self, "view") and self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
        yield from super().doCleanups()
