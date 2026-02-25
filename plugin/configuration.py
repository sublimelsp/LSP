from __future__ import annotations

from .core.registry import windows
from .core.settings import client_configs
from .core.windows import WindowManager
from functools import partial
import sublime
import sublime_plugin


class LspEnableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        self._items = [config.name for config in client_configs.all.values() if not config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index: int) -> None:
        if index != -1:
            config_name = self._items[index]
            client_configs.enable(config_name)


class LspEnableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        self._items = [config.name for config in wm.get_config_manager().all.values() if not config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, partial(self._on_done, wm))
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, wm: WindowManager, index: int) -> None:
        if index == -1:
            return
        config_name = self._items[index]
        sublime.set_timeout_async(lambda: wm.enable_config_async(config_name))


class LspDisableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        self._items = [config.name for config in client_configs.all.values() if config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index: int) -> None:
        if index == -1:
            return
        config_name = self._items[index]
        client_configs.disable(config_name)


class LspDisableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        self._items = [config.name for config in wm.get_config_manager().all.values() if config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, partial(self._on_done, wm))
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, wm: WindowManager, index: int) -> None:
        if index == -1:
            return
        config_name = self._items[index]
        sublime.set_timeout_async(lambda: wm.disable_config_async(config_name))
