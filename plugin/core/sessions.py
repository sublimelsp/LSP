from .types import ClientConfig, ClientStates, Settings
from .protocol import Request
from .transports import start_tcp_transport, start_tcp_listener, TCPTransport, Transport
from .rpc import Client, attach_stdio_client
from .process import start_server
from .logging import debug
import os
from .protocol import completion_item_kinds, symbol_kinds
try:
    from typing import Callable, Dict, Any, Optional, Iterable, Union, List
    from .workspace import Workspace
    from .types import WindowLike
    assert Callable and Dict and Any and Optional and Iterable and Transport and Union and List
    assert Workspace
    assert WindowLike
except ImportError:
    pass


def create_session(window: 'WindowLike',
                   config: ClientConfig,
                   workspaces: 'Optional[Iterable[Workspace]]',
                   env: dict,
                   settings: Settings,
                   on_pre_initialize: 'Optional[Callable[[Session], None]]' = None,
                   on_post_initialize: 'Optional[Callable[[Session], None]]' = None,
                   on_post_exit: 'Optional[Callable[[str], None]]' = None,
                   bootstrap_client: 'Optional[Any]' = None) -> 'Optional[Session]':

    def with_client(client: Client) -> 'Session':
        return Session(
            config=config,
            workspaces=workspaces,
            client=client,
            on_pre_initialize=on_pre_initialize,
            on_post_initialize=on_post_initialize,
            on_post_exit=on_post_exit)

    session = None
    if config.binary_args:
        tcp_port = config.tcp_port
        server_args = config.binary_args

        if config.tcp_mode == "host":
            socket = start_tcp_listener(tcp_port or 0)
            tcp_port = socket.getsockname()[1]
            server_args = list(s.replace("{port}", str(tcp_port)) for s in config.binary_args)

        process = start_server(window, config, server_args, env, settings.log_stderr)
        if process:
            if config.tcp_mode == "host":
                client_socket, address = socket.accept()
                transport = TCPTransport(client_socket)  # type: Transport
                session = with_client(Client(transport, settings))
            elif tcp_port:
                transport = start_tcp_transport(tcp_port, config.tcp_host)
                if transport:
                    session = with_client(Client(transport, settings))
                else:
                    # try to terminate the process
                    try:
                        process.terminate()
                    except Exception:
                        pass
            else:
                session = with_client(attach_stdio_client(process, settings))
    else:
        if config.tcp_port:
            transport = start_tcp_transport(config.tcp_port)
            session = with_client(Client(transport, settings))
        elif bootstrap_client:
            session = with_client(bootstrap_client)
        else:
            debug("No way to start session")
    return session


def get_initialize_params(workspaces: 'Optional[Iterable[Workspace]]', config: ClientConfig) -> dict:
    root_uri = None
    lsp_workspaces = None
    if workspaces is not None:
        root_uri = next(iter(workspaces)).uri
        lsp_workspaces = [workspace.to_dict() for workspace in workspaces]
    debug("starting session in", lsp_workspaces)
    initializeParams = {
        "processId": os.getpid(),
        "rootUri": root_uri,
        "workspaceFolders": lsp_workspaces,
        "capabilities": {
            "textDocument": {
                "synchronization": {
                    "didSave": True,
                    "willSaveWaitUntil": True
                },
                "hover": {
                    "contentFormat": ["markdown", "plaintext"]
                },
                "completion": {
                    "completionItem": {
                        "snippetSupport": True
                    },
                    "completionItemKind": {
                        "valueSet": completion_item_kinds
                    }
                },
                "signatureHelp": {
                    "signatureInformation": {
                        "documentationFormat": ["markdown", "plaintext"],
                        "parameterInformation": {
                            "labelOffsetSupport": True
                        }
                    }
                },
                "references": {},
                "documentHighlight": {},
                "documentSymbol": {
                    "symbolKind": {
                        "valueSet": symbol_kinds
                    }
                },
                "formatting": {},
                "rangeFormatting": {},
                "declaration": {},
                "definition": {},
                "typeDefinition": {},
                "implementation": {},
                "codeAction": {
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": []
                        }
                    }
                },
                "rename": {},
                "colorProvider": {}
            },
            "workspace": {
                "applyEdit": True,
                "didChangeConfiguration": {},
                "executeCommand": {},
                "symbol": {
                    "symbolKind": {
                        "valueSet": symbol_kinds
                    }
                },
                "workspaceFolders": True
            }
        }
    }  # type: Dict[str, Union[None, int, str, Dict[str, Any], List]]
    if config.init_options:
        initializeParams['initializationOptions'] = config.init_options

    return initializeParams


class Session(object):
    def __init__(self,
                 config: ClientConfig,
                 workspaces: 'Optional[Iterable[Workspace]]',
                 client: Client,
                 on_pre_initialize: 'Optional[Callable[[Session], None]]' = None,
                 on_post_initialize: 'Optional[Callable[[Session], None]]' = None,
                 on_post_exit: 'Optional[Callable[[str], None]]' = None) -> None:
        self.config = config
        self.state = ClientStates.STARTING
        self._on_post_initialize = on_post_initialize
        self._on_post_exit = on_post_exit
        self.capabilities = dict()  # type: Dict[str, Any]
        self.client = client
        if on_pre_initialize:
            on_pre_initialize(self)
        self.initialize(workspaces)

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability: str) -> 'Optional[Any]':
        return self.capabilities.get(capability)

    def initialize(self, workspaces: 'Optional[Iterable[Workspace]]') -> None:
        params = get_initialize_params(workspaces, self.config)
        self.client.send_request(Request.initialize(params), self._handle_initialize_result)

    def _handle_initialize_result(self, result: 'Any') -> None:
        self.state = ClientStates.READY
        self.capabilities = result.get('capabilities', dict())
        if self._on_post_initialize:
            self._on_post_initialize(self)

    def end(self) -> None:
        self.state = ClientStates.STOPPING
        self.client.send_request(
            Request.shutdown(),
            lambda result: self._handle_shutdown_result(),
            lambda error: self._handle_shutdown_result())

    def _handle_shutdown_result(self) -> None:
        self.client.exit()
        self.client = None  # type: ignore
        self.capabilities = dict()
        if self._on_post_exit:
            self._on_post_exit(self.config.name)
