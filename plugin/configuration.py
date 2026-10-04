from __future__ import annotations

from .core.registry import windows
from .core.settings import client_configs
import sublime_aio


class LspEnableLanguageServerGloballyCommand(sublime_aio.WindowCommand):

    async def run(self) -> None:
        items = [config.name for config in client_configs.all.values() if not config.enabled]
        if not items:
            self.window.status_message("No config available to enable")
            return
        if (index := await self.window.show_quick_panel(items)) != -1:
            client_configs.enable(items[index])


class LspEnableLanguageServerInProjectCommand(sublime_aio.WindowCommand):

    async def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        items = [config.name for config in wm.get_config_manager().all.values() if not config.enabled]
        if not items:
            self.window.status_message("No config available to enable")
            return
        if (index := await self.window.show_quick_panel(items)) != -1:
            wm.enable_config_async(items[index])


class LspDisableLanguageServerGloballyCommand(sublime_aio.WindowCommand):

    async def run(self) -> None:
        if not windows.lookup(self.window):
            return
        items = [config.name for config in client_configs.all.values() if config.enabled]
        if not items:
            self.window.status_message("No config available to disable")
            return
        if (index := await self.window.show_quick_panel(items)) != -1:
            client_configs.disable(items[index])


class LspDisableLanguageServerInProjectCommand(sublime_aio.WindowCommand):

    async def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        items = [config.name for config in wm.get_config_manager().all.values() if config.enabled]
        if not items:
            self.window.status_message("No config available to disable")
            return
        if (index := await self.window.show_quick_panel(items)) != -1:
            wm.disable_config_async(items[index])
