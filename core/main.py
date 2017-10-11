import os
import subprocess
import webbrowser

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

import sublime_plugin
import sublime

import mdpopups

from .url import filename_to_uri, uri_to_filename
from .protocol import (
    Request, Notification, Point, Range, SymbolKind
)
from .settings import (
    ClientConfig, settings, client_configs, load_settings, unload_settings, PLUGIN_NAME
)
from .logging import debug, exception_log, server_log
from .rpc import Client
from .workspace import get_project_path, enable_in_project, disable_in_project
from .configurations import (
    config_for_scope, is_supported_view, is_supported_syntax, is_supportable_syntax, get_default_client_config,
    clear_window_client_configs, get_scope_client_config
)
from .clients import (
    client_for_view, add_window_client, window_clients, check_window_unloaded, unload_old_clients,
    unload_window_clients, unload_all_clients
)
from .events import Events
from .documents import purge_did_change, get_document_position, initialize_document_sync, notify_did_open
from .diagnostics import handle_diagnostics, remove_diagnostics, get_line_diagnostics, get_point_diagnostics
from .panels import create_output_panel


SUBLIME_WORD_MASK = 515
NO_HOVER_SCOPES = 'comment, constant, keyword, storage, string'


symbol_kind_names = {
    SymbolKind.File: "file",
    SymbolKind.Module: "module",
    SymbolKind.Namespace: "namespace",
    SymbolKind.Package: "package",
    SymbolKind.Class: "class",
    SymbolKind.Method: "method",
    SymbolKind.Function: "function",
    SymbolKind.Field: "field",
    SymbolKind.Variable: "variable",
    SymbolKind.Constant: "constant"
}


def plugin_loaded():
    load_settings()
    Events.subscribe("view.on_load_async", initialize_on_open)
    Events.subscribe("view.on_activated_async", initialize_on_open)
    if settings.show_status_messages:
        sublime.status_message("LSP initialized")
    start_active_view()


def plugin_unloaded():
    unload_settings()
    unload_all_clients()


def start_active_view():
    window = sublime.active_window()
    if window:
        view = window.active_view()
        debug('starting initial view', view.file_name())
        if view and is_supported_view(view):
            initialize_on_open(view)
        else:
            debug('view not supported')


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2

didopen_after_initialize = list()
unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


def initialize_on_open(view: sublime.View):
    window = view.window()

    if not window:
        return

    if window_clients(window):
        unload_old_clients(window)

    global didopen_after_initialize
    config = config_for_scope(view)
    if config:
        if config.enabled:
            if config.name not in window_clients(window):
                didopen_after_initialize.append(view)
                get_window_client(view, window, config)
        else:
            debug(config.name, 'is not enabled')
    else:
        available_config = get_default_client_config(view)
        if available_config:
            show_enable_config(view, available_config)


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
        view = self.window.active_view()
        available_config = get_scope_client_config(view, client_configs.defaults) or get_default_client_config(view)
        if available_config:
            client_configs.enable(available_config.name)
            clear_window_client_configs(self.window)
            sublime.set_timeout_async(start_active_view, 500)
            self.window.status_message("{} enabled, starting server...".format(available_config.name))
            return

        self.window.status_message("No config available to enable")


class LspEnableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()

        # if no default_config, nothing we can do.
        default_config = get_default_client_config(view)
        if default_config:
            enable_in_project(self.window, default_config.name)
            clear_window_client_configs(self.window)
            sublime.set_timeout_async(start_active_view, 500)
            self.window.status_message("{} enabled in project, starting server...".format(default_config.name))
        else:
            self.window.status_message("No config available to enable")


class LspDisableLanguageServerGloballyCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        global_config = get_scope_client_config(view, client_configs.all)
        if global_config:
            client_configs.disable(global_config.name)
            clear_window_client_configs(self.window)
            sublime.set_timeout_async(lambda: unload_window_clients(self.window.id()), 500)
            self.window.status_message("{} disabled, shutting down server...".format(global_config.name))
            return

        self.window.status_message("No config available to disable")


class LspDisableLanguageServerInProjectCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        global_config = get_scope_client_config(view, client_configs.defaults)
        if global_config:
            disable_in_project(self.window, global_config.name)
            clear_window_client_configs(self.window)
            sublime.set_timeout_async(lambda: unload_window_clients(self.window.id()), 500)
            self.window.status_message("{} disabled in project, shutting down server...".format(global_config.name))
            return
        else:
            self.window.status_message("No config available to disable")


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


setup_css = ".mdpopups .lsp_documentation { margin: 20px; font-family: sans-serif; font-size: 1.2rem; line-height: 2}"


class LspSetupLanguageServerCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        syntax = view.settings().get("syntax")
        available_config = get_default_client_config(view)

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
            css=setup_css,
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


def handle_initialize_result(result, client, window, config):
    global didopen_after_initialize
    capabilities = result.get("capabilities")
    client.set_capabilities(capabilities)

    # handle server requests and notifications
    client.on_request(
        "workspace/applyEdit",
        lambda params: apply_workspace_edit(sublime.active_window(), params))

    client.on_notification(
        "textDocument/publishDiagnostics",
        lambda params: handle_diagnostics(params))
    client.on_notification(
        "window/showMessage",
        lambda params: sublime.active_window().message_dialog(params.get("message")))
    if settings.log_server:
        client.on_notification(
            "window/logMessage",
            lambda params: server_log(params.get("message")))

    # TODO: These handlers is already filtered by syntax but does not need to
    # be enabled 2x per client
    # Move filtering?
    document_sync = capabilities.get("textDocumentSync")
    if document_sync:
        initialize_document_sync(document_sync)

    Events.subscribe('view.on_close', remove_diagnostics)

    client.send_notification(Notification.initialized())
    if config.settings:
        configParams = {
            'settings': config.settings
        }
        client.send_notification(Notification.didChangeConfiguration(configParams))

    for view in didopen_after_initialize:
        notify_did_open(view)
    if settings.show_status_messages:
        window.status_message("{} initialized".format(config.name))
    didopen_after_initialize = list()


class LspSymbolRenameCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        # TODO: check what kind of scope we're in.
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('renameProvider'):
                return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
        pos = get_position(self.view, event)
        params = get_document_position(self.view, pos)
        current_name = self.view.substr(self.view.word(pos))
        if not current_name:
            current_name = ""
        self.view.window().show_input_panel(
            "New name:", current_name, lambda text: self.request_rename(params, text),
            None, None)

    def request_rename(self, params, new_name):
        client = client_for_view(self.view)
        if client:
            params["newName"] = new_name
            client.send_request(Request.rename(params), self.handle_response)

    def handle_response(self, response):
        if 'changes' in response:
            changes = response.get('changes')
            if len(changes) > 0:
                self.view.window().run_command('lsp_apply_workspace_edit',
                                               {'changes': response})

    def want_event(self):
        return True


class LspFormatDocumentCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('documentFormattingProvider'):
                return True
        return False

    def run(self, edit):
        client = client_for_view(self.view)
        if client:
            pos = self.view.sel()[0].begin()
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "options": {
                    "tabSize": 4,  # TODO: Fetch these from the project settings / global settings
                    "insertSpaces": True
                }
            }
            request = Request.formatting(params)
            client.send_request(
                request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        self.view.run_command('lsp_apply_document_edit',
                              {'changes': response})


class LspFormatDocumentRangeCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('documentRangeFormattingProvider'):
                if len(self.view.sel()) == 1:
                    region = self.view.sel()[0]
                    if region.begin() != region.end():
                        return True
        return False

    def run(self, _):
        client = client_for_view(self.view)
        if client:
            region = self.view.sel()[0]
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "range": Range.from_region(self.view, region).to_lsp(),
                "options": {
                    "tabSize": 4,  # TODO: Fetch these from the project settings / global settings
                    "insertSpaces": True
                }
            }
            client.send_request(Request.rangeFormatting(params),
                                lambda response: self.view.run_command('lsp_apply_document_edit',
                                                                       {'changes': response}))


class LspSymbolDefinitionCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        # TODO: check what kind of scope we're in.
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('definitionProvider'):
                return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
        client = client_for_view(self.view)
        if client:
            pos = get_position(self.view, event)
            document_position = get_document_position(self.view, pos)
            if document_position:
                request = Request.definition(document_position)
                client.send_request(
                    request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, position):
        window = sublime.active_window()
        if response:
            location = response if isinstance(response, dict) else response[0]
            file_path = uri_to_filename(location.get("uri"))
            start = Point.from_lsp(location['range']['start'])
            file_location = "{}:{}:{}".format(file_path, start.row + 1, start.col + 1)
            debug("opening location", location)
            window.open_file(file_location, sublime.ENCODED_POSITION)
            # TODO: can add region here.
        else:
            window.run_command("goto_definition")

    def want_event(self):
        return True


def format_symbol_kind(kind):
    return symbol_kind_names.get(kind, str(kind))


def format_symbol(item):
    """
    items may be a list of strings, or a list of string lists.
    In the latter case, each entry in the quick panel will show multiple rows
    """
    # file_path = uri_to_filename(location.get("uri"))
    # kind = format_symbol_kind(item.get("kind"))
    # return [item.get("name"), kind]
    return [item.get("name")]


class LspDocumentSymbolsCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('documentSymbolProvider'):
                return True
        return False

    def run(self, edit):
        client = client_for_view(self.view)
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                }
            }
            request = Request.documentSymbols(params)
            client.send_request(request, self.handle_response)

    def handle_response(self, response):
        symbols = list(format_symbol(item) for item in response)
        self.symbols = response
        self.view.window().show_quick_panel(symbols, self.on_symbol_selected)

    def on_symbol_selected(self, symbol_index):
        selected_symbol = self.symbols[symbol_index]
        range = selected_symbol['location']['range']
        region = Range.from_lsp(range).to_region(self.view)
        self.view.show_at_center(region)
        self.view.sel().clear()
        self.view.sel().add(region)


def get_position(view: sublime.View, event=None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


def is_at_word(view: sublime.View, event) -> bool:
    pos = get_position(view, event)
    point_classification = view.classify(pos)
    if point_classification & SUBLIME_WORD_MASK:
        return True
    else:
        return False


def ensure_references_panel(window: sublime.Window):
    return window.find_output_panel("references") or create_references_panel(window)


def create_references_panel(window: sublime.Window):
    panel = create_output_panel(window, "references")
    panel.settings().set("result_file_regex",
                         r"^\s+\S\s+(\S.+)\s+(\d+):?(\d+)$")
    panel.assign_syntax("Packages/" + PLUGIN_NAME +
                        "/Syntaxes/References.sublime-syntax")
    # Call create_output_panel a second time after assigning the above
    # settings, so that it'll be picked up as a result buffer
    # see: Packages/Default/exec.py#L228-L230
    panel = window.create_output_panel("references")
    return panel


class LspSymbolReferencesCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('referencesProvider'):
                return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
        client = client_for_view(self.view)
        if client:
            pos = get_position(self.view, event)
            document_position = get_document_position(self.view, pos)
            if document_position:
                document_position['context'] = {
                    "includeDeclaration": False
                }
                request = Request.references(document_position)
                client.send_request(
                    request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        window = self.view.window()
        word = self.view.substr(self.view.word(pos))
        base_dir = get_project_path(window)
        file_path = self.view.file_name()
        relative_file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path

        references = list(format_reference(item, base_dir) for item in response)

        if (len(references)) > 0:
            panel = ensure_references_panel(window)
            panel.settings().set("result_base_dir", base_dir)
            panel.set_read_only(False)
            panel.run_command("lsp_clear_panel")
            panel.run_command('append', {
                'characters': 'References to "' + word + '" at ' + relative_file_path + ':\n'
            })
            window.run_command("show_panel", {"panel": "output.references"})
            for reference in references:
                panel.run_command('append', {
                    'characters': reference + "\n",
                    'force': True,
                    'scroll_to_end': True
                })
            panel.set_read_only(True)

        else:
            window.run_command("hide_panel", {"panel": "output.references"})
            window.status_message("No references found")

    def want_event(self):
        return True


def format_reference(reference, base_dir):
    start = Point.from_lsp(reference.get('range').get('start'))
    file_path = uri_to_filename(reference.get("uri"))
    relative_file_path = os.path.relpath(file_path, base_dir)
    return " ◌ {} {}:{}".format(relative_file_path, start.row + 1, start.col + 1)


class LspClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """

    def run(self, edit):
        self.view.erase(edit, sublime.Region(0, self.view.size()))


class LspUpdatePanelCommand(sublime_plugin.TextCommand):
    """
    A update_panel command to update the error panel with new text.
    """

    def run(self, edit, characters):
        self.view.replace(edit, sublime.Region(0, self.view.size()), characters)

        # Move cursor to the end
        selection = self.view.sel()
        selection.clear()
        selection.add(sublime.Region(self.view.size(), self.view.size()))


def start_client(window: sublime.Window, config: ClientConfig):
    project_path = get_project_path(window)
    if project_path is None:
        return None

    if settings.show_status_messages:
        window.status_message("Starting " + config.name + "...")
    debug("starting in", project_path)

    # Create a dictionary of Sublime Text variables
    variables = window.extract_variables()

    # Expand language server command line environment variables
    expanded_args = list(
        sublime.expand_variables(os.path.expanduser(arg), variables)
        for arg in config.binary_args
    )

    # Override OS environment variables
    env = os.environ.copy()
    for var, value in config.env.items():
        # Expand both ST and OS environment variables
        env[var] = os.path.expandvars(sublime.expand_variables(value, variables))

    client = start_server(expanded_args, project_path, env)
    if not client:
        window.status_message("Could not start " + config.name + ", disabling")
        debug("Could not start", config.binary_args, ", disabling")
        return None

    initializeParams = {
        "processId": client.process.pid,
        "rootUri": filename_to_uri(project_path),
        "rootPath": project_path,
        "capabilities": {
            "textDocument": {
                "completion": {
                    "completionItem": {
                        "snippetSupport": True
                    }
                },
                "synchronization": {
                    "didSave": True
                }
            },
            "workspace": {
                "applyEdit": True
            }
        }
    }
    if config.init_options:
        initializeParams['initializationOptions'] = config.init_options

    client.send_request(
        Request.initialize(initializeParams),
        lambda result: handle_initialize_result(result, client, window, config))
    return client


def get_window_client(view: sublime.View, window: sublime.Window, config: ClientConfig) -> Client:

    clients = window_clients(window)
    if config.name not in clients:
        client = start_client(window, config)
        add_window_client(window, config.name, client)
    else:
        client = clients[config.name]

    return client


def start_server(server_binary_args, working_dir, env):
    debug("starting " + str(server_binary_args))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()  # type: ignore
        si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
    try:
        process = subprocess.Popen(
            server_binary_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_dir,
            env=env,
            startupinfo=si)
        return Client(process, working_dir)

    except Exception as err:
        sublime.status_message("Failed to start LSP server {}".format(str(server_binary_args)))
        exception_log("Failed to start server", err)


class HoverHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def on_hover(self, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT or self.view.is_popup_visible():
            return
        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            self.show_diagnostics_hover(point, point_diagnostics)
        else:
            self.request_symbol_hover(point)

    def request_symbol_hover(self, point):
        if self.view.match_selector(point, NO_HOVER_SCOPES):
            return
        client = client_for_view(self.view)
        if client and client.has_capability('hoverProvider'):
            word_at_sel = self.view.classify(point)
            if word_at_sel & SUBLIME_WORD_MASK:
                document_position = get_document_position(self.view, point)
                if document_position:
                    client.send_request(
                        Request.hover(document_position),
                        lambda response: self.handle_response(response, point))

    def handle_response(self, response, point):
        debug(response)
        if self.view.is_popup_visible():
            return
        contents = "No description available."
        if isinstance(response, dict):
            # Flow returns None sometimes
            # See: https://github.com/flowtype/flow-language-server/issues/51
            contents = response.get('contents') or contents
        self.show_hover(point, contents)

    def show_diagnostics_hover(self, point, diagnostics):
        formatted = list("{}: {}".format(diagnostic.source, diagnostic.message) for diagnostic in diagnostics)
        formatted.append("[{}]({})".format('Code Actions', 'code-actions'))
        mdpopups.show_popup(
            self.view,
            "\n".join(formatted),
            css=".mdpopups .lsp_hover { margin: 4px; }",
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class="lsp_hover",
            max_width=800,
            on_navigate=lambda href: self.on_diagnostics_navigate(href, point, diagnostics))

    def on_diagnostics_navigate(self, href, point, diagnostics):
        # TODO: don't mess with the user's cursor.
        # Instead, pass code actions requested from phantoms & hovers should call lsp_code_actions with
        # diagnostics as args, positioning resulting UI close to the clicked link.
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command("lsp_code_actions")

    def show_hover(self, point, contents):
        formatted = []
        if not isinstance(contents, list):
            contents = [contents]

        for item in contents:
            value = ""
            language = None
            if isinstance(item, str):
                value = item
            else:
                value = item.get("value")
                language = item.get("language")
            if language:
                formatted.append("```{}\n{}\n```".format(language, value))
            else:
                formatted.append(value)

        mdpopups.show_popup(
            self.view,
            preserve_whitespace("\n".join(formatted)),
            css=".mdpopups .lsp_hover { margin: 4px; } .mdpopups p { margin: 0.1rem; }",
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class="lsp_hover",
            max_width=800)


def preserve_whitespace(contents: str) -> str:
    """Preserve empty lines and whitespace for markdown conversion."""
    contents = contents.strip(' \t\r\n')
    contents = contents.replace('\t', '&nbsp;' * 4)
    contents = contents.replace('  ', '&nbsp;' * 2)
    contents = contents.replace('\n\n', '\n&nbsp;\n')
    return contents


class SignatureHelpListener(sublime_plugin.ViewEventListener):

    css = ".mdpopups .lsp_signature { margin: 4px; } .mdpopups p { margin: 0.1rem; }"
    wrapper_class = "lsp_signature"

    def __init__(self, view):
        self.view = view
        self._initialized = False
        self._signature_help_triggers = []  # type: List[str]
        self._visible = False
        self._language_id = ""
        self._signatures = []  # type: List[Any]
        self._active_signature = -1

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def initialize(self):
        client = client_for_view(self.view)
        if client:
            signatureHelpProvider = client.get_capability(
                'signatureHelpProvider')
            if signatureHelpProvider:
                self.signature_help_triggers = signatureHelpProvider.get(
                    'triggerCharacters')

        config = config_for_scope(self.view)
        if config:
            self._language_id = config.languageId

        self._initialized = True

    def on_modified_async(self):
        pos = self.view.sel()[0].begin()
        last_char = self.view.substr(pos - 1)
        # TODO: this will fire too often, narrow down using scopes or regex
        if not self._initialized:
            self.initialize()

        if self.signature_help_triggers:
            if last_char in self.signature_help_triggers:
                client = client_for_view(self.view)
                if client:
                    purge_did_change(self.view.buffer_id())
                    document_position = get_document_position(self.view, pos)
                    if document_position:
                        client.send_request(
                            Request.signatureHelp(document_position),
                            lambda response: self.handle_response(response, pos))
            else:
                # TODO: this hides too soon.
                if self._visible:
                    self.view.hide_popup()

    def handle_response(self, response, point):
        if response is not None:
            self._signatures = response.get("signatures", [])
            self._active_signature = response.get("activeSignature", -1)

            if self._signatures:
                if not 0 <= self._active_signature < len(self._signatures):
                    debug("activeSignature {} not a valid index for signatures length {}".format(
                        self._active_signature, len(self._signatures)))
                    self._active_signature = 0
            else:
                if self._active_signature != -1:
                    debug("activeSignature should be -1 or null when no signatures are returned")
                    self._active_signature = -1

            if len(self._signatures) > 0:
                mdpopups.show_popup(self.view,
                                    self._build_popup_content(),
                                    css=self.__class__.css,
                                    md=True,
                                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                                    location=point,
                                    wrapper_class=self.__class__.wrapper_class,
                                    max_width=800,
                                    on_hide=self._on_hide)
                self._visible = True

    def on_query_context(self, key, _, operand, __):
        if key != "lsp.signature_help":
            return False  # Let someone else handle this keybinding.
        elif not self._visible:
            return False  # Let someone else handle this keybinding.
        elif len(self._signatures) < 2:
            return False  # Let someone else handle this keybinding.
        else:
            # We use the "operand" for the number -1 or +1. See the keybindings.
            new_index = self._active_signature + operand

            # clamp signature index
            new_index = max(0, min(new_index, len(self._signatures) - 1))

            # only update when changed
            if new_index != self._active_signature:
                self._active_signature = new_index
                mdpopups.update_popup(self.view,
                                      self._build_popup_content(),
                                      css=self.__class__.css,
                                      md=True,
                                      wrapper_class=self.__class__.wrapper_class)

            return True  # We handled this keybinding.

    def _on_hide(self):
        self._visible = False

    def _build_popup_content(self) -> str:
        signature = self._signatures[self._active_signature]
        formatted = []

        if len(self._signatures) > 1:
            signature_navigation = "**{}** of **{}** overloads (use the arrow keys to navigate):\n".format(
                str(self._active_signature + 1), str(len(self._signatures)))
            formatted.append(signature_navigation)

        label = "```{}\n{}\n```".format(self._language_id, signature.get('label'))
        formatted.append(label)

        params = signature.get('parameters')
        if params:
            for parameter in params:
                paramDocs = parameter.get('documentation', None)
                if paramDocs:
                    formatted.append("**{}**\n".format(parameter.get('label')))
                    formatted.append("* *{}*\n".format(paramDocs))
        sigDocs = signature.get('documentation', None)
        if sigDocs:
            formatted.append(sigDocs)
        return preserve_whitespace("\n".join(formatted))


class LspCodeActionsCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('codeActionProvider'):
                return True
        return False

    def run(self, edit, event=None):
        client = client_for_view(self.view)
        if client:
            pos = get_position(self.view, event)
            row, col = self.view.rowcol(pos)
            line_diagnostics = get_line_diagnostics(self.view, pos)
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "context": {
                    "diagnostics": list(diagnostic.to_lsp() for diagnostic in line_diagnostics)
                }
            }
            if len(line_diagnostics) > 0:
                # TODO: merge ranges.
                params["range"] = line_diagnostics[0].range.to_lsp()
            else:
                params["range"] = Range(Point(row, col), Point(row, col)).to_lsp()

            if event:  # if right-clicked, set cursor to menu position
                sel = self.view.sel()
                sel.clear()
                sel.add(sublime.Region(pos))

            client.send_request(Request.codeAction(params), self.handle_codeaction_response)

    def handle_codeaction_response(self, response):
        titles = []
        self.commands = response
        for command in self.commands:
            titles.append(
                command.get('title'))  # TODO parse command and arguments
        if len(self.commands) > 0:
            self.view.show_popup_menu(titles, self.handle_select)
        else:
            self.view.show_popup('No actions available', sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def handle_select(self, index):
        if index > -1:
            client = client_for_view(self.view)
            if client:
                client.send_request(
                    Request.executeCommand(self.commands[index]),
                    self.handle_command_response)

    def handle_command_response(self, response):
        pass

    def want_event(self):
        return True


def apply_workspace_edit(window, params):
    edit = params.get('edit')
    window.run_command('lsp_apply_workspace_edit', {'changes': edit})


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        window = self.view.window()
        unload_window_clients(window.id())


class LspApplyWorkspaceEditCommand(sublime_plugin.WindowCommand):
    def run(self, changes):
        debug('workspace edit', changes)
        if changes.get('changes'):
            for uri, file_changes in changes.get('changes').items():
                path = uri_to_filename(uri)
                view = self.window.open_file(path)
                if view:
                    if view.is_loading():
                        # TODO: wait for event instead.
                        sublime.set_timeout_async(
                            lambda: view.run_command('lsp_apply_document_edit', {'changes': file_changes}),
                            500
                        )
                    else:
                        view.run_command('lsp_apply_document_edit',
                                         {'changes': file_changes})
                else:
                    debug('view not found to apply', path, file_changes)


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):
    def run(self, edit, changes):
        regions = list(self.create_region(change) for change in changes)
        replacements = list(change.get('newText') for change in changes)

        self.view.add_regions('lsp_edit', regions, "source.python")

        index = 0
        # use regions from view as they are correctly updated after edits.
        for newText in replacements:
            region = self.view.get_regions('lsp_edit')[index]
            self.apply_change(region, newText, edit)
            index += 1

        self.view.erase_regions('lsp_edit')

    def create_region(self, change):
        return Range.from_lsp(change['range']).to_region(self.view)

    def apply_change(self, region, newText, edit):
        if region.empty():
            self.view.insert(edit, region.a, newText)
        else:
            if len(newText) > 0:
                self.view.replace(edit, region, newText)
            else:
                self.view.erase(edit, region)


class CloseListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if is_supported_syntax(view.settings().get("syntax")):
            Events.publish("view.on_close", view)
        sublime.set_timeout_async(check_window_unloaded, 500)


class SaveListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        if is_supported_view(view):
            Events.publish("view.on_post_save_async", view)


def is_transient_view(view):
    window = view.window()
    return view == window.transient_view_in_group(window.active_group())


class DiagnosticsCursorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.has_status = False

    @classmethod
    def is_applicable(cls, view_settings):
        syntax = view_settings.get('syntax')
        return settings.show_diagnostics_in_view_status and syntax and is_supported_syntax(syntax)

    def on_selection_modified_async(self):
        pos = self.view.sel()[0].begin()
        line_diagnostics = get_line_diagnostics(self.view, pos)
        if len(line_diagnostics) > 0:
            self.show_diagnostics_status(line_diagnostics)
        elif self.has_status:
            self.clear_diagnostics_status()

    def show_diagnostics_status(self, line_diagnostics):
        self.has_status = True
        self.view.set_status('lsp_diagnostics', line_diagnostics[0].message)

    def clear_diagnostics_status(self):
        self.view.set_status('lsp_diagnostics', "")
        self.has_status = False


class DocumentSyncListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        # This enables all of document sync for any supportable syntax
        # Global performance cost, consider a detect_lsp_support setting
        return syntax and (is_supported_syntax(syntax) or is_supportable_syntax(syntax))

    @classmethod
    def applies_to_primary_view_only(cls):
        return False

    def on_load_async(self):
        # skip transient views: if not is_transient_view(self.view):
        Events.publish("view.on_load_async", self.view)

    def on_modified(self):
        if self.view.file_name():
            Events.publish("view.on_modified", self.view)

    def on_activated_async(self):
        if self.view.file_name():
            Events.publish("view.on_activated_async", self.view)
