from .types import ClientConfig, ClientStates
from .protocol import Request, Notification
from .transports import start_tcp_transport, StdioTransport
from .rpc import Client
from .process import start_server
from .url import filename_to_uri
import os
from .protocol import CompletionItemKind, SymbolKind
try:
    from typing import Callable, Dict, Any
    assert Callable and Dict and Any
except ImportError:
    pass


class ClientBootstrapper(object):
    def __init__(self):
        self._callback = None
        pass

    def when_ready(self, receive_client):
        self._callback = receive_client

# todo: make some provider-like pattern so these can be composable?


class TCPOnlyBootstrapper(ClientBootstrapper):
    def __init__(self, port, settings):
        self._port = port
        self._settings = settings

    def when_ready(self, receive_client):
        transport = start_tcp_transport(self._port)
        if transport:
            receive_client(Client(transport, self._settings))


class ProcessManager(object):
    def __init__(self, config: ClientConfig, project_path, env) -> None:
        self._config = config
        self._project_path = project_path
        self._env = env

    def start(self, receive_process):
        # see start_server from main.py - move this to process.py
        process = start_server(self._config.binary_args, self._project_path, self._env)
        if process:
            receive_process(process)


class StdioServerBootstrapper(ClientBootstrapper):
    def __init__(self, process_manager, settings):
        self._process_manager = process_manager
        self._client_receiver = None
        self._settings = settings

    def when_ready(self, receive_client):
        self._client_receiver = receive_client
        self._process_manager.start(lambda process: self._receive_process(process))

    def _receive_process(self, process):
        self._client_receiver(Client(StdioTransport(process), self._settings))


class TCPServerBootstrapper(ClientBootstrapper):
    def __init__(self, process_manager, port, settings):
        self._process_manager = process_manager
        self._port = port
        self._client_receiver = None
        self._process = None
        self._settings = settings

    def when_ready(self, receive_client):
        self._client_reciever = receive_client
        self._process_manager.start(lambda process: self._receive_process(process))

    def _receive_process(self, process):
        self._process = process
        transport = start_tcp_transport(self._port)
        self._client_receiver(Client(transport, self._settings))


def create_session(config: ClientConfig, project_path: str, env: dict, settings,
                   on_created=None, on_failed=None, bootstrap_client=None) -> 'Session':
    if config.binary_args:
        if config.tcp_port:
            # session = Session(project_path, ClientProvider(TcpTransportProvider(
            # ProcessProvider(config, project_path), config.tcp_port)))
            session = Session(config, project_path,
                              TCPServerBootstrapper(ProcessManager(config, project_path, env),
                                                    config.tcp_port,
                                                    settings), on_created, on_failed)
        else:
            session = Session(config, project_path,
                              StdioServerBootstrapper(ProcessManager(config, project_path, env),
                                                      settings), on_created, on_failed)
    else:
        if config.tcp_port:
            session = Session(config, project_path, TCPOnlyBootstrapper(config.tcp_port, settings),
                              on_created, on_failed)

        if bootstrap_client:
            session = Session(config, project_path, TestClientBootstrapper(bootstrap_client),
                              on_created, on_failed)
        else:
            raise Exception("No way to start session")

    # TODO: missing error notifications

    # if not process:
    #     window.status_message("Could not start " + config.name + ", disabling")
    #     debug("Could not start", config.binary_args, ", disabling")
    #     return None

    # if not client:
    #     window.status_message("Could not connect to " + config.name + ", disabling")
    #     return None

    # Finally, also remove this session if startup fails

    return session


class TestClientBootstrapper(ClientBootstrapper):
    def __init__(self, bootstrap_client):
        self._make_client = bootstrap_client

    def when_ready(self, receive_client):
        receive_client(self._make_client())


def get_initialize_params(project_path: str, config: ClientConfig):
    initializeParams = {
        "processId": os.getpid(),
        "rootUri": filename_to_uri(project_path),
        "rootPath": project_path,
        "capabilities": {
            "textDocument": {
                "synchronization": {
                    "didSave": True
                },
                "hover": {
                    "contentFormat": ["markdown", "plaintext"]
                },
                "completion": {
                    "completionItem": {
                        "snippetSupport": True
                    },
                    "completionItemKind": {
                        "valueSet": [
                            CompletionItemKind.Text,
                            CompletionItemKind.Method,
                            CompletionItemKind.Function,
                            CompletionItemKind.Constructor,
                            CompletionItemKind.Field,
                            CompletionItemKind.Variable,
                            CompletionItemKind.Class,
                            CompletionItemKind.Interface,
                            CompletionItemKind.Module,
                            CompletionItemKind.Property,
                            CompletionItemKind.Unit,
                            CompletionItemKind.Value,
                            CompletionItemKind.Enum,
                            CompletionItemKind.Keyword,
                            CompletionItemKind.Snippet,
                            CompletionItemKind.Color,
                            CompletionItemKind.File,
                            CompletionItemKind.Reference
                        ]
                    }
                },
                "signatureHelp": {
                    "signatureInformation": {
                        "documentationFormat": ["markdown", "plaintext"]
                    }
                },
                "references": {},
                "documentHighlight": {},
                "documentSymbol": {
                    "symbolKind": {
                        "valueSet": [
                            SymbolKind.File,
                            SymbolKind.Module,
                            SymbolKind.Namespace,
                            SymbolKind.Package,
                            SymbolKind.Class,
                            SymbolKind.Method,
                            SymbolKind.Property,
                            SymbolKind.Field,
                            # SymbolKind.Constructor,
                            # SymbolKind.Enum,
                            SymbolKind.Interface,
                            SymbolKind.Function,
                            SymbolKind.Variable,
                            SymbolKind.Constant
                            # SymbolKind.String,
                            # SymbolKind.Number,
                            # SymbolKind.Boolean,
                            # SymbolKind.Array
                        ]
                    }
                },
                "formatting": {},
                "rangeFormatting": {},
                "definition": {},
                "codeAction": {},
                "rename": {}
            },
            "workspace": {
                "applyEdit": True,
                "didChangeConfiguration": {}
            }
        }
    }
    if config.init_options:
        initializeParams['initializationOptions'] = config.init_options

    return initializeParams


class Session(object):
    def __init__(self, config: ClientConfig, project_path, bootstrapper: ClientBootstrapper,
                 on_created, on_failed) -> None:
        self.config = config
        self.project_path = project_path
        self.state = ClientStates.STARTING
        self._on_created = on_created
        self._on_failed = on_failed
        self.capabilities = dict()  # type: Dict[str, Any]
        self._bootstrapper = bootstrapper
        self._bootstrapper.when_ready(lambda client: self._receive_client(client))

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities

    def has_capability(self, capability):
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def _receive_client(self, client):
        self.client = client
        params = get_initialize_params(self.project_path, self.config)
        self.client.send_request(
            Request.initialize(params),
            lambda result: self._handle_initialize_result(result))

    def _handle_initialize_result(self, result):
        self.state = ClientStates.READY
        self.capabilities = result.get('capabilities', dict())
        if self._on_created:
            self._on_created(self)

    def end(self):
        self.state = ClientStates.STOPPING
        self.client.send_request(
            Request.shutdown(),
            lambda result: self._handle_shutdown_result(result))

    def _handle_shutdown_result(self, result):
        self.client.send_notification(Notification.exit())
        self.client = None
        self.capabilities = None
