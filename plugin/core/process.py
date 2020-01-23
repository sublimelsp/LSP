from .logging import debug, exception_log
from .typing import Any, List, Dict, Callable, Optional, IO
import os
import shutil
import subprocess
import threading


def add_extension_if_missing(server_binary_args: List[str]) -> List[str]:
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
    server_binary_args: List[str],
    working_dir: Optional[str],
    env: Dict[str, str],
    on_stderr_log: Optional[Callable[[str], None]]
) -> Optional[subprocess.Popen]:
    si = None
    if os.name == "nt":
        server_binary_args = add_extension_if_missing(server_binary_args)
        si = subprocess.STARTUPINFO()  # type: ignore
        si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore

    debug("starting " + str(server_binary_args))

    stderr_destination = subprocess.PIPE if on_stderr_log else subprocess.DEVNULL

    process = subprocess.Popen(
        server_binary_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_destination,
        cwd=working_dir,
        env=env,
        startupinfo=si)

    if on_stderr_log is not None:
        attach_logger(process, process.stderr, on_stderr_log)

    return process


def attach_logger(process: subprocess.Popen, stream: IO[Any], log_callback: Callable[[str], None]) -> None:
    threading.Thread(target=log_stream, args=(process, stream, log_callback)).start()


def log_stream(process: subprocess.Popen, stream: IO[Any], log_callback: Callable[[str], None]) -> None:
    """
    Read lines from a stream and invoke the log_callback on the result
    """
    running = True
    while running:
        running = process.poll() is None

        try:
            content = stream.readline()
            if not content:
                break
            log_callback(content.decode('UTF-8', 'replace').strip())
        except IOError as err:
            exception_log("Failure reading stream", err)
            return

    debug("LSP stream logger stopped.")
