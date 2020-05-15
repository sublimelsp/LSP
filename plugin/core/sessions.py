from .edit import parse_workspace_edit
from .logging import debug, exception_log
from .protocol import completion_item_kinds, symbol_kinds, WorkspaceFolder, Request, Notification, Response
from .protocol import TextDocumentSyncKindNone, TextDocumentSyncKindIncremental
from .rpc import Client
from .settings import client_configs
from .transports import Transport
from .types import ClientConfig, LanguageConfig, ClientStates, Settings
from .typing import Dict, Any, Optional, List, Tuple, Generator, Type
from .workspace import is_subpath_of
from abc import ABCMeta, abstractmethod
import os
import sublime
import weakref


__version__ = (0, 11, 0)


class Manager(metaclass=ABCMeta):
    """
    A Manager is a container of Sessions.
    """

    # Observers

    @abstractmethod
    def window(self) -> sublime.Window:
        """
        Get the window associated with this manager.
        """
        pass

    @abstractmethod
    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> 'Generator[Session, None, None]':
        """
        Iterate over the sessions stored in this manager, applicable to the given view, with the given capability.
        """
        pass

    # Mutators

    @abstractmethod
    def start(self, configuration: ClientConfig, initiating_view: sublime.View) -> None:
        """
        Start a new Session with the given configuration. The initiating view is the view that caused this method to
        be called.

        A normal flow of calls would be start -> on_post_initialize -> do language server things -> on_post_exit.
        However, it is possible that the subprocess cannot start, in which case on_post_initialize will never be called.
        """
        pass

    # Event callbacks

    @abstractmethod
    def on_post_exit(self, session: 'Session', exit_code: int, exception: Optional[Exception]) -> None:
        """
        The given Session has stopped with the given exit code.
        """
        pass

    @abstractmethod
    def on_post_initialize(self, session: 'Session') -> None:
        """
        The language server returned a response from the initialize request. The response is stored in
        session.capabilities.
        """
        pass


def get_initialize_params(workspace_folders: List[WorkspaceFolder], config: ClientConfig) -> dict:
    first_folder = workspace_folders[0] if workspace_folders else None
    capabilities = {
        "textDocument": {
            "synchronization": {
                "dynamicRegistration": True,  # exceptional
                "didSave": True,
                "willSave": True,
                "willSaveWaitUntil": True
            },
            "hover": {
                "dynamicRegistration": True,
                "contentFormat": ["markdown", "plaintext"]
            },
            "completion": {
                "dynamicRegistration": True,
                "completionItem": {
                    "snippetSupport": True,
                    "deprecatedSupport": True
                },
                "completionItemKind": {
                    "valueSet": completion_item_kinds
                }
            },
            "signatureHelp": {
                "dynamicRegistration": True,
                "signatureInformation": {
                    "documentationFormat": ["markdown", "plaintext"],
                    "parameterInformation": {
                        "labelOffsetSupport": True
                    }
                }
            },
            "references": {
                "dynamicRegistration": True
            },
            "documentHighlight": {
                "dynamicRegistration": True
            },
            "documentSymbol": {
                "dynamicRegistration": True,
                "hierarchicalDocumentSymbolSupport": True,
                "symbolKind": {
                    "valueSet": symbol_kinds
                }
            },
            "formatting": {
                "dynamicRegistration": True  # exceptional
            },
            "rangeFormatting": {
                "dynamicRegistration": True
            },
            "declaration": {
                "dynamicRegistration": True,
                "linkSupport": True
            },
            "definition": {
                "dynamicRegistration": True,
                "linkSupport": True
            },
            "typeDefinition": {
                "dynamicRegistration": True,
                "linkSupport": True
            },
            "implementation": {
                "dynamicRegistration": True,
                "linkSupport": True
            },
            "codeAction": {
                "dynamicRegistration": True,
                "codeActionLiteralSupport": {
                    "codeActionKind": {
                        "valueSet": []
                    }
                }
            },
            "rename": {
                "dynamicRegistration": True
            },
            "colorProvider": {
                "dynamicRegistration": True  # exceptional
            },
            "publishDiagnostics": {
                "relatedInformation": True
            }
        },
        "workspace": {
            "applyEdit": True,
            "didChangeConfiguration": {
                "dynamicRegistration": True
            },
            "executeCommand": {},
            "workspaceEdit": {
                "documentChanges": True,
                "failureHandling": "abort",
            },
            "workspaceFolders": True,
            "symbol": {
                "dynamicRegistration": True,  # exceptional
                "symbolKind": {
                    "valueSet": symbol_kinds
                }
            },
            "configuration": True
        },
        "window": {
            "workDoneProgress": True
        }
    }
    if config.experimental_capabilities is not None:
        capabilities['experimental'] = config.experimental_capabilities
    params = {
        "processId": os.getpid(),
        "clientInfo": {
            "name": "Sublime Text LSP",
            "version": ".".join(map(str, __version__))
        },
        "rootUri": first_folder.uri() if first_folder else None,
        "rootPath": first_folder.path if first_folder else None,
        "workspaceFolders": [folder.to_lsp() for folder in workspace_folders] if workspace_folders else None,
        "capabilities": capabilities
    }
    if config.init_options is not None:
        params['initializationOptions'] = config.init_options
    return params


# method -> (capability dotted path, optional registration dotted path)
# these are the EXCEPTIONS. The general rule is: method foo/bar --> (barProvider, barProvider.id)
METHOD_TO_CAPABILITY_EXCEPTIONS = {
    'workspace/symbol': ('workspaceSymbolProvider', None),
    'workspace/didChangeWorkspaceFolders': ('workspace.workspaceFolders',
                                            'workspace.workspaceFolders.changeNotifications'),
    'textDocument/didOpen': ('textDocumentSync.openClose', None),
    'textDocument/didChange': ('textDocumentSync.change', None),
    'textDocument/didSave': ('textDocumentSync.save', None),
    'textDocument/willSave': ('textDocumentSync.willSave', None),
    'textDocument/willSaveWaitUntil': ('textDocumentSync.willSaveWaitUntil', None),
    'textDocument/formatting': ('documentFormattingProvider', None),
    'textDocument/documentColor': ('colorProvider', None)
}  # type: Dict[str, Tuple[str, Optional[str]]]


def method_to_capability(method: str) -> Tuple[str, str]:
    """
    Given a method, returns the corresponding capability path, and the associated path to stash the registration key.

    Examples:

        textDocument/definition --> (definitionProvider, definitionProvider.id)
        textDocument/references --> (referencesProvider, referencesProvider.id)
        textDocument/didOpen --> (textDocumentSync.openClose, textDocumentSync.openClose.id)
    """
    capability_path, registration_path = METHOD_TO_CAPABILITY_EXCEPTIONS.get(method, (None, None))
    if capability_path is None:
        capability_path = method.split('/')[1] + "Provider"
    if registration_path is None:
        # This path happens to coincide with the StaticRegistrationOptions' id, which is on purpose. As a consequence,
        # if a server made a "registration" via the initialize response, it can call client/unregisterCapability at
        # a later date, and the capability will pop from the capabilities dict.
        registration_path = capability_path + ".id"
    return capability_path, registration_path


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


def set_dotted_value(current: dict, dotted: str, value: Any) -> None:
    keys = dotted.split('.')
    for i in range(0, len(keys) - 1):
        key = keys[i]
        next_current = current.get(key)
        if not isinstance(next_current, dict):
            next_current = {}
            current[key] = next_current
        current = next_current
    current[keys[-1]] = value


def clear_dotted_value(current: dict, dotted: str) -> None:
    keys = dotted.split('.')
    for i in range(0, len(keys) - 1):
        key = keys[i]
        next_current = current.get(key)
        if not isinstance(next_current, dict):
            return
        current = next_current
    current.pop(keys[-1], None)


class AbstractPlugin(metaclass=ABCMeta):
    """
    You can define notification and request handlers by defining methods that start with 'm_'.

    python/analysisStarted -> def m_python_analysisStarted(self, params: JSONValue) -> None: ...
    python/analysisStopped -> def m_python_analysisStopped(self, params: JSONValue) -> None: ...
    """

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """
        A human-friendly name
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def languages(cls) -> List[LanguageConfig]:
        """
        The languages that this plugin serves
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def command(cls) -> List[str]:
        """
        The startup command for the language server process
        """
        raise NotImplementedError()

    @classmethod
    def tcp_port(cls) -> Optional[int]:
        """
        The TCP port used in case we're doing JSON-RPC over TCP
        """
        return None

    @classmethod
    def experimental_capabilities(cls) -> Optional[Dict[str, Any]]:
        """
        Experimental capabilities for the initialize request
        """
        return None

    @classmethod
    def initialization_options(cls) -> Optional[Dict[str, Any]]:
        """
        initializationOptions for the initialize request
        """
        return None

    @classmethod
    def default_settings(cls) -> Optional[Dict[str, Any]]:
        """
        Settings for the workspace/didChangeConfiguration notification and the workspace/configuration request
        """
        return None

    @classmethod
    def env(cls) -> Dict[str, str]:
        """
        Extra environment variables for the process of the language server binary
        """
        return {}

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        """
        If this plugin manages its own server binary, then this is the place to check whether the binary needs
        an update, or whether it needs to be installed before starting the language server.
        """
        return False

    @classmethod
    def install_or_update(cls) -> None:
        """
        Do the actual update/installation of the server binary. This runs in a separate thread, so don't spawn threads
        yourself here.
        """
        pass

    @classmethod
    def adjust_user_configuration(cls, configuration: ClientConfig) -> None:
        pass

    @classmethod
    def can_start(cls, window: sublime.Window, initiating_view: sublime.View,
                  workspace_folders: List[WorkspaceFolder], configuration: ClientConfig) -> Optional[str]:
        """
        Determines ability to start. This is called after needs_update_or_installation and after install_or_update.
        So you may assume that if you're managing your server binary, then it is already installed when this
        classmethod is called.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders
        :param      configuration:      The configuration

        :returns:   A string describing the reason why we should not start a language server session, or None if we
                    should go ahead and start a session.
        """
        return None

    def __init__(self, weaksession: 'weakref.ref[Session]') -> None:
        """
        Constructs a new instance.

        :param      weaksession:  A weak reference to the Session. You can grab a strong reference through
                                  self.weaksession(), but don't hold on to that reference.
        """
        self.weaksession = weaksession


_plugins = {}  # type: Dict[str, Type[AbstractPlugin]]


def register_plugin(plugin: Type[AbstractPlugin], update_global_configs: bool = True) -> None:
    global _plugins
    global client_configs
    try:
        config = ClientConfig(
            name=plugin.name(),
            binary_args=plugin.command(),
            languages=plugin.languages(),
            tcp_port=plugin.tcp_port(),
            enabled=True,
            init_options=plugin.initialization_options(),
            settings=plugin.default_settings(),
            env=plugin.env()
        )
        client_configs.add_external_config(config)
        _plugins[config.name] = plugin
        if update_global_configs:
            client_configs.update_configs()
    except Exception as ex:
        exception_log("Failed to register plugin", ex)


def unregister_plugin(plugin: Type[AbstractPlugin]) -> None:
    global _plugins
    global client_configs
    try:
        name = plugin.name()
        client_configs.remove_external_config(name)
        _plugins.pop(name, None)
    except Exception as ex:
        exception_log("Failed to unregister plugin", ex)
    finally:
        client_configs.update_configs()


def get_plugin(name: str) -> Optional[Type[AbstractPlugin]]:
    global _plugins
    return _plugins.get(name, None)


class Session(Client):

    def __init__(self, manager: Manager, settings: Settings, workspace_folders: List[WorkspaceFolder],
                 config: ClientConfig, plugin_class: Optional[Type[AbstractPlugin]]) -> None:
        self.config = config
        self.manager = weakref.ref(manager)
        self.window = manager.window()
        self.state = ClientStates.STARTING
        self.capabilities = dict()  # type: Dict[str, Any]
        self._workspace_folders = workspace_folders
        self._progress = {}  # type: Dict[Any, Dict[str, str]]
        self._plugin_class = plugin_class
        self._plugin = None  # type: Optional[AbstractPlugin]
        super().__init__(config.name, settings)

    def __getattr__(self, name: str) -> Any:
        """
        If we don't have a request/notification handler, look up the request/notification handler in the plugin.
        """
        if name.startswith('m_'):
            attr = getattr(self._plugin, name)
            if attr is not None:
                return attr
        raise AttributeError(name)

    def has_capability(self, capability: str) -> bool:
        value = self.get_capability(capability)
        return value is not False and value is not None

    def get_capability(self, capability: str) -> Optional[Any]:
        return get_dotted_value(self.capabilities, capability)

    def should_notify_did_open(self) -> bool:
        if self.has_capability('textDocumentSync.openClose'):
            return True
        textsync = self.get_capability('textDocumentSync')
        return isinstance(textsync, int) and textsync > TextDocumentSyncKindNone

    def text_sync_kind(self) -> int:
        textsync = self.capabilities.get('textDocumentSync')
        if isinstance(textsync, dict):
            change = textsync.get('change', TextDocumentSyncKindNone)
            if isinstance(change, dict):
                # dynamic registration
                return TextDocumentSyncKindIncremental  # or TextDocumentSyncKindFull?
            return int(change)
        if isinstance(textsync, int):
            return textsync
        return TextDocumentSyncKindNone

    def should_notify_did_change(self) -> bool:
        return self.text_sync_kind() > TextDocumentSyncKindNone

    def should_notify_will_save(self) -> bool:
        return self.has_capability('textDocumentSync.willSave')

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

    def should_notify_did_change_workspace_folders(self) -> bool:
        return self.has_capability("workspace.workspaceFolders.changeNotifications")

    def should_notify_did_change_configuration(self) -> bool:
        return self.has_capability("didChangeConfigurationProvider")

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
        if self.should_notify_did_change_workspace_folders():
            added, removed = diff_folders(self._workspace_folders, folders)
            params = {
                "event": {
                    "added": [a.to_lsp() for a in added],
                    "removed": [r.to_lsp() for r in removed]
                }
            }
            notification = Notification.didChangeWorkspaceFolders(params)
            self.send_notification(notification)
        if self._supports_workspace_folders():
            self._workspace_folders = folders

    def initialize(self, transport: Transport) -> None:
        self.transport = transport
        params = get_initialize_params(self._workspace_folders, self.config)
        self.send_request(Request.initialize(params), self._handle_initialize_result, lambda _: self.end())

    def call_manager(self, method: str, *args: Any) -> None:
        mgr = self.manager()
        if mgr:
            getattr(mgr, method)(*args)

    def on_stderr_message(self, message: str) -> None:
        self.call_manager('handle_stderr_log', self, message)

    def _supports_workspace_folders(self) -> bool:
        return self.has_capability("workspace.workspaceFolders.supported")

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
        if self._plugin_class is not None:
            self._plugin = self._plugin_class(weakref.ref(self))
        if self.config.settings:
            self.send_notification(Notification.didChangeConfiguration({'settings': self.config.settings}))
        execute_commands = self.get_capability('executeCommandProvider.commands')
        if execute_commands:
            debug("{}: Supported execute commands: {}".format(self.config.name, execute_commands))
        mgr = self.manager()
        if mgr:
            mgr.on_post_initialize(self)

    def m_window_showMessageRequest(self, params: Any, request_id: Any) -> None:
        """handles the window/showMessageRequest request"""
        self.call_manager('handle_message_request', self, params, request_id)

    def m_window_showMessage(self, params: Any) -> None:
        """handles the window/showMessage notification"""
        self.call_manager('handle_show_message', self, params)

    def m_window_logMessage(self, params: Any) -> None:
        """handles the window/logMessage notification"""
        self.call_manager('handle_log_message', self, params)

    def m_workspace_workspaceFolders(self, _: Any, request_id: Any) -> None:
        """handles the workspace/workspaceFolders request"""
        self.send_response(Response(request_id, [wf.to_lsp() for wf in self._workspace_folders]))

    def m_workspace_configuration(self, params: Dict[str, Any], request_id: Any) -> None:
        """handles the workspace/configuration request"""
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
        self.send_response(Response(request_id, items))

    def m_workspace_applyEdit(self, params: Any, request_id: Any) -> None:
        """handles the workspace/applyEdit request"""
        edit = params.get('edit', {})
        self.window.run_command('lsp_apply_workspace_edit', {'changes': parse_workspace_edit(edit)})
        # TODO: We should ideally wait for all changes to have been applied. This is currently not "async".
        self.send_response(Response(request_id, {"applied": True}))

    def m_textDocument_publishDiagnostics(self, params: Any) -> None:
        """handles the textDocument/publishDiagnostics notification"""
        mgr = self.manager()
        if mgr:
            mgr.diagnostics.receive(self.config.name, params)  # type: ignore

    def m_client_registerCapability(self, params: Any, request_id: Any) -> None:
        """handles the client/registerCapability request"""
        registrations = params["registrations"]
        for registration in registrations:
            method = registration["method"]
            capability_path, registration_path = method_to_capability(method)
            debug("{}: registering capability:".format(self.config.name), capability_path)
            set_dotted_value(self.capabilities, capability_path, registration.get("registerOptions", {}))
            set_dotted_value(self.capabilities, registration_path, registration["id"])
        self.send_response(Response(request_id, None))

    def m_client_unregisterCapability(self, params: Any, request_id: Any) -> None:
        """handles the client/unregisterCapability request"""
        unregistrations = params["unregisterations"]  # typo in the official specification
        for unregistration in unregistrations:
            capability_path, registration_path = method_to_capability(unregistration["method"])
            debug("{}: unregistering capability:".format(self.config.name), capability_path)
            clear_dotted_value(self.capabilities, capability_path)
            clear_dotted_value(self.capabilities, registration_path)
        self.send_response(Response(request_id, None))

    def m_window_workDoneProgress_create(self, params: Any, request_id: Any) -> None:
        """handles the window/workDoneProgress/create request"""
        self._progress[params['token']] = dict()
        self.send_response(Response(request_id, None))

    def m___progress(self, params: Any) -> None:
        """handles the $/progress notification"""
        token = params['token']
        if token not in self._progress:
            debug('unknown $/progress token: {}'.format(token))
            return
        value = params['value']
        if value['kind'] == 'begin':
            self._progress[token]['title'] = value['title']  # mandatory
            self._progress[token]['message'] = value.get('message')  # optional
            self.window.status_message(self._progress_string(token, value))
        elif value['kind'] == 'report':
            self.window.status_message(self._progress_string(token, value))
        elif value['kind'] == 'end':
            if value.get('message'):
                status_msg = self._progress[token]['title'] + ': ' + value['message']
                self.window.status_message(status_msg)
            self._progress.pop(token, None)

    def _progress_string(self, token: Any, value: Dict[str, Any]) -> str:
        status_msg = self._progress[token]['title']
        progress_message = value.get('message')  # optional
        progress_percentage = value.get('percentage')  # optional
        if progress_message:
            self._progress[token]['message'] = progress_message
            status_msg += ': ' + progress_message
        elif self._progress[token]['message']:  # reuse last known message if not present
            status_msg += ': ' + self._progress[token]['message']
        if progress_percentage:
            fmt = ' ({:.1f}%)' if isinstance(progress_percentage, float) else ' ({}%)'
            status_msg += fmt.format(progress_percentage)
        return status_msg

    def end(self) -> None:
        self._plugin = None
        debug("stopping", self.config.name, "gracefully")
        self.capabilities.clear()
        self.state = ClientStates.STOPPING
        self.send_request(Request.shutdown(), self._handle_shutdown_result, self._handle_shutdown_result)

    def _handle_shutdown_result(self, _: Any) -> None:
        self.send_notification(Notification.exit())

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        super().on_transport_close(exit_code, exception)
        debug("stopped", self.config.name, "exit code", exit_code)
        mgr = self.manager()
        if mgr:
            mgr.on_post_exit(self, exit_code, exception)
