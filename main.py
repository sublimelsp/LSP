import html
import json
import os
import subprocess
import sys
import threading
from collections import OrderedDict
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import pathname2url
from urllib.request import url2pathname
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

import sublime_plugin
import sublime

import mdpopups


PLUGIN_NAME = 'LSP'
SUBLIME_WORD_MASK = 515
NO_HOVER_SCOPES = 'comment, constant, keyword, storage, string'
NO_COMPLETION_SCOPES = 'comment, string'
show_status_messages = True
show_view_status = True
auto_show_diagnostics_panel = True
show_diagnostics_phantoms = False
show_diagnostics_in_view_status = True
only_show_lsp_completions = False
diagnostics_highlight_style = "underline"
diagnostics_gutter_marker = "dot"
complete_all_chars = False
resolve_completion_for_snippets = False
log_debug = True
log_server = True
log_stderr = False

global_client_configs = []  # type: List[ClientConfig]
window_client_configs = dict()  # type: Dict[int, List[ClientConfig]]


class DiagnosticSeverity(object):
    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


diagnostic_severity_names = {
    DiagnosticSeverity.Error: "error",
    DiagnosticSeverity.Warning: "warning",
    DiagnosticSeverity.Information: "info",
    DiagnosticSeverity.Hint: "hint"
}

diagnostic_severity_scopes = {
    DiagnosticSeverity.Error: 'markup.deleted.lsp sublimelinter.mark.error markup.error.lsp',
    DiagnosticSeverity.Warning: 'markup.changed.lsp sublimelinter.mark.warning markup.warning.lsp',
    DiagnosticSeverity.Information: 'markup.inserted.lsp sublimelinter.gutter-mark markup.info.lsp',
    DiagnosticSeverity.Hint: 'markup.inserted.lsp sublimelinter.gutter-mark markup.info.suggestion.lsp'
}


class SymbolKind(object):
    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18


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


class CompletionItemKind(object):
    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18


completion_item_kind_names = {v: k for k, v in CompletionItemKind.__dict__.items()}


class Request:
    def __init__(self, method, params):
        self.method = method
        self.params = params
        self.jsonrpc = "2.0"

    @classmethod
    def initialize(cls, params):
        return Request("initialize", params)

    @classmethod
    def hover(cls, params):
        return Request("textDocument/hover", params)

    @classmethod
    def complete(cls, params):
        return Request("textDocument/completion", params)

    @classmethod
    def signatureHelp(cls, params):
        return Request("textDocument/signatureHelp", params)

    @classmethod
    def references(cls, params):
        return Request("textDocument/references", params)

    @classmethod
    def definition(cls, params):
        return Request("textDocument/definition", params)

    @classmethod
    def rename(cls, params):
        return Request("textDocument/rename", params)

    @classmethod
    def codeAction(cls, params):
        return Request("textDocument/codeAction", params)

    @classmethod
    def executeCommand(cls, params):
        return Request("workspace/executeCommand", params)

    @classmethod
    def formatting(cls, params):
        return Request("textDocument/formatting", params)

    @classmethod
    def documentSymbols(cls, params):
        return Request("textDocument/documentSymbol", params)

    @classmethod
    def resolveCompletionItem(cls, params):
        return Request("completionItem/resolve", params)

    def __repr__(self):
        return self.method + " " + str(self.params)

    def to_payload(self, id):
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r["jsonrpc"] = "2.0"
        r["id"] = id
        r["method"] = self.method
        r["params"] = self.params
        return r


class Notification:
    def __init__(self, method, params):
        self.method = method
        self.params = params
        self.jsonrpc = "2.0"

    @classmethod
    def initialized(cls):
        return Notification("initialized", None)

    @classmethod
    def didOpen(cls, params):
        return Notification("textDocument/didOpen", params)

    @classmethod
    def didChange(cls, params):
        return Notification("textDocument/didChange", params)

    @classmethod
    def didSave(cls, params):
        return Notification("textDocument/didSave", params)

    @classmethod
    def didClose(cls, params):
        return Notification("textDocument/didClose", params)

    @classmethod
    def didChangeConfiguration(cls, params):
        return Notification("workspace/didChangeConfiguration", params)

    @classmethod
    def exit(cls):
        return Notification("exit", None)

    def __repr__(self):
        return self.method + " " + str(self.params)

    def to_payload(self):
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r["jsonrpc"] = "2.0"
        r["method"] = self.method
        r["params"] = self.params
        return r


class Point(object):
    def __init__(self, row: int, col: int) -> None:
        self.row = int(row)
        self.col = int(col)

    def __repr__(self):
        return "{}:{}".format(self.row, self.col)

    @classmethod
    def from_lsp(cls, point: dict) -> 'Point':
        return Point(point['line'], point['character'])

    def to_lsp(self) -> dict:
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r['line'] = self.row
        r['character'] = self.col
        return r

    @classmethod
    def from_text_point(self, view: sublime.View, point: int) -> 'Point':
        return Point(*view.rowcol(point))

    def to_text_point(self, view) -> int:
        return view.text_point(self.row, self.col)


class Range(object):
    def __init__(self, start: Point, end: Point) -> None:
        self.start = start
        self.end = end

    def __repr__(self):
        return "({} {})".format(self.start, self.end)

    @classmethod
    def from_lsp(cls, range: dict) -> 'Range':
        return Range(Point.from_lsp(range['start']), Point.from_lsp(range['end']))

    def to_lsp(self) -> dict:
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r['start'] = self.start.to_lsp()
        r['end'] = self.end.to_lsp()
        return r

    @classmethod
    def from_region(self, view: sublime.View, region: sublime.Region) -> 'Range':
        return Range(
            Point.from_text_point(view, region.begin()),
            Point.from_text_point(view, region.end())
        )

    def to_region(self, view: sublime.View) -> sublime.Region:
        return sublime.Region(self.start.to_text_point(view), self.end.to_text_point(view))


class Diagnostic(object):
    def __init__(self, message, range, severity, source, lsp_diagnostic):
        self.message = message
        self.range = range
        self.severity = severity
        self.source = source
        self._lsp_diagnostic = lsp_diagnostic

    @classmethod
    def from_lsp(cls, lsp_diagnostic):
        return Diagnostic(
            # crucial keys
            lsp_diagnostic['message'],
            Range.from_lsp(lsp_diagnostic['range']),
            # optional keys
            lsp_diagnostic.get('severity', DiagnosticSeverity.Error),
            lsp_diagnostic.get('source'),
            lsp_diagnostic
        )

    def to_lsp(self):
        return self._lsp_diagnostic


def read_client_config(name, client_config):
    return ClientConfig(
        name,
        client_config.get("command", []),
        client_config.get("scopes", []),
        client_config.get("syntaxes", []),
        client_config.get("languageId", ""),
        client_config.get("enabled", True),
        client_config.get("initializationOptions", dict())
    )


def load_settings():
    settings_obj = sublime.load_settings("LSP.sublime-settings")
    update_settings(settings_obj)
    settings_obj.add_on_change("_on_new_settings", lambda: update_settings(settings_obj))


def read_bool_setting(settings_obj: sublime.Settings, key: str, default: bool) -> bool:
    val = settings_obj.get(key)
    if isinstance(val, bool):
        return val
    else:
        return default


def read_str_setting(settings_obj: sublime.Settings, key: str, default: str) -> str:
    val = settings_obj.get(key)
    if isinstance(val, str):
        return val
    else:
        return default


def update_settings(settings_obj: sublime.Settings):
    global show_status_messages
    global show_view_status
    global auto_show_diagnostics_panel
    global show_diagnostics_phantoms
    global show_diagnostics_in_view_status
    global only_show_lsp_completions
    global diagnostics_highlight_style
    global diagnostics_gutter_marker
    global complete_all_chars
    global resolve_completion_for_snippets
    global log_debug
    global log_server
    global log_stderr
    global global_client_configs

    global_client_configs = []
    client_configs = settings_obj.get("clients", {})
    if isinstance(client_configs, dict):
        for client_name, client_config in client_configs.items():
            config = read_client_config(client_name, client_config)
            if config:
                debug("Config added:", client_name, '(enabled)' if config.enabled else '(disabled)')
                global_client_configs.append(config)
    else:
        raise ValueError("client_configs")

    show_status_messages = read_bool_setting(settings_obj, "show_status_messages", True)
    show_view_status = read_bool_setting(settings_obj, "show_view_status", True)
    auto_show_diagnostics_panel = read_bool_setting(settings_obj, "auto_show_diagnostics_panel", True)
    show_diagnostics_phantoms = read_bool_setting(settings_obj, "show_diagnostics_phantoms", False)
    show_diagnostics_in_view_status = read_bool_setting(settings_obj, "show_diagnostics_in_view_status", True)
    diagnostics_highlight_style = read_str_setting(settings_obj, "diagnostics_highlight_style", "underline")
    diagnostics_gutter_marker = read_str_setting(settings_obj, "diagnostics_gutter_marker", "dot")
    only_show_lsp_completions = read_bool_setting(settings_obj, "only_show_lsp_completions", False)
    complete_all_chars = read_bool_setting(settings_obj, "complete_all_chars", True)
    resolve_completion_for_snippets = read_bool_setting(settings_obj, "resolve_completion_for_snippets", False)
    log_debug = read_bool_setting(settings_obj, "log_debug", False)
    log_server = read_bool_setting(settings_obj, "log_server", True)
    log_stderr = read_bool_setting(settings_obj, "log_stderr", False)


class ClientConfig(object):
    def __init__(self, name, binary_args, scopes, syntaxes, languageId,
                 enabled=True, init_options=dict(), settings=dict()):
        self.name = name
        self.binary_args = binary_args
        self.scopes = scopes
        self.syntaxes = syntaxes
        self.languageId = languageId
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings


def format_request(payload: 'Dict[str, Any]'):
    """Converts the request into json and adds the Content-Length header"""
    content = json.dumps(payload, sort_keys=False)
    content_length = len(content)
    result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
    return result


class Client(object):
    def __init__(self, process, project_path):
        self.process = process
        self.stdout_thread = threading.Thread(target=self.read_stdout)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self.read_stderr)
        self.stderr_thread.start()
        self.project_path = project_path
        self.request_id = 0
        self.handlers = {}  # type: Dict[int, Callable]
        self.capabilities = {}  # type: Dict[str, Any]

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities

    def get_project_path(self):
        return self.project_path

    def has_capability(self, capability):
        return capability in self.capabilities

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def send_request(self, request: Request, handler: 'Callable'):
        self.request_id += 1
        debug('request {}: {} '.format(self.request_id, request.method))
        if handler is not None:
            self.handlers[self.request_id] = handler
        self.send_payload(request.to_payload(self.request_id))

    def send_notification(self, notification: Notification):
        debug('notify: ' + notification.method)
        self.send_payload(notification.to_payload())

    def kill(self):
        self.process.kill()

    def send_payload(self, payload):
        try:
            message = format_request(payload)
            self.process.stdin.write(bytes(message, 'UTF-8'))
            self.process.stdin.flush()
        except BrokenPipeError as e:
            printf("client unexpectedly died:", e)

    def read_stdout(self):
        """
        Reads JSON responses from process and dispatch them to response_handler
        """
        ContentLengthHeader = b"Content-Length: "

        while self.process.poll() is None:
            try:

                in_headers = True
                content_length = 0
                while in_headers:
                    header = self.process.stdout.readline().strip()
                    if (len(header) == 0):
                        in_headers = False

                    if header.startswith(ContentLengthHeader):
                        content_length = int(header[len(ContentLengthHeader):])

                if (content_length > 0):
                    content = self.process.stdout.read(content_length).decode(
                        "UTF-8")

                    payload = None
                    try:
                        payload = json.loads(content)
                        limit = min(len(content), 200)
                        if payload.get("method") != "window/logMessage":
                            debug("got json: ", content[0:limit])
                    except IOError:
                        printf("Got a non-JSON payload: ", content)
                        continue

                    try:
                        if "error" in payload:
                            error = payload['error']
                            debug("got error: ", error)
                            sublime.status_message(error.get('message'))
                        elif "method" in payload:
                            if "id" in payload:
                                self.request_handler(payload)
                            else:
                                self.notification_handler(payload)
                        elif "id" in payload:
                            self.response_handler(payload)
                        else:
                            debug("Unknown payload type: ", payload)
                    except Exception as err:
                        printf("Error handling server content:", err)

            except IOError:
                printf("LSP stdout process ending due to exception: ",
                       sys.exc_info())
                self.process.terminate()
                self.process = None
                return

        debug("LSP stdout process ended.")

    def read_stderr(self):
        """
        Reads any errors from the LSP process.
        """
        while self.process.poll() is None:
            try:
                content = self.process.stderr.readline()
                if log_stderr and len(content) > 0:
                    printf("(stderr): ", content.strip())
            except IOError:
                printf("LSP stderr process ending due to exception: ",
                       sys.exc_info())
                return

        debug("LSP stderr process ended.")

    def response_handler(self, response):
        try:
            handler_id = int(response.get("id"))  # dotty sends strings back :(
            result = response.get('result', None)
            if (self.handlers[handler_id]):
                self.handlers[handler_id](result)
            else:
                debug("No handler found for id" + response.get("id"))
        except Exception as e:
            debug("error handling response", handler_id)
            raise

    def request_handler(self, request):
        method = request.get("method")
        if method == "workspace/applyEdit":
            apply_workspace_edit(sublime.active_window(),
                                 request.get("params"))
        else:
            debug("Unhandled request", method)

    def notification_handler(self, response):
        method = response.get("method")
        if method == "textDocument/publishDiagnostics":
            Events.publish("document.diagnostics", response.get("params"))
        elif method == "window/showMessage":
            sublime.active_window().message_dialog(
                response.get("params").get("message"))
        elif method == "window/logMessage" and log_server:
            server_log(self.process.args[0],
                       response.get("params").get("message"))
        else:
            debug("Unhandled notification:", method)


def debug(*args):
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        printf(*args)


def server_log(binary, *args):
    printf(*args, prefix=binary)


def printf(*args, prefix=PLUGIN_NAME):
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)


def get_project_path(window: sublime.Window) -> 'Optional[str]':
    """
    Returns the common root of all open folders in the window
    """
    if len(window.folders()):
        folder_paths = window.folders()
        return folder_paths[0]
    else:
        debug("Couldn't determine project directory")
        return None


def get_common_parent(paths: 'List[str]') -> str:
    """
    Get the common parent directory of multiple paths.

    Python 3.5+ includes os.path.commonpath which does this, however Sublime
    currently embeds Python 3.3.
    """
    return os.path.commonprefix([path + '/' for path in paths]).rstrip('/')


def is_in_workspace(window: sublime.Window, file_path: str) -> bool:
    workspace_path = get_project_path(window)
    if workspace_path is None:
        return False

    common_dir = get_common_parent([workspace_path, file_path])
    return workspace_path == common_dir


def plugin_loaded():
    load_settings()
    Events.subscribe("view.on_load_async", initialize_on_open)
    Events.subscribe("view.on_activated_async", initialize_on_open)
    if show_status_messages:
        sublime.status_message("LSP initialized")
    start_active_view()


def start_active_view():
    window = sublime.active_window()
    if window:
        view = window.active_view()
        if view and is_supported_view(view):
            initialize_on_open(view)


def check_window_unloaded():
    global clients_by_window
    open_window_ids = list(window.id() for window in sublime.windows())
    iterable_clients_by_window = clients_by_window.copy()
    closed_windows = []
    for id, window_clients in iterable_clients_by_window.items():
        if id not in open_window_ids:
            debug("window closed", id)
            closed_windows.append(id)
    for closed_window_id in closed_windows:
        unload_window_clients(closed_window_id)


def unload_window_clients(window_id: int):
    global clients_by_window
    if window_id in clients_by_window:
        window_clients = clients_by_window[window_id]
        del clients_by_window[window_id]
        for config, client in window_clients.items():
            debug("unloading client", config, client)
            unload_client(client)


def unload_client(client: Client):
    debug("unloading client", client)
    try:
        client.send_notification(Notification.exit())
        client.kill()
    except Exception as e:
        debug("error exiting", e)


def plugin_unloaded():
    for window in sublime.windows():
        for client in window_clients(window).values():
            unload_client(client)


def get_scope_client_config(view: 'sublime.View', configs: 'List[ClientConfig]') -> 'Optional[ClientConfig]':
    for config in configs:
        for scope in config.scopes:
            if len(view.sel()) > 0:
                if view.match_selector(view.sel()[0].begin(), scope):
                    return config

    return None


def get_global_client_config(view: sublime.View) -> 'Optional[ClientConfig]':
    return get_scope_client_config(view, global_client_configs)


def get_project_config(view: sublime.View) -> dict:
    view_settings = view.settings().get('LSP', dict())
    return view_settings if view_settings else dict()


def get_window_client_config(view: sublime.View) -> 'Optional[ClientConfig]':
    if view.window():
        configs_for_window = window_client_configs.get(view.window().id(), [])
        return get_scope_client_config(view, configs_for_window)
    else:
        return None


def add_window_client_config(window: 'sublime.Window', config: 'ClientConfig'):
    global window_client_configs
    window_client_configs.setdefault(window.id(), []).append(config)


def apply_window_settings(client_config: 'ClientConfig', view: 'sublime.View') -> 'ClientConfig':
    window_config = get_project_config(view)

    if client_config.name in window_config:
        overrides = window_config[client_config.name]
        debug('window has override for', client_config.name, overrides)
        merged_init_options = dict(client_config.init_options)
        merged_init_options.update(overrides.get("initializationOptions", dict()))
        return ClientConfig(
            client_config.name,
            overrides.get("command", client_config.binary_args),
            overrides.get("scopes", client_config.scopes),
            overrides.get("syntaxes", client_config.syntaxes),
            overrides.get("languageId", client_config.languageId),
            overrides.get("enabled", client_config.enabled),
            merged_init_options,
            overrides.get("settings", dict()))
    else:
        return client_config


def config_for_scope(view: sublime.View) -> 'Optional[ClientConfig]':
    # check window_client_config first
    window_client_config = get_window_client_config(view)
    if not window_client_config:
        global_client_config = get_global_client_config(view)
        if global_client_config and view.window():
            window_client_config = apply_window_settings(global_client_config, view)
            add_window_client_config(view.window(), window_client_config)
            return window_client_config

    return window_client_config


def is_supported_syntax(syntax: str) -> bool:
    for config in global_client_configs:
        if syntax in config.syntaxes:
            return True
    return False


def is_supported_view(view: sublime.View) -> bool:
    # TODO: perhaps make this check for a client instead of a config
    if config_for_scope(view):
        return True
    else:
        return False


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2

didopen_after_initialize = list()
unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


def filename_to_uri(path: str) -> str:
    return urljoin('file:', pathname2url(path))


def uri_to_filename(uri: str) -> str:
    return url2pathname(urlparse(uri).path)


def client_for_view(view: sublime.View) -> 'Optional[Client]':
    config = config_for_scope(view)
    if not config:
        debug("config not available for view", view.file_name())
        return None
    clients = window_clients(view.window())
    if config.name not in clients:
        debug(config.name, "not available for view",
              view.file_name(), "in window", view.window().id())
        return None
    else:
        return clients[config.name]


clients_by_window = {}  # type: Dict[int, Dict[str, Client]]


def window_clients(window: sublime.Window) -> 'Dict[str, Client]':
    global clients_by_window
    if window.id() in clients_by_window:
        return clients_by_window[window.id()]
    else:
        debug("no clients found for window", window.id())
        return {}


def initialize_on_open(view: sublime.View):
    if not view.window():
        return

    window = view.window()

    if window.id() in clients_by_window:
        unload_old_clients(window)

    global didopen_after_initialize
    config = config_for_scope(view)
    if config:
        if config.enabled:
            if config.name not in window_clients(window):
                didopen_after_initialize.append(view)
                get_window_client(view, config)
        else:
            debug(config.name, 'is not enabled')


def unload_old_clients(window: sublime.Window):
    project_path = get_project_path(window)
    clients_by_config = window_clients(window)
    clients_to_unload = {}
    for config_name, client in clients_by_config.items():
        if client and client.get_project_path() != project_path:
            debug('unload', config_name, 'project path changed from ', client.get_project_path())
            clients_to_unload[config_name] = client

    for config_name, client in clients_to_unload.items():
        unload_client(client)
        del clients_by_config[config_name]


def notify_did_open(view: sublime.View):
    config = config_for_scope(view)
    client = client_for_view(view)
    if client and config:
        view.settings().set("show_definitions", False)
        if view.file_name() not in document_states:
            ds = get_document_state(view.file_name())
            if show_view_status:
                view.set_status("lsp_clients", config.name)
            params = {
                "textDocument": {
                    "uri": filename_to_uri(view.file_name()),
                    "languageId": config.languageId,
                    "text": view.substr(sublime.Region(0, view.size())),
                    "version": ds.version
                }
            }
            client.send_notification(Notification.didOpen(params))


def notify_did_close(view: sublime.View):
    if view.file_name() in document_states:
        del document_states[view.file_name()]
        config = config_for_scope(view)
        clients = window_clients(sublime.active_window())
        if config and config.name in clients:
            client = clients[config.name]
            params = {"textDocument": {"uri": filename_to_uri(view.file_name())}}
            client.send_notification(Notification.didClose(params))


def notify_did_save(view: sublime.View):
    if view.file_name() in document_states:
        client = client_for_view(view)
        if client:
            params = {"textDocument": {"uri": filename_to_uri(view.file_name())}}
            client.send_notification(Notification.didSave(params))
    else:
        debug('document not tracked', view.file_name())


# TODO: this should be per-window ?
document_states = {}  # type: Dict[str, DocumentState]


class DocumentState:
    """Stores version count for documents open in a language service"""
    def __init__(self, path: str) -> 'None':
        self.path = path
        self.version = 0

    def inc_version(self):
        self.version += 1
        return self.version


def get_document_state(path: str) -> DocumentState:
    if path not in document_states:
        document_states[path] = DocumentState(path)
    return document_states[path]


pending_buffer_changes = dict()  # type: Dict[int, Dict]


def queue_did_change(view: sublime.View):
    buffer_id = view.buffer_id()
    buffer_version = 1
    pending_buffer = None
    if buffer_id in pending_buffer_changes:
        pending_buffer = pending_buffer_changes[buffer_id]
        buffer_version = pending_buffer["version"] + 1
        pending_buffer["version"] = buffer_version
    else:
        pending_buffer_changes[buffer_id] = {
            "view": view,
            "version": buffer_version
        }

    sublime.set_timeout_async(
        lambda: purge_did_change(buffer_id, buffer_version), 500)


def purge_did_change(buffer_id: int, buffer_version=None):
    if buffer_id not in pending_buffer_changes:
        return

    pending_buffer = pending_buffer_changes.get(buffer_id)

    if pending_buffer:
        if buffer_version is None or buffer_version == pending_buffer["version"]:
            notify_did_change(pending_buffer["view"])


def notify_did_change(view: sublime.View):
    if view.buffer_id() in pending_buffer_changes:
        del pending_buffer_changes[view.buffer_id()]
    # config = config_for_scope(view)
    client = client_for_view(view)
    if client:
        document_state = get_document_state(view.file_name())
        uri = filename_to_uri(view.file_name())
        params = {
            "textDocument": {
                "uri": uri,
                # "languageId": config.languageId, clangd does not like this field, but no server uses it?
                "version": document_state.inc_version(),
            },
            "contentChanges": [{
                "text": view.substr(sublime.Region(0, view.size()))
            }]
        }
        client.send_notification(Notification.didChange(params))


document_sync_initialized = False


def initialize_document_sync(text_document_sync_kind):
    global document_sync_initialized
    if document_sync_initialized:
        return
    document_sync_initialized = True
    # TODO: hook up events per scope/client
    Events.subscribe('view.on_load_async', notify_did_open)
    Events.subscribe('view.on_activated_async', notify_did_open)
    Events.subscribe('view.on_modified_async', queue_did_change)
    Events.subscribe('view.on_post_save_async', notify_did_save)
    Events.subscribe('view.on_close', notify_did_close)


def handle_initialize_result(result, client, window, config):
    global didopen_after_initialize
    capabilities = result.get("capabilities")
    client.set_capabilities(capabilities)

    # TODO: These handlers is already filtered by syntax but does not need to
    # be enabled 2x per client
    # Move filtering?
    document_sync = capabilities.get("textDocumentSync")
    if document_sync:
        initialize_document_sync(document_sync)

    Events.subscribe('document.diagnostics', handle_diagnostics)
    Events.subscribe('view.on_close', remove_diagnostics)

    client.send_notification(Notification.initialized())
    if config.settings:
        configParams = {
            'settings': config.settings
        }
        client.send_notification(Notification.didChangeConfiguration(configParams))

    for view in didopen_after_initialize:
        notify_did_open(view)
    if show_status_messages:
        window.status_message("{} initialized".format(config.name))
    didopen_after_initialize = list()


stylesheet = '''
            <style>
                div.error {
                    padding: 0.4rem 0 0.4rem 0.7rem;
                    margin: 0.2rem 0;
                    border-radius: 2px;
                }
                div.error span.message {
                    padding-right: 0.7rem;
                }
                div.error a {
                    text-decoration: inherit;
                    padding: 0.35rem 0.7rem 0.45rem 0.8rem;
                    position: relative;
                    bottom: 0.05rem;
                    border-radius: 0 2px 2px 0;
                    font-weight: bold;
                }
                html.dark div.error a {
                    background-color: #00000018;
                }
                html.light div.error a {
                    background-color: #ffffff18;
                }
            </style>
        '''


def create_phantom_html(text: str) -> str:
    global stylesheet
    return """<body id=inline-error>{}
                <div class="error">
                    <span class="message">{}</span>
                    <a href="code-actions">Code Actions</a>
                </div>
                </body>""".format(stylesheet, html.escape(text, quote=False))


def on_phantom_navigate(view: sublime.View, href: str, point: int):
    # TODO: don't mess with the user's cursor.
    sel = view.sel()
    sel.clear()
    sel.add(sublime.Region(point))
    view.run_command("lsp_code_actions")


def create_phantom(view: sublime.View, diagnostic: Diagnostic) -> sublime.Phantom:
    region = diagnostic.range.to_region(view)
    # TODO: hook up hide phantom (if keeping them)
    content = create_phantom_html(diagnostic.message)
    return sublime.Phantom(
        region,
        '<p>' + content + '</p>',
        sublime.LAYOUT_BELOW,
        lambda href: on_phantom_navigate(view, href, region.begin())
    )


def format_severity(severity: int) -> str:
    return diagnostic_severity_names.get(severity, "???")


def format_diagnostic(diagnostic: Diagnostic) -> str:
    location = "{:>8}:{:<4}".format(
        diagnostic.range.start.row + 1, diagnostic.range.start.col + 1)
    message = diagnostic.message.replace("\n", " ").replace("\r", "")
    return " {}\t{:<12}\t{:<10}\t{}".format(
        location, diagnostic.source, format_severity(diagnostic.severity), message)


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
                    "tabSize": 4,
                    "insertSpaces": True
                }
            }
            request = Request.formatting(params)
            client.send_request(
                request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        self.view.run_command('lsp_apply_document_edit',
                              {'changes': response})


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
            request = Request.definition(get_document_position(self.view, pos))
            client.send_request(
                request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, position):
        window = sublime.active_window()
        if len(response) < 1:
            window.run_command("goto_definition")
        else:
            location = response[0]
            file_path = uri_to_filename(location.get("uri"))
            start = Point.from_lsp(location['range']['start'])
            file_location = "{}:{}:{}".format(file_path, start.row + 1, start.col + 1)
            debug("opening location", location)
            window.open_file(file_location, sublime.ENCODED_POSITION)
            # TODO: can add region here.

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


OUTPUT_PANEL_SETTINGS = {
    "auto_indent": False,
    "draw_indent_guides": False,
    "draw_white_space": "None",
    "gutter": False,
    'is_widget': True,
    "line_numbers": False,
    "margin": 3,
    "match_brackets": False,
    "scroll_past_end": False,
    "tab_size": 4,
    "translate_tabs_to_spaces": False,
    "word_wrap": False
}


def create_output_panel(window: sublime.Window, name: str) -> sublime.View:
    panel = window.create_output_panel(name)
    settings = panel.settings()
    for key, value in OUTPUT_PANEL_SETTINGS.items():
        settings.set(key, value)
    return panel


def ensure_references_panel(window: sublime.Window):
    return window.find_output_panel("references") or create_references_panel(window)


def create_references_panel(window: sublime.Window):
    panel = create_output_panel(window, "references")
    panel.settings().set("result_file_regex",
                         r"^\s+\S\s+(\S.+)\s+(\d+):?(\d+)$")
    panel.assign_syntax("Packages/" + PLUGIN_NAME +
                        "/Syntaxes/References.sublime-syntax")
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
            sublime.status_message("No references found")

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


UNDERLINE_FLAGS = (sublime.DRAW_SQUIGGLY_UNDERLINE
                   | sublime.DRAW_NO_OUTLINE
                   | sublime.DRAW_NO_FILL
                   | sublime.DRAW_EMPTY_AS_OVERWRITE)

BOX_FLAGS = sublime.DRAW_NO_FILL | sublime.DRAW_EMPTY_AS_OVERWRITE

window_file_diagnostics = dict(
)  # type: Dict[int, Dict[str, Dict[str, List[Diagnostic]]]]


def update_file_diagnostics(window: sublime.Window, file_path: str, source: str,
                            diagnostics: 'List[Diagnostic]'):
    if diagnostics:
        window_file_diagnostics.setdefault(window.id(), dict()).setdefault(
            file_path, dict())[source] = diagnostics
    else:
        if window.id() in window_file_diagnostics:
            file_diagnostics = window_file_diagnostics[window.id()]
            if file_path in file_diagnostics:
                if source in file_diagnostics[file_path]:
                    del file_diagnostics[file_path][source]
                if not file_diagnostics[file_path]:
                    del file_diagnostics[file_path]


phantom_sets_by_buffer = {}  # type: Dict[int, sublime.PhantomSet]


def update_diagnostics_phantoms(view: sublime.View, diagnostics: 'List[Diagnostic]'):
    global phantom_sets_by_buffer

    buffer_id = view.buffer_id()
    if not show_diagnostics_phantoms or view.is_dirty():
        phantoms = None
    else:
        phantoms = list(
            create_phantom(view, diagnostic) for diagnostic in diagnostics)
    if phantoms:
        phantom_set = phantom_sets_by_buffer.get(buffer_id)
        if not phantom_set:
            phantom_set = sublime.PhantomSet(view, "lsp_diagnostics")
            phantom_sets_by_buffer[buffer_id] = phantom_set
        phantom_set.update(phantoms)
    else:
        phantom_sets_by_buffer.pop(buffer_id, None)


def update_diagnostics_regions(view: sublime.View, diagnostics: 'List[Diagnostic]', severity: int):
    region_name = "lsp_" + format_severity(severity)
    if show_diagnostics_phantoms and not view.is_dirty():
        regions = None
    else:
        regions = list(diagnostic.range.to_region(view) for diagnostic in diagnostics
                       if diagnostic.severity == severity)
    if regions:
        scope_name = diagnostic_severity_scopes[severity]
        view.add_regions(
            region_name, regions, scope_name, diagnostics_gutter_marker,
            UNDERLINE_FLAGS if diagnostics_highlight_style == "underline" else BOX_FLAGS)
    else:
        view.erase_regions(region_name)


def update_diagnostics_in_view(view: sublime.View, diagnostics: 'List[Diagnostic]'):
    if view and view.is_valid():
        update_diagnostics_phantoms(view, diagnostics)
        for severity in range(DiagnosticSeverity.Error, DiagnosticSeverity.Information):
            update_diagnostics_regions(view, diagnostics, severity)


def remove_diagnostics(view: sublime.View):
    """Removes diagnostics for a file if no views exist for it
    """
    window = sublime.active_window()

    file_path = view.file_name()
    if not window.find_open_file(view.file_name()):
        update_file_diagnostics(window, file_path, 'lsp', [])
        update_diagnostics_panel(window)
    else:
        debug('file still open?')


def handle_diagnostics(update: 'Any'):
    file_path = uri_to_filename(update.get('uri'))
    window = sublime.active_window()

    if not is_in_workspace(window, file_path):
        debug("Skipping diagnostics for file", file_path,
              " it is not in the workspace")
        return

    diagnostics = list(
        Diagnostic.from_lsp(item) for item in update.get('diagnostics', []))

    view = window.find_open_file(file_path)

    # diagnostics = update.get('diagnostics')

    update_diagnostics_in_view(view, diagnostics)

    # update panel if available

    origin = 'lsp'  # TODO: use actual client name to be able to update diagnostics per client

    update_file_diagnostics(window, file_path, origin, diagnostics)
    update_diagnostics_panel(window)


class LspShowDiagnosticsPanelCommand(sublime_plugin.WindowCommand):
    def run(self):
        ensure_diagnostics_panel(self.window)
        self.window.run_command("show_panel", {"panel": "output.diagnostics"})


def create_diagnostics_panel(window):
    panel = create_output_panel(window, "diagnostics")
    panel.settings().set("result_file_regex", r"^\s*\S\s+(\S.*):$")
    panel.settings().set("result_line_regex", r"^\s+([0-9]+):?([0-9]+).*$")
    panel.assign_syntax("Packages/" + PLUGIN_NAME +
                        "/Syntaxes/Diagnostics.sublime-syntax")
    return panel


def ensure_diagnostics_panel(window):
    return window.find_output_panel("diagnostics") or create_diagnostics_panel(window)


def update_diagnostics_panel(window):
    assert window, "missing window!"
    base_dir = get_project_path(window)

    panel = ensure_diagnostics_panel(window)
    assert panel, "must have a panel now!"

    if window.id() in window_file_diagnostics:
        active_panel = window.active_panel()
        is_active_panel = (active_panel == "output.diagnostics")
        panel.settings().set("result_base_dir", base_dir)
        panel.set_read_only(False)
        file_diagnostics = window_file_diagnostics[window.id()]
        if file_diagnostics:
            to_render = []
            for file_path, source_diagnostics in file_diagnostics.items():
                relative_file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                if source_diagnostics:
                    to_render.append(format_diagnostics(relative_file_path, source_diagnostics))
            panel.run_command("lsp_update_panel", {"characters": "\n".join(to_render)})
            if auto_show_diagnostics_panel and not active_panel:
                window.run_command("show_panel",
                                   {"panel": "output.diagnostics"})
        else:
            panel.run_command("lsp_clear_panel")
            if auto_show_diagnostics_panel and is_active_panel:
                window.run_command("hide_panel",
                                   {"panel": "output.diagnostics"})
        panel.set_read_only(True)


def format_diagnostics(file_path, origin_diagnostics):
    content = " ◌ {}:\n".format(file_path)
    for origin, diagnostics in origin_diagnostics.items():
        for diagnostic in diagnostics:
            item = format_diagnostic(diagnostic)
            content += item + "\n"
    return content


def start_client(window: sublime.Window, config: ClientConfig):
    project_path = get_project_path(window)
    if project_path:
        if show_status_messages:
            window.status_message("Starting " + config.name + "...")
        debug("starting in", project_path)

        variables = window.extract_variables()
        expanded_args = list(sublime.expand_variables(os.path.expanduser(arg), variables) for arg in config.binary_args)

        client = start_server(expanded_args, project_path)
        if not client:
            window.status_message("Could not start " + config.name + ", disabling")
            debug("Could not start", config.binary_args, ", disabling")
            return

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


def get_window_client(view: sublime.View, config: ClientConfig) -> Client:
    global clients_by_window

    window = view.window()
    clients = window_clients(window)
    if config.name not in clients:
        client = start_client(window, config)
        clients_by_window.setdefault(window.id(), {})[config.name] = client
        debug("client registered for window",
              window.id(), window_clients(window))
    else:
        client = clients[config.name]

    return client


def start_server(server_binary_args, working_dir):
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
            startupinfo=si)
        return Client(process, working_dir)

    except Exception as err:
        printf(err)


def get_document_range(view: sublime.View, region: sublime.Region) -> OrderedDict:
    d = OrderedDict()  # type: OrderedDict[str, Any]
    d['textDocument'] = {"uri": filename_to_uri(view.file_name())}
    d['range'] = Range.from_region(view, region).to_lsp()
    return d


def get_document_position(view: sublime.View, point) -> OrderedDict:
    if not point:
        point = view.sel()[0].begin()
    d = OrderedDict()  # type: OrderedDict[str, Any]
    d['textDocument'] = {"uri": filename_to_uri(view.file_name())}
    d['position'] = Point.from_text_point(view, point).to_lsp()
    return d


class Events:
    listener_dict = dict()  # type: Dict[str, Callable[..., None]]

    @classmethod
    def subscribe(cls, key, listener):
        if key in cls.listener_dict:
            cls.listener_dict[key].append(listener)
        else:
            cls.listener_dict[key] = [listener]
        return lambda: cls.unsubscribe(key, listener)

    @classmethod
    def unsubscribe(cls, key, listener):
        if key in cls.listener_dict:
            cls.listener_dict[key].remove(listener)

    @classmethod
    def publish(cls, key, *args):
        if key in cls.listener_dict:
            for listener in cls.listener_dict[key]:
                listener(*args)


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
                client.send_request(
                    Request.hover(get_document_position(self.view, point)),
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
            on_navigate=lambda href: self.on_diagnostics_navigate(self, href, point, diagnostics))

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
            "\n".join(formatted),
            css=".mdpopups .lsp_hover { margin: 4px; } .mdpopups p { margin: 0.1rem; }",
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class="lsp_hover",
            max_width=800)


class CompletionState(object):
    IDLE = 0
    REQUESTING = 1
    APPLYING = 2
    CANCELLING = 3


resolvable_completion_items = []  # type: List[Any]


def find_completion_item(label: str) -> 'Optional[Any]':
    matches = list(filter(lambda i: i.get("label") == label, resolvable_completion_items))
    return matches[0] if matches else None


class CompletionContext(object):

    def __init__(self, begin):
        self.begin = begin  # type: Optional[int]
        self.end = None  # type: Optional[int]
        self.region = None  # type: Optional[sublime.Region]
        self.committing = False

    def committed_at(self, end):
        self.end = end
        self.region = sublime.Region(self.begin, self.end)
        self.committing = False


current_completion = None  # type: Optional[CompletionContext]


def has_resolvable_completions(view):
    client = client_for_view(view)
    if client:
        completionProvider = client.get_capability(
            'completionProvider')
        if completionProvider:
            if completionProvider.get('resolveProvider', False):
                return True
    return False


class CompletionSnippetHandler(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        global current_completion
        if resolve_completion_for_snippets and has_resolvable_completions(view):
            current_completion = CompletionContext(view.sel()[0].begin())

    def on_text_command(self, view, command_name, args):
        if resolve_completion_for_snippets and current_completion:
            current_completion.committing = command_name in ('commit_completion', 'insert_best_completion')

    def on_modified(self, view):
        global current_completion

        if resolve_completion_for_snippets and view.file_name():
            if current_completion and current_completion.committing:
                current_completion.committed_at(view.sel()[0].end())
                inserted = view.substr(current_completion.region)
                item = find_completion_item(inserted)
                if item:
                    self.resolve_completion(item, view)
                else:
                    current_completion = None

    def resolve_completion(self, item, view):
        client = client_for_view(view)
        if not client:
            return

        client.send_request(
            Request.resolveCompletionItem(item),
            lambda response: self.handle_resolve_response(response, view))

    def handle_resolve_response(self, response, view):
        # replace inserted text if a snippet was returned.
        if current_completion and response.get('insertTextFormat') == 2:  # snippet
            insertText = response.get('insertText')
            try:
                sel = view.sel()
                sel.clear()
                sel.add(current_completion.region)
                view.run_command("insert_snippet", {"contents": insertText})
            except Exception as e:
                debug('error inserting snippet', insertText, e)


class CompletionHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.initialized = False
        self.enabled = False
        self.trigger_chars = []  # type: List[str]
        self.resolve = False
        self.resolve_details = []  # type: List[Tuple[str, str]]
        self.state = CompletionState.IDLE
        self.next_request = None

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def initialize(self):
        self.initialized = True
        client = client_for_view(self.view)
        if client:
            completionProvider = client.get_capability(
                'completionProvider')
            if completionProvider:
                self.enabled = True
                self.trigger_chars = completionProvider.get(
                    'triggerCharacters') or []
                self.has_resolve_provider = completionProvider.get('resolveProvider', False)

    def is_after_trigger_character(self, location):
        if location > 0:
            prev_char = self.view.substr()
            return prev_char in self.trigger_chars

    def on_query_completions(self, prefix, locations):
        if self.view.match_selector(locations[0], NO_COMPLETION_SCOPES):
            return

        if not self.initialized:
            self.initialize()

        if self.enabled:
            if self.state == CompletionState.IDLE:
                self.do_request(prefix, locations)
                self.completions = []  # type: List[Tuple[str, str]]

            elif self.state in (CompletionState.REQUESTING, CompletionState.CANCELLING):
                self.next_request = (prefix, locations)
                self.state = CompletionState.CANCELLING

            elif self.state == CompletionState.APPLYING:
                self.state = CompletionState.IDLE

            return (
                self.completions,
                0 if self.state == CompletionState.IDLE and not only_show_lsp_completions
                else sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
            )

    def do_request(self, prefix, locations):
        self.next_request = None
        view = self.view

        # don't store client so we can handle restarts
        client = client_for_view(view)
        if not client:
            return

        if complete_all_chars or self.is_after_trigger_character(locations[0]):
            purge_did_change(view.buffer_id())
            client.send_request(
                Request.complete(get_document_position(view, locations[0])),
                self.handle_response)
            self.state = CompletionState.REQUESTING

    def format_completion(self, item) -> 'Tuple[str, str]':
        # Sublime handles snippets automatically, so we don't have to care about insertTextFormat.
        label = item.get("label")
        detail = item.get("detail")
        kind = item.get("kind")
        if not detail:
            if kind is not None:
                detail = completion_item_kind_names[kind]
        insertText = item.get("insertText", None)
        if not insertText:
            insertText = label
        if insertText[0] == '$':  # sublime needs leading '$' escaped.
            insertText = '\$' + insertText[1:]
        return "{}\t{}".format(label, detail) if detail else label, insertText

    def handle_response(self, response):
        global resolvable_completion_items
        if self.state == CompletionState.REQUESTING:
            items = response["items"] if isinstance(response,
                                                    dict) else response
            self.completions = list(self.format_completion(item) for item in items)

            if self.has_resolve_provider:
                resolvable_completion_items = items

            self.state = CompletionState.APPLYING
            self.run_auto_complete()
        elif self.state == CompletionState.CANCELLING:
            self.do_request(*self.next_request)
        else:
            debug('Got unexpected response while in state {}'.format(self.state))

    def run_auto_complete(self):
        self.view.run_command(
            "auto_complete", {
                'disable_auto_insert': True,
                'api_completions_only': True,
                'next_completion_if_showing': False,
                'auto_complete_commit_on_tab': True,
            })


class SignatureHelpListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.signature_help_triggers = None

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def initialize_triggers(self):
        client = client_for_view(self.view)
        if client:
            signatureHelpProvider = client.get_capability(
                'signatureHelpProvider')
            if signatureHelpProvider:
                self.signature_help_triggers = signatureHelpProvider.get(
                    'triggerCharacters')
                return

        self.signature_help_triggers = []

    def on_modified_async(self):
        pos = self.view.sel()[0].begin()
        last_char = self.view.substr(pos - 1)
        # TODO: this will fire too often, narrow down using scopes or regex
        if self.signature_help_triggers is None:
            self.initialize_triggers()

        if self.signature_help_triggers:
            if last_char in self.signature_help_triggers:
                client = client_for_view(self.view)
                if client:
                    purge_did_change(self.view.buffer_id())
                    client.send_request(
                        Request.signatureHelp(get_document_position(self.view, pos)),
                        lambda response: self.handle_response(response, pos))
            else:
                # TODO: this hides too soon.
                if self.view.is_popup_visible():
                    self.view.hide_popup()

    def handle_response(self, response, point):
        if response is not None:
            config = config_for_scope(self.view)
            signatures = response.get("signatures")
            activeSignature = response.get("activeSignature")
            debug("got signatures, active is", len(signatures), activeSignature)
            if len(signatures) > 0 and config:
                signature = signatures[activeSignature]
                debug("active signature", signature)
                formatted = []
                formatted.append(
                    "```{}\n{}\n```".format(config.languageId, signature.get('label')))
                params = signature.get('parameters')
                if params is None:  # for pyls TODO create issue?
                    params = signature.get('params')
                debug("params", params)
                for parameter in params:
                    paramDocs = parameter.get('documentation')
                    if paramDocs:
                        formatted.append("**{}**\n".format(parameter.get('label')))
                        formatted.append("* *{}*\n".format(paramDocs))

                formatted.append(signature.get('documentation'))

                mdpopups.show_popup(
                    self.view,
                    "\n".join(formatted),
                    css=".mdpopups .lsp_signature { margin: 4px; } .mdpopups p { margin: 0.1rem; }",
                    md=True,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    wrapper_class="lsp_signature",
                    max_width=800)


def get_line_diagnostics(view, point):
    row, _ = view.rowcol(point)
    diagnostics = get_diagnostics_for_view(view)
    return tuple(
        diagnostic for diagnostic in diagnostics
        if diagnostic.range.start.row <= row <= diagnostic.range.end.row
    )


def get_point_diagnostics(view, point):
    diagnostics = get_diagnostics_for_view(view)
    return tuple(
        diagnostic for diagnostic in diagnostics
        if diagnostic.range.to_region(view).contains(point)
    )


def get_diagnostics_for_view(view: sublime.View) -> 'List[Diagnostic]':
    window = view.window()
    file_path = view.file_name()
    origin = 'lsp'
    if window.id() in window_file_diagnostics:
        file_diagnostics = window_file_diagnostics[window.id()]
        if file_path in file_diagnostics:
            if origin in file_diagnostics[file_path]:
                return file_diagnostics[file_path][origin]
    return []


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
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        global show_diagnostics_in_view_status
        return show_diagnostics_in_view_status and syntax and is_supported_syntax(syntax)

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
        return syntax and is_supported_syntax(syntax)

    @classmethod
    def applies_to_primary_view_only(cls):
        return False

    def on_load_async(self):
        # skip transient views: if not is_transient_view(self.view):
        Events.publish("view.on_load_async", self.view)

    def on_modified_async(self):
        if self.view.file_name():
            Events.publish("view.on_modified_async", self.view)

    def on_activated_async(self):
        if self.view.file_name():
            Events.publish("view.on_activated_async", self.view)
