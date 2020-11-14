import sublime
import sublime_plugin
from .core.registry import windows
from .core.settings import client_configs


class LspEnableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self._items = [config.name for config in client_configs.all.values() if not config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index]
            client_configs.enable(config_name)


class LspEnableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        wm = windows.lookup(self.window)
        self._items = [config.name for config in wm._configs.all.values() if not config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index]
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.enable_config_async(config_name))


class LspDisableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        self._items = [config.name for config in client_configs.all.values() if config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index]
            client_configs.disable(config_name)
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.end_config_sessions_async(config_name))


class LspDisableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        wm = windows.lookup(self.window)
        self._items = [config.name for config in wm._configs.all.values() if config.enabled]
        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index: int) -> None:
        if index > -1:
            config_name = self._items[index]
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.disable_config_async(config_name))
