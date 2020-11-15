from .collections import DottedDict
from .edit import apply_workspace_edit
from .edit import parse_workspace_edit
from .logging import debug
from .logging import exception_log
from .open import open_externally
from .open import open_file_and_center_async
from .promise import Promise
from .protocol import CompletionItemTag
from .protocol import Error
from .protocol import ErrorCode
from .protocol import Notification
from .protocol import Request
from .protocol import Response
from .protocol import WorkspaceFolder
from .settings import client_configs
from .transports import Transport
from .transports import TransportCallbacks
from .types import Capabilities
from .types import ClientConfig
from .types import ClientStates
from .types import debounced
from .types import diff
from .types import DocumentSelector
from .types import method_to_capability
from .types import ResolvedStartupConfig
from .types import SettingsRegistration
from .typing import Callable, Dict, Any, Optional, List, Tuple, Generator, Type, Protocol, Mapping, Union
from .url import uri_to_filename
from .version import __version__
from .views import COMPLETION_KINDS
from .views import extract_variables
from .views import get_storage_path
from .views import SYMBOL_KINDS
from .workspace import is_subpath_of
from abc import ABCMeta
from abc import abstractmethod
from weakref import WeakSet
import functools
import os
import sublime
import weakref


InitCallback = Callable[['Session', bool], None]


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

    @abstractmethod
    def get_project_path(self, file_path: str) -> Optional[str]:
        """
        Get the project path for the given file.
        """
        pass

    # Mutators

    @abstractmethod
    def start_async(self, configuration: ClientConfig, initiating_view: sublime.View) -> None:
        """
        Start a new Session with the given configuration. The initiating view is the view that caused this method to
        be called.

        A normal flow of calls would be start -> on_post_initialize -> do language server things -> on_post_exit.
        However, it is possible that the subprocess cannot start, in which case on_post_initialize will never be called.
        """
        pass

    @abstractmethod
    def update_diagnostics_panel_async(self) -> None:
        pass

    @abstractmethod
    def show_diagnostics_panel_async(self) -> None:
        pass

    @abstractmethod
    def hide_diagnostics_panel_async(self) -> None:
        pass

    # Event callbacks

    @abstractmethod
    def on_post_exit_async(self, session: 'Session', exit_code: int, exception: Optional[Exception]) -> None:
        """
        The given Session has stopped with the given exit code.
        """
        pass


def get_initialize_params(variables: Dict[str, str], workspace_folders: List[WorkspaceFolder],
                          config: ClientConfig) -> dict:
    completion_kinds = list(range(1, len(COMPLETION_KINDS) + 1))
    symbol_kinds = list(range(1, len(SYMBOL_KINDS) + 1))
    completion_tag_value_set = [v for k, v in CompletionItemTag.__dict__.items() if not k.startswith('_')]
    first_folder = workspace_folders[0] if workspace_folders else None
    capabilities = {
        "general": {
            "regularExpressions": {
                "engine": "ECMAScript"
            }
        },
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
                    "documentationFormat": ["markdown", "plaintext"],
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
                        "valueSet": [
                            "quickfix",
                            "refactor",
                            "refactor.extract",
                            "refactor.inline",
                            "refactor.rewrite",
                            "source.organizeImports"
                        ]
                    }
                },
                "dataSupport": True,
                "resolveSupport": {
                    "properties": [
                        "edit",
                        "command"
                    ]
                }
            },
            "rename": {
                "dynamicRegistration": True,
                "prepareSupport": True
            },
            "colorProvider": {
                "dynamicRegistration": True  # exceptional
            },
            "publishDiagnostics": {
                "relatedInformation": True
            },
            "selectionRange": {
                "dynamicRegistration": True
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
            "showDocument": {
                "support": True
            },
            "showMessage": {
                "messageActionItem": {
                    "additionalPropertiesSupport": True
                }
            },
            "workDoneProgress": True
        }
    }
    if config.experimental_capabilities is not None:
        capabilities['experimental'] = config.experimental_capabilities
    return {
        "processId": os.getpid(),
        "clientInfo": {
            "name": "Sublime Text LSP",
            "version": ".".join(map(str, __version__))
        },
        "rootUri": first_folder.uri() if first_folder else None,
        "rootPath": first_folder.path if first_folder else None,
        "workspaceFolders": [folder.to_lsp() for folder in workspace_folders] if workspace_folders else None,
        "capabilities": capabilities,
        "initializationOptions": sublime.expand_variables(config.init_options.get(), variables)
    }


class SessionViewProtocol(Protocol):

    session = None  # type: Session
    view = None  # type: sublime.View
    listener = None  # type: Any
    session_buffer = None  # type: Any

    def on_capability_added_async(self, registration_id: str, capability_path: str, options: Dict[str, Any]) -> None:
        ...

    def on_capability_removed_async(self, registration_id: str, discarded_capabilities: Dict[str, Any]) -> None:
        ...

    def has_capability_async(self, capability_path: str) -> bool:
        ...

    def shutdown_async(self) -> None:
        ...

    def present_diagnostics_async(self, flags: int) -> None:
        ...

    def on_request_started_async(self, request_id: int, request: Request) -> None:
        ...

    def on_request_finished_async(self, request_id: int) -> None:
        ...


class SessionBufferProtocol(Protocol):

    session = None  # type: Session
    session_views = None  # type: WeakSet[SessionViewProtocol]
    file_name = None  # type: str
    language_id = None  # type: str

    def register_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: Dict[str, Any]
    ) -> None:
        ...

    def unregister_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str
    ) -> None:
        ...

    def on_diagnostics_async(self, diagnostics: List[Dict[str, Any]], version: Optional[int]) -> None:
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
    def configuration(cls) -> Tuple[sublime.Settings, str]:
        """
        Return the Settings object that defines the "command", "languages", and optionally the "initializationOptions",
        "default_settings", "env" and "tcp_port" as the first element in the tuple, and the path to the base settings
        filename as the second element in the tuple.

        The second element in the tuple is used to handle "settings" overrides from users properly. For example, if your
        plugin is called LSP-foobar, you would return "Packages/LSP-foobar/LSP-foobar.sublime-settings".

        The "command", "initializationOptions" and "env" are subject to template string substitution. The following
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

        $storage_path The path to the package storage (see AbstractPlugin.storage_path)
        $cache_path   sublime.cache_path()
        $temp_dir     tempfile.gettempdir()
        $home         os.path.expanduser('~')
        $port         A random free TCP-port on localhost in case "tcp_port" is set to 0. This string template can only
                      be used in the "command"

        The "command" and "env" are expanded upon starting the subprocess of the Session. The "initializationOptions"
        are expanded upon doing the initialize request. "initializationOptions" does not expand $port.

        When you're managing your own server binary, you would typically place it in sublime.cache_path(). So your
        "command" should look like this: "command": ["$cache_path/LSP-foobar/server_binary", "--stdio"]
        """
        name = cls.name()
        basename = "LSP-{}.sublime-settings".format(name)
        filepath = "Packages/LSP-{}/{}".format(name, basename)
        return sublime.load_settings(basename), filepath

    @classmethod
    def additional_variables(cls) -> Optional[Dict[str, str]]:
        """
        In addition to the above variables, add more variables here to be expanded.
        """
        return None

    @classmethod
    def storage_path(cls) -> str:
        """
        The storage path. Use this as your base directory to install server files. Its path is '$DATA/Package Storage'.
        You should have an additional subdirectory preferrably the same name as your plugin. For instance:

        ```python
        from LSP.plugin import AbstractPlugin
        import os


        class MyPlugin(AbstractPlugin):

            @classmethod
            def name(cls) -> str:
                return "my-plugin"

            @classmethod
            def basedir(cls) -> str:
                # Do everything relative to this directory
                return os.path.join(cls.storage_path(), cls.name())
        ```
        """
        return get_storage_path()

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

    @classmethod
    def on_pre_start(cls, window: sublime.Window, initiating_view: sublime.View,
                     workspace_folders: List[WorkspaceFolder], resolved: ResolvedStartupConfig) -> Optional[str]:
        """
        Callback invoked just before the language server subprocess is started. This is the place to do last-minute
        adjustments to your "command" or "initializationOptions" in the passed-in "resolved" argument, or change the
        order of the workspace folders. You can also choose to return a custom working directory, but consider that a
        language server should not care about the working directory.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders, you can modify these
        :param      resolved:           The resolved configuration, you can modify these

        :returns:   A desired working directory, or None if you don't care
        """
        return None

    @classmethod
    def on_post_start(cls, window: sublime.Window, initiating_view: sublime.View,
                      workspace_folders: List[WorkspaceFolder], resolved: ResolvedStartupConfig) -> None:
        """
        Callback invoked when the subprocess was just started.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders
        :param      resolved:           The resolved configuration
        """
        pass

    def __init__(self, weaksession: 'weakref.ref[Session]') -> None:
        """
        Constructs a new instance. Your instance is constructed after a response to the initialize request.

        :param      weaksession:  A weak reference to the Session. You can grab a strong reference through
                                  self.weaksession(), but don't hold on to that reference.
        """
        self.weaksession = weaksession

    def on_pre_workspace_configuration(self, settings: DottedDict) -> None:
        """
        Override this method to alter the server settings for the workspace/didChangeConfiguration notification.

        :param      settings:      The settings that are about to be sent to the language server
        """
        pass

    def on_workspace_configuration(self, params: Dict, configuration: Any) -> None:
        """
        Override to augment configuration returned for the workspace/configuration request.

        :param      params:         A ConfigurationItem for which configuration is requested.
        :param      configuration:  The resolved configuration for given params.
        """
        pass

    def on_pre_server_command(self, command: Mapping[str, Any], done_callback: Callable[[], None]) -> bool:
        """
        Intercept a command that is about to be sent to the language server.

        :param    command:        The payload containing a "command" and optionally "arguments".
        :param    done_callback:  The callback that you promise to invoke when you return true.

        :returns: True if *YOU* will handle this command plugin-side, false otherwise. You must invoke the
                  passed `done_callback` when you're done.
        """
        return False


_plugins = {}  # type: Dict[str, Tuple[Type[AbstractPlugin], SettingsRegistration]]


def _register_plugin_impl(plugin: Type[AbstractPlugin], notify_listener: bool) -> None:
    global _plugins
    name = plugin.name()
    try:
        settings, base_file = plugin.configuration()
        if client_configs.add_external_config(name, settings, base_file, notify_listener):
            on_change = functools.partial(client_configs.update_external_config, name, settings, base_file)
            _plugins[name] = (plugin, SettingsRegistration(settings, on_change))
    except Exception as ex:
        exception_log('Failed to register plugin "{}"'.format(name), ex)


def register_plugin(plugin: Type[AbstractPlugin], notify_listener: bool = True) -> None:
    """
    Register an LSP plugin in LSP.

    You should put a call to this function in your `plugin_loaded` callback. This way, when your package is disabled
    by a user and then re-enabled again by a user, the changes in state are picked up by LSP, and your language server
    will start for the relevant views.

    While your helper package may still work without calling `register_plugin` in `plugin_loaded`, the user will have a
    better experience when you do call this function.

    Your implementation should look something like this:

    ```python
    from LSP.plugin import register_plugin
    from LSP.plugin import unregister_plugin
    from LSP.plugin import AbstractPlugin


    class MyPlugin(AbstractPlugin):
        ...


    def plugin_loaded():
        register_plugin(MyPlugin)

    def plugin_unloaded():
        unregister_plugin(MyPlugin)
    ```

    If you need to install supplementary files (e.g. javascript source code that implements the actual server), do so
    in `AbstractPlugin.install_or_update` in a blocking manner, without the use of Python's `threading` module.
    """
    if notify_listener:
        # There is a bug in Sublime Text's `plugin_loaded` callback. When the package is in the list of
        # `"ignored_packages"` in Packages/User/Preferences.sublime-settings, and then removed from that list, the
        # sublime.Settings object has missing keys/values. To circumvent this, we run the actual registration one tick
        # later. At that point, the settings object is fully loaded. At least, it seems that way. For more context,
        # see https://github.com/sublimehq/sublime_text/issues/3379
        # and https://github.com/sublimehq/sublime_text/issues/2099
        sublime.set_timeout(lambda: _register_plugin_impl(plugin, notify_listener))
    else:
        _register_plugin_impl(plugin, notify_listener)


def unregister_plugin(plugin: Type[AbstractPlugin]) -> None:
    """
    Unregister an LSP plugin in LSP.

    You should put a call to this function in your `plugin_unloaded` callback. this way, when your package is disabled
    by a user, your language server is shut down for the views that it is attached to. This results in a good user
    experience.
    """
    global _plugins
    name = plugin.name()
    try:
        _plugins.pop(name, None)
        client_configs.remove_external_config(name)
    except Exception as ex:
        exception_log('Failed to unregister plugin "{}"'.format(name), ex)


def get_plugin(name: str) -> Optional[Type[AbstractPlugin]]:
    global _plugins
    tup = _plugins.get(name, None)
    return tup[0] if tup else None


class Logger(metaclass=ABCMeta):

    @abstractmethod
    def stderr_message(self, message: str) -> None:
        pass

    @abstractmethod
    def outgoing_response(self, request_id: Any, params: Any) -> None:
        pass

    @abstractmethod
    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        pass

    @abstractmethod
    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def outgoing_notification(self, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def incoming_response(self, request_id: int, params: Any, is_error: bool) -> None:
        pass

    @abstractmethod
    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        pass


def print_to_status_bar(error: Dict[str, Any]) -> None:
    sublime.status_message(error["message"])


def method2attr(method: str) -> str:
    # window/messageRequest -> m_window_messageRequest
    # $/progress -> m___progress
    # client/registerCapability -> m_client_registerCapability
    return 'm_' + ''.join(map(lambda c: c if c.isalpha() else '_', method))


class _RegistrationData:

    __slots__ = ("registration_id", "capability_path", "registration_path", "options", "session_buffers", "selector")

    def __init__(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: Dict[str, Any]
    ) -> None:
        self.registration_id = registration_id
        self.registration_path = registration_path
        self.capability_path = capability_path
        document_selector = options.pop("documentSelector", None)
        if not isinstance(document_selector, list):
            document_selector = []
        self.selector = DocumentSelector(document_selector)
        self.options = options
        self.session_buffers = WeakSet()  # type: WeakSet[SessionBufferProtocol]

    def __del__(self) -> None:
        for sb in self.session_buffers:
            sb.unregister_capability_async(self.registration_id, self.capability_path, self.registration_path)

    def check_applicable(self, sb: SessionBufferProtocol) -> None:
        for sv in sb.session_views:
            if self.selector.matches(sv.view):
                self.session_buffers.add(sb)
                sb.register_capability_async(
                    self.registration_id, self.capability_path, self.registration_path, self.options)
                return


class Session(TransportCallbacks):

    def __init__(self, manager: Manager, logger: Logger, workspace_folders: List[WorkspaceFolder],
                 config: ClientConfig, plugin_class: Optional[Type[AbstractPlugin]]) -> None:
        self.transport = None  # type: Optional[Transport]
        self.request_id = 0  # Our request IDs are always integers.
        self._logger = logger
        self._response_handlers = {}  # type: Dict[int, Tuple[Request, Callable, Optional[Callable[[Any], None]]]]
        self.config = config
        self.manager = weakref.ref(manager)
        self.window = manager.window()
        self.state = ClientStates.STARTING
        self.capabilities = Capabilities()
        self.exiting = False
        self._registrations = {}  # type: Dict[str, _RegistrationData]
        self._init_callback = None  # type: Optional[InitCallback]
        self._initialize_error = None  # type: Optional[Tuple[int, Optional[Exception]]]
        self._views_opened = 0
        self._workspace_folders = workspace_folders
        self._session_views = WeakSet()  # type: WeakSet[SessionViewProtocol]
        self._session_buffers = WeakSet()  # type: WeakSet[SessionBufferProtocol]
        self._progress = {}  # type: Dict[Any, Dict[str, str]]
        self._plugin_class = plugin_class
        self._plugin = None  # type: Optional[AbstractPlugin]

    def __del__(self) -> None:
        debug(self.config.command, "ended")
        for token in self._progress.keys():
            key = self._progress_status_key(token)
            for sv in self.session_views_async():
                if sv.view.is_valid():
                    sv.view.erase_status(key)

    def __getattr__(self, name: str) -> Any:
        """
        If we don't have a request/notification handler, look up the request/notification handler in the plugin.
        """
        if name.startswith('m_'):
            attr = getattr(self._plugin, name)
            if attr is not None:
                return attr
        raise AttributeError(name)

    # TODO: Create an assurance that the API doesn't change here as it can be used by plugins.
    def get_workspace_folders(self) -> List[WorkspaceFolder]:
        return self._workspace_folders

    # --- session view management --------------------------------------------------------------------------------------

    def register_session_view_async(self, sv: SessionViewProtocol) -> None:
        self._session_views.add(sv)
        self._views_opened += 1

    def unregister_session_view_async(self, sv: SessionViewProtocol) -> None:
        self._session_views.discard(sv)
        if not self._session_views:
            current_count = self._views_opened
            debounced(self.end_async, 3000, lambda: self._views_opened == current_count, async_thread=True)

    def session_views_async(self) -> Generator[SessionViewProtocol, None, None]:
        """
        It is only safe to iterate over this in the async thread
        """
        yield from self._session_views

    def session_view_for_view_async(self, view: sublime.View) -> Optional[SessionViewProtocol]:
        for sv in self.session_views_async():
            if sv.view == view:
                return sv
        return None

    def set_window_status_async(self, key: str, message: str) -> None:
        for sv in self.session_views_async():
            sv.view.set_status(key, message)

    def erase_window_status_async(self, key: str) -> None:
        for sv in self.session_views_async():
            sv.view.erase_status(key)

    # --- session buffer management ------------------------------------------------------------------------------------

    def register_session_buffer_async(self, sb: SessionBufferProtocol) -> None:
        self._session_buffers.add(sb)
        for data in self._registrations.values():
            data.check_applicable(sb)

    def unregister_session_buffer_async(self, sb: SessionBufferProtocol) -> None:
        self._session_buffers.discard(sb)

    def session_buffers_async(self) -> Generator[SessionBufferProtocol, None, None]:
        """
        It is only safe to iterate over this in the async thread
        """
        yield from self._session_buffers

    def get_session_buffer_for_uri_async(self, uri: str) -> Optional[SessionBufferProtocol]:
        file_name = uri_to_filename(uri)
        for sb in self.session_buffers_async():
            try:
                if sb.file_name == file_name or os.path.samefile(file_name, sb.file_name):
                    return sb
            except FileNotFoundError:
                pass
        return None

    # --- capability observers -----------------------------------------------------------------------------------------

    def can_handle(self, view: sublime.View, capability: Optional[str], inside_workspace: bool) -> bool:
        file_name = view.file_name() or ''
        if (self.config.match_view(view)
                and self.state == ClientStates.READY
                and self.handles_path(file_name, inside_workspace)):
            # If there's no capability requirement then this session can handle the view
            if capability is None:
                return True
            sv = self.session_view_for_view_async(view)
            if sv:
                return sv.has_capability_async(capability)
            else:
                return self.has_capability(capability)
        return False

    def has_capability(self, capability: str) -> bool:
        value = self.get_capability(capability)
        return value is not False and value is not None

    def get_capability(self, capability: str) -> Optional[Any]:
        return self.capabilities.get(capability)

    def should_notify_did_open(self) -> bool:
        return self.capabilities.should_notify_did_open()

    def text_sync_kind(self) -> int:
        return self.capabilities.text_sync_kind()

    def should_notify_did_change(self) -> bool:
        return self.capabilities.should_notify_did_change()

    def should_notify_did_change_workspace_folders(self) -> bool:
        return self.capabilities.should_notify_did_change_workspace_folders()

    def should_notify_will_save(self) -> bool:
        return self.capabilities.should_notify_will_save()

    def should_notify_did_save(self) -> Tuple[bool, bool]:
        return self.capabilities.should_notify_did_save()

    def should_notify_did_close(self) -> bool:
        return self.capabilities.should_notify_did_close()

    # --- misc methods -------------------------------------------------------------------------------------------------

    def handles_path(self, file_path: Optional[str], inside_workspace: bool) -> bool:
        if self._supports_workspace_folders():
            # A workspace-aware language server handles any path, both inside and outside the workspaces.
            return True
        # If we end up here then the language server is workspace-unaware. This means there can be more than one
        # language server with the same config name. So we have to actually do the subpath checks.
        if not file_path:
            return False
        if not self._workspace_folders or not inside_workspace:
            return True
        for folder in self._workspace_folders:
            if is_subpath_of(file_path, folder.path):
                return True
        return False

    def update_folders(self, folders: List[WorkspaceFolder]) -> None:
        if self.should_notify_did_change_workspace_folders():
            added, removed = diff(self._workspace_folders, folders)
            if added or removed:
                params = {
                    "event": {
                        "added": [a.to_lsp() for a in added],
                        "removed": [r.to_lsp() for r in removed]
                    }
                }
                self.send_notification(Notification.didChangeWorkspaceFolders(params))
        if self._supports_workspace_folders():
            self._workspace_folders = folders
        else:
            self._workspace_folders = folders[:1]

    def initialize_async(self, variables: Dict[str, str], transport: Transport, init_callback: InitCallback) -> None:
        self.transport = transport
        params = get_initialize_params(variables, self._workspace_folders, self.config)
        self._init_callback = init_callback
        self.send_request_async(
            Request.initialize(params), self._handle_initialize_success, self._handle_initialize_error)

    def _handle_initialize_success(self, result: Any) -> None:
        self.capabilities.assign(result.get('capabilities', dict()))
        if self._workspace_folders and not self._supports_workspace_folders():
            self._workspace_folders = self._workspace_folders[:1]
        self.state = ClientStates.READY
        if self._plugin_class is not None:
            self._plugin = self._plugin_class(weakref.ref(self))
        self.send_notification(Notification.initialized())
        self._maybe_send_did_change_configuration()
        execute_commands = self.get_capability('executeCommandProvider.commands')
        if execute_commands:
            debug("{}: Supported execute commands: {}".format(self.config.name, execute_commands))
        code_action_kinds = self.get_capability('codeActionProvider.codeActionKinds')
        if code_action_kinds:
            debug('{}: supported code action kinds: {}'.format(self.config.name, code_action_kinds))
        if self._init_callback:
            self._init_callback(self, False)
            self._init_callback = None

    def _handle_initialize_error(self, result: Any) -> None:
        self._initialize_error = (result.get('code', -1), Exception(result.get('message', 'Error initializing server')))
        # Init callback called after transport is closed to avoid pre-mature GC of Session.
        self.end_async()

    def call_manager(self, method: str, *args: Any) -> None:
        mgr = self.manager()
        if mgr:
            getattr(mgr, method)(*args)

    def clear_diagnostics_async(self) -> None:
        # XXX: Remove this functionality?
        for sb in self.session_buffers_async():
            sb.on_diagnostics_async([], None)

    def on_stderr_message(self, message: str) -> None:
        self.call_manager('handle_stderr_log', self, message)
        self._logger.stderr_message(message)

    def _supports_workspace_folders(self) -> bool:
        return self.has_capability("workspace.workspaceFolders.supported")

    def _maybe_send_did_change_configuration(self) -> None:
        if self.config.settings:
            variables = self._template_variables()
            resolved = self.config.settings.create_resolved(variables)
            if self._plugin:
                self._plugin.on_pre_workspace_configuration(resolved)
            self.send_notification(Notification("workspace/didChangeConfiguration", {"settings": resolved.get()}))

    def _template_variables(self) -> Dict[str, str]:
        variables = extract_variables(self.window)
        if self._plugin_class is not None:
            extra_vars = self._plugin_class.additional_variables()
            if extra_vars:
                variables.update(extra_vars)
        return variables

    def run_command(self, command: Mapping[str, Any]) -> Promise:
        """Run a command from any thread. Your .then() continuations will run in Sublime's worker thread."""
        if self._plugin:
            promise, callback = Promise.packaged_task()
            if self._plugin.on_pre_server_command(command, callback):
                return promise
        # TODO: Our Promise class should be able to handle errors/exceptions
        return Promise(
            lambda resolve: self.send_request(
                Request.executeCommand(command),
                resolve,
                lambda err: resolve(Error(err["code"], err["message"], err.get("data")))
            )
        )

    def run_code_action_async(self, code_action: Mapping[str, Any]) -> Promise:
        command = code_action.get("command")
        if isinstance(command, str):
            # This is actually a command.
            return self.run_command(code_action)
        # At this point it cannot be a command anymore, it has to be a proper code action.
        # A code action can have an edit and/or command. Note that it can have *both*. In case both are present, we
        # must apply the edits before running the command.
        if self.has_capability("codeActionProvider.resolveSupport"):
            # TODO: Should we accept a SessionBuffer? What if this capability is registered with a documentSelector?
            # We must first resolve the command and edit properties, because they can potentially be absent.
            promise = self.send_request_task(Request("codeAction/resolve", code_action))
        else:
            promise = Promise.resolve(code_action)
        return promise.then(self._apply_code_action_async)

    def _apply_code_action_async(self, code_action: Union[Error, Mapping[str, Any]]) -> Promise:
        if isinstance(code_action, Error):
            # TODO: our promise must be able to handle exceptions (or, wait until we can use coroutines)
            self.window.status_message("Failed to apply code action: {}".format(code_action))
            return Promise.resolve()
        command = code_action.get("command")
        edit = code_action.get("edit")
        promise = self._apply_workspace_edit_async(edit) if edit else Promise.resolve()
        return promise.then(lambda _: self.run_command(command) if isinstance(command, dict) else Promise.resolve())

    def _apply_workspace_edit_async(self, edit: Any) -> Promise:
        """
        Apply workspace edits, and return a promise that resolves on the async thread again after the edits have been
        applied.
        """
        changes = parse_workspace_edit(edit)
        return Promise.on_main_thread() \
            .then(lambda _: apply_workspace_edit(self.window, changes)) \
            .then(Promise.on_async_thread)

    # --- server request handlers --------------------------------------------------------------------------------------

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
            configuration = self.config.settings.copy(requested_item.get('section') or None)
            if self._plugin:
                self._plugin.on_workspace_configuration(requested_item, configuration)
            items.append(configuration)
        self.send_response(Response(request_id, sublime.expand_variables(items, self._template_variables())))

    def m_workspace_applyEdit(self, params: Any, request_id: Any) -> None:
        """handles the workspace/applyEdit request"""
        self._apply_workspace_edit_async(params.get('edit', {})).then(
            lambda _: self.send_response(Response(request_id, {"applied": True})))

    def m_textDocument_publishDiagnostics(self, params: Any) -> None:
        """handles the textDocument/publishDiagnostics notification"""
        uri = params["uri"]
        sb = self.get_session_buffer_for_uri_async(uri)
        if sb:
            sb.on_diagnostics_async(params["diagnostics"], params.get("version"))

    def m_client_registerCapability(self, params: Any, request_id: Any) -> None:
        """handles the client/registerCapability request"""
        registrations = params["registrations"]
        for registration in registrations:
            registration_id = registration["id"]
            capability_path, registration_path = method_to_capability(registration["method"])
            debug("{}: registering capability:".format(self.config.name), capability_path)
            options = registration.get("registerOptions")  # type: Optional[Dict[str, Any]]
            if not isinstance(options, dict):
                options = {}
            data = _RegistrationData(registration_id, capability_path, registration_path, options)
            self._registrations[registration_id] = data
            if data.selector:
                # The registration is applicable only to certain buffers, so let's check which buffers apply.
                for sb in self.session_buffers_async():
                    data.check_applicable(sb)
            else:
                # The registration applies globally to all buffers.
                self.capabilities.register(registration_id, capability_path, registration_path, options)
                # We must inform our SessionViews of the new capabilities, in case it's for instance a hoverProvider
                # or a completionProvider for trigger characters.
                for sv in self.session_views_async():
                    sv.on_capability_added_async(registration_id, capability_path, options)
        self.send_response(Response(request_id, None))

    def m_client_unregisterCapability(self, params: Any, request_id: Any) -> None:
        """handles the client/unregisterCapability request"""
        unregistrations = params["unregisterations"]  # typo in the official specification
        for unregistration in unregistrations:
            registration_id = unregistration["id"]
            capability_path, registration_path = method_to_capability(unregistration["method"])
            debug("{}: unregistering capability:".format(self.config.name), capability_path)
            data = self._registrations.pop(registration_id, None)
            if not data:
                message = "no registration data found for registration ID {}".format(registration_id)
                self.send_error_response(request_id, Error(ErrorCode.InvalidParams, message))
                return
            elif not data.selector:
                discarded = self.capabilities.unregister(registration_id, capability_path, registration_path)
                # We must inform our SessionViews of the removed capabilities, in case it's for instance a hoverProvider
                # or a completionProvider for trigger characters.
                if isinstance(discarded, dict):
                    for sv in self.session_views_async():
                        sv.on_capability_removed_async(registration_id, discarded)
        self.send_response(Response(request_id, None))

    def m_window_showDocument(self, params: Any, request_id: Any) -> None:
        """handles the window/showDocument request"""
        uri = params.get("uri")

        def success(b: bool) -> None:
            self.send_response(Response(request_id, {"success": b}))

        if params.get("external"):
            success(open_externally(uri, bool(params.get("takeFocus"))))
        else:
            # TODO: ST API does not allow us to say "do not focus this new view"
            filename = uri_to_filename(uri)
            selection = params.get("selection")
            open_file_and_center_async(self.window, filename, selection).then(lambda _: success(True))

    def m_window_workDoneProgress_create(self, params: Any, request_id: Any) -> None:
        """handles the window/workDoneProgress/create request"""
        self._progress[params['token']] = dict()
        self.send_response(Response(request_id, None))

    def _progress_status_key(self, token: str) -> str:
        return "lspprogress{}{}".format(self.config.name, token)

    def m___progress(self, params: Any) -> None:
        """handles the $/progress notification"""
        token = params['token']
        data = self._progress.get(token)
        if not isinstance(data, dict):
            debug('unknown $/progress token: {}'.format(token))
            return
        value = params['value']
        kind = value['kind']
        key = self._progress_status_key(token)
        if kind == 'begin':
            data['title'] = value['title']  # mandatory
            data['message'] = value.get('message')  # optional
            progress_string = self._progress_string(data, value)
            self.set_window_status_async(key, progress_string)
        elif kind == 'report':
            progress_string = self._progress_string(data, value)
            self.set_window_status_async(key, progress_string)
        elif kind == 'end':
            message = value.get('message')
            if message:
                self.window.status_message(data['title'] + ': ' + message)
            self.erase_window_status_async(key)
            self._progress.pop(token, None)

    def _progress_string(self, data: Dict[str, Any], value: Dict[str, Any]) -> str:
        status_msg = data['title']
        progress_message = value.get('message')  # optional
        progress_percentage = value.get('percentage')  # optional
        if progress_message:
            data['message'] = progress_message
            status_msg += ': ' + progress_message
        elif data['message']:  # reuse last known message if not present
            status_msg += ': ' + data['message']
        if progress_percentage:
            fmt = ' ({:.1f}%)' if isinstance(progress_percentage, float) else ' ({}%)'
            status_msg += fmt.format(progress_percentage)
        return status_msg

    # --- shutdown dance -----------------------------------------------------------------------------------------------

    def end_async(self) -> None:
        # TODO: Ensure this function is called only from the async thread
        if self.exiting:
            return
        self.exiting = True
        self._plugin = None
        for sv in self.session_views_async():
            sv.shutdown_async()
        self.capabilities.clear()
        self._registrations.clear()
        self.state = ClientStates.STOPPING
        self.send_request_async(Request.shutdown(), self._handle_shutdown_result, self._handle_shutdown_result)

    def _handle_shutdown_result(self, _: Any) -> None:
        self.exit()

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        self.exiting = True
        self.state = ClientStates.STOPPING
        self.transport = None
        self._response_handlers.clear()
        if self._initialize_error:
            # Override potential exit error with a saved one.
            exit_code, exception = self._initialize_error
        mgr = self.manager()
        if mgr:
            if self._init_callback:
                self._init_callback(self, True)
                self._init_callback = None
            mgr.on_post_exit_async(self, exit_code, exception)

    # --- RPC message handling ----------------------------------------------------------------------------------------

    def send_request_async(
            self,
            request: Request,
            on_result: Callable[[Any], None],
            on_error: Optional[Callable[[Any], None]] = None
    ) -> None:
        """You must call this method from Sublime's worker thread. Callbacks will run in Sublime's worker thread."""
        self.request_id += 1
        request_id = self.request_id
        self._response_handlers[request_id] = (request, on_result, on_error)
        if request.view:
            sv = self.session_view_for_view_async(request.view)
            if sv:
                sv.on_request_started_async(request_id, request)
        else:
            # This is a workspace or window request
            for sv in self.session_views_async():
                sv.on_request_started_async(request_id, request)
        self._logger.outgoing_request(request_id, request.method, request.params)
        self.send_payload(request.to_payload(request_id))

    def send_request(
            self,
            request: Request,
            on_result: Callable[[Any], None],
            on_error: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """You can call this method from any thread. Callbacks will run in Sublime's worker thread."""
        sublime.set_timeout_async(functools.partial(self.send_request_async, request, on_result, on_error))

    def send_request_task(self, request: Request) -> Promise:
        promise, resolver = Promise.packaged_task()
        self.send_request_async(request, resolver, lambda x: resolver(Error.from_lsp(x)))
        return promise

    def send_notification(self, notification: Notification) -> None:
        self._logger.outgoing_notification(notification.method, notification.params)
        self.send_payload(notification.to_payload())

    def send_response(self, response: Response) -> None:
        self._logger.outgoing_response(response.request_id, response.result)
        self.send_payload(response.to_payload())

    def send_error_response(self, request_id: Any, error: Error) -> None:
        self._logger.outgoing_error_response(request_id, error)
        self.send_payload({'jsonrpc': '2.0', 'id': request_id, 'error': error.to_lsp()})

    def exit(self) -> None:
        self.send_notification(Notification.exit())
        try:
            self.transport.close()  # type: ignore
        except AttributeError:
            pass

    def send_payload(self, payload: Dict[str, Any]) -> None:
        try:
            self.transport.send(payload)  # type: ignore
        except AttributeError:
            pass

    def deduce_payload(
        self,
        payload: Dict[str, Any]
    ) -> Tuple[Optional[Callable], Any, Optional[int], Optional[str], Optional[str]]:
        if "method" in payload:
            method = payload["method"]
            handler = self._get_handler(method)
            result = payload.get("params")
            if "id" in payload:
                req_id = payload["id"]
                self._logger.incoming_request(req_id, method, result)
                if handler is None:
                    self.send_error_response(req_id, Error(ErrorCode.MethodNotFound, method))
                else:
                    tup = (handler, result, req_id, "request", method)
                    return tup
            else:
                res = (handler, result, None, "notification", method)
                self._logger.incoming_notification(method, result, res[0] is None)
                return res
        elif "id" in payload:
            response_id = int(payload["id"])
            handler, result, is_error = self.response_handler(response_id, payload)
            response_tuple = (handler, result, None, None, None)
            self._logger.incoming_response(response_id, result, is_error)
            return response_tuple
        else:
            debug("Unknown payload type: ", payload)
        return (None, None, None, None, None)

    def on_payload(self, payload: Dict[str, Any]) -> None:
        handler, result, req_id, typestr, method = self.deduce_payload(payload)
        if handler:
            try:
                if req_id is None:
                    # notification or response
                    handler(result)
                else:
                    # request
                    try:
                        handler(result, req_id)
                    except Error as err:
                        self.send_error_response(req_id, err)
                    except Exception as ex:
                        self.send_error_response(req_id, Error.from_exception(ex))
                        raise
            except Exception as err:
                exception_log("Error handling {}".format(typestr), err)

    def response_handler(self, response_id: int, response: Dict[str, Any]) -> Tuple[Optional[Callable], Any, bool]:
        request, handler, error_handler = self._response_handlers.pop(response_id, (None, None, None))
        if not request:
            error = {"code": ErrorCode.InvalidParams, "message": "unknown response ID {}".format(response_id)}
            return (print_to_status_bar, error, True)
        if request.view:
            sv = self.session_view_for_view_async(request.view)
            if sv:
                sv.on_request_finished_async(response_id)
        else:
            for sv in self.session_views_async():
                sv.on_request_finished_async(response_id)
        if "result" in response and "error" not in response:
            return (handler, response["result"], False)
        if not error_handler:
            error_handler = print_to_status_bar
        if "result" not in response and "error" in response:
            error = response["error"]
        else:
            error = {"code": ErrorCode.InvalidParams, "message": "invalid response payload"}
        return (error_handler, error, True)

    def _get_handler(self, method: str) -> Optional[Callable]:
        return getattr(self, method2attr(method), None)
