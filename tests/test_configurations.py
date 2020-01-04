from LSP.plugin.core.configurations import _merge_dicts
from LSP.plugin.core.configurations import ConfigManager
from LSP.plugin.core.configurations import is_supported_syntax
from LSP.plugin.core.configurations import WindowConfigManager
from test_mocks import MockView
from test_mocks import MockWindow
from test_mocks import TEST_CONFIG, DISABLED_CONFIG
from test_mocks import TEST_LANGUAGE
import unittest


class GlobalConfigManagerTests(unittest.TestCase):

    def test_empty_configs(self):
        manager = ConfigManager([])
        window_mgr = manager.for_window(MockWindow())
        self.assertEqual(window_mgr.all, [])

    def test_global_config(self):
        manager = ConfigManager([TEST_CONFIG])
        window_mgr = manager.for_window(MockWindow())
        self.assertEqual(window_mgr.all, [TEST_CONFIG])

    def test_override_config(self):
        manager = ConfigManager([TEST_CONFIG])
        self.assertTrue(TEST_CONFIG.enabled)
        win = MockWindow()
        win.set_project_data({'settings': {'LSP': {TEST_CONFIG.name: {"enabled": False}}}})
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
        view = MockView(__file__)
        manager = WindowConfigManager(MockWindow(), [])
        self.assertFalse(manager.is_supported(view))
        self.assertFalse(manager.syntax_supported(view))

    def test_with_single_config(self):
        view = MockView(__file__)
        manager = WindowConfigManager(MockWindow(), [TEST_CONFIG])
        self.assertTrue(manager.is_supported(view))
        self.assertEqual(list(manager.scope_configs(view)), [TEST_CONFIG])
        self.assertTrue(manager.syntax_supported(view))
        self.assertEqual(manager.syntax_configs(view), [TEST_CONFIG])
        lang_configs = manager.syntax_config_languages(view)
        self.assertEqual(len(lang_configs), 1)
        self.assertEqual(lang_configs[TEST_CONFIG.name].id, TEST_CONFIG.languages[0].id)

    def test_applies_project_settings(self):
        view = MockView(__file__)
        window = MockWindow()
        window.set_project_data({
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
        configs = manager.syntax_configs(view)

        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(DISABLED_CONFIG.name, config.name)
        self.assertTrue(config.enabled)

    def test_disables_temporarily(self):
        view = MockView(__file__)
        window = MockWindow()
        window.set_project_data({
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
        self.assertEqual([], manager.syntax_configs(view))


class IsSupportedSyntaxTests(unittest.TestCase):

    def test_no_configs(self):
        self.assertFalse(is_supported_syntax('asdf', []))

    def test_single_config(self):
        self.assertEqual(TEST_LANGUAGE.syntaxes[0], TEST_CONFIG.languages[0].syntaxes[0])
        self.assertTrue(is_supported_syntax(TEST_LANGUAGE.syntaxes[0], [TEST_CONFIG]))
