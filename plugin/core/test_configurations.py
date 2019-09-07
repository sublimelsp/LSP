import unittest
from .configurations import WindowConfigManager, _merge_dicts, ConfigManager, is_supported_syntax
from .test_session import test_config, test_language
from .test_windows import MockView, MockWindow


class GlobalConfigManagerTests(unittest.TestCase):

    def test_empty_configs(self):
        manager = ConfigManager([])
        window_mgr = manager.for_window(MockWindow())
        self.assertEqual(window_mgr.all, [])

    def test_global_config(self):
        manager = ConfigManager([test_config])
        window_mgr = manager.for_window(MockWindow())
        self.assertEqual(window_mgr.all, [test_config])

    def test_override_config(self):
        manager = ConfigManager([test_config])
        self.assertTrue(test_config.enabled)
        win = MockWindow()
        win.set_project_data({'settings': {'LSP': {test_config.name: {"enabled": False}}}})
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
        manager = WindowConfigManager([])
        self.assertFalse(manager.is_supported(view))
        self.assertFalse(manager.syntax_supported(view))

    def test_with_single_config(self):
        view = MockView(__file__)
        manager = WindowConfigManager([test_config])
        self.assertTrue(manager.is_supported(view))
        self.assertEqual(list(manager.scope_configs(view)), [test_config])
        self.assertTrue(manager.syntax_supported(view))
        self.assertEqual(manager.syntax_configs(view), [test_config])
        lang_configs = manager.syntax_config_languages(view)
        self.assertEqual(len(lang_configs), 1)
        self.assertEqual(lang_configs[test_config.name].id, test_config.languages[0].id)


class IsSupportedSyntaxTests(unittest.TestCase):

    def test_no_configs(self):
        self.assertFalse(is_supported_syntax('asdf', []))

    def test_single_config(self):
        self.assertEqual(test_language.syntaxes[0], test_config.languages[0].syntaxes[0])
        self.assertTrue(is_supported_syntax(test_language.syntaxes[0], [test_config]))
