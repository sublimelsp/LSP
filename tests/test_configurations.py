from LSP.plugin.core.configurations import ConfigManager
from LSP.plugin.core.configurations import WindowConfigManager
from test_mocks import DISABLED_CONFIG
from test_mocks import TEST_CONFIG
from unittest.mock import MagicMock
import sublime
import unittest


class GlobalConfigManagerTests(unittest.TestCase):

    def test_empty_configs(self):
        manager = ConfigManager({})
        window_mgr = manager.for_window(sublime.active_window())
        self.assertNotIn(TEST_CONFIG.name, window_mgr.all)

    def test_global_config(self):
        manager = ConfigManager({TEST_CONFIG.name: TEST_CONFIG})
        window_mgr = manager.for_window(sublime.active_window())
        self.assertIn(TEST_CONFIG.name, window_mgr.all)

    def test_override_config(self):
        manager = ConfigManager({TEST_CONFIG.name: TEST_CONFIG})
        self.assertTrue(TEST_CONFIG.enabled)
        win = sublime.active_window()
        win.project_data = MagicMock(return_value={'settings': {'LSP': {TEST_CONFIG.name: {"enabled": False}}}})
        window_mgr = manager.for_window(win)
        self.assertFalse(list(window_mgr.all.values())[0].enabled)


class WindowConfigManagerTests(unittest.TestCase):

    def test_no_configs(self):
        view = sublime.active_window().active_view()
        self.assertIsNotNone(view)
        assert view
        manager = WindowConfigManager(sublime.active_window(), {})
        self.assertEqual(list(manager.match_view(view)), [])

    def test_with_single_config(self):
        window = sublime.active_window()
        view = window.active_view()
        self.assertIsNotNone(view)
        assert view
        manager = WindowConfigManager(window, {TEST_CONFIG.name: TEST_CONFIG})
        view.syntax = MagicMock(return_value=sublime.Syntax(
            path="Packages/Text/Plain text.tmLanguage",
            name="Plain Text",
            scope="text.plain",
            hidden=False
        ))
        self.assertEqual(list(manager.match_view(view)), [TEST_CONFIG])

    def test_applies_project_settings(self):
        window = sublime.active_window()
        view = window.active_view()
        assert view
        window.project_data = MagicMock(return_value={
            "settings": {
                "LSP": {
                    "test": {
                        "enabled": True
                    }
                }
            }
        })
        manager = WindowConfigManager(window, {DISABLED_CONFIG.name: DISABLED_CONFIG})
        view.syntax = MagicMock(return_value=sublime.Syntax(
            path="Packages/Text/Plain text.tmLanguage",
            name="Plain Text",
            scope="text.plain",
            hidden=False
        ))
        configs = list(manager.match_view(view))
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(DISABLED_CONFIG.name, config.name)
        self.assertTrue(config.enabled)

    def test_disables_temporarily(self):
        window = sublime.active_window()
        view = window.active_view()
        window.project_data = MagicMock(return_value={
            "settings": {
                "LSP": {
                    "test": {
                        "enabled": True
                    }
                }
            }
        })

        manager = WindowConfigManager(window, {DISABLED_CONFIG.name: DISABLED_CONFIG})
        # disables config in-memory
        manager.disable_config(DISABLED_CONFIG.name, only_for_session=True)
        self.assertFalse(any(manager.match_view(view)))
