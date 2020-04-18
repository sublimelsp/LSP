from .logging import debug
from .process import start_server
from .protocol import completion_item_kinds, symbol_kinds, WorkspaceFolder, Request, Notification
from .protocol import TextDocumentSyncKindNone
from .rpc import Client, attach_stdio_client, Response
from .transports import start_tcp_transport, start_tcp_listener, TCPTransport, Transport
from .types import ClientConfig, ClientStates, Settings
from .typing import Callable, Dict, Any, Optional, List, Tuple
from .workspace import is_subpath_of
import os


def get_initialize_params(workspace_folders: List[WorkspaceFolder], config: ClientConfig) -> dict:
    first_folder = workspace_folders[0] if workspace_folders else None
    capabilities = {
        "textDocument": {
            "synchronization": {
                "didSave": True,
                "willSave": True,
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

    if config.experimental_capabilities is not None:
        capabilities['experimental'] = config.experimental_capabilities

    initializeParams = {
        "processId": os.getpid(),
        "clientInfo": {
            "name": "Sublime Text LSP",
        },
        "rootUri": first_folder.uri() if first_folder else None,
        "rootPath": first_folder.path if first_folder else None,
        "workspaceFolders": [folder.to_lsp() for folder in workspace_folders] if workspace_folders else None,
        "capabilities": capabilities
    }
    if config.init_options is not None:
        initializeParams['initializationOptions'] = config.init_options

    return initializeParams


def diff_folders(old: List[WorkspaceFolder],
                 new: List[WorkspaceFolder]) -> Tuple[List[WorkspaceFolder], List[WorkspaceFolder]]:
    added = []  # type: List[WorkspaceFolder]
    removed = []  # type: List[WorkspaceFolder]
    for folder in old:
        if folder not in new:
            removed.append(folder)
    for folder in new:
        if folder not in old:
            added.append(folder)
    return added, removed


def get_dotted_value(current: Any, dotted: str) -> Any:
    keys = dotted.split('.')
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


class Session(object):
    def __init__(self,
                 config: ClientConfig,
                 workspace_folders: List[WorkspaceFolder],
                 client: Client,
                 on_pre_initialize: 'Optional[Callable[[Session], None]]' = None,
                 on_post_initialize: 'Optional[Callable[[Session], None]]' = None,
                 on_post_exit: Optional[Callable[[str], None]] = None) -> None:
        self.config = config
        self.state = ClientStates.STARTING
        self._on_post_initialize = on_post_initialize
        self._on_post_exit = on_post_exit
        self.capabilities = dict()  # type: Dict[str, Any]
        self.client = client
        self._workspace_folders = workspace_folders
        if on_pre_initialize:
            on_pre_initialize(self)
        self._initialize()

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability: str) -> Optional[Any]:
        return self.capabilities.get(capability)

    def should_notify_did_open(self) -> bool:
        textsync = self.capabilities.get('textDocumentSync')
        if isinstance(textsync, dict):
            return bool(textsync.get('openClose'))
        if isinstance(textsync, int):
            return textsync > TextDocumentSyncKindNone
        return False

    def text_sync_kind(self) -> int:
        textsync = self.capabilities.get('textDocumentSync')
        if isinstance(textsync, dict):
            return int(textsync.get('change', TextDocumentSyncKindNone))
        if isinstance(textsync, int):
            return textsync
        return TextDocumentSyncKindNone

    def should_notify_did_change(self) -> bool:
        return self.text_sync_kind() > TextDocumentSyncKindNone

    def should_notify_will_save(self) -> bool:
        textsync = self.capabilities.get('textDocumentSync')
        if isinstance(textsync, dict):
            return bool(textsync.get('willSave'))
        return False

    def should_request_will_save_wait_until(self) -> bool:
        textsync = self.capabilities.get('textDocumentSync')
        if isinstance(textsync, dict):
            return bool(textsync.get('willSaveWaitUntil'))
        return False

    def should_notify_did_save(self) -> Tuple[bool, bool]:
        textsync = self.capabilities.get('textDocumentSync')
        if isinstance(textsync, dict):
            options = textsync.get('save')
            if isinstance(options, dict):
                return True, bool(options.get('includeText'))
            elif isinstance(options, bool):
                return options, False
        return False, False

    def should_notify_did_close(self) -> bool:
        return self.should_notify_did_open()

    def handles_path(self, file_path: Optional[str]) -> bool:
        if not file_path:
            return False

        if not self._workspace_folders:
            return True

        for folder in self._workspace_folders:
            if is_subpath_of(file_path, folder.path):
                return True

        return False

    def update_folders(self, folders: List[WorkspaceFolder]) -> None:
        if self._supports_workspace_folders():
            added, removed = diff_folders(self._workspace_folders, folders)
            params = {
                "event": {
                    "added": [a.to_lsp() for a in added],
                    "removed": [r.to_lsp() for r in removed]
                }
            }
            notification = Notification.didChangeWorkspaceFolders(params)
            self.client.send_notification(notification)
            self._workspace_folders = folders

    def _initialize(self) -> None:
        params = get_initialize_params(self._workspace_folders, self.config)
        self.client.send_request(
            Request.initialize(params),
            self._handle_initialize_result,
            self._handle_initialize_error)

    def _supports_workspace_folders(self) -> bool:
        workspace_cap = self.capabilities.get("workspace", {})
        workspace_folder_cap = workspace_cap.get("workspaceFolders", {})
        return workspace_folder_cap.get("supported")

    def on_request(self, method: str, handler: Callable) -> None:
        self.client.on_request(method, handler)

    def on_notification(self, method: str, handler: Callable) -> None:
        self.client.on_notification(method, handler)

    def _handle_initialize_error(self, error: Any) -> None:
        self.state = ClientStates.STOPPING
        self.end()

    def _handle_initialize_result(self, result: Any) -> None:
        self.capabilities.update(result.get('capabilities', dict()))

        # only keep supported amount of folders
        if self._workspace_folders:
            if self._supports_workspace_folders():
                debug('multi folder session:', self._workspace_folders)
            else:
                self._workspace_folders = self._workspace_folders[:1]
                debug('single folder session:', self._workspace_folders[0])
        else:
            debug("session with no workspace folders")

        self.state = ClientStates.READY

        self.on_request("workspace/workspaceFolders", self._handle_request_workspace_folders)
        self.on_request("workspace/configuration", self._handle_request_workspace_configuration)
        if self.config.settings:
            self.client.send_notification(Notification.didChangeConfiguration({'settings': self.config.settings}))

        if self._on_post_initialize:
            self._on_post_initialize(self)

    def _handle_request_workspace_folders(self, _: Any, request_id: Any) -> None:
        self.client.send_response(Response(request_id, [wf.to_lsp() for wf in self._workspace_folders]))

    def _handle_request_workspace_configuration(self, params: Dict[str, Any], request_id: Any) -> None:
        items = []  # type: List[Any]
        requested_items = params.get("items") or []
        for requested_item in requested_items:
            if 'section' in requested_item:
                section = requested_item['section']
                if section:
                    items.append(get_dotted_value(self.config.settings, section))
                else:
                    items.append(self.config.settings)
            else:
                items.append(self.config.settings)
        self.client.send_response(Response(request_id, items))

    def end(self) -> None:
        self.state = ClientStates.STOPPING
        self.client.send_request(
            Request.shutdown(),
            lambda result: self._handle_shutdown_result(),
            lambda error: self._handle_shutdown_result())

    def _handle_shutdown_result(self) -> None:
        self.client.exit()
        self.client = None  # type: ignore
        self.capabilities.clear()
        if self._on_post_exit:
            self._on_post_exit(self.config.name)


def create_session(config: ClientConfig,
                   workspace_folders: List[WorkspaceFolder],
                   env: dict,
                   settings: Settings,
                   on_pre_initialize: Optional[Callable[[Session], None]] = None,
                   on_post_initialize: Optional[Callable[[Session], None]] = None,
                   on_post_exit: Optional[Callable[[str], None]] = None,
                   on_stderr_log: Optional[Callable[[str], None]] = None,
                   bootstrap_client: Optional[Any] = None) -> Optional[Session]:

    def with_client(client: Client) -> Session:
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

        working_dir = workspace_folders[0].path if workspace_folders else None
        process = start_server(server_args, working_dir, env, on_stderr_log)
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
