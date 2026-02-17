from __future__ import annotations
from ..protocol import LSPAny
from .core.constants import ST_STORAGE_PATH
from .core.protocol import Response
from .core.types import method2attr
from .core.url import parse_uri
from .core.views import uri_from_view
from functools import wraps
from pathlib import Path
from typing import Any, Callable, ClassVar, TypedDict, TypeVar, final, TYPE_CHECKING
import inspect
import sublime

if TYPE_CHECKING:
    from ..protocol import ConfigurationItem
    from ..protocol import DocumentUri
    from ..protocol import ExecuteCommandParams
    from .core.collections import DottedDict
    from .core.promise import Promise
    from .core.protocol import Notification
    from .core.protocol import Request
    from .core.sessions import Session
    from .core.sessions import SessionBufferProtocol
    from .core.sessions import SessionViewProtocol
    from .core.types import ClientConfig
    from .core.views import MarkdownLangMap
    from .core.workspace import WorkspaceFolder
    from weakref import ref

__all__ = [
    'APIHandler',
    'notification_handler',
    'request_handler',
]

HANDLER_MARKER = '__HANDLER_MARKER'

# P represents the parameters *after* the 'self' argument
P = TypeVar('P', bound=LSPAny)
R = TypeVar('R', bound=LSPAny)


class HandleUpdateOrInstallationParams(TypedDict):
    set_installing_status: Callable[[], None]


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


@final
class PluginContext:
    def __init__(
        self,
        configuration: ClientConfig,
        initiating_view: sublime.View,
        window: sublime.Window,
        workspace_folders: list[WorkspaceFolder]
    ) -> None:
        self.configuration = configuration
        self.initiating_view = initiating_view
        self.window = window
        self.workspace_folders = workspace_folders


class LspPlugin:

    storage_path: ClassVar[Path] = Path(ST_STORAGE_PATH)
    """
    The storage path. Use this as your base directory to install server files. Its path is '$DATA/Package Storage'.
    You should have an additional subdirectory preferably the same name as your plugin. For instance:

    ```py
    from LSP.plugin import LspPlugin
    from pathlib import Path


    class MyPlugin(LspPlugin):

        @classmethod
        def basedir(cls) -> Path:
            # Do everything relative to this directory
            return cls.storage_path / 'LSP-myplugin'
    ```
    """

    @classmethod
    def is_applicable(cls, context: PluginContext) -> bool:
        """
        Determine whether the server should run on the given view.

        The default implementation checks whether the URI scheme and the syntax scope match against the schemes and
        selector from the settings file. You can override this method for example to dynamically evaluate the applicable
        selector, or to ignore certain views even when those would match the static config. Please note that no document
        syncronization messages (textDocument/didOpen, textDocument/didChange, textDocument/didClose, etc.) are sent to
        the server for ignored views.

        This method is called when the view gets opened. To manually trigger this method again, run the
        `lsp_check_applicable` TextCommand for the given view and with a `session_name` keyword argument.

        :param      context:           The plugin context
        """
        view = context.initiating_view
        if (syntax := view.syntax()) and (selector := context.configuration.selector.strip()):
            scheme, _ = parse_uri(uri_from_view(view))
            return scheme in context.configuration.schemes and sublime.score_selector(syntax.scope, selector) > 0
        return False

    @classmethod
    def additional_variables(cls, context: PluginContext) -> dict[str, str] | None:
        """
        In addition to the above variables, add more variables here to be expanded.
        """
        return None

    @classmethod
    def install_async(cls, context: PluginContext) -> None:
        """Update or install the server binary if this plugin manages one. Called before server is started.

        Make sure to call `params.set_installing_status()` before starting long-running operations to give user
        a better feedback that something is happening.
        """
        return

    @classmethod
    def can_start(cls, context: PluginContext) -> str | None:
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
    def on_pre_start(cls, context: PluginContext) -> str | None:
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
    def markdown_language_id_to_st_syntax_map(cls) -> MarkdownLangMap | None:
        """
        Override this method to tweak the syntax highlighting of code blocks in popups from your language server.
        The returned object should be a dictionary exactly in the form of mdpopup's language_map setting.

        See: https://facelessuser.github.io/sublime-markdown-popups/settings/#mdpopupssublime_user_lang_map

        :returns:   The markdown language map, or None
        """
        return None

    def __init__(self, weaksession: ref[Session], context: PluginContext) -> None:
        """
        Constructs a new instance. Your instance is constructed after a response to the initialize request.

        :param      weaksession:  A weak reference to the Session. You can grab a strong reference through
                                  self.weaksession(), but don't hold on to that reference.
        """
        self.weaksession: ref[Session] = weaksession
        self.context: PluginContext = context

    # ------------- OLD --------------

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

    def on_settings_changed(self, settings: DottedDict) -> None:
        """
        Override this method to alter the settings that are returned to the server for the
        workspace/didChangeConfiguration notification and the workspace/configuration requests.

        :param      settings:      The settings that the server should receive.
        """
        return

    def on_workspace_configuration(self, params: ConfigurationItem, configuration: Any) -> Any:
        """
        Override to augment configuration returned for the workspace/configuration request.

        :param      params:         A ConfigurationItem for which configuration is requested.
        :param      configuration:  The pre-resolved configuration for given params using the settings object or None.

        :returns: The resolved configuration for given params.
        """
        return configuration

    def on_execute_command(self, command: ExecuteCommandParams) -> Promise[None] | None:
        """
        Intercept a command that is about to be sent to the language server.

        :param    command:        The payload containing a "command" and optionally "arguments".

        :returns: Promise if *YOU* will handle this command plugin-side, None otherwise.
        """
        return None

    def on_pre_send_request_async(self, request_id: int, request: Request[Any, Any]) -> None:
        """
        Notifies about a request that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    request_id:  The request ID.
        :param    request:     The request object. The request params can be modified by the plugin.
        """
        return

    def on_pre_send_notification_async(self, notification: Notification[Any]) -> None:
        """
        Notifies about a notification that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    notification:  The notification object. The notification params can be modified by the plugin.
        """
        return

    def on_server_response_async(self, method: str, response: Response[Any]) -> None:
        """
        Notifies about a response message that has been received from the language server.
        Only successful responses are passed to this method.

        :param    method:    The method of the request.
        :param    response:  The response object to the request. The response.result field can be modified by the
                             plugin, before it gets further handled by the LSP package.
        """
        return

    def on_server_notification_async(self, notification: Notification[Any]) -> None:
        """
        Notifies about a notification message that has been received from the language server.

        :param    notification:  The notification object.
        """
        return

    def on_open_uri_async(self, uri: DocumentUri) -> Promise[sublime.Sheet] | None:
        """
        Called when a language server reports to open an URI. If you know how to handle this URI, then return a Promise
        resolved with `sublime.Sheet` instance.
        """
        return None

    def on_session_buffer_changed_async(self, session_buffer: SessionBufferProtocol) -> None:
        """
        Called when the context of the session buffer has changed or a new buffer was opened.
        """
        return

    def on_selection_modified_async(self, session_view: SessionViewProtocol) -> None:
        """
        Called after the selection has been modified in a view (debounced).
        """
        return

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
        return
