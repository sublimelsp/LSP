from .collections import DottedDict
from .edit import parse_workspace_edit
from .logging import debug
from .logging import exception_log
from .protocol import TextDocumentSyncKindNone, TextDocumentSyncKindIncremental, CompletionItemTag
from .protocol import WorkspaceFolder, Request, Notification, Response
from .rpc import Client
from .settings import client_configs
from .transports import Transport
from .types import ClientConfig, ClientStates, Settings
from .typing import Dict, Any, Optional, List, Tuple, Generator, Type, Protocol
from .views import COMPLETION_KINDS
from .views import did_change_configuration
from .views import SYMBOL_KINDS
from .workspace import is_subpath_of
from abc import ABCMeta, abstractmethod
from weakref import WeakSet
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


def get_initialize_params(variables: Dict[str, str], workspace_folders: List[WorkspaceFolder],
                          config: ClientConfig) -> dict:
    completion_kinds = list(range(1, len(COMPLETION_KINDS) + 1))
    symbol_kinds = list(range(1, len(SYMBOL_KINDS) + 1))
    completion_tag_value_set = [v for k, v in CompletionItemTag.__dict__.items() if not k.startswith('_')]
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
                    "deprecatedSupport": True,
                    "tagSupport": {
                        "valueSet": completion_tag_value_set
                    }
                },
                "completionItemKind": {
                    "valueSet": completion_kinds
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
        params['initializationOptions'] = sublime.expand_variables(config.init_options, variables)
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


class SessionViewProtocol(Protocol):

    session = None  # type: Session
    view = None  # type: sublime.View
    listener = None  # type: Any

    def on_diagnostics(self, diagnostics: Any) -> None:
        ...

    def shutdown(self) -> None:
        ...

    def __hash__(self) -> int:
        ...


class AbstractPlugin(metaclass=ABCMeta):
    """
    Inherit from this class to handle non-standard requests and notifications.
    Given a request/notification, replace the non-alphabetic characters with an underscore, and prepend it with "m_".
    This will be the name of your method.
    For instance, to implement the non-standard eslint/openDoc request, define the Python method

        def m_eslint_openDoc(self, params, request_id):
            session = self.weaksession()
            if session:
                webbrowser.open_tab(params['url'])
                session.send_response(Response(request_id, None))

    To handle the non-standard eslint/status notification, define the Python method

        def m_eslint_status(self, params):
            pass

    To understand how this works, see the __getattr__ method of the Session class.
    """

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """
        A human-friendly name. If your plugin is called "LSP-foobar", then this should return "foobar". If you also
        have your settings file called "LSP-foobar.sublime-settings", then you don't even need to re-implement the
        configuration method (see below).
        """
        raise NotImplementedError()

    @classmethod
    def configuration(cls) -> sublime.Settings:
        """
        The Settings object that defines the `command`, `languages`, and optionally the `initializationOptions`,
        `settings`, `env` and `tcp_port`.

        The `command`, `initializationOptions` and `env` are subject to template string substitution. The following
        template strings are recognized:

        $file
        $file_base_name
        $file_extension
        $file_name
        $file_path
        $platform
        $project
        $project_base_name
        $project_extension
        $project_name
        $project_path

        These are just the values from window.extract_variables(). Additionally,

        $cache_path   sublime.cache_path()
        $temp_dir     tempfile.gettempdir()
        $home         os.path.expanduser('~')
        $port         A random free TCP-port on localhost in case `tcp_port` is set to 0. This string template can only
                      be used in the `command`

        The `command` and `env` are expanded upon starting the subprocess of the Session. The `initializationOptions`
        are expanded upon doing the initialize request. `initializationOptions` does not expand $port.

        When you're managing your own server binary, you would typically place it in sublime.cache_path(). So your
        `command` should look like this: "command": ["$cache_path/LSP-foobar/server_binary", "--stdio"]
        """
        return sublime.load_settings('LSP-{}.sublime-settings'.format(cls.name()))

    @classmethod
    def additional_variables(cls) -> Optional[Dict[str, str]]:
        """
        In addition to the above variables, add more variables here to be expanded.
        """
        return None

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


def register_plugin(plugin: Type[AbstractPlugin]) -> None:
    global _plugins
    try:
        name = plugin.name()
        client_configs.add_external_config(name, plugin.configuration())
        _plugins[name] = plugin
    except Exception as ex:
        exception_log("Failed to register plugin", ex)


def unregister_plugin(plugin: Type[AbstractPlugin]) -> None:
    global _plugins
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
        self.capabilities = DottedDict()
        self.exiting = False
        self._workspace_folders = workspace_folders
        self._session_views = WeakSet()  # type: WeakSet[SessionViewProtocol]
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

    def register_session_view(self, sv: SessionViewProtocol) -> None:
        self._session_views.add(sv)

    def unregister_session_view(self, sv: SessionViewProtocol) -> None:
        self._session_views.discard(sv)

    def session_views(self) -> Generator[SessionViewProtocol, None, None]:
        yield from self._session_views

    def can_handle(self, view: sublime.View, capability: Optional[str] = None) -> bool:
        if self.state == ClientStates.READY and self.config.match_view(view):
            if self.handles_path(view.file_name() or ''):
                if capability is None or capability in self.capabilities:
                    return True
        return False

    def has_capability(self, capability: str) -> bool:
        value = self.get_capability(capability)
        return value is not False and value is not None

    def get_capability(self, capability: str) -> Optional[Any]:
        return self.capabilities.get(capability)

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
        if self._supports_workspace_folders():
            return True
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

    def initialize(self, variables: Dict[str, str], transport: Transport) -> None:
        self.transport = transport
        params = get_initialize_params(variables, self._workspace_folders, self.config)
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
        self.capabilities.assign(result.get('capabilities', dict()))
        if self._workspace_folders and not self._supports_workspace_folders():
            self._workspace_folders = self._workspace_folders[:1]
        self.state = ClientStates.READY
        if self._plugin_class is not None:
            self._plugin = self._plugin_class(weakref.ref(self))
        if self.config.settings:
            self.send_notification(did_change_configuration(self.config.settings))
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
            items.append(self.config.settings.get(requested_item.get('section') or None))
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
            self.capabilities.set(capability_path, registration.get("registerOptions", {}))
            self.capabilities.set(registration_path, registration["id"])
        self.send_response(Response(request_id, None))

    def m_client_unregisterCapability(self, params: Any, request_id: Any) -> None:
        """handles the client/unregisterCapability request"""
        unregistrations = params["unregisterations"]  # typo in the official specification
        for unregistration in unregistrations:
            capability_path, registration_path = method_to_capability(unregistration["method"])
            debug("{}: unregistering capability:".format(self.config.name), capability_path)
            self.capabilities.remove(capability_path)
            self.capabilities.remove(registration_path)
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
        self.exiting = True
        self._plugin = None
        for sv in self.session_views():
            sv.shutdown()
        self.capabilities.clear()
        self.state = ClientStates.STOPPING
        self.send_request(Request.shutdown(), self._handle_shutdown_result, self._handle_shutdown_result)

    def _handle_shutdown_result(self, _: Any) -> None:
        self.exit()

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        self.exiting = True
        self.state = ClientStates.STOPPING
        super().on_transport_close(exit_code, exception)
        debug("stopped", self.config.name, "exit code", exit_code)
        mgr = self.manager()
        if mgr:
            mgr.on_post_exit(self, exit_code, exception)
