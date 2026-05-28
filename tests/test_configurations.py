from __future__ import annotations

from .test_mocks import DISABLED_CONFIG
from .test_mocks import TEST_CONFIG
from copy import deepcopy
from LSP.plugin import ClientConfig
from LSP.plugin.core.configurations import WindowConfigChangeListener
from LSP.plugin.core.configurations import WindowConfigManager
from unittest import TestCase
from unittest.mock import MagicMock
from unittesting import ViewTestCase
import sublime

PROJECT_TEST_CONFIG_NAME = 'test-project-config'
PROJECT_TEST_CONFIG = {
    'enabled': True,
    'command': [],
    'selector': 'plain.text'
}


class WindowConfigChangeTestListener(WindowConfigChangeListener):

    def on_configs_changed(self, configs: list[ClientConfig]) -> None:
        pass

    def on_server_settings_changed(self, configs: list[ClientConfig]) -> None:
        pass


class GlobalConfigManagerTests(TestCase):

    def test_empty_configs(self) -> None:
        window_mgr = WindowConfigManager(sublime.active_window(), {})
        self.assertNotIn(TEST_CONFIG.name, window_mgr.all)

    def test_global_config(self) -> None:
        window_mgr = WindowConfigManager(sublime.active_window(), {TEST_CONFIG.name: TEST_CONFIG})
        self.assertIn(TEST_CONFIG.name, window_mgr.all)

    def test_override_config(self) -> None:
        self.assertTrue(TEST_CONFIG.enabled)
        win = sublime.active_window()
        win.project_data = MagicMock(return_value={'settings': {'LSP': {TEST_CONFIG.name: {"enabled": False}}}})
        window_mgr = WindowConfigManager(win, {TEST_CONFIG.name: TEST_CONFIG})
        self.assertFalse(next(iter(window_mgr.all.values())).enabled)


class WindowConfigManagerTests(ViewTestCase):

    def test_no_configs(self) -> None:
        self.assertIsNotNone(self.view)
        self.assertIsNotNone(self.window)
        manager = WindowConfigManager(self.window, {})
        self.assertEqual(list(manager.match_view(self.view, [])), [])

    def test_with_single_config(self) -> None:
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
        self.assertEqual(list(manager.match_view(self.view, [])), [TEST_CONFIG])

    def test_applies_project_settings(self) -> None:
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
        configs = list(manager.match_view(self.view, []))
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(DISABLED_CONFIG.name, config.name)
        self.assertTrue(config.enabled)

    def test_disables_temporarily(self) -> None:
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
        self.assertFalse(any(manager.match_view(self.view, [])))

    def test_global_update(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        config = ClientConfig.from_config(TEST_CONFIG, {})
        global_configs = {config.name: config}
        manager = WindowConfigManager(self.window, global_configs)
        manager.add_change_listener(change_listener)
        manager.update()
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(config.name, manager.all)

    def test_global_config_not_changed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        manager = WindowConfigManager(self.window, {TEST_CONFIG.name: TEST_CONFIG})
        self.assertIn(TEST_CONFIG.name, manager.all)
        manager.add_change_listener(change_listener)
        manager.update(TEST_CONFIG.name)
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(TEST_CONFIG.name, manager.all)

    def test_global_config_settings_changed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        config = ClientConfig.from_config(TEST_CONFIG, {})
        manager = WindowConfigManager(self.window, {config.name: config})
        manager.add_change_listener(change_listener)
        config.settings.set('foo', 'bar')
        manager.update(config.name)
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_called_once_with([config])
        self.assertIn(config.name, manager.all)

    def test_global_config_root_changed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        config = ClientConfig.from_config(TEST_CONFIG, {})
        manager = WindowConfigManager(self.window, {config.name: config})
        manager.add_change_listener(change_listener)
        config.initialization_options.set('foo', 'bar')
        manager.update(config.name)
        change_listener.on_configs_changed.assert_called_once_with([config])
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(config.name, manager.all)

    def test_global_config_added(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        global_configs = {}
        manager = WindowConfigManager(self.window, global_configs)
        manager.add_change_listener(change_listener)
        global_configs[TEST_CONFIG.name] = TEST_CONFIG
        manager.update(TEST_CONFIG.name)
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(TEST_CONFIG.name, manager.all)

    def test_global_config_removed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        config = ClientConfig.from_config(TEST_CONFIG, {})
        global_configs = {config.name: config}
        manager = WindowConfigManager(self.window, global_configs)
        manager.add_change_listener(change_listener)
        global_configs.pop(config.name)
        manager.update()
        change_listener.on_configs_changed.assert_called_once_with([config])
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertNotIn(config.name, manager.all)

    def test_project_update(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        self.window.project_data = MagicMock(return_value={
            "settings": {
                "LSP": {
                    PROJECT_TEST_CONFIG_NAME: deepcopy(PROJECT_TEST_CONFIG)
                }
            }
        })
        manager = WindowConfigManager(self.window, {})
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)
        manager.add_change_listener(change_listener)
        manager.update()
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)

    def test_project_config_not_changed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        self.window.project_data = MagicMock(return_value={
            "settings": {
                "LSP": {
                    PROJECT_TEST_CONFIG_NAME: deepcopy(PROJECT_TEST_CONFIG)
                }
            }
        })
        manager = WindowConfigManager(self.window, {})
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)
        manager.add_change_listener(change_listener)
        manager.update(PROJECT_TEST_CONFIG_NAME)
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)

    def test_project_config_settings_changed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        config = deepcopy(PROJECT_TEST_CONFIG)
        self.window.project_data = MagicMock()
        self.window.project_data.return_value = {
            "settings": {
                "LSP": {
                    PROJECT_TEST_CONFIG_NAME: config
                }
            }
        }
        manager = WindowConfigManager(self.window, {})
        manager.add_change_listener(change_listener)
        config['settings'] = {'foo': 'bar'}
        manager.update(PROJECT_TEST_CONFIG_NAME)
        changed_config = manager.all[PROJECT_TEST_CONFIG_NAME]
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_called_once_with([changed_config])
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)

    def test_project_config_root_changed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        config = deepcopy(PROJECT_TEST_CONFIG)
        self.window.project_data = MagicMock()
        self.window.project_data.return_value = {
            "settings": {
                "LSP": {
                    PROJECT_TEST_CONFIG_NAME: config
                }
            }
        }
        manager = WindowConfigManager(self.window, {})
        manager.add_change_listener(change_listener)
        config['initialization_options'] = {'foo': 'bar'}
        manager.update(PROJECT_TEST_CONFIG_NAME)
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)
        change_listener.on_configs_changed.assert_called_once_with([manager.all[PROJECT_TEST_CONFIG_NAME]])
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)

    def test_project_config_added(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        manager = WindowConfigManager(self.window, {})
        manager.add_change_listener(change_listener)
        self.window.project_data = MagicMock()
        self.window.project_data.return_value = {
            "settings": {
                "LSP": {
                    PROJECT_TEST_CONFIG_NAME: PROJECT_TEST_CONFIG
                }
            }
        }
        manager.update()
        change_listener.on_configs_changed.assert_not_called()
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertIn(PROJECT_TEST_CONFIG_NAME, manager.all)

    def test_project_config_removed(self) -> None:
        change_listener = WindowConfigChangeTestListener()
        change_listener.on_configs_changed = MagicMock()
        change_listener.on_server_settings_changed = MagicMock()
        self.window.project_data = MagicMock()
        self.window.project_data.return_value = {
            "settings": {
                "LSP": {
                    PROJECT_TEST_CONFIG_NAME: PROJECT_TEST_CONFIG
                }
            }
        }
        manager = WindowConfigManager(self.window, {})
        manager.add_change_listener(change_listener)
        self.window.project_data.return_value = {}
        manager.update()
        removed_config = ClientConfig.from_dict(PROJECT_TEST_CONFIG_NAME, PROJECT_TEST_CONFIG)
        change_listener.on_configs_changed.assert_called_once_with([removed_config])
        change_listener.on_server_settings_changed.assert_not_called()
        self.assertNotIn(PROJECT_TEST_CONFIG_NAME, manager.all)
