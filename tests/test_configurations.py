from __future__ import annotations

from LSP.plugin.core.configurations import WindowConfigManager
from test_mocks import DISABLED_CONFIG
from test_mocks import TEST_CONFIG
from unittest import TestCase
from unittest.mock import MagicMock
from unittesting import ViewTestCase
import sublime


class GlobalConfigManagerTests(TestCase):

    def test_empty_configs(self):
        window_mgr = WindowConfigManager(sublime.active_window(), {})
        self.assertNotIn(TEST_CONFIG.name, window_mgr.all)

    def test_global_config(self):
        window_mgr = WindowConfigManager(sublime.active_window(), {TEST_CONFIG.name: TEST_CONFIG})
        self.assertIn(TEST_CONFIG.name, window_mgr.all)

    def test_override_config(self):
        self.assertTrue(TEST_CONFIG.enabled)
        win = sublime.active_window()
        win.project_data = MagicMock(return_value={'settings': {'LSP': {TEST_CONFIG.name: {"enabled": False}}}})
        window_mgr = WindowConfigManager(win, {TEST_CONFIG.name: TEST_CONFIG})
        self.assertFalse(list(window_mgr.all.values())[0].enabled)


class WindowConfigManagerTests(ViewTestCase):

    def test_no_configs(self):
        self.assertIsNotNone(self.view)
        self.assertIsNotNone(self.window)
        manager = WindowConfigManager(self.window, {})
        self.assertEqual(list(manager.match_view(self.view)), [])

    def test_with_single_config(self):
        self.assertIsNotNone(self.view)
        self.assertIsNotNone(self.window)
        manager = WindowConfigManager(self.window, {TEST_CONFIG.name: TEST_CONFIG})
        self.view.syntax = MagicMock(return_value=sublime.Syntax(
            path="Packages/Text/Plain text.tmLanguage",
            name="Plain Text",
            scope="text.plain",
            hidden=False
        ))
        self.view.settings().set("lsp_uri", "file:///foo/bar.txt")
        self.assertEqual(list(manager.match_view(self.view)), [TEST_CONFIG])

    def test_applies_project_settings(self):
        self.window.project_data = MagicMock(return_value={
            "settings": {
                "LSP": {
                    "test": {
                        "enabled": True
                    }
                }
            }
        })
        manager = WindowConfigManager(self.window, {DISABLED_CONFIG.name: DISABLED_CONFIG})
        self.view.syntax = MagicMock(return_value=sublime.Syntax(
            path="Packages/Text/Plain text.tmLanguage",
            name="Plain Text",
            scope="text.plain",
            hidden=False
        ))
        self.view.settings().set("lsp_uri", "file:///foo/bar.txt")
        configs = list(manager.match_view(self.view))
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(DISABLED_CONFIG.name, config.name)
        self.assertTrue(config.enabled)

    def test_disables_temporarily(self):
        self.window.project_data = MagicMock(return_value={
            "settings": {
                "LSP": {
                    "test": {
                        "enabled": True
                    }
                }
            }
        })

        manager = WindowConfigManager(self.window, {DISABLED_CONFIG.name: DISABLED_CONFIG})
        # disables config in-memory
        manager.disable_config(DISABLED_CONFIG.name, only_for_session=True)
        self.assertFalse(any(manager.match_view(self.view)))
