from .types import ClientConfig, ClientStates, Settings
from .protocol import Request
from .transports import start_tcp_transport
from .rpc import Client, attach_stdio_client
from .process import start_server
from .url import filename_to_uri
from .logging import debug
import os
from .protocol import CompletionItemKind, SymbolKind
try:
    from typing import Callable, Dict, Any, Optional
    assert Callable and Dict and Any and Optional
except ImportError:
    pass


def create_session(config: ClientConfig, project_path: str, env: dict, settings: Settings,
                   on_created=None, on_ended: 'Optional[Callable[[str], None]]' = None,
                   bootstrap_client=None) -> 'Optional[Session]':
    session = None
    if config.binary_args:

        process = start_server(config.binary_args, project_path, env, settings.log_stderr)
        if process:
            if config.tcp_port:
                transport = start_tcp_transport(config.tcp_port, config.tcp_host)
                if transport:
                    session = Session(config, project_path, Client(transport, settings), on_created, on_ended)
                else:
                    # try to terminate the process
                    try:
                        process.terminate()
                    except Exception:
                        pass
            else:
                client = attach_stdio_client(process, settings)
                session = Session(config, project_path, client, on_created, on_ended)
    else:
        if config.tcp_port:
            transport = start_tcp_transport(config.tcp_port)

            session = Session(config, project_path, Client(transport, settings),
                              on_created, on_ended)
        elif bootstrap_client:
            session = Session(config, project_path, bootstrap_client,
                              on_created, on_ended)
        else:
            debug("No way to start session")

    return session


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
                        "valueSet": [
                            SymbolKind.File,
                            SymbolKind.Module,
                            SymbolKind.Namespace,
                            SymbolKind.Package,
                            SymbolKind.Class,
                            SymbolKind.Method,
                            SymbolKind.Property,
                            SymbolKind.Field,
                            SymbolKind.Constructor,
                            SymbolKind.Enum,
                            SymbolKind.Interface,
                            SymbolKind.Function,
                            SymbolKind.Variable,
                            SymbolKind.Constant,
                            SymbolKind.String,
                            SymbolKind.Number,
                            SymbolKind.Boolean,
                            SymbolKind.Array,
                            SymbolKind.Object,
                            SymbolKind.Key,
                            SymbolKind.Null,
                            SymbolKind.EnumMember,
                            SymbolKind.Struct,
                            SymbolKind.Event,
                            SymbolKind.Operator,
                            SymbolKind.TypeParameter
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
    def __init__(self, config: ClientConfig, project_path, client: Client,
                 on_created=None, on_ended: 'Optional[Callable[[str], None]]' = None) -> None:
        self.config = config
        self.project_path = project_path
        self.state = ClientStates.STARTING
        self._on_created = on_created
        self._on_ended = on_ended
        self.capabilities = dict()  # type: Dict[str, Any]
        self.client = client
        self.initialize()

    def has_capability(self, capability):
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def initialize(self):
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
            lambda result: self._handle_shutdown_result(),
            lambda: self._handle_shutdown_result())

    def _handle_shutdown_result(self):
        self.client.exit()
        self.client = None
        self.capabilities = dict()
        if self._on_ended:
            self._on_ended(self.config.name)
