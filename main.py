import sublime_plugin
import sublime
import subprocess
import threading
import json
import os
import sys
import urllib.request as urllib
from urllib.parse import urljoin
from collections import OrderedDict
import html
import mdpopups
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


PLUGIN_NAME = 'LSP'
SUBLIME_WORD_MASK = 515
SUBLIME_LINTER_MARK_ERROR = 'sublimelinter.mark.error'
show_status_messages = True
show_view_status = True
auto_show_diagnostics_panel = True
show_diagnostics_phantoms = True
diagnostic_error_region_scope = SUBLIME_LINTER_MARK_ERROR  # 'markup.deleted.diff'

configs = []  # type: List[ClientConfig]


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


class Range(object):
    def __init__(self, start, end):
        self.start = start
        self.end = end

    @classmethod
    def from_lsp(cls, lsp_range):
        start = lsp_range.get('start')
        end = lsp_range.get('end')
        return Range(
            (start.get('line'), start.get('character')),
            (end.get('line'), end.get('character'))
        )

    def to_lsp(self):
        return make_lsp_range(self.start, self.end)


def make_lsp_range(start_rowcol, end_rowcol):
    (start_line, start_character) = start_rowcol
    (end_line, end_character) = end_rowcol
    return {
        "start": {"line": start_line, "character": start_character},
        "end": {"line": end_line, "character": end_character}
    }


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
            lsp_diagnostic.get('message'),
            Range.from_lsp(lsp_diagnostic.get('range')),
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
        client_config.get("languageId", "")
    )


def load_settings():
    global show_status_messages
    global show_view_status
    global auto_show_diagnostics_panel
    global show_diagnostics_phantoms
    global diagnostic_error_region_scope
    global configs
    settings_obj = sublime.load_settings("LSP.sublime-settings")

    configs = []
    client_configs = settings_obj.get("clients", {})
    for client_name, client_config in client_configs.items():
        config = read_client_config(client_name, client_config)
        if config:
            debug("Config added:", client_name)
            configs.append(config)

    show_status_messages = settings_obj.get("show_status_messages", True)
    show_view_status = settings_obj.get("show_view_status", True)
    auto_show_diagnostics_panel = settings_obj.get("auto_show_diagnostics_panel", True)
    show_diagnostics_phantoms = settings_obj.get("show_diagnostics_phantoms", True)
    diagnostic_error_region_scope = settings_obj.get("diagnostic_error_region_scope", SUBLIME_LINTER_MARK_ERROR)
    settings_obj.add_on_change("_on_new_settings", load_settings)


class ClientConfig(object):
    def __init__(self, name, binary_args, scopes, syntaxes, languageId):
        self.name = name
        self.binary_args = binary_args
        self.scopes = scopes
        self.syntaxes = syntaxes
        self.languageId = languageId


def format_request(payload: 'Dict[str, Any]'):
    """Converts the request into json and adds the Content-Length header"""
    content = json.dumps(payload, sort_keys=False)
    content_length = len(content)
    result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
    return result


class Client(object):
    def __init__(self, process):
        self.process = process
        self.stdout_thread = threading.Thread(target=self.read_stdout)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self.read_stderr)
        self.stderr_thread.start()
        self.request_id = 0
        self.handlers = {}  # type: Dict[int, Callable]
        self.capabilities = {}  # type: Dict[str, Any]

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities

    def has_capability(self, capability):
        return capability in self.capabilities

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def send_request(self, request: Request, handler: 'Callable'):
        self.request_id += 1
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
                error = self.process.stderr.readline().decode('UTF-8')
                if len(error) > 0:
                    printf("(stderr): ", error.strip())
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
        elif method == "window/logMessage":
            server_log(self.process.args[0],
                       response.get("params").get("message"))
        else:
            debug("Unhandled notification:", method)


def debug(*args):
    """Print args to the console if the "debug" setting is True."""
    # if settings.get('debug'):
    printf(*args)


def server_log(binary, *args):
    print(binary + ": ", end='')

    for arg in args:
        print(arg, end=' ')

    print()


def printf(*args):
    """Print args to the console, prefixed by the plugin name."""
    print(PLUGIN_NAME + ': ', end='')

    for arg in args:
        print(arg, end=' ')

    print()


def get_project_path(window: sublime.Window) -> 'Optional[str]':
    """
    Returns the common root of all open folders in the window
    """
    if len(window.folders()):
        folder_paths = window.folders()
        return os.path.commonprefix(folder_paths)
    else:
        debug("Couldn't determine project directory")
        return None


def is_in_workspace(window: sublime.Window, file_path: str) -> bool:
    workspace_path = get_project_path(window)
    if workspace_path is None:
        return False

    common_dir = os.path.commonprefix([workspace_path, file_path])
    return workspace_path == common_dir


def plugin_loaded():
    load_settings()
    Events.subscribe("view.on_load_async", initialize_on_open)
    Events.subscribe("view.on_activated_async", initialize_on_open)
    if show_status_messages:
        sublime.status_message("LSP initialized")


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


def config_for_scope(view: sublime.View) -> 'Optional[ClientConfig]':
    for config in configs:
        for scope in config.scopes:
            if view.match_selector(view.sel()[0].begin(), scope):
                return config
    return None


def is_supported_syntax(syntax: str) -> bool:
    for config in configs:
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
    return urljoin('file:', urllib.pathname2url(path))


def uri_to_filename(uri: str) -> str:
    if os.name == 'nt':
        return urllib.url2pathname(uri.replace("file://", ""))
    else:
        return urllib.url2pathname(uri).replace("file://", "")


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
    global didopen_after_initialize
    config = config_for_scope(view)
    if config:
        if config.name not in window_clients(view.window()):
            didopen_after_initialize.append(view)
            get_window_client(view, config)


def notify_did_open(view: sublime.View):
    config = config_for_scope(view)
    client = client_for_view(view)
    if client and config:
        view.settings().set("show_definitions", False)
        if view.file_name() not in document_states:
            get_document_state(view.file_name())
            if show_view_status:
                view.set_status("lsp_clients", config.name)
            params = {
                "textDocument": {
                    "uri": filename_to_uri(view.file_name()),
                    "languageId": config.languageId,
                    "text": view.substr(sublime.Region(0, view.size()))
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
    region = create_region(view, diagnostic)
    # TODO: hook up hide phantom (if keeping them)
    content = create_phantom_html(diagnostic.message)
    point = view.text_point(*diagnostic.range.start)
    return sublime.Phantom(
        region,
        '<p>' + content + '</p>',
        sublime.LAYOUT_BELOW,
        lambda href: on_phantom_navigate(view, href, point)
    )


def create_region(view, diagnostic: Diagnostic) -> sublime.Region:
    return sublime.Region(
        view.text_point(*diagnostic.range.start),
        view.text_point(*diagnostic.range.end))


def format_severity(severity: int) -> str:
    return diagnostic_severity_names.get(severity, "???")


def format_diagnostic(diagnostic: Diagnostic) -> str:
    line, column = diagnostic.range.start
    location = "{:>8}:{:<4}".format(line + 1, column + 1)
    message = diagnostic.message.replace("\n", " ").replace("\r", "")
    return "{}\t{:<12}\t{:<10}\t{}".format(
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
            start = location.get('range').get('start')
            file_location = "{}:{}:{}".format(file_path,
                                              start.get('line') + 1,
                                              start.get('character') + 1)
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
        location = selected_symbol.get("location")
        start = location.get("range").get("start")
        end = location.get("range").get("end")
        startpos = self.view.text_point(start.get('line'), start.get('character'))
        endpos = self.view.text_point(end.get('line'), end.get('character'))
        region = sublime.Region(startpos, endpos)
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
                         r"^\s+(\S*)\s+([0-9]+):?([0-9]+)$")
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
    start = reference.get('range').get('start')
    file_path = uri_to_filename(reference.get("uri"))
    relative_file_path = os.path.relpath(file_path, base_dir)
    return "\t{}\t{}:{}".format(
        relative_file_path,
        start.get('line') + 1,
        start.get('character') + 1
    )


class LspClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """

    def run(self, edit):
        self.view.erase(edit, sublime.Region(0, self.view.size()))


UNDERLINE_FLAGS = (sublime.DRAW_NO_FILL
                   | sublime.DRAW_NO_OUTLINE
                   | sublime.DRAW_EMPTY_AS_OVERWRITE)

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


def update_diagnostics_in_view(view: sublime.View, diagnostics: 'List[Diagnostic]'):
    global phantom_sets_by_buffer

    phantoms = []  # type: List[sublime.Phantom]
    regions = []  # type: List[sublime.Region]

    if view is not None:
        if view.is_dirty() or not show_diagnostics_phantoms:
            regions = list(
                create_region(view, diagnostic) for diagnostic in diagnostics)
        else:
            phantoms = list(
                create_phantom(view, diagnostic) for diagnostic in diagnostics)

        # TODO: if phantoms are disabled, this logic can be skipped
        buffer_id = view.buffer_id()
        if buffer_id not in phantom_sets_by_buffer:
            phantom_set = sublime.PhantomSet(view, "diagnostics")
            phantom_sets_by_buffer[buffer_id] = phantom_set
        else:
            phantom_set = phantom_sets_by_buffer[buffer_id]

        phantom_set.update(phantoms)
        # TODO: split between warning and error
        if (len(regions)) > 0:
            # TODO: stop stealing SublimeLinter's coloring.
            view.add_regions("errors", regions, diagnostic_error_region_scope,
                             "dot",
                             sublime.DRAW_SQUIGGLY_UNDERLINE | UNDERLINE_FLAGS)
        else:
            view.erase_regions("errors")


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
        panel.run_command("lsp_clear_panel")
        file_diagnostics = window_file_diagnostics[window.id()]
        if file_diagnostics:
            for file_path, source_diagnostics in file_diagnostics.items():
                relative_file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                if source_diagnostics:
                    append_diagnostics(panel, relative_file_path, source_diagnostics)
            if auto_show_diagnostics_panel and not active_panel:
                window.run_command("show_panel",
                                   {"panel": "output.diagnostics"})
        else:
            if auto_show_diagnostics_panel and is_active_panel:
                window.run_command("hide_panel",
                                   {"panel": "output.diagnostics"})
        panel.set_read_only(True)



def append_diagnostics(panel, file_path, origin_diagnostics):
    panel.run_command('append',
                      {'characters':  " ◌ {}:\n".format(file_path),
                       'force': True})
    for origin, diagnostics in origin_diagnostics.items():
        for diagnostic in diagnostics:
            item = format_diagnostic(diagnostic)
            panel.run_command('append', {
                'characters': item + "\n",
                'force': True,
                'scroll_to_end': True
            })


def start_client(window: sublime.Window, config: ClientConfig):
    project_path = get_project_path(window)
    if project_path:
        if show_status_messages:
            window.status_message("Starting " + config.name + "...")
        debug("starting in", project_path)
        client = start_server(config.binary_args, project_path)
        if not client:
            window.status_message("Could not start" + config.name + ", disabling")
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
                    }
                }
            }
        }
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
    args = server_binary_args
    debug("starting " + str(args))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()  # type: ignore
        si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_dir,
            startupinfo=si)
        return Client(process)

    except Exception as err:
        print(err)


def get_document_range(view: sublime.View) -> 'Any':
    range = {
        "start": {
            "line": 0,
            "character": 0
        },
        "end": {
            "line": 0,
            "character": 0
        }
    }
    return {
        "textDocument": {
            "uri": filename_to_uri(view.file_name())
        },
        "range": range
    }


def get_document_position(view, point):
    if point:
        (row, col) = view.rowcol(point)
    else:
        view.sel()
    uri = filename_to_uri(view.file_name())
    position = OrderedDict(line=row, character=col)
    dp = OrderedDict()  # type: Dict[str, Any]
    dp["textDocument"] = {"uri": uri}
    dp["position"] = position
    return dp


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


class DiagnosticsHoverHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return is_supported_syntax(syntax)

    def on_hover(self, point, hover_zone):
        (row, col) = self.view.rowcol(point)
        diagnostics = get_diagnostics_for_view(self.view)
        line_diagnostics = []
        for diagnostic in diagnostics:
            (start_line, _) = diagnostic.range.start
            (end_line, _) = diagnostic.range.end
            if row >= start_line and row <= end_line:
                line_diagnostics.append(diagnostic)
        if line_diagnostics:
            self.show_hover(point, line_diagnostics)

    def show_hover(self, point, diagnostics):
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
            on_navigate=lambda href: self.on_navigate(href, point, diagnostics))

    def on_navigate(self, href, point, diagnostics):
        # TODO: don't mess with the user's cursor.
        # Instead, pass code actions requested from phantoms & hovers should call lsp_code_actions with
        # diagnostics as args, positioning resulting UI close to the clicked link.
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command("lsp_code_actions")


class HoverHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return is_supported_syntax(syntax)

    def on_hover(self, point, hover_zone):
        client = client_for_view(self.view)
        if not client:
            return
        if not client.has_capability('hoverProvider'):
            return

        if hover_zone == sublime.HOVER_TEXT:
            word_at_sel = self.view.classify(point)
            if word_at_sel & SUBLIME_WORD_MASK:
                client.send_request(
                    Request.hover(get_document_position(self.view, point)),
                    lambda response: self.handle_response(response, point))

    def handle_response(self, response, point):
        debug(response)
        contents = response.get('contents')
        if len(contents) < 1:
            return

        self.show_hover(point, contents)

    def show_hover(self, point, contents):
        formatted = []
        if isinstance(contents, str):
            formatted.append(contents)
        else:
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
            css=".mdpopups .lsp_hover { margin: 4px; }",
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class="lsp_hover",
            max_width=800)


class CompletionHandler(sublime_plugin.EventListener):
    def __init__(self):
        self.completions = []  # type: List[Tuple[str, str]]
        self.refreshing = False

    def on_query_completions(self, view, prefix, locations):
        if not is_supported_view(view):
            return None

        if not self.refreshing:
            client = client_for_view(view)

            if not client:
                return

            completionProvider = client.get_capability('completionProvider')
            if not completionProvider:
                return

            autocomplete_triggers = completionProvider.get('triggerCharacters')

            if locations[0] > 0:
                self.completions = []
                prev_char = view.substr(
                    sublime.Region(locations[0] - 1, locations[0]))
                if prev_char not in autocomplete_triggers:
                    return None

            purge_did_change(view.buffer_id())
            client.send_request(
                Request.complete(get_document_position(view, locations[0])),
                self.handle_response)

        self.refreshing = False
        return self.completions, (sublime.INHIBIT_WORD_COMPLETIONS
                                  | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def format_completion(self, item) -> 'Tuple[str, str]':
        label = item.get("label")
        # kind = item.get("kind")
        detail = item.get("detail")
        insertText = None
        if item.get("insertTextFormat") == 2:
            insertText = item.get("insertText")
        return ("{}\t{}".format(label, detail), insertText
                if insertText else label)

    def handle_response(self, response):
        items = response["items"] if isinstance(response,
                                                dict) else response
        self.completions = list(self.format_completion(item) for item in items)
        self.run_auto_complete()

    def run_auto_complete(self):
        self.refreshing = True
        sublime.active_window().active_view().run_command(
            "auto_complete", {
                'disable_auto_insert': True,
                'api_completions_only': False,
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
        return is_supported_syntax(syntax)

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
                    css=".mdpopups .lsp_signature { margin: 4px; }",
                    md=True,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    wrapper_class="lsp_signature",
                    max_width=800)


def get_line_diagnostics(view: sublime.View, row: int, col: int) -> 'List[Diagnostic]':
    line_diagnostics = []
    file_diagnostics = window_file_diagnostics.get(view.window().id(), {})
    if view.file_name() in file_diagnostics:
        source_diagnostics = file_diagnostics[view.file_name()]
        diagnostics = source_diagnostics.get('lsp', [])
        if len(diagnostics) > 0:
            for diagnostic in diagnostics:
                (start_line, _) = diagnostic.range.start
                (end_line, _) = diagnostic.range.end
                if row >= start_line and row <= end_line:
                    line_diagnostics.append(diagnostic)
    return line_diagnostics


class LspCodeActionsCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            return client and client.has_capability('codeActionProvider')
        return False

    def run(self, edit, event=None):
        client = client_for_view(self.view)
        if client:
            pos = get_position(self.view, event)
            row, col = self.view.rowcol(pos)
            line_diagnostics = get_line_diagnostics(self.view, row, col)
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
                params["range"] = make_lsp_range((row, col), (row, col))

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
        range = Range.from_lsp(change.get('range'))
        start_position = self.view.text_point(*range.start)
        end_position = self.view.text_point(*range.end)
        return sublime.Region(start_position, end_position)

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
        sublime.set_timeout_async(check_window_unloaded, 500)


class SaveListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        if is_supported_view(view):
            # debug("on_post_save_async", view.file_name())
            Events.publish("view.on_post_save_async", view)

    def on_close(self, view):
        if is_supported_view(view):
            # TODO check if more views are open for this file.
            Events.publish("view.on_close", view)


def is_transient_view(view):
    window = view.window()
    return view == window.transient_view_in_group(window.active_group())


class DocumentSyncListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return is_supported_syntax(syntax)

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
