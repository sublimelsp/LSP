import sublime
import sublime_plugin

from .core.settings import ClientConfig, client_configs
from .core.registry import windows

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
    assert ClientConfig
except ImportError:
    pass


def create_config_items(configs: 'List[ClientConfig]') -> 'List[List[str]]':
    return [[
        config.name, ", ".join(language.id
                               for language in config.languages)
    ] for config in configs]


class LspEnableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self._items = create_config_items([config for config in client_configs.all if not config.enabled])
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index][0]
            client_configs.enable(config_name)

            # start the server on the current window.
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.start_active_views(), 500)
            self.window.status_message("{} enabled, starting server...".format(config_name))


class LspEnableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        wm = windows.lookup(self.window)
        self._items = create_config_items([config for config in wm._configs.all if not config.enabled])
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index][0]
            wm = windows.lookup(self.window)
            wm.enable_config(config_name)


class LspDisableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self._items = create_config_items([config for config in client_configs.all if config.enabled])
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index][0]
            client_configs.disable(config_name)
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.end_config_sessions(config_name), 500)
            self.window.status_message("{} disabled, shutting down server...".format(config_name))


class LspDisableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        wm = windows.lookup(self.window)
        self._items = create_config_items([config for config in wm._configs.all if config.enabled])
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index][0]
            wm = windows.lookup(self.window)
            wm.disable_config(config_name)
