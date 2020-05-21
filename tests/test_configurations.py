from LSP.plugin.core.configurations import ConfigManager
from LSP.plugin.core.configurations import WindowConfigManager
from LSP.plugin.core.settings import client_configs
from test_mocks import DISABLED_CONFIG
from test_mocks import TEST_CONFIG
from test_mocks import TEST_LANGUAGE
from unittest.mock import MagicMock
import sublime
import unittest


class GlobalConfigManagerTests(unittest.TestCase):

    def test_empty_configs(self):
        manager = ConfigManager([])
        window_mgr = manager.for_window(sublime.active_window())
        self.assertEqual(window_mgr.all, [])

    def test_global_config(self):
        manager = ConfigManager([TEST_CONFIG])
        window_mgr = manager.for_window(sublime.active_window())
        self.assertEqual(window_mgr.all, [TEST_CONFIG])

    def test_override_config(self):
        manager = ConfigManager([TEST_CONFIG])
        self.assertTrue(TEST_CONFIG.enabled)
        win = sublime.active_window()
        win.project_data = MagicMock(return_value={'settings': {'LSP': {TEST_CONFIG.name: {"enabled": False}}}})
        window_mgr = manager.for_window(win)
        self.assertFalse(window_mgr.all[0].enabled)


class WindowConfigManagerTests(unittest.TestCase):

    def test_no_configs(self):
        view = sublime.active_window().active_view()
        manager = WindowConfigManager(sublime.active_window(), [])
        self.assertFalse(manager.is_supported(view))

    def test_with_single_config(self):
        window = sublime.active_window()
        view = window.active_view()
        manager = WindowConfigManager(window, [TEST_CONFIG])
        view.scope_name = MagicMock(return_value='text.plain ')
        self.assertTrue(manager.is_supported(view))
        self.assertEqual(list(manager.match_view(view)), [TEST_CONFIG])

    def test_applies_project_settings(self):
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
        manager = WindowConfigManager(window, [DISABLED_CONFIG])
        manager.update()
        view.scope_name = MagicMock(return_value='text.plain ')
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

        manager = WindowConfigManager(window, [DISABLED_CONFIG])
        manager.update()

        # crash handler disables config and shows popup
        manager.disable_temporarily(DISABLED_CONFIG.name)

        # view is activated after popup, we try to start a session again...
        manager.update()
        self.assertFalse(any(manager.match_view(view)))


class IsSupportedSyntaxTests(unittest.TestCase):

    def tearDown(self) -> None:
        # Resets state of configs to match settings
        client_configs.update_configs()

    def test_has_no_matching_config(self) -> None:
        self.assertFalse(client_configs.is_syntax_supported('asdf'))

    def test_has_matching_config(self) -> None:
        client_configs.all.append(TEST_CONFIG)
        self.assertEqual(TEST_LANGUAGE.feature_selector, TEST_CONFIG.languages[0].feature_selector)
        self.assertTrue(client_configs.is_syntax_supported("Packages/Text/Plain text.tmLanguage"))
        client_configs.all.remove(TEST_CONFIG)

    def test_does_not_match_after_removing_config(self) -> None:
        client_configs.all.append(TEST_CONFIG)
        self.assertTrue(client_configs.is_syntax_supported("Packages/Text/Plain text.tmLanguage"))
        # Removes manually added config
        client_configs.update_configs()
        self.assertFalse(client_configs.is_syntax_supported("Packages/Text/Plain text.tmLanguage"))
