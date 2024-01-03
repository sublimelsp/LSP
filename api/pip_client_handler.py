from .generic_client_handler import GenericClientHandler
from .server_pip_resource import ServerPipResource
from .server_resource_interface import ServerResourceInterface
from LSP.plugin.core.typing import List, Optional
from os import path
import shutil
import sublime

__all__ = ['PipClientHandler']


class PipClientHandler(GenericClientHandler):
    """
    An implementation of :class:`GenericClientHandler` for handling pip-based LSP plugins.

    Automatically manages a pip-based server by installing and updating dependencies based on provided
    `requirements.txt` file.
    """
    __server = None  # type: Optional[ServerPipResource]

    requirements_txt_path = ''
    """
    The path to the `requirements.txt` file containing a list of dependencies required by the server.

    If the package `LSP-foo` has a `requirements.txt` file at the root then the path will be just `requirements.txt`.

    The file format is `dependency_name==dependency_version` or just a direct path to the dependency (for example to
    a github repo). For example:

    .. code::

        pyls==0.1.2
        colorama==1.2.2
        git+https://github.com/tomv564/pyls-mypy.git

    :required: Yes
    """

    server_filename = ''
    """
    The file name of the binary used to start the server.

    :required: Yes
    """

    @classmethod
    def get_python_binary(cls) -> str:
        """
        Returns a binary name or a full path to the Python interpreter used to create environment for the server.

        The default implementation returns `python` on Windows and `python3` on other platforms. When only the binary
        name is specified then it will be expected that it can be found on the PATH.
        """
        return 'python' if sublime.platform() == 'windows' else 'python3'

    # --- GenericClientHandler handlers -------------------------------------------------------------------------------

    @classmethod
    def manages_server(cls) -> bool:
        return True

    @classmethod
    def get_server(cls) -> Optional[ServerResourceInterface]:
        if not cls.__server:
            python_binary = cls.get_python_binary()
            if not shutil.which(python_binary):
                raise Exception('Python binary "{}" not found!'.format(python_binary))
            cls.__server = ServerPipResource(
                cls.storage_path(), cls.package_name, cls.requirements_txt_path, cls.server_filename, python_binary)
        return cls.__server

    @classmethod
    def get_additional_paths(cls) -> List[str]:
        server = cls.get_server()
        if server:
            return [path.dirname(server.binary_path)]
        return []
