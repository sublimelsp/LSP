from .types import ClientConfig, ClientStates, Settings
from .protocol import Request
from .transports import start_tcp_transport, start_tcp_listener, TCPTransport, Transport
from .rpc import Client, attach_stdio_client
from .process import start_server
from .url import filename_to_uri
from .logging import debug
import os
from .protocol import completion_item_kinds, symbol_kinds
try:
    from typing import Callable, Dict, Any, Optional, List
    assert Callable and Dict and Any and Optional and Transport and List
except ImportError:
    pass


def create_session(config: ClientConfig,
                   workspace_folders: 'List[str]',
                   env: dict,
                   settings: Settings,
                   on_pre_initialize: 'Optional[Callable[[Session], None]]' = None,
                   on_post_initialize: 'Optional[Callable[[Session], None]]' = None,
                   on_post_exit: 'Optional[Callable[[str], None]]' = None,
                   bootstrap_client: 'Optional[Any]' = None) -> 'Optional[Session]':

    def with_client(client: Client) -> 'Session':
        return Session(
            config=config,
            workspace_folders=workspace_folders,
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

        process = start_server(server_args, workspace_folders[0], env, settings.log_stderr)
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


def get_initialize_params(workspace_folders: 'List[str]', config: ClientConfig) -> dict:
    lsp_folders = [{"uri": filename_to_uri(f), "name": os.path.basename(f)} for f in workspace_folders]

    initializeParams = {
        "processId": os.getpid(),
        "rootUri": filename_to_uri(workspace_folders[0]),
        "rootPath": workspace_folders[0],
        "workspaceFolders": lsp_folders,
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
                "declaration": {"linkSupport": True},
                "definition": {"linkSupport": True},
                "typeDefinition": {"linkSupport": True},
                "implementation": {"linkSupport": True},
                "codeAction": {
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": []
                        }
                    }
                },
                "rename": {},
                "colorProvider": {},
                "publishDiagnostics": {
                    "relatedInformation": True
                }
            },
            "workspace": {
                "applyEdit": True,
                "didChangeConfiguration": {},
                "executeCommand": {},
                "workspaceFolders": True,
                "symbol": {
                    "symbolKind": {
                        "valueSet": symbol_kinds
                    }
                },
                "configuration": True
            }
        }
    }
    if config.init_options:
        initializeParams['initializationOptions'] = config.init_options

    return initializeParams


class Session(object):
    def __init__(self,
                 config: ClientConfig,
                 workspace_folders: 'List[str]',
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
        self._workspace_folders = workspace_folders  # TODO: perhaps not until initialized?
        if on_pre_initialize:
            on_pre_initialize(self)
        self._initialize()

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability: str) -> 'Optional[Any]':
        return self.capabilities.get(capability)

    def handles_path(self, file_path: 'Optional[str]') -> bool:
        if not file_path:
            return False

        for folder in self._workspace_folders:
            if file_path.startswith(folder):
                return True

        return False

    def _initialize(self) -> None:
        params = get_initialize_params(self._workspace_folders, self.config)
        self.client.send_request(
            Request.initialize(params),
            lambda result: self._handle_initialize_result(result))

    def _handle_initialize_result(self, result: 'Any') -> None:
        # only keep supported amount of folders
        self.capabilities = result.get('capabilities', dict())
        # 'capabilities': {'workspace': {'workspaceFolders': {'supported': True
        workspace_cap = self.capabilities.get("workspace", {})
        workspace_folder_cap = workspace_cap.get("workspaceFolders", {})
        if not workspace_folder_cap.get("supported"):
            self._workspace_folders = self._workspace_folders[:1]
            debug('single folder session:', self._workspace_folders[0])
        else:
            debug('multi folder session:', self._workspace_folders)
        self.state = ClientStates.READY
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
