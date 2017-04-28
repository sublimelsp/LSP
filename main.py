import sublime_plugin
import sublime
import subprocess
import threading
import json
import os
import sys
import urllib.request as urllib
from urllib.parse import urljoin
import html
import mdpopups

PLUGIN_NAME = 'LSP'
SUBLIME_WORD_MASK = 515


class Config(object):
    def __init__(self, name, binary_args, scopes, syntaxes):
        self.name = name
        self.binary_args = binary_args
        self.scopes = scopes
        self.syntaxes = syntaxes


jsts_command = "javascript-typescript-stdio"
if os.name == 'nt':
    jsts_command = "javascript-typescript-stdio.cmd"

configs = [
    Config(
        'jsts',
        [jsts_command],
        ['source.ts'],
        ['Packages/TypeScript-TmLanguage/TypeScript.tmLanguage']
    ),
    Config(
        'rls',
        ["rustup", "run", "nightly", "rls"],
        ["source.rust"],
        ['Packages/Rust/Rust.sublime-syntax'])
]


def format_request(request):
    """Converts the request into json and adds the Content-Length header"""
    content = json.dumps(request, indent=2)
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
        self.handlers = {}
        self.capabilities = {}

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities

    def has_capability(self, capability):
        return capability in self.capabilities

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def send_request(self, request, handler):
        self.request_id += 1
        request.id = self.request_id
        if handler is not None:
            self.handlers[request.id] = handler
        self.send_call(request)

    def send_notification(self, notification):
        self.send_call(notification)

    def send_call(self, payload):
        try:
            debug(payload)
            message = format_request(payload.__dict__)
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

                    if (header.startswith(ContentLengthHeader)):
                        content_length = int(header[len(ContentLengthHeader):])

                if (content_length > 0):
                    content = self.process.stdout.read(content_length).decode("UTF-8")
                    # debug(content)

                    payload = None
                    try:
                        payload = json.loads(content)
                        limit = min(len(content), 200)
                        if payload.get("method") != "window/logMessage":
                            debug("got json: ", content[0:limit])
                    except:
                        printf("Got a non-JSON payload: ", content)
                        continue

                    try:
                        if "error" in payload:
                            debug("got error: ", payload.get("error"))
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

            except:
                printf("LSP stdout process ending due to exception: ", sys.exc_info())
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
                    printf("LSP error: ", error)
            except:
                printf("LSP stderr process ending due to exception: ", sys.exc_info())
                return

        debug("LSP stderr process ended.")

    def response_handler(self, response):
        # todo: try catch ?
        if (self.handlers[response.get("id")]):
            self.handlers[response.get("id")](response.get("result"))
        else:
            debug("No handler found for id" + response.get("id"))

    def request_handler(self, request):
        method = request.get("method")
        if method == "workspace/applyEdit":
            apply_workspace_edit(sublime.active_window(), request.get("params"))
        else:
            debug("Unhandled request", method)

    def notification_handler(self, response):
        method = response.get("method")
        if method == "textDocument/publishDiagnostics":
            Events.publish("document.diagnostics", response.get("params"))
        elif method == "window/showMessage":
            sublime.active_window().message_dialog(response.get("params").get("message"))
        elif method == "window/logMessage":
            server_log(self.process.args[0], response.get("params").get("message"))
        else:
            debug("Unhandled notification:", method)



def debug(*args):
    """Print args to the console if the "debug" setting is True."""
    # if settings.get('debug'):
    printf(*args)


def server_log(binary, *args):
    print(binary + ': ', end='')

    for arg in args:
        print(arg, end=' ')

    print()


def printf(*args):
    """Print args to the console, prefixed by the plugin name."""
    print(PLUGIN_NAME + ': ', end='')

    for arg in args:
        print(arg, end=' ')

    print()


def first_folder(window):
    """
    We only support running one stack-ide instance per window currently,
    on the first folder open in that window.
    """
    if len(window.folders()):
        return window.folders()[0]
    else:
        debug("Couldn't determine project directory")
        return None


def plugin_loaded():
    Events.subscribe("view.on_load_async", initialize_on_open)
    Events.subscribe("view.on_activated_async", initialize_on_open)
    debug("plugin loaded")


def plugin_unloaded():
    for window in sublime.windows():
        for client in window_clients(window).values():
            client.send_notification(Notification.exit())
    debug("plugin unloaded")


def config_for_scope(view):
    for config in configs:
        for scope in config.scopes:
            if view.match_selector(view.sel()[0].begin(), scope):
                return config
    return None


def is_supported_syntax(syntax):
    for config in configs:
        if syntax in config.syntaxes:
            return True
    return False


def is_supported_view(view):
    # TODO: perhaps make this check for a client instead of a config
    if config_for_scope(view):
        return True
    else:
        return False

    # for supported_scope in supported_scopes:
    #     if view.match_selector(view.sel()[0].begin(), supported_scope):
    #         return True
    # return False


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2

didopen_after_initialize = list()
unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


def filename_to_uri(path):
    return urljoin('file:', urllib.pathname2url(path))


def uri_to_filename(uri):
    if os.name == 'nt':
        return urllib.url2pathname(uri.replace("file://", ""))
    else:
        return urllib.url2pathname(uri).replace("file://", "")


def client_for_view(view):
    config = config_for_scope(view)
    if not config:
        debug("config not available for view", view.file_name())
        return None
    clients = window_clients(view.window())
    if config.name not in clients:
        debug(config.name, "not available for view", view.file_name(), "in window", view.window().id())
    else:
        return clients[config.name]


clients_by_window = {}

def window_clients(window):
    global clients_by_window
    if window.id() in clients_by_window:
        return clients_by_window[window.id()]
    else:
        debug("no clients found for window", window.id())
        return {}


def initialize_on_open(view):
    global didopen_after_initialize
    config = config_for_scope(view)
    if config:
        if config.name not in window_clients(view.window()):
            didopen_after_initialize.append(view)
            get_window_client(view, config)


def notify_did_open(view):
    client = client_for_view(view)
    if view.file_name() not in document_states:
        get_document_state(view.file_name())
        params = {
            "textDocument": {
               "uri": filename_to_uri(view.file_name()),
               "languageId": "ts",
               "text": view.substr(sublime.Region(0, view.size()))
            }
        }
        client.send_notification(Notification.didOpen(params))


def notify_did_close(view):
    config = config_for_scope(view)
    clients = window_clients(sublime.active_window())
    if config and config.name in clients:
        client = clients[config.name]
        params = {
            "textDocument": {
                "uri": filename_to_uri(view.file_name())
            }
        }
        client.send_notification(Notification.didClose(params))


def notify_did_save(view):
    client = client_for_view(view)
    params = {
        "textDocument": {
            "uri": filename_to_uri(view.file_name())
        }
    }
    client.send_notification(Notification.didSave(params))


documentVersion = 0
document_states = {}


class DocumentState:
    def __init__(self, path):
        self.path = path
        self.version = 0

    def inc_version(self):
        self.version += 1
        return self.version


def get_document_state(path):
    if path not in document_states:
        document_states[path] = DocumentState(path)
    return document_states.get(path)


pending_buffer_changes = dict()


def queue_did_change(view):
    buffer_id = view.buffer_id()
    buffer_version = 1
    if buffer_id in pending_buffer_changes:
        pending_buffer = pending_buffer_changes[buffer_id]
        buffer_version = pending_buffer["version"] + 1
        pending_buffer["version"] = buffer_version
    else:
        pending_buffer_changes[buffer_id] = {"view": view, "version": buffer_version}

    sublime.set_timeout(lambda: purge_did_change(buffer_id, buffer_version), 500)


def purge_did_change(buffer_id, buffer_version=None):
    if buffer_id in pending_buffer_changes:
        pending_buffer = pending_buffer_changes[buffer_id]
        if buffer_version is None or buffer_version == pending_buffer["version"]:
            notify_did_change(pending_buffer["view"])


def notify_did_change(view):
    if view.buffer_id() in pending_buffer_changes:
        del pending_buffer_changes[view.buffer_id()]
    client = client_for_view(view)
    document_state = get_document_state(view.file_name())
    params = {
        "textDocument": {
           "uri": filename_to_uri(view.file_name()),
           "languageId": "ts",
           "version": document_state.inc_version(),
        },
        "contentChanges": [{
            "text": view.substr(sublime.Region(0, view.size()))
        }]
    }
    client.send_notification(Notification.didChange(params))


def initialize_document_sync(text_document_sync_kind):
    Events.subscribe('view.on_load_async', notify_did_open)
    Events.subscribe('view.on_activated_async', notify_did_open)
    Events.subscribe('view.on_modified_async', queue_did_change)
    Events.subscribe('view.on_post_save_async', notify_did_save)
    Events.subscribe('view.on_close', notify_did_close)


# TODO fix all these globals (they should be capabilities stored on the client)

def handle_initialize_result(result, client):
    global didopen_after_initialize
    capabilities = result.get("capabilities")
    client.set_capabilities(capabilities)

    # TODO: These handlers is already filtered by syntax but does not need to be enabled 2x per client
    # Move filtering?
    document_sync = capabilities.get("textDocumentSync")
    if document_sync:
        initialize_document_sync(document_sync)

    Events.subscribe('document.diagnostics', handle_diagnostics)
    for view in didopen_after_initialize:
        notify_did_open(view)
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


def create_phantom_html(text):
    global stylesheet
    return """<body id=inline-error>{}
                <div class="error">
                    <span class="message">{}</span>
                    <a href=hide>{}</a>
                </div>
                </body>""".format(stylesheet, html.escape(text, quote=False), chr(0x00D7))


def create_phantom(view, diagnostic):
    region = create_region(view, diagnostic)
    # TODO: hook up hide phantom (if keeping them)
    return sublime.Phantom(region, '<p>' + create_phantom_html(diagnostic.get('message')) + '</p>', sublime.LAYOUT_BELOW)


def create_region(view, diagnostic):
    start = diagnostic.get('range').get('start')
    end = diagnostic.get('range').get('end')
    region = sublime.Region(view.text_point(start.get('line'), start.get('character')),
                            view.text_point(end.get('line'), end.get('character')))
    return region


def build_location_severity_message(diagnostic):
    start = diagnostic.get('range').get('start')
    line = start.get('line') or 0
    character = start.get('character') or 0
    level = "error"
    return ((line, character), level, diagnostic.get('message'))


def build_diagnostic(file_path, diagnostic):
    start = diagnostic.get('range').get('start')
    line = start.get('line') or 0
    character = start.get('character') or 0
    level = "error"
    source = "lsp"
    return format_diagnostic(line, character, source, level, diagnostic.get('message'))
    #return "\t{}:{}\t{}\t{}\t{}".format(line + 1, character + 1, source, level, diagnostic.get('message'))

def format_diagnostic(line, character, source, level, message):
    location = "{}:{}".format(line + 1, character + 1)
    return "\t{:<8}\t{:<8}\t{:<8}\t{}".format(location, source, level, message)

class SymbolRenameCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        # TODO: check what kind of scope we're in.
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client.has_capability('renameProvider'):
                point = self.view.sel()[0].begin()
                word_at_sel = self.view.classify(point)
                if word_at_sel & SUBLIME_WORD_MASK:
                    return True
        return False

    def run(self, edit):
        pos = self.view.sel()[0].begin()
        params = get_document_position(self.view, pos)
        sublime.active_window().show_input_panel("New name:", "", lambda text: self.request_rename(params, text), None, None)

    def request_rename(self, params, new_name):
        client = client_for_view(self.view)
        params["newName"] = new_name
        client.send_request(Request.rename(params),
                            lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        debug(response)


class SymbolDefinitionCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        # TODO: check what kind of scope we're in.
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client.has_capability('definitionProvider'):
                point = self.view.sel()[0].begin()
                word_at_sel = self.view.classify(point)
                if word_at_sel & SUBLIME_WORD_MASK:
                    return True
        return False

    def run(self, edit):
        client = client_for_view(self.view)
        pos = self.view.sel()[0].begin()
        client.send_request(Request.definition(get_document_position(self.view, pos)),
                            lambda response: self.handle_response(response, pos))

    def handle_response(self, response, position):
        window = sublime.active_window()
        if len(response) < 1:
                # view.set_status("diagnostics", "{} errors".format(len(diagnostics)))
            self.view.set_status("definition", "Could not find definition")
        else:
            location = response[0]
            file_path = uri_to_filename(location.get("uri"))
            start = location.get('range').get('start')
            file_location = "{}:{}:{}".format(file_path, start.get('line') + 1, start.get('character') + 1)
            debug("opening location", location)
            window.open_file(file_location, sublime.ENCODED_POSITION)
            # TODO: can add region here.


class SymbolReferencesCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('referencesProvider'):
                point = self.view.sel()[0].begin()
                word_at_sel = self.view.classify(point)
                if word_at_sel & SUBLIME_WORD_MASK:
                    return True
        return False


    def run(self, edit):
        client = client_for_view(self.view)
        pos = self.view.sel()[0].begin()
        client.send_request(Request.references(get_document_position(self.view, pos)),
                            lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        window = sublime.active_window()
        references = list(format_reference(item) for item in response)

        if (len(response)) > 0:
            panel = window.find_output_panel("references")
            if panel is None:
                # debug("creating panel")
                panel = window.create_output_panel("references")
                panel.settings().set("result_file_regex", r"^(.*)\t([0-9]+):?([0-9]+)$")

            panel.run_command("clear_error_panel")

            window.run_command("show_panel", {"panel": "output.references"})
            for reference in references:
                panel.run_command('append', {'characters': reference + "\n", 'force': True, 'scroll_to_end': True})

        else:
            window.run_command("hide_panel", {"panel": "output.references"})


def format_reference(reference):
    start = reference.get('range').get('start')
    file_path = uri_to_filename(reference.get("uri"))
    return "{}\t{}:{}".format(file_path, start.get('line') + 1, start.get('character') + 1)


class ClearErrorPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_error_panel command to clear the error panel.
    """
    def run(self, edit):
        self.view.erase(edit, sublime.Region(0, self.view.size()))


UNDERLINE_FLAGS = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_EMPTY_AS_OVERWRITE


window_file_diagnostics = dict()

def update_file_diagnostics(window, relative_file_path, source, location_severity_messages):
    # debug("window", window.id(), "updating", relative_file_path, "from", source, "with", location_severity_messages)
    if location_severity_messages:
        window_file_diagnostics.setdefault(window.id(), dict()).setdefault(relative_file_path, dict())[source] = location_severity_messages
        # file_diagnostics.setdefault(relative_file_path, dict())[source] = location_severity_messages
    else:
        if window.id() in window_file_diagnostics:
            file_diagnostics = window_file_diagnostics[window.id()]
            if relative_file_path in file_diagnostics:
                if source in file_diagnostics[relative_file_path]:
                    del file_diagnostics[relative_file_path][source]
                if not file_diagnostics[relative_file_path]:
                    del file_diagnostics[relative_file_path]


def update_view_diagnostics(view, source, location_severity_messages):
    window = view.window()
    base_dir = first_folder(window)
    relative_file_path = os.path.relpath(view.file_name(), base_dir)
    update_file_diagnostics(window, relative_file_path, source, location_severity_messages)
    update_output_panel(window)

phantom_sets_by_buffer = {}

file_diagnostics = {}

def handle_diagnostics(update):
    global phantom_sets_by_buffer
    #debug(update)
    file_path = uri_to_filename(update.get('uri'))
    window = sublime.active_window()

    diagnostics = update.get('diagnostics')
    phantoms = list()
    regions = list()

    view = window.find_open_file(file_path)
    if view is not None:
        if view.is_dirty():
            regions = list(create_region(view, diagnostic) for diagnostic in diagnostics)
        else:
            phantoms = list(create_phantom(view, diagnostic) for diagnostic in diagnostics)

        buffer_id = view.buffer_id()
        if buffer_id not in phantom_sets_by_buffer:
            phantom_set = sublime.PhantomSet(view, "diagnostics")
            phantom_sets_by_buffer[buffer_id] = phantom_set
        else:
            phantom_set = phantom_sets_by_buffer[buffer_id]

        phantom_set.update(phantoms)

        if (len(regions)) > 0:
            # steal SublimeLinter's coloring.
            view.add_regions("errors", regions, "sublimelinter.mark.error", "dot", sublime.DRAW_SQUIGGLY_UNDERLINE | UNDERLINE_FLAGS)
        else:
            view.erase_regions("errors")

    base_dir = first_folder(window)
    relative_file_path = os.path.relpath(file_path, base_dir)
    file_diagnostics[file_path] = diagnostics

    location_severity_messages = list(build_location_severity_message(diagnostic) for diagnostic in diagnostics)
    update_file_diagnostics(window, relative_file_path, 'lsp', location_severity_messages)
    update_output_panel(window)


def update_output_panel(window):
    base_dir = first_folder(window)
    panel = window.find_output_panel("diagnostics")
    if panel is None:
        panel = window.create_output_panel("diagnostics")
        panel.settings().set("result_file_regex", r"^(.*):$")
        panel.settings().set("result_line_regex", r"^\t([0-9]+):?([0-9]+)\s*\t.*\t.*\t(.*)$")
        panel.settings().set("result_base_dir", base_dir)
        panel.settings().set("line_numbers", False)
        panel.assign_syntax("Packages/" + PLUGIN_NAME + "/Diagnostics.sublime-syntax")

        # Call create_output_panel a second time after assigning the above
        # settings, so that it'll be picked up as a result buffer
        window.create_output_panel("diagnostics")
    else:
        panel.run_command("clear_error_panel")
        window.run_command("show_panel", {"panel": "output.diagnostics"})

    if window.id() in window_file_diagnostics:
        file_diagnostics = window_file_diagnostics[window.id()]
        if file_diagnostics:
            for file_path, source_diagnostics in file_diagnostics.items():
                if source_diagnostics:
                    panel.run_command('append', {'characters': file_path + ":\n", 'force': True})
                    # debug("source diagnostics for", file_path, source_diagnostics)
                    for source, location_severity_messages in source_diagnostics.items():
                        for location, severity, message in location_severity_messages:
                            line, character = location
                            item = format_diagnostic(line, character, source, severity, message)
                            panel.run_command('append', {'characters': item + "\n", 'force': True, 'scroll_to_end': True})
        else:
            window.run_command("hide_panel", {"panel": "output.diagnostics"})


def start_client(window, config):
    project_path = first_folder(window)
    client = start_server(config.binary_args, project_path)
    initializeParams = {
        "processId": client.process.pid,
        "rootUri": filename_to_uri(project_path),
        # "rootPath": project_path,
        "capabilities": {
            "completion": {
                "completionItem": {
                    "snippetSupport": True
                }
            }
        }
    }
    client.send_request(Request.initialize(initializeParams),
                        lambda result: handle_initialize_result(result, client))
    return client


def get_window_client(view, config):
    global clients_by_window

    window = view.window()
    clients = window_clients(window)
    if config.name not in clients:
        project_path = first_folder(window)
        client = start_client(window, config)
        clients_by_window.setdefault(window.id(), {})[config.name] = client
        debug("client registered for window", window.id(), window_clients(window))
    else:
        client = clients[config.name]

    return client


def start_server(server_binary_args, working_dir):
    args = server_binary_args
    debug("starting " + str(args))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_dir,
            startupinfo=si
        )
        return Client(process)

    except Exception as err:
        print(err)

def get_document_range(view):
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
    if (point):
        (row, col) = view.rowcol(point)
    else:
        view.sel()
    return {
        "textDocument": {
            "uri": filename_to_uri(view.file_name())
        },
        "position": {
            "line": row,
            "character": col
        }
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

    def __repr__(self):
        return self.method + " " + str(self.params)


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


class Events:
    listener_dict = dict()

    @classmethod
    def subscribe(cls, key, listener):
        if key in cls.listener_dict:
            cls.listener_dict[key].append(listener)
        else:
            cls.listener_dict[key] = [listener]
        return lambda : cls.unsubscribe(key, listener)

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
                client.send_request(Request.hover(get_document_position(self.view, point)),
                                    lambda response: self.handle_response(response, point))

    def handle_response(self, response, point):
        # debug(response)
        contents = response.get('contents')
        if len(contents) < 1:
            return
        formatted = []
        for item in contents:
            if isinstance(item, str):
                formatted.append(item)
            else:
                value = item.get("value")
                language = item.get("language")
                if language:
                    formatted.append("```{}\n{}\n```".format(language, value))
                else:
                    formatted.append(value)

        mdpopups.show_popup(self.view, "\n".join(formatted), css=".mdpopups .lsp_hover { margin: 4px; }", md=True, flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY, location=point, wrapper_class="lsp_hover", max_width=800)



class CompletionHandler(sublime_plugin.EventListener):
    def __init__(self):
        self.completions = []
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
                prev_char = view.substr(sublime.Region(locations[0] - 1, locations[0]))
                if prev_char not in autocomplete_triggers:
                    return None

            purge_did_change(view.buffer_id())
            client.send_request(Request.complete(get_document_position(view, locations[0])), self.handle_response)

        self.refreshing = False
        return self.completions, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

    def format_completion(self, item):
        label = item.get("label")
        kind = item.get("kind")
        detail = item.get("detail")
        insertText = None
        if item.get("insertTextFormat") == 2:
            insertText = item.get("insertText")
        return ("{}\t{}".format(label, detail), insertText if insertText else label)

    def handle_response(self, response):
        items = response.get("items") if isinstance(response, dict) else response
        self.completions = list(self.format_completion(item) for item in items)
        self.run_auto_complete()

    def run_auto_complete(self):
        self.refreshing = True
        sublime.active_window().active_view().run_command("auto_complete", {
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
            signatureHelpProvider = client.get_capability('signatureHelpProvider')
            if signatureHelpProvider:
                self.signature_help_triggers = signatureHelpProvider.get('triggerCharacters')
                return

        self.signature_help_triggers = []


    def on_modified_async(self):
        pos = self.view.sel()[0].begin()
        last_char = self.view.substr(pos - 1)
        # TODO: this will fire too often, narrow down using scopes or regex
        if self.signature_help_triggers is None:
            self.initialize_triggers()

        if last_char in self.signature_help_triggers:
            client = client_for_view(self.view)
            purge_did_change(self.view.buffer_id())
            client.send_request(Request.signatureHelp(get_document_position(self.view, pos)),
                                lambda response: self.handle_response(response, pos))
        else:
            # TODO: this hides too soon.
            if self.view.is_popup_visible():
                self.view.hide_popup()

    def handle_response(self, response, point):
        signatures = response.get("signatures")
        debug(signatures)
        if len(signatures) > 0:
            signature = signatures[response.get("activeSignature")]
            formatted = []
            formatted.append("```{}\n{}\n```".format("typescript", signature.get('label')))
            for parameter in signature.get('parameters'):
                paramDocs = parameter.get('documentation')
                formatted.append("**{}**\n".format(parameter.get('label')))
                if paramDocs:
                    formatted.append("* *{}*\n".format(paramDocs))

            formatted.append("&nbsp;")
            formatted.append(signature.get('documentation'))

            mdpopups.show_popup(self.view, "\n".join(formatted), css=".mdpopups .lsp_signature { margin: 4px; }", md=True, flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY, location=point, wrapper_class="lsp_signature", max_width=800)


class FixDiagnosticCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return True
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('codeActionProvider'):
                return True
        return True
        #         point = self.view.sel()[0].begin()
        #         word_at_sel = self.view.classify(point)
        #         if word_at_sel & SUBLIME_WORD_MASK:
        #             return True
        # return False


    def run(self, edit):
        client = client_for_view(self.view)
        # get current diagnostic from cursor position (how does sublimelinter do this?)
        # for now just use the first diagnostic in the document
        if self.view.file_name() in file_diagnostics:
            diagnostics = file_diagnostics[self.view.file_name()]
            if len(diagnostics) > 0:
                diagnostic = diagnostics[0]
                params = {
                    "textDocument": {
                        "uri": filename_to_uri(self.view.file_name())
                    },
                    "range": diagnostic.get('range'),
                    "context": {
                        "diagnostics": [diagnostic]
                    }
                }
                client.send_request(Request.codeAction(params), self.handle_codeaction_response)


    def handle_codeaction_response(self, response):
        titles = []
        debug(response)
        self.commands = response
        for command in self.commands:
            titles.append(command.get('title')) # TODO parse command and arguments
        if len(self.commands) > 0:
            self.view.show_popup_menu(titles, self.handle_select)


    def handle_select(self, index):
        client = client_for_view(self.view)
        client.send_request(Request.executeCommand(self.commands[index]), self.handle_command_response)


    def handle_command_response(self, response):
        pass
        # debug('executeCommand response:', response)


def apply_workspace_edit(window, params):
    edit = params.get('edit')
    window.run_command('apply_workspace_edit', {'changes': edit})

class ApplyWorkspaceEditCommand(sublime_plugin.WindowCommand):
    def run(self, changes):
        debug('workspace edit', changes)
        # for document_edit in changes.get('documentChanges') or []:
        #     document = document_edit.get('textDocument')
        #     path = uri_to_filename(document.get('uri'))
        #     edits = document_edit.get('edits')
        #     for edit in edits:
        #         range = edit.get('range')
        #         newText = edit.get('newText')
        if changes.get('changes'):
            for uri, file_changes in changes.get('changes').items():
                path = uri_to_filename(uri)
                view = self.window.open_file(path)
                if view:
                    if view.is_loading():
                        # TODO: schedule
                        debug('view not ready', view)
                    else:
                        view.run_command('apply_document_edit', {'changes': file_changes})
                else:
                    debug('view not found to apply', path, file_changes)


class ApplyDocumentEditCommand(sublime_plugin.TextCommand):
    def run(self, edit, changes):
        for change in changes:
            newText = change.get('newText')
            # TODO create a Range type
            start = change.get('range').get('start')
            end = change.get('range').get('end')
            start_position = self.view.text_point(start.get('line'), start.get('character'))
            end_position = self.view.text_point(end.get('line'), end.get('character'))
            region = sublime.Region(start_position, end_position)
            if region.empty():
                self.view.insert(edit, start_position, newText)
            else:
                if len(newText) > 0:
                    self.view.replace(edit, region, newText)
                else:
                    self.view.erase(edit, region)


class SaveListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        if is_supported_view(view):
            # debug("on_post_save_async", view.file_name())
            Events.publish("view.on_post_save_async", view)

    def on_close(self, view):
        if is_supported_view(view):
            #TODO check if more views are open for this file.
            Events.publish("view.on_close", view)


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
        # debug("on_load_async", self.view.file_name())
        Events.publish("view.on_load_async", self.view)


    def on_modified_async(self):
        if self.view.file_name():
            # debug("on_modified_async", self.view.file_name())
            Events.publish("view.on_modified_async", self.view)

    def on_activated_async(self):
        if self.view.file_name():
            # debug("on_activated_async", self.view.file_name())
            Events.publish("view.on_activated_async", self.view)

