from LSP.plugin.core.configurations import _merge_dicts
from LSP.plugin.core.configurations import ConfigManager
from LSP.plugin.core.configurations import is_supported_syntax
from LSP.plugin.core.configurations import WindowConfigManager
import sublime
import unittest
from unittest.mock import MagicMock
from test_mocks import DISABLED_CONFIG
from test_mocks import TEST_CONFIG
from test_mocks import TEST_LANGUAGE


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


class MergeDictsTests(unittest.TestCase):

    def test_preserves_against_empty(self):

        # merge against one empty dict
        self.assertEqual(_merge_dicts({'a': 1}, {}), {'a': 1})
        self.assertEqual(_merge_dicts({}, {'a': 1}), {'a': 1})

        # first-level collision
        self.assertEqual(_merge_dicts({'a': 2}, {'a': 1}), {'a': 1})

        # replace number value with dict
        self.assertEqual(_merge_dicts({'a': 2}, {'a': {'b': 4}}), {'a': {'b': 4}})

        # update existing child dict.
        self.assertEqual(_merge_dicts({'a': {'b': 2, 'c': 3}}, {'a': {'b': 4}}), {'a': {'b': 4, 'c': 3}})


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

    def test_no_configs(self):
        self.assertFalse(is_supported_syntax('asdf', []))

    def test_single_config(self):
        self.assertEqual(TEST_LANGUAGE.feature_selector, TEST_CONFIG.languages[0].feature_selector)
        self.assertTrue(is_supported_syntax("Packages/Text/Plain text.tmLanguage", [TEST_CONFIG]))
