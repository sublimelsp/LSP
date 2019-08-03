from .types import ClientConfig, ClientStates, Settings
from .protocol import Request
from .transports import start_tcp_transport
from .rpc import Client, attach_stdio_client
from .process import start_server
from .url import filename_to_uri
from .logging import debug
import os
from .protocol import completion_item_kinds, symbol_kinds
try:
    from typing import Callable, Dict, Any, Optional, List, Union
    assert Callable and Dict and Any and Optional and List and Union
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


def basic_capability() -> 'Dict[str, Any]':
    return {"dynamicRegistration": False}


def supported_content_formats() -> 'List[str]':
    return ["markdown", "plaintext"]


def value_set(items: 'List[int]') -> 'Dict[str, List[int]]':
    return {"valueSet": items}


def symbol_kind_value_set() -> 'Dict[str, List[int]]':
    return value_set(symbol_kinds)


def code_action_kind_value_set() -> 'Dict[str, List[int]]':
    return value_set([])


def completion_item_kind_value_set() -> 'Dict[str, List[int]]':
    return value_set(completion_item_kinds)


def text_document_capabilities() -> 'Dict[str, dict]':
    return {
        "synchronization": {
            "dynamicRegistration": False,
            "didSave": True
        },
        "hover": {
            "dynamicRegistration": False,
            "contentFormat": supported_content_formats()
        },
        "completion": {
            "dynamicRegistration": False,
            "completionItem": {"snippetSupport": True},
            "completionItemKind": completion_item_kind_value_set()
        },
        "signatureHelp": {
            "dynamicRegistration": False,
            "signatureInformation": {
                "documentationFormat": supported_content_formats(),
                "parameterInformation": {"labelOffsetSupport": True}
            }
        },
        "documentSymbol": {
            "dynamicRegistration": False,
            "symbolKind": symbol_kind_value_set()
        },
        "codeAction": {
            "dynamicRegistration": False,
            "codeActionLiteralSupport": {
                "codeActionKind": code_action_kind_value_set()
            }
        },
        "publishDiagnostics": {"relatedInformation": False},
        "documentHighlight": basic_capability(),
        "references": basic_capability(),
        "formatting": basic_capability(),
        "rangeFormatting": basic_capability(),
        "definition": basic_capability(),
        "typeDefinition": basic_capability(),
        "declaration": basic_capability(),
        "implementation": basic_capability(),
        "rename": basic_capability()
    }


def workspace_capabilities() -> 'Dict[str, Union[bool, dict]]':
    return {
        "applyEdit": True,
        "didChangeConfiguration": basic_capability(),
        "executeCommand": basic_capability(),
        "symbol": {
            "dynamicRegistration": False,
            "symbolKind": symbol_kind_value_set()
        }
    }


def capabilities() -> 'Dict[str, dict]':
    return {
        "textDocument": text_document_capabilities(),
        "workspace": workspace_capabilities()
    }


def get_initialize_params(project_path: str, config: ClientConfig) -> 'Dict[str, Any]':
    initializeParams = {
        "processId": os.getpid(),
        "rootUri": filename_to_uri(project_path),
        "rootPath": project_path,
        "capabilities": capabilities()
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
