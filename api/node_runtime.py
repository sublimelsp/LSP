from .helpers import rmtree_ex
from .helpers import run_command_sync
from .helpers import SemanticVersion
from .helpers import version_to_string
from contextlib import contextmanager
from LSP.plugin.core.constants import SUBLIME_SETTINGS_FILENAME
from LSP.plugin.core.logging import debug
from LSP.plugin.core.typing import cast, Any, Dict, Generator, List, Optional, Tuple, Union
from LSP.third_party.semantic_version import NpmSpec, Version
from os import path
from os import remove
from sublime_lib import ActivityIndicator
import os
import shutil
import sublime
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

__all__ = ['NodeRuntime']

IS_WINDOWS_7_OR_LOWER = sys.platform == 'win32' and sys.getwindowsversion()[:2] <= (6, 1)  # type: ignore

NODE_RUNTIME_VERSION = '18.18.1'
NODE_DIST_URL = 'https://nodejs.org/dist/v{version}/{filename}'

ELECTRON_RUNTIME_VERSION = '27.0.0'  # includes Node.js v18.17.1
ELECTRON_NODE_VERSION = '18.17.1'
ELECTRON_DIST_URL = 'https://github.com/electron/electron/releases/download/v{version}/{filename}'
YARN_URL = 'https://github.com/yarnpkg/yarn/releases/download/v1.22.21/yarn-1.22.21.js'

NO_NODE_FOUND_MESSAGE = 'Could not start {package_name} due to not being able to resolve suitable Node.js \
runtime on the PATH. Press the "Download Node.js" button to get required Node.js version \
(note that it will be used only by LSP and will not affect your system otherwise).'


class NodeRuntime:
    _node_runtime_resolved = False
    _node_runtime = None  # Optional[NodeRuntime]
    """
    Cached instance of resolved Node.js runtime. This is only done once per-session to avoid unnecessary IO.
    """

    @classmethod
    def get(
        cls, package_name: str, storage_path: str, required_node_version: Union[str, SemanticVersion]
    ) -> Optional['NodeRuntime']:
        if isinstance(required_node_version, tuple):
            required_semantic_version = NpmSpec('>={}'.format(version_to_string(required_node_version)))
        else:
            required_semantic_version = NpmSpec(required_node_version)
        if cls._node_runtime_resolved:
            if cls._node_runtime:
                cls._node_runtime.check_satisfies_version(required_semantic_version)
            return cls._node_runtime
        cls._node_runtime_resolved = True
        cls._node_runtime = cls._resolve_node_runtime(package_name, storage_path, required_semantic_version)
        debug('Resolved Node.js Runtime for package {}: {}'.format(package_name, cls._node_runtime))
        return cls._node_runtime

    @classmethod
    def _resolve_node_runtime(
        cls, package_name: str, storage_path: str, required_node_version: NpmSpec
    ) -> 'NodeRuntime':
        resolved_runtime = None  # type: Optional[NodeRuntime]
        default_runtimes = ['system', 'local']
        settings = sublime.load_settings(SUBLIME_SETTINGS_FILENAME)
        selected_runtimes = cast(List[str], settings.get('nodejs_runtime') or default_runtimes)
        log_lines = ['--- LSP.api Node.js resolving start ---']
        for runtime_type in selected_runtimes:
            if runtime_type == 'system':
                log_lines.append('Resolving Node.js Runtime in env PATH for package {}...'.format(package_name))
                path_runtime = NodeRuntimePATH()
                try:
                    path_runtime.check_binary_present()
                except Exception as ex:
                    log_lines.append(' * Failed: {}'.format(ex))
                    continue
                try:
                    path_runtime.check_satisfies_version(required_node_version)
                    resolved_runtime = path_runtime
                    break
                except Exception as ex:
                    log_lines.append(' * {}'.format(ex))
            elif runtime_type == 'local':
                log_lines.append('Resolving Node.js Runtime from LSP.api for package {}...'.format(package_name))
                use_electron = cast(bool, settings.get('local_use_electron') or False)
                runtime_dir = path.join(storage_path, 'LSP', 'node-runtime')
                local_runtime = ElectronRuntimeLocal(runtime_dir) if use_electron else NodeRuntimeLocal(runtime_dir)
                try:
                    local_runtime.check_binary_present()
                except Exception as ex:
                    log_lines.append(' * Binaries check failed: {}'.format(ex))
                    if selected_runtimes[0] != 'local':
                        if not sublime.ok_cancel_dialog(
                                NO_NODE_FOUND_MESSAGE.format(package_name=package_name), 'Download Node.js'):
                            log_lines.append(' * Download skipped')
                            continue
                    # Remove outdated runtimes.
                    if path.isdir(runtime_dir):
                        for directory in next(os.walk(runtime_dir))[1]:
                            old_dir = path.join(runtime_dir, directory)
                            print('[LSP.api] Deleting outdated Node.js runtime directory "{}"'.format(old_dir))
                            try:
                                rmtree_ex(old_dir)
                            except Exception as ex:
                                log_lines.append(' * Failed deleting: {}'.format(ex))
                    try:
                        local_runtime.install_node()
                    except Exception as ex:
                        log_lines.append(' * Failed downloading: {}'.format(ex))
                        continue
                    try:
                        local_runtime.check_binary_present()
                    except Exception as ex:
                        log_lines.append(' * Failed: {}'.format(ex))
                        continue
                try:
                    local_runtime.check_satisfies_version(required_node_version)
                    resolved_runtime = local_runtime
                    break
                except Exception as ex:
                    log_lines.append(' * {}'.format(ex))
        if not resolved_runtime:
            log_lines.append('--- LSP.api Node.js resolving end ---')
            print('\n'.join(log_lines))
            raise Exception('Failed resolving Node.js Runtime. Please check in the console for more details.')
        return resolved_runtime

    def __init__(self) -> None:
        self._node = None  # type: Optional[str]
        self._npm = None  # type: Optional[str]
        self._version = None  # type: Optional[Version]
        self._additional_paths = []  # type: List[str]

    def __repr__(self) -> str:
        return '{}(node: {}, npm: {}, version: {})'.format(
            self.__class__.__name__, self._node, self._npm, self._version if self._version else None)

    def install_node(self) -> None:
        raise Exception('Not supported!')

    def node_bin(self) -> Optional[str]:
        return self._node

    def npm_bin(self) -> Optional[str]:
        return self._npm

    def node_env(self) -> Dict[str, str]:
        if IS_WINDOWS_7_OR_LOWER:
            return {'NODE_SKIP_PLATFORM_CHECK': '1'}
        return {}

    def check_binary_present(self) -> None:
        if self._node is None:
            raise Exception('"node" binary not found')
        if self._npm is None:
            raise Exception('"npm" binary not found')

    def check_satisfies_version(self, required_node_version: NpmSpec) -> None:
        node_version = self.resolve_version()
        if node_version not in required_node_version:
            raise Exception(
                'Node.js version requirement failed. Expected {}, got {}.'.format(required_node_version, node_version))

    def resolve_version(self) -> Version:
        if self._version:
            return self._version
        if not self._node:
            raise Exception('Node.js not initialized')
        # In this case we have fully resolved binary path already so shouldn't need `shell` on Windows.
        version, error = run_command_sync([self._node, '--version'], extra_env=self.node_env(), shell=False)
        if error is None:
            self._version = Version(version.replace('v', ''))
        else:
            raise Exception('Failed resolving Node.js version. Error:\n{}'.format(error))
        return self._version

    def run_node(
        self,
        args: List[str],
        stdin: int = subprocess.PIPE,
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        env: Dict[str, Any] = {}
    ) -> Optional['subprocess.Popen[bytes]']:
        node_bin = self.node_bin()
        if node_bin is None:
            return None
        os_env = os.environ.copy()
        os_env.update(self.node_env())
        os_env.update(env)
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(
            [node_bin] + args, stdin=stdin, stdout=stdout, stderr=stderr, env=os_env, startupinfo=startupinfo)

    def run_install(self, cwd: str) -> None:
        if not path.isdir(cwd):
            raise Exception('Specified working directory "{}" does not exist'.format(cwd))
        if not self._node:
            raise Exception('Node.js not installed. Use NodeInstaller to install it first.')
        args = [
            'ci',
            '--omit=dev',
            '--scripts-prepend-node-path=true',
            '--verbose',
        ]
        stdout, error = run_command_sync(
            self.npm_command() + args, cwd=cwd, extra_env=self.node_env(), extra_paths=self._additional_paths,
            shell=False
        )
        print('[LSP.api] START output of command: "{}"'.format(' '.join(args)))
        print(stdout)
        print('[LSP.api] Command output END')
        if error is not None:
            raise Exception('Failed to run npm command "{}":\n{}'.format(' '.join(args), error))

    def npm_command(self) -> List[str]:
        if self._npm is None:
            raise Exception('Npm command not initialized')
        return [self._npm]


class NodeRuntimePATH(NodeRuntime):
    def __init__(self) -> None:
        super().__init__()
        self._node = shutil.which('node')
        self._npm = shutil.which('npm')


class NodeRuntimeLocal(NodeRuntime):
    def __init__(self, base_dir: str, node_version: str = NODE_RUNTIME_VERSION):
        super().__init__()
        self._base_dir = path.abspath(path.join(base_dir, node_version))
        self._node_version = node_version
        self._node_dir = path.join(self._base_dir, 'node')
        self._install_in_progress_marker_file = path.join(self._base_dir, '.installing')
        self._resolve_paths()

    # --- NodeRuntime overrides ----------------------------------------------------------------------------------------

    def npm_command(self) -> List[str]:
        if not self._node or not self._npm:
            raise Exception('Node.js or Npm command not initialized')
        return [self._node, self._npm]

    def install_node(self) -> None:
        os.makedirs(os.path.dirname(self._install_in_progress_marker_file), exist_ok=True)
        open(self._install_in_progress_marker_file, 'a').close()
        with ActivityIndicator(sublime.active_window(), 'Downloading Node.js'):
            install_node = NodeInstaller(self._base_dir, self._node_version)
            install_node.run()
            self._resolve_paths()
        remove(self._install_in_progress_marker_file)
        self._resolve_paths()

    # --- private methods ----------------------------------------------------------------------------------------------

    def _resolve_paths(self) -> None:
        if path.isfile(self._install_in_progress_marker_file):
            # Will trigger re-installation.
            return
        self._node = self._resolve_binary()
        self._node_lib = self._resolve_lib()
        self._npm = path.join(self._node_lib, 'npm', 'bin', 'npm-cli.js')
        self._additional_paths = [path.dirname(self._node)] if self._node else []

    def _resolve_binary(self) -> Optional[str]:
        exe_path = path.join(self._node_dir, 'node.exe')
        binary_path = path.join(self._node_dir, 'bin', 'node')
        if path.isfile(exe_path):
            return exe_path
        if path.isfile(binary_path):
            return binary_path
        return None

    def _resolve_lib(self) -> str:
        lib_path = path.join(self._node_dir, 'lib', 'node_modules')
        if not path.isdir(lib_path):
            lib_path = path.join(self._node_dir, 'node_modules')
        return lib_path


class NodeInstaller:
    '''Command to install a local copy of Node.js'''

    def __init__(self, base_dir: str, node_version: str = NODE_RUNTIME_VERSION) -> None:
        """
        :param base_dir: The base directory for storing given Node.js runtime version
        :param node_version: The Node.js version to install
        """
        self._base_dir = base_dir
        self._node_version = node_version
        self._cache_dir = path.join(self._base_dir, 'cache')

    def run(self) -> None:
        archive, url = self._node_archive()
        print('[LSP.api] Downloading Node.js {} from {}'.format(self._node_version, url))
        if not self._archive_exists(archive):
            self._download_node(url, archive)
        self._install_node(archive)

    def _node_archive(self) -> Tuple[str, str]:
        platform = sublime.platform()
        arch = sublime.arch()
        if platform == 'windows' and arch == 'x64':
            node_os = 'win'
            archive = 'zip'
        elif platform == 'linux':
            node_os = 'linux'
            archive = 'tar.gz'
        elif platform == 'osx':
            node_os = 'darwin'
            archive = 'tar.gz'
        else:
            raise Exception('{} {} is not supported'.format(arch, platform))
        filename = 'node-v{}-{}-{}.{}'.format(self._node_version, node_os, arch, archive)
        dist_url = NODE_DIST_URL.format(version=self._node_version, filename=filename)
        return filename, dist_url

    def _archive_exists(self, filename: str) -> bool:
        archive = path.join(self._cache_dir, filename)
        return path.isfile(archive)

    def _download_node(self, url: str, filename: str) -> None:
        if not path.isdir(self._cache_dir):
            os.makedirs(self._cache_dir)
        archive = path.join(self._cache_dir, filename)
        with urllib.request.urlopen(url) as response:
            with open(archive, 'wb') as f:
                shutil.copyfileobj(response, f)

    def _install_node(self, filename: str) -> None:
        archive = path.join(self._cache_dir, filename)
        opener = zipfile.ZipFile if filename.endswith('.zip') else tarfile.open  # type: Any
        try:
            with opener(archive) as f:
                names = f.namelist() if hasattr(f, 'namelist') else f.getnames()
                install_dir, _ = next(x for x in names if '/' in x).split('/', 1)
                bad_members = [x for x in names if x.startswith('/') or x.startswith('..')]
                if bad_members:
                    raise Exception('{} appears to be malicious, bad filenames: {}'.format(filename, bad_members))
                f.extractall(self._base_dir)
                with chdir(self._base_dir):
                    os.rename(install_dir, 'node')
        except Exception as ex:
            raise ex
        finally:
            remove(archive)


class ElectronRuntimeLocal(NodeRuntime):
    def __init__(self, base_dir: str):
        super().__init__()
        self._base_dir = path.abspath(path.join(base_dir, ELECTRON_NODE_VERSION))
        self._yarn = path.join(self._base_dir, 'yarn.js')
        self._install_in_progress_marker_file = path.join(self._base_dir, '.installing')
        if not path.isfile(self._install_in_progress_marker_file):
            self._resolve_paths()

    # --- NodeRuntime overrides ----------------------------------------------------------------------------------------

    def node_env(self) -> Dict[str, str]:
        extra_env = super().node_env()
        extra_env.update({'ELECTRON_RUN_AS_NODE': 'true'})
        return extra_env

    def install_node(self) -> None:
        os.makedirs(os.path.dirname(self._install_in_progress_marker_file), exist_ok=True)
        open(self._install_in_progress_marker_file, 'a').close()
        with ActivityIndicator(sublime.active_window(), 'Downloading Node.js'):
            install_node = ElectronInstaller(self._base_dir)
            install_node.run()
            self._resolve_paths()
        remove(self._install_in_progress_marker_file)

    def run_install(self, cwd: str) -> None:
        self._run_yarn(['import'], cwd)
        args = [
            'install',
            '--production',
            '--frozen-lockfile',
            '--scripts-prepend-node-path=true',
            '--cache-folder={}'.format(path.join(self._base_dir, 'cache', 'yarn')),
            # '--verbose',
        ]
        self._run_yarn(args, cwd)

    # --- private methods ----------------------------------------------------------------------------------------------

    def _resolve_paths(self) -> None:
        self._node = self._resolve_binary()
        self._npm = path.join(self._base_dir, 'yarn.js')

    def _resolve_binary(self) -> Optional[str]:
        binary_path = None
        platform = sublime.platform()
        if platform == 'osx':
            binary_path = path.join(self._base_dir, 'Electron.app', 'Contents', 'MacOS', 'Electron')
        elif platform == 'windows':
            binary_path = path.join(self._base_dir, 'electron.exe')
        else:
            binary_path = path.join(self._base_dir, 'electron')
        return binary_path if binary_path and path.isfile(binary_path) else None

    def _run_yarn(self, args: List[str], cwd: str) -> None:
        if not path.isdir(cwd):
            raise Exception('Specified working directory "{}" does not exist'.format(cwd))
        if not self._node:
            raise Exception('Node.js not installed. Use NodeInstaller to install it first.')
        stdout, error = run_command_sync(
            [self._node, self._yarn] + args, cwd=cwd, extra_env=self.node_env(), shell=False
        )
        print('[LSP.api] START output of command: "{}"'.format(' '.join(args)))
        print(stdout)
        print('[LSP.api] Command output END')
        if error is not None:
            raise Exception('Failed to run yarn command "{}":\n{}'.format(' '.join(args), error))


class ElectronInstaller:
    '''Command to install a local copy of Node.js'''

    def __init__(self, base_dir: str) -> None:
        """
        :param base_dir: The base directory for storing given Node.js runtime version
        """
        self._base_dir = base_dir
        self._cache_dir = path.join(self._base_dir, 'cache')

    def run(self) -> None:
        archive, url = self._node_archive()
        print(
            '[LSP.api] Downloading Electron {} (Node.js runtime {}) from {}'.format(
                ELECTRON_RUNTIME_VERSION, ELECTRON_NODE_VERSION, url
            )
        )
        if not self._archive_exists(archive):
            self._download(url, archive)
        self._install(archive)
        self._download_yarn()

    def _node_archive(self) -> Tuple[str, str]:
        platform = sublime.platform()
        arch = sublime.arch()
        if platform == 'windows':
            platform_code = 'win32'
        elif platform == 'linux':
            platform_code = 'linux'
        elif platform == 'osx':
            platform_code = 'darwin'
        else:
            raise Exception('{} {} is not supported'.format(arch, platform))
        filename = 'electron-v{}-{}-{}.zip'.format(ELECTRON_RUNTIME_VERSION, platform_code, arch)
        dist_url = ELECTRON_DIST_URL.format(version=ELECTRON_RUNTIME_VERSION, filename=filename)
        return filename, dist_url

    def _archive_exists(self, filename: str) -> bool:
        archive = path.join(self._cache_dir, filename)
        return path.isfile(archive)

    def _download(self, url: str, filename: str) -> None:
        if not path.isdir(self._cache_dir):
            os.makedirs(self._cache_dir)
        archive = path.join(self._cache_dir, filename)
        with urllib.request.urlopen(url) as response:
            with open(archive, 'wb') as f:
                shutil.copyfileobj(response, f)

    def _install(self, filename: str) -> None:
        archive = path.join(self._cache_dir, filename)
        try:
            if sublime.platform() == 'windows':
                with zipfile.ZipFile(archive) as f:
                    names = f.namelist()
                    _, _ = next(x for x in names if '/' in x).split('/', 1)
                    bad_members = [x for x in names if x.startswith('/') or x.startswith('..')]
                    if bad_members:
                        raise Exception('{} appears to be malicious, bad filenames: {}'.format(filename, bad_members))
                    f.extractall(self._base_dir)
            else:
                # ZipFile doesn't handle symlinks and permissions correctly on Linux and Mac. Use unzip instead.
                _, error = run_command_sync(['unzip', archive, '-d', self._base_dir], cwd=self._cache_dir)
                if error:
                    raise Exception('Error unzipping electron archive: {}'.format(error))
        except Exception as ex:
            raise ex
        finally:
            remove(archive)

    def _download_yarn(self) -> None:
        archive = path.join(self._base_dir, 'yarn.js')
        with urllib.request.urlopen(YARN_URL) as response:
            with open(archive, 'wb') as f:
                shutil.copyfileobj(response, f)


@contextmanager
def chdir(new_dir: str) -> Generator[None, None, None]:
    '''Context Manager for changing the working directory'''
    cur_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(cur_dir)
