from ..api_wrapper_interface import ApiWrapperInterface
from ..server_resource_interface import ServerResourceInterface
from abc import ABCMeta
from abc import abstractmethod
from LSP.plugin import ClientConfig
from LSP.plugin import DottedDict
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.typing import Dict, List, Optional, Tuple
import sublime

__all__ = ['ClientHandlerInterface']


class ClientHandlerInterface(metaclass=ABCMeta):
    package_name = ''

    @classmethod
    @abstractmethod
    def setup(cls) -> None:
        ...

    @classmethod
    @abstractmethod
    def cleanup(cls) -> None:
        ...

    @classmethod
    @abstractmethod
    def get_displayed_name(cls) -> str:
        ...

    @classmethod
    @abstractmethod
    def package_storage(cls) -> str:
        ...

    @classmethod
    @abstractmethod
    def get_additional_variables(cls) -> Dict[str, str]:
        ...

    @classmethod
    @abstractmethod
    def get_additional_paths(cls) -> List[str]:
        ...

    @classmethod
    @abstractmethod
    def manages_server(cls) -> bool:
        ...

    @classmethod
    @abstractmethod
    def get_command(cls) -> List[str]:
        ...

    @classmethod
    @abstractmethod
    def binary_path(cls) -> str:
        ...

    @classmethod
    @abstractmethod
    def get_server(cls) -> Optional[ServerResourceInterface]:
        ...

    @classmethod
    @abstractmethod
    def get_binary_arguments(cls) -> List[str]:
        ...

    @classmethod
    @abstractmethod
    def read_settings(cls) -> Tuple[sublime.Settings, str]:
        ...

    @classmethod
    @abstractmethod
    def on_settings_read(cls, settings: sublime.Settings) -> bool:
        ...

    @classmethod
    @abstractmethod
    def is_allowed_to_start(
        cls,
        window: sublime.Window,
        initiating_view: Optional[sublime.View] = None,
        workspace_folders: Optional[List[WorkspaceFolder]] = None,
        configuration: Optional[ClientConfig] = None
    ) -> Optional[str]:
        ...

    @abstractmethod
    def on_ready(self, api: ApiWrapperInterface) -> None:
        ...

    @abstractmethod
    def on_settings_changed(self, settings: DottedDict) -> None:
        ...
