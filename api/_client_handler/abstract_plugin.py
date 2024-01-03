from .._util import weak_method
from ..api_wrapper_interface import ApiWrapperInterface
from ..server_resource_interface import ServerStatus
from .api_decorator import register_decorated_handlers
from .interface import ClientHandlerInterface
from functools import partial
from LSP.plugin import AbstractPlugin
from LSP.plugin import ClientConfig
from LSP.plugin import Notification
from LSP.plugin import register_plugin
from LSP.plugin import Request
from LSP.plugin import Response
from LSP.plugin import Session
from LSP.plugin import unregister_plugin
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.rpc import method2attr
from LSP.plugin.core.typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict
from os import path
from weakref import ref
import sublime

__all__ = ['ClientHandler']

LanguagesDict = TypedDict('LanguagesDict', {
    'document_selector': Optional[str],
    'languageId': Optional[str],
    'scopes': Optional[List[str]],
    'syntaxes': Optional[List[str]],
}, total=False)
ApiNotificationHandler = Callable[[Any], None]
ApiRequestHandler = Callable[[Any, Callable[[Any], None]], None]


class ApiWrapper(ApiWrapperInterface):
    def __init__(self, plugin: 'ref[AbstractPlugin]'):
        self.__plugin = plugin

    def __session(self) -> Optional[Session]:
        plugin = self.__plugin()
        return plugin.weaksession() if plugin else None

    # --- ApiWrapperInterface -----------------------------------------------------------------------------------------

    def on_notification(self, method: str, handler: ApiNotificationHandler) -> None:
        def handle_notification(weak_handler: ApiNotificationHandler, params: Any) -> None:
            weak_handler(params)

        plugin = self.__plugin()
        if plugin:
            setattr(plugin, method2attr(method), partial(handle_notification, weak_method(handler)))

    def on_request(self, method: str, handler: ApiRequestHandler) -> None:
        def send_response(request_id: Any, result: Any) -> None:
            session = self.__session()
            if session:
                session.send_response(Response(request_id, result))

        def on_response(weak_handler: ApiRequestHandler, params: Any, request_id: Any) -> None:
            weak_handler(params, lambda result: send_response(request_id, result))

        plugin = self.__plugin()
        if plugin:
            setattr(plugin, method2attr(method), partial(on_response, weak_method(handler)))

    def send_notification(self, method: str, params: Any) -> None:
        session = self.__session()
        if session:
            session.send_notification(Notification(method, params))

    def send_request(self, method: str, params: Any, handler: Callable[[Any, bool], None]) -> None:
        session = self.__session()
        if session:
            session.send_request(
                Request(method, params), lambda result: handler(result, False), lambda result: handler(result, True))
        else:
            handler(None, True)


class ClientHandler(AbstractPlugin, ClientHandlerInterface):
    """
    The base class for creating an LSP plugin.
    """

    # --- AbstractPlugin handlers -------------------------------------------------------------------------------------

    @classmethod
    def name(cls) -> str:
        return cls.get_displayed_name()

    @classmethod
    def configuration(cls) -> Tuple[sublime.Settings, str]:
        return cls.read_settings()

    @classmethod
    def additional_variables(cls) -> Dict[str, str]:
        return cls.get_additional_variables()

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        if cls.manages_server():
            server = cls.get_server()
            return bool(server and server.needs_installation())
        return False

    @classmethod
    def install_or_update(cls) -> None:
        server = cls.get_server()
        if server:
            server.install_or_update()

    @classmethod
    def can_start(cls, window: sublime.Window, initiating_view: sublime.View,
                  workspace_folders: List[WorkspaceFolder], configuration: ClientConfig) -> Optional[str]:
        if cls.manages_server():
            server = cls.get_server()
            if not server or server.get_status() == ServerStatus.ERROR:
                return "{}: Error installing server dependencies.".format(cls.package_name)
            if server.get_status() != ServerStatus.READY:
                return "{}: Server installation in progress...".format(cls.package_name)
        message = cls.is_allowed_to_start(window, initiating_view, workspace_folders, configuration)
        if message:
            return message
        # Lazily update command after server has initialized if not set manually by the user.
        if not configuration.command:
            configuration.command = cls.get_command()
        return None

    @classmethod
    def on_pre_start(cls, window: sublime.Window, initiating_view: sublime.View,
                     workspace_folders: List[WorkspaceFolder], configuration: ClientConfig) -> Optional[str]:
        extra_paths = path.pathsep.join(cls.get_additional_paths())
        if extra_paths:
            original_path = configuration.env.get('PATH') or ''
            if isinstance(original_path, list):
                original_path = path.pathsep.join(original_path)
            configuration.env['PATH'] = path.pathsep.join([extra_paths, original_path])
        return None

    # --- ClientHandlerInterface --------------------------------------------------------------------------------------

    @classmethod
    def setup(cls) -> None:
        register_plugin(cls)

    @classmethod
    def cleanup(cls) -> None:
        unregister_plugin(cls)

    # --- Internals ---------------------------------------------------------------------------------------------------

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        api = ApiWrapper(ref(self))  # type: ignore
        register_decorated_handlers(self, api)
        self.on_ready(api)
