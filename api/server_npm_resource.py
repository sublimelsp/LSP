from .helpers import rmtree_ex
from .helpers import SemanticVersion
from .node_runtime import NodeRuntime
from .server_resource_interface import ServerResourceInterface
from .server_resource_interface import ServerStatus
from hashlib import md5
from LSP.plugin.core.typing import Dict, Optional, TypedDict, Union
from os import makedirs
from os import path
from os import remove
from os import walk
from sublime_lib import ResourcePath

__all__ = ['ServerNpmResource']

ServerNpmResourceCreateOptions = TypedDict('ServerNpmResourceCreateOptions', {
    'package_name': str,
    'server_directory': str,
    'server_binary_path': str,
    'package_storage': str,
    'storage_path': str,
    'minimum_node_version': SemanticVersion,
    'required_node_version': str,
    'skip_npm_install': bool,
})


class ServerNpmResource(ServerResourceInterface):
    """
    An implementation of :class:`LSP.api.ServerResourceInterface` implementing server management for
    node-based severs. Handles installation and updates of the server in package storage.
    """

    @classmethod
    def create(cls, options: ServerNpmResourceCreateOptions) -> 'ServerNpmResource':
        package_name = options['package_name']
        server_directory = options['server_directory']
        server_binary_path = options['server_binary_path']
        package_storage = options['package_storage']
        storage_path = options['storage_path']
        minimum_node_version = options['minimum_node_version']
        required_node_version = options['required_node_version']  # type: Union[str, SemanticVersion]
        skip_npm_install = options['skip_npm_install']
        # Fallback to "minimum_node_version" if "required_node_version" is 0.0.0 (not overridden).
        if '0.0.0' == required_node_version:
            required_node_version = minimum_node_version
        node_runtime = NodeRuntime.get(package_name, storage_path, required_node_version)
        if not node_runtime:
            raise Exception('Failed resolving Node.js Runtime. Please see Sublime Text console for more information.')
        return ServerNpmResource(
            package_name, server_directory, server_binary_path, package_storage, node_runtime, skip_npm_install)

    def __init__(self, package_name: str, server_directory: str, server_binary_path: str,
                 package_storage: str, node_runtime: NodeRuntime, skip_npm_install: bool) -> None:
        if not package_name or not server_directory or not server_binary_path or not node_runtime:
            raise Exception('ServerNpmResource could not initialize due to wrong input')
        self._status = ServerStatus.UNINITIALIZED
        self._package_name = package_name
        self._package_storage = package_storage
        self._server_src = 'Packages/{}/{}/'.format(self._package_name, server_directory)
        node_version = str(node_runtime.resolve_version())
        self._node_version = node_version
        self._server_dest = path.join(package_storage, node_version, server_directory)
        self._binary_path = path.join(package_storage, node_version, server_binary_path)
        self._installation_marker_file = path.join(package_storage, node_version, '.installing')
        self._node_runtime = node_runtime
        self._skip_npm_install = skip_npm_install

    @property
    def server_directory_path(self) -> str:
        return self._server_dest

    @property
    def node_bin(self) -> str:
        node_bin = self._node_runtime.node_bin()
        if node_bin is None:
            raise Exception('Failed to resolve path to the Node.js runtime')
        return node_bin

    @property
    def node_env(self) -> Optional[Dict[str, str]]:
        return self._node_runtime.node_env()

    # --- ServerResourceInterface -------------------------------------------------------------------------------------

    @property
    def binary_path(self) -> str:
        return self._binary_path

    def get_status(self) -> int:
        return self._status

    def needs_installation(self) -> bool:
        installed = False
        if self._skip_npm_install or path.isdir(path.join(self._server_dest, 'node_modules')):
            # Server already installed. Check if version has changed or last installation did not complete.
            src_package_json = ResourcePath(self._server_src, 'package.json')
            if not src_package_json.exists():
                raise Exception('Missing required "package.json" in {}'.format(self._server_src))
            src_hash = md5(src_package_json.read_bytes()).hexdigest()
            try:
                with open(path.join(self._server_dest, 'package.json'), 'rb') as file:
                    dst_hash = md5(file.read()).hexdigest()
                if src_hash == dst_hash and not path.isfile(self._installation_marker_file):
                    installed = True
            except FileNotFoundError:
                # Needs to be re-installed.
                pass
        if installed:
            self._status = ServerStatus.READY
            return False
        return True

    def install_or_update(self) -> None:
        try:
            self._cleanup_package_storage()
            makedirs(path.dirname(self._installation_marker_file), exist_ok=True)
            open(self._installation_marker_file, 'a').close()
            if path.isdir(self._server_dest):
                rmtree_ex(self._server_dest)
            ResourcePath(self._server_src).copytree(self._server_dest, exist_ok=True)
            if not self._skip_npm_install:
                self._node_runtime.run_install(cwd=self._server_dest)
            remove(self._installation_marker_file)
        except Exception as error:
            self._status = ServerStatus.ERROR
            raise Exception('Error installing the server:\n{}'.format(error))
        self._status = ServerStatus.READY

    def _cleanup_package_storage(self) -> None:
        if not path.isdir(self._package_storage):
            return
        """Clean up subdirectories of package storage that belong to other node versions."""
        subdirectories = next(walk(self._package_storage))[1]
        for directory in subdirectories:
            if directory == self._node_version:
                continue
            node_storage_path = path.join(self._package_storage, directory)
            print('[LSP.api] Deleting outdated storage directory "{}"'.format(node_storage_path))
            rmtree_ex(node_storage_path)
