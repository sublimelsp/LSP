from .helpers import rmtree_ex
from .helpers import run_command_sync
from .server_resource_interface import ServerResourceInterface
from .server_resource_interface import ServerStatus
from hashlib import md5
from LSP.plugin.core.typing import Any, Optional
from os import path
from sublime_lib import ResourcePath
import os
import sublime

__all__ = ['ServerPipResource']


class ServerPipResource(ServerResourceInterface):
    """
    An implementation of :class:`LSP.api.ServerResourceInterface` implementing server management for
    pip-based servers. Handles installation and updates of the server in the package storage.

    :param storage_path: The path to the package storage (pass :meth:`LSP.api.GenericClientHandler.storage_path()`)
    :param package_name: The package name (used as a directory name for storage)
    :param requirements_path: The path to the `requirements.txt` file, relative to the package directory.
           If the package `LSP-foo` has a `requirements.txt` file at the root then the path will be `requirements.txt`.
    :param server_binary_filename: The name of the file used to start the server.
    """

    @classmethod
    def file_extension(cls) -> str:
        return '.exe' if sublime.platform() == 'windows' else ''

    @classmethod
    def run(cls, *args: Any, cwd: Optional[str] = None) -> str:
        output, error = run_command_sync(list(args), cwd=cwd)
        if error:
            raise Exception(error)
        return output

    def __init__(self, storage_path: str, package_name: str, requirements_path: str,
                 server_binary_filename: str, python_binary: str) -> None:
        self._storage_path = storage_path
        self._package_name = package_name
        self._requirements_path_relative = requirements_path
        self._requirements_path = 'Packages/{}/{}'.format(self._package_name, requirements_path)
        self._server_binary_filename = server_binary_filename
        self._python_binary = python_binary
        self._status = ServerStatus.UNINITIALIZED

    def basedir(self) -> str:
        return path.join(self._storage_path, self._package_name)

    def bindir(self) -> str:
        bin_dir = 'Scripts' if sublime.platform() == 'windows' else 'bin'
        return path.join(self.basedir(), bin_dir)

    def server_binary(self) -> str:
        return path.join(self.bindir(), self._server_binary_filename + self.file_extension())

    def pip_binary(self) -> str:
        return path.join(self.bindir(), 'pip' + self.file_extension())

    def python_version(self) -> str:
        return path.join(self.basedir(), 'python_version')

    # --- ServerResourceInterface handlers ----------------------------------------------------------------------------

    @property
    def binary_path(self) -> str:
        return self.server_binary()

    def get_status(self) -> int:
        return self._status

    def needs_installation(self) -> bool:
        if not path.exists(self.server_binary()) or not path.exists(self.pip_binary()):
            return True
        if not path.exists(self.python_version()):
            return True
        with open(self.python_version(), 'r') as f:
            if f.readline().strip() != self.run(self._python_binary, '--version').strip():
                return True
        src_requirements_resource = ResourcePath(self._requirements_path)
        if not src_requirements_resource.exists():
            raise Exception('Missing required "requirements.txt" in {}'.format(self._requirements_path))
        src_requirements_hash = md5(src_requirements_resource.read_bytes()).hexdigest()
        try:
            with open(path.join(self.basedir(), self._requirements_path_relative), 'rb') as file:
                dst_requirements_hash = md5(file.read()).hexdigest()
            if src_requirements_hash != dst_requirements_hash:
                return True
        except FileNotFoundError:
            # Needs to be re-installed.
            return True
        self._status = ServerStatus.READY
        return False

    def install_or_update(self) -> None:
        rmtree_ex(self.basedir(), ignore_errors=True)
        try:
            os.makedirs(self.basedir(), exist_ok=True)
            self.run(self._python_binary, '-m', 'venv', self._package_name, cwd=self._storage_path)
            dest_requirements_txt_path = path.join(self._storage_path, self._package_name, 'requirements.txt')
            ResourcePath(self._requirements_path).copy(dest_requirements_txt_path)
            self.run(self.pip_binary(), 'install', '-r', dest_requirements_txt_path, '--disable-pip-version-check')
            with open(self.python_version(), 'w') as f:
                f.write(self.run(self._python_binary, '--version'))
        except Exception as error:
            self._status = ServerStatus.ERROR
            raise Exception('Error installing the server:\n{}'.format(error))
        self._status = ServerStatus.READY
