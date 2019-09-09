import mdpopups
import sublime
import sublime_plugin
import webbrowser

from .core.settings import ClientConfig, client_configs
from .core.configurations import (
    create_window_configs,
    get_global_client_config
)
from .core.registry import configs_for_scope, windows
from .core.events import global_events
from .core.workspace import enable_in_project, disable_in_project

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
except ImportError:
    pass


# todo: delete this feature
def detect_supportable_view(view: sublime.View):
    config = configs_for_scope(view)
    if not config:
        available_config = get_global_client_config(view, client_configs.all)
        if available_config:
            show_enable_config(view, available_config)


global_events.subscribe("view.on_load_async", detect_supportable_view)
global_events.subscribe("view.on_activated_async", detect_supportable_view)


def extract_syntax_name(syntax_file: str) -> str:
    return syntax_file.split('/')[-1].split('.')[0]


def show_enable_config(view: sublime.View, config: ClientConfig):
    syntax = str(view.settings().get("syntax", ""))
    message = "LSP has found a language server for {}. Run \"Setup Language Server\" to start using it".format(
        extract_syntax_name(syntax)
    )
    window = view.window()
    if window:
        window.status_message(message)


class LspEnableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self):
        self._items = []  # type: List[List[str]]
        for config in client_configs.all:
            if not config.enabled:
                self._items.append([
                    config.name,
                    ", ".join(language.id for language in config.languages)
                ])

        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index):
        if index > -1:
            config_name = self._items[index][0]

            # too much work
            client_configs.enable(config_name)
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.start_active_views(), 500)
            self.window.status_message("{} enabled, starting server...".format(config_name))


class LspEnableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self):
        self._items = []  # type: List[List[str]]
        wm = windows.lookup(self.window)
        for config in wm._configs.all:
            # should also check if enabled here.
            if not config.enabled:
                self._items.append([
                    config.name,
                    ", ".join(language.id for language in config.languages)
                ])

        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to enable")

    def _on_done(self, index):
        if index > -1:
            config_name = self._items[index][0]
            wm = windows.lookup(self.window)
            enable_in_project(self.window, config_name)
            wm.update_configs(create_window_configs(self.window, client_configs.all))
            sublime.set_timeout_async(lambda: wm.start_active_views(), 500)
            self.window.status_message("{} enabled, starting server...".format(config_name))


class LspDisableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self):
        self._items = []  # type: List[List[str]]
        for config in client_configs.all:
            if config.enabled:
                self._items.append([
                    config.name,
                    ", ".join(language.id for language in config.languages)
                ])

        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index):
        if index > -1:
            config_name = self._items[index][0]
            client_configs.disable(config_name)
            wm = windows.lookup(self.window)
            sublime.set_timeout_async(lambda: wm.end_session(config_name), 500)
            self.window.status_message("{} disabled, shutting down server...".format(config_name))


class LspDisableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self):
        wm = windows.lookup(self.window)
        self._items = []  # type: List[List[str]]
        for config in wm._configs.all:
            if config.enabled:
                self._items.append([
                    config.name,
                    ", ".join(language.id for language in config.languages)
                ])

        if len(self._items) > 0:
            self.window.show_quick_panel(self._items, self._on_done)
        else:
            self.window.status_message("No config available to disable")

    def _on_done(self, index):
        if index > -1:
            config_name = self._items[index][0]
            wm = windows.lookup(self.window)
            disable_in_project(self.window, config_name)
            wm.update_configs(create_window_configs(self.window, client_configs.all))
            wm.end_session(config_name)


supported_syntax_template = '''
Installation steps:

* Open the [LSP documentation](https://lsp.readthedocs.io)
* Read the instructions for {}
* Install the language server on your system
* Choose an option below to start the server

Enable: [Globally](#enable_globally) | [This Project Only](#enable_project)
'''

unsupported_syntax_template = """
*LSP has no built-in configuration for a {} language server*

Visit [langserver.org](https://langserver.org) to find out if a language server exists for this language."""


class LspSetupLanguageServerCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        syntax = view.settings().get("syntax")
        available_config = get_global_client_config(view, client_configs.all)

        syntax_name = extract_syntax_name(syntax)
        title = "# Language Server for {}\n".format(syntax_name)

        if available_config:
            content = supported_syntax_template.format(syntax_name)
        else:
            title = "# No Language Server support"
            content = unsupported_syntax_template.format(syntax_name)

        mdpopups.show_popup(
            view,
            "\n".join([title, content]),
            css='''
                .lsp_documentation {
                    margin: 1rem 1rem 0.5rem 1rem;
                    font-family: system;
                }
                .lsp_documentation h1,
                .lsp_documentation p {
                    margin: 0 0 0.5rem 0;
                }
            ''',
            md=True,
            wrapper_class="lsp_documentation",
            max_width=800,
            max_height=600,
            on_navigate=self.on_hover_navigate
        )

    def on_hover_navigate(self, href):
        if href == "#enable_globally":
            self.window.run_command("lsp_enable_language_server_globally")
        elif href == "#enable_project":
            self.window.run_command("lsp_enable_language_server_in_project")
        else:
            webbrowser.open_new_tab(href)
