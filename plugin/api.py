from __future__ import annotations

from ..protocol import ConfigurationItem
from ..protocol import DocumentUri
from ..protocol import ExecuteCommandParams
from ..protocol import LSPAny
from .core.constants import ST_STORAGE_PATH
from .core.logging import exception_log
from .core.protocol import Notification
from .core.protocol import Request
from .core.protocol import Response
from .core.settings import client_configs
from .core.types import ClientConfig
from .core.types import method2attr
from .core.types import SettingsRegistration
from .core.url import parse_uri
from .core.views import MarkdownLangMap
from .core.views import uri_from_view
from .core.workspace import WorkspaceFolder
from abc import ABC
from abc import abstractmethod
from functools import partial
from functools import wraps
from typing import Any
from typing import Callable
from typing import TYPE_CHECKING
from typing import TypeVar
from typing_extensions import deprecated
import inspect
import sublime

if TYPE_CHECKING:
    from .core.collections import DottedDict
    from .core.promise import Promise
    from .core.sessions import Session
    from plugin.core.sessions import SessionBufferProtocol
    from plugin.core.sessions import SessionViewProtocol
    import weakref

__all__ = [
    'APIHandler',
    'notification_handler',
    'request_handler',
]

HANDLER_MARKER = '__HANDLER_MARKER'

# P represents the parameters *after* the 'self' argument
P = TypeVar('P', bound=LSPAny)
R = TypeVar('R', bound=LSPAny)


g_plugins: dict[str, type[AbstractPlugin]] = {}


def register_plugin(plugin: type[AbstractPlugin], notify_listener: bool = True) -> None:
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


def unregister_plugin(plugin: type[AbstractPlugin]) -> None:
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
        exception_log(f'Failed to unregister plugin "{name}"', ex)


def get_plugin(name: str) -> type[AbstractPlugin] | None:
    global _plugins
    tup = _plugins.get(name, None)
    return tup[0] if tup else None


class APIHandler:
    """Trigger initialization of decorated API methods."""

    def __init__(self) -> None:
        super().__init__()
        for _, method in inspect.getmembers(self, inspect.ismethod):
            if hasattr(method, HANDLER_MARKER):
                # Set method with transformed name on the class instance.
                setattr(self, method2attr(getattr(method, HANDLER_MARKER)), method)


def notification_handler(method: str) -> Callable[[Callable[[Any, P], None]], Callable[[Any, P], None]]:
    """Decorator to mark a method as a handler for a specific LSP notification.

    Usage:
        ```py
        @notification_handler('eslint/status')
        def on_eslint_status(self, params: str) -> None:
            ...
        ```

    The decorated method will be called with the notification parameters whenever the specified
    notification is received from the language server. Notification handlers do not return a value.

    :param      method:             The LSP notification method name (e.g., 'eslint/status').
    :returns:   A decorator that registers the function as a notification handler.
    """

    def decorator(func: Callable[[Any, P], None]) -> Callable[[Any, P], None]:
        setattr(func, HANDLER_MARKER, method)
        return func

    return decorator


def request_handler(
    method: str
) -> Callable[[Callable[[Any, P], Promise[R]]], Callable[[Any, P, int], Promise[Response[R]]]]:
    """Decorator to mark a method as a handler for a specific LSP request.

    Usage:
        ```py
        @request_handler('eslint/openDoc')
        def on_open_doc(self, params: TextDocumentIdentifier) -> Promise[bool]:
            ...
        ```

    The decorated method will be called with the request parameters whenever the specified
    request is received from the language server. The method must return a Promise that resolves
    to the response value. The framework will automatically send it back to the server.

    :param      method:             The LSP request method name (e.g., 'eslint/openDoc').
    :returns:   A decorator that registers the function as a request handler.
    """

    def decorator(func: Callable[[Any, P], Promise[R]]) -> Callable[[Any, P, int], Promise[Response[R]]]:

        @wraps(func)
        def wrapper(self: Any, params: P, request_id: int) -> Promise[Response[Any]]:
            promise = func(self, params)
            return promise.then(lambda result: Response(request_id, result))

        setattr(wrapper, HANDLER_MARKER, method)
        return wrapper

    return decorator


class AbstractPlugin(APIHandler, ABC):

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
    def configuration(cls) -> tuple[sublime.Settings, str]:
        """
        Return the Settings object that defines the "command", "selector", and optionally the "initializationOptions",
        "env" and "tcp_port" as the first element in the tuple, and the path to the base settings
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
        basename = f"LSP-{name}.sublime-settings"
        filepath = f"Packages/LSP-{name}/{basename}"
        return sublime.load_settings(basename), filepath

    @classmethod
    def is_applicable(cls, view: sublime.View, config: ClientConfig) -> bool:
        """
        Determine whether the server should run on the given view.

        The default implementation checks whether the URI scheme and the syntax scope match against the schemes and
        selector from the settings file. You can override this method for example to dynamically evaluate the applicable
        selector, or to ignore certain views even when those would match the static config. Please note that no document
        syncronization messages (textDocument/didOpen, textDocument/didChange, textDocument/didClose, etc.) are sent to
        the server for ignored views.

        This method is called when the view gets opened. To manually trigger this method again, run the
        `lsp_check_applicable` TextCommand for the given view and with a `session_name` keyword argument.

        :param      view:             The view
        :param      config:           The config
        """
        if (syntax := view.syntax()) and (selector := cls.selector(view, config).strip()):
            # TODO replace `cls.selector(view, config)` with `config.selector` after the next release
            scheme, _ = parse_uri(uri_from_view(view))
            return scheme in config.schemes and sublime.score_selector(syntax.scope, selector) > 0
        return False

    @classmethod
    @deprecated("Use `is_applicable(view, config)` instead.")
    def selector(cls, view: sublime.View, config: ClientConfig) -> str:
        return config.selector

    @classmethod
    def additional_variables(cls) -> dict[str, str] | None:
        """
        In addition to the above variables, add more variables here to be expanded.
        """
        return None

    @classmethod
    def storage_path(cls) -> str:
        """
        The storage path. Use this as your base directory to install server files. Its path is '$DATA/Package Storage'.
        You should have an additional subdirectory preferably the same name as your plugin. For instance:

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
        return ST_STORAGE_PATH

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
                  workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> str | None:
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
                     workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> str | None:
        """
        Callback invoked just before the language server subprocess is started. This is the place to do last-minute
        adjustments to your "command" or "init_options" in the passed-in "configuration" argument, or change the
        order of the workspace folders. You can also choose to return a custom working directory, but consider that a
        language server should not care about the working directory.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders, you can modify these
        :param      configuration:      The configuration, you can modify this one

        :returns:   A desired working directory, or None if you don't care
        """
        return None

    @classmethod
    def on_post_start(cls, window: sublime.Window, initiating_view: sublime.View,
                      workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> None:
        """
        Callback invoked when the subprocess was just started.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders
        :param      configuration:      The configuration
        """
        pass

    @classmethod
    @deprecated("Use `is_applicable(view, config)` instead.")
    def should_ignore(cls, view: sublime.View) -> bool:
        return False

    @classmethod
    def markdown_language_id_to_st_syntax_map(cls) -> MarkdownLangMap | None:
        """
        Override this method to tweak the syntax highlighting of code blocks in popups from your language server.
        The returned object should be a dictionary exactly in the form of mdpopup's language_map setting.

        See: https://facelessuser.github.io/sublime-markdown-popups/settings/#mdpopupssublime_user_lang_map

        :returns:   The markdown language map, or None
        """
        return None

    def __init__(self, weaksession: weakref.ref[Session]) -> None:
        """
        Constructs a new instance. Your instance is constructed after a response to the initialize request.

        :param      weaksession:  A weak reference to the Session. You can grab a strong reference through
                                  self.weaksession(), but don't hold on to that reference.
        """

        super().__init__()
        self.weaksession = weaksession

    def on_settings_changed(self, settings: DottedDict) -> None:
        """
        Override this method to alter the settings that are returned to the server for the
        workspace/didChangeConfiguration notification and the workspace/configuration requests.

        :param      settings:      The settings that the server should receive.
        """
        pass

    def on_workspace_configuration(self, params: ConfigurationItem, configuration: Any) -> Any:
        """
        Override to augment configuration returned for the workspace/configuration request.

        :param      params:         A ConfigurationItem for which configuration is requested.
        :param      configuration:  The pre-resolved configuration for given params using the settings object or None.

        :returns: The resolved configuration for given params.
        """
        return configuration

    def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
        """
        Intercept a command that is about to be sent to the language server.

        :param    command:        The payload containing a "command" and optionally "arguments".
        :param    done_callback:  The callback that you promise to invoke when you return true.

        :returns: True if *YOU* will handle this command plugin-side, false otherwise. You must invoke the
                  passed `done_callback` when you're done.
        """
        return False

    def on_pre_send_request_async(self, request_id: int, request: Request[Any, Any]) -> None:
        """
        Notifies about a request that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    request_id:  The request ID.
        :param    request:     The request object. The request params can be modified by the plugin.
        """
        pass

    def on_pre_send_notification_async(self, notification: Notification[Any]) -> None:
        """
        Notifies about a notification that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    notification:  The notification object. The notification params can be modified by the plugin.
        """
        pass

    def on_server_response_async(self, method: str, response: Response[Any]) -> None:
        """
        Notifies about a response message that has been received from the language server.
        Only successful responses are passed to this method.

        :param    method:    The method of the request.
        :param    response:  The response object to the request. The response.result field can be modified by the
                             plugin, before it gets further handled by the LSP package.
        """
        pass

    def on_server_notification_async(self, notification: Notification[Any]) -> None:
        """
        Notifies about a notification message that has been received from the language server.

        :param    notification:  The notification object.
        """
        pass

    def on_open_uri_async(self, uri: DocumentUri, callback: Callable[[str | None, str, str], None]) -> bool:
        """
        Called when a language server reports to open an URI. If you know how to handle this URI, then return True and
        invoke the passed-in callback some time.

        The arguments of the provided callback work as follows:

        - The first argument is the title of the view that will be populated with the content of a new scratch view.
          If `None` is passed, no new view will be opened and the other arguments are ignored.
        - The second argument is the content of the view.
        - The third argument is the syntax to apply for the new view.
        """
        return False

    def on_session_buffer_changed_async(self, session_buffer: SessionBufferProtocol) -> None:
        """
        Called when the context of the session buffer has changed or a new buffer was opened.
        """
        pass

    def on_selection_modified_async(self, session_view: SessionViewProtocol) -> None:
        """
        Called after the selection has been modified in a view (debounced).
        """
        pass

    def on_session_end_async(self, exit_code: int | None, exception: Exception | None) -> None:
        """
        Notifies about the session ending (also if the session has crashed). Provides an opportunity to clean up
        any stored state or delete references to the session or plugin instance that would otherwise prevent the
        instance from being garbage-collected.

        If the session hasn't crashed, a shutdown message will be send immediately
        after this method returns. In this case exit_code and exception are None.
        If the session has crashed, the exit_code and an optional exception are provided.

        This API is triggered on async thread.
        """
        pass


_plugins: dict[str, tuple[type[AbstractPlugin], SettingsRegistration]] = {}


def _register_plugin_impl(plugin: type[AbstractPlugin], notify_listener: bool) -> None:
    global _plugins
    name = plugin.name()
    if name in _plugins:
        return
    try:
        settings, base_file = plugin.configuration()
        if client_configs.add_external_config(name, settings, base_file, notify_listener):
            on_change = partial(client_configs.update_external_config, name, settings, base_file)
            _plugins[name] = (plugin, SettingsRegistration(settings, on_change))
    except Exception as ex:
        exception_log(f'Failed to register plugin "{name}"', ex)
