from __future__ import annotations

from .core.aio import show_quick_panel
from .core.registry import LspWindowCommand
from .core.settings import client_configs


class LspEnableLanguageServerGloballyCommand(LspWindowCommand):

    async def run(self) -> None:
        items = [config.name for config in client_configs.all.values() if not config.enabled]
        if not items:
            self.window.status_message("No config available to enable")
            return
        if (index := await show_quick_panel(self.window, items)) != -1:
            client_configs.enable(items[index])


class LspEnableLanguageServerInProjectCommand(LspWindowCommand):

    async def run(self) -> None:
        wm = self.manager()
        if not wm:
            return
        items = [config.name for config in wm.get_config_manager().all.values() if not config.enabled]
        if not items:
            self.window.status_message("No config available to enable")
            return
        if (index := await show_quick_panel(self.window, items)) != -1:
            wm.enable_config_async(items[index])


class LspDisableLanguageServerGloballyCommand(LspWindowCommand):

    async def run(self) -> None:
        items = [config.name for config in client_configs.all.values() if config.enabled]
        if not items:
            self.window.status_message("No config available to disable")
            return
        if (index := await show_quick_panel(self.window, items)) != -1:
            client_configs.disable(items[index])


class LspDisableLanguageServerInProjectCommand(LspWindowCommand):

    async def run(self) -> None:
        wm = self.manager()
        if not wm:
            return
        items = [config.name for config in wm.get_config_manager().all.values() if config.enabled]
        if not items:
            self.window.status_message("No config available to disable")
            return
        if (index := await show_quick_panel(self.window, items)) != -1:
            wm.disable_config_async(items[index])
