from LSP.plugin.core.typing import Any, Callable, Dict, List, Optional, Tuple
import os
import shutil
import sublime
import subprocess
import threading

StringCallback = Callable[[str], None]
SemanticVersion = Tuple[int, int, int]

is_windows = sublime.platform() == 'windows'


def run_command_sync(
    args: List[str],
    cwd: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
    extra_paths: List[str] = [],
    shell: bool = is_windows,
) -> Tuple[str, Optional[str]]:
    """
    Runs the given command synchronously.

    :returns: A two-element tuple with the returned value and an optional error. If running the command has failed, the
              first tuple element will be empty string and the second will contain the potential `stderr` output. If the
              command has succeeded then the second tuple element will be `None`.
    """
    try:
        env = None
        if extra_env or extra_paths:
            env = os.environ.copy()
            if extra_env:
                env.update(extra_env)
            if extra_paths:
                env['PATH'] = os.path.pathsep.join(extra_paths) + os.path.pathsep + env['PATH']
        startupinfo = None
        if is_windows:
            startupinfo = subprocess.STARTUPINFO()  # type: ignore
            startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
        output = subprocess.check_output(
            args, cwd=cwd, shell=shell, stderr=subprocess.STDOUT, env=env, startupinfo=startupinfo)
        return (decode_bytes(output).strip(), None)
    except subprocess.CalledProcessError as error:
        return ('', decode_bytes(error.output).strip())


def run_command_async(args: List[str], on_success: StringCallback, on_error: StringCallback, **kwargs: Any) -> None:
    """
    Runs the given command asynchronously.

    On success calls the provided `on_success` callback with the value the the command has returned.
    On error calls the provided `on_error` callback with the potential `stderr` output.
    """

    def execute(on_success: StringCallback, on_error: StringCallback, args: List[str]) -> None:
        result, error = run_command_sync(args, **kwargs)
        on_error(error) if error is not None else on_success(result)

    thread = threading.Thread(target=execute, args=(on_success, on_error, args))
    thread.start()


def decode_bytes(data: bytes) -> str:
    """
    Decodes provided bytes using `utf-8` decoding, ignoring potential decoding errors.
    """
    return data.decode('utf-8', 'ignore')


def rmtree_ex(path: str, ignore_errors: bool = False) -> None:
    # On Windows, "shutil.rmtree" will raise file not found errors when deleting a long path (>255 chars).
    # See https://stackoverflow.com/a/14076169/4643765
    # See https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
    path = R'\\?\{}'.format(path) if sublime.platform() == 'windows' else path
    shutil.rmtree(path, ignore_errors)


def version_to_string(version: SemanticVersion) -> str:
    """
    Returns a string representation of a version tuple.
    """
    return '.'.join([str(c) for c in version])


def log_and_show_message(message: str, additional_logs: Optional[str] = None, show_in_status: bool = True) -> None:
    """
    Logs the message in the console and optionally sets it as a status message on the window.

    :param message: The message to log or show in the status.
    :param additional_logs: The extra value to log on a separate line.
    :param show_in_status: Whether to briefly show the message in the status bar of the current window.
    """
    print(message, '\n', additional_logs) if additional_logs else print(message)
    if show_in_status:
        sublime.active_window().status_message(message)
