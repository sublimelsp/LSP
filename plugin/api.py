from __future__ import annotations
from .core.constants import ST_STORAGE_PATH
from .core.url import parse_uri
from .core.views import uri_from_view
from abc import ABCMeta
from abc import abstractmethod
from typing import Any, Callable, Literal, TypedDict, final, TYPE_CHECKING
import sublime

if TYPE_CHECKING:
    from ..protocol import ConfigurationItem
    from ..protocol import DocumentUri
    from ..protocol import ExecuteCommandParams
    from .core.collections import DottedDict
    from .core.protocol import Notification
    from .core.protocol import Request
    from .core.protocol import Response
    from .core.sessions import Session
    from .core.sessions import SessionBufferProtocol
    from .core.sessions import SessionViewProtocol
    from .core.types import ClientConfig
    from .core.views import MarkdownLangMap
    from .core.workspace import WorkspaceFolder
    from weakref import ref


class HandleUpdateOrInstallationParams(TypedDict):
    set_installing_status: Callable[[], None]


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


class LspPlugin(metaclass=ABCMeta):
    """
    TODO: doc
    """

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """
        A human-friendly name. If your plugin is called "LSP-foobar", then this should return "foobar". If you also
        have your settings file called "LSP-foobar.sublime-settings", then you don't even need to re-implement the
        configuration method (see below).
        """
        raise NotImplementedError

    @classmethod
    def configuration(cls) -> tuple[sublime.Settings, str]:
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
        basename = f"LSP-{name}.sublime-settings"
        filepath = f"Packages/LSP-{name}/{basename}"
        return sublime.load_settings(basename), filepath

    @classmethod
    def is_applicable(cls, context: PluginContext, view: sublime.View) -> bool:
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

    def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
        """
        Intercept a command that is about to be sent to the language server.

        :param    command:        The payload containing a "command" and optionally "arguments".
        :param    done_callback:  The callback that you promise to invoke when you return true.

        :returns: True if *YOU* will handle this command plugin-side, false otherwise. You must invoke the
                  passed `done_callback` when you're done.
        """
        return False

    def on_pre_send_request_async(self, request_id: int, request: Request) -> None:
        """
        Notifies about a request that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    request_id:  The request ID.
        :param    request:     The request object. The request params can be modified by the plugin.
        """
        return

    def on_pre_send_notification_async(self, notification: Notification) -> None:
        """
        Notifies about a notification that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    notification:  The notification object. The notification params can be modified by the plugin.
        """
        return

    def on_server_response_async(self, method: str, response: Response) -> None:
        """
        Notifies about a response message that has been received from the language server.
        Only successful responses are passed to this method.

        :param    method:    The method of the request.
        :param    response:  The response object to the request. The response.result field can be modified by the
                             plugin, before it gets further handled by the LSP package.
        """
        return

    def on_server_notification_async(self, notification: Notification) -> None:
        """
        Notifies about a notification message that has been received from the language server.

        :param    notification:  The notification object.
        """
        return

    def on_open_uri_async(self, uri: DocumentUri, callback: Callable[[str, str, str], None]) -> bool:
        """
        Called when a language server reports to open an URI. If you know how to handle this URI, then return True and
        invoke the passed-in callback some time.

        The arguments of the provided callback work as follows:

        - The first argument is the title of the view that will be populated with the content of a new scratch view
        - The second argument is the content of the view
        - The third argument is the syntax to apply for the new view
        """
        return False

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
