from .logging import debug, exception_log, server_log
from .types import ClientConfig
import os
import shutil
import subprocess
import threading

try:
    from .types import WindowLike
    from typing import Any, List, Dict, Tuple, Callable, Optional, Union, IO
    assert Any and List and Dict and Tuple and Callable and Optional and Union and IO
    assert WindowLike
except ImportError:
    pass


def add_extension_if_missing(server_binary_args: 'List[str]') -> 'List[str]':
    if len(server_binary_args) > 0:
        executable_arg = server_binary_args[0]
        fname, ext = os.path.splitext(executable_arg)
        if len(ext) < 1:
            path_to_executable = shutil.which(executable_arg)

            # what extensions should we append so CreateProcess can find it?
            # node has .cmd
            # dart has .bat
            # python has .exe wrappers - not needed
            for extension in ['.cmd', '.bat']:
                if path_to_executable and path_to_executable.lower().endswith(extension):
                    executable_arg = executable_arg + extension
                    updated_args = [executable_arg]
                    updated_args.extend(server_binary_args[1:])
                    return updated_args

    return server_binary_args


def start_server(
    window: 'WindowLike',
    config: ClientConfig,
    server_binary_args: 'List[str]',
    env: 'Dict[str,str]',
    attach_stderr: bool
) -> 'Optional[subprocess.Popen]':
    startupinfo = None
    if os.name == "nt":
        server_binary_args = add_extension_if_missing(config.binary_args)
        startupinfo = subprocess.STARTUPINFO()  # type: ignore
        startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
    resolved_working_dir = config.resolve_working_dir(window)
    debug("starting", str(server_binary_args), "in", resolved_working_dir)
    stderr_destination = subprocess.PIPE if attach_stderr else subprocess.DEVNULL
    return subprocess.Popen(
        server_binary_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_destination,
        cwd=resolved_working_dir,
        env=env,
        startupinfo=startupinfo)


def attach_logger(process: 'subprocess.Popen', stream: 'IO[Any]') -> None:
    threading.Thread(target=log_stream, args=(process, stream)).start()


def log_stream(process: 'subprocess.Popen', stream: 'IO[Any]') -> None:
    """
    Reads any errors from the LSP process.
    """
    running = True
    while running:
        running = process.poll() is None

        try:
            content = stream.readline()
            if not content:
                break
            try:
                decoded = content.decode("UTF-8")
            except UnicodeDecodeError:
                # todo: do we still need this ?
                decoded = content  # type: ignore
            server_log(decoded.strip())
        except IOError as err:
            exception_log("Failure reading stream", err)
            return

    debug("LSP stream logger stopped.")
