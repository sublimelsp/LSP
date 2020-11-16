from .logging import exception_log
from .promise import Promise
from .promise import ResolveFunc
from .protocol import Range
from .typing import Any, Dict, Tuple, Callable, Optional
from .url import uri_to_filename
from .views import range_to_region
import os
import sublime
import subprocess
import webbrowser


opening_files = {}  # type: Dict[str, Tuple[Promise[Optional[sublime.View]], ResolveFunc[sublime.View]]]


def open_file(
    window: sublime.Window, file_path: str, flags: int = 0, group: int = -1
) -> Promise[Optional[sublime.View]]:
    """Open a file asynchronously. It is only safe to call this function from the UI thread."""
    view = window.open_file(file_path, flags, group)
    if not view.is_loading():
        # It's already loaded. Possibly already open in a tab.
        return Promise.resolve(view)

    # Is the view opening right now? Then return the associated unresolved promise
    for fn, value in opening_files.items():
        if fn == file_path or os.path.samefile(fn, file_path):
            # Return the unresolved promise. A future on_load event will resolve the promise.
            return value[0]

    # Prepare a new promise to be resolved by a future on_load event (see the event listener in main.py)
    def fullfill(resolve: ResolveFunc[sublime.View]) -> None:
        global opening_files
        # Save the promise in the first element of the tuple -- except we cannot yet do that here
        opening_files[file_path] = (None, resolve)  # type: ignore

    promise = Promise(fullfill)
    tup = opening_files[file_path]
    # Save the promise in the first element of the tuple so that the for-loop above can return it
    opening_files[file_path] = (promise, tup[1])
    return promise


def open_file_and_center(window: sublime.Window, file_path: str, r: Optional[Dict[str, Any]], flag: int = 0,
                         group: int = -1) -> Promise:
    """Open a file asynchronously and center the range. It is only safe to call this function from the UI thread."""

    def center_selection(v: Optional[sublime.View]) -> None:
        if not v or not v.is_valid() or not r:
            return
        selection = range_to_region(Range.from_lsp(r), v)
        v.show_at_center(selection.a)
        v.run_command("lsp_selection_set", {"regions": [(selection.a, selection.b)]})

    # TODO: ST API does not allow us to say "do not focus this new view"
    return open_file(window, file_path).then(center_selection)


def open_file_and_center_async(window: sublime.Window, file_path: str, r: Optional[Dict[str, Any]], flag: int = 0,
                               group: int = -1) -> Promise:
    """Open a file asynchronously and center the range, worker thread version."""
    return Promise.on_main_thread() \
        .then(lambda _: open_file_and_center(window, file_path, r, flag, group)) \
        .then(Promise.on_async_thread)


def open_externally(uri: str, take_focus: bool) -> bool:
    """
    A blocking function that invokes the OS's "open with default extension"
    """
    if uri.startswith("http:") or uri.startswith("https:"):
        return webbrowser.open(uri, autoraise=take_focus)
    file = uri_to_filename(uri)
    try:
        # TODO: handle take_focus
        if sublime.platform() == "windows":
            # os.startfile only exists on windows, but pyright does not understand sublime.platform().
            # TODO: How to make pyright understand platform-specific code with sublime.platform()?
            os.startfile(file)  # type: ignore
        elif sublime.platform() == "osx":
            subprocess.check_call(("/usr/bin/open", file))
        else:  # linux
            subprocess.check_call(("xdg-open", file))
        return True
    except Exception as ex:
        exception_log("Failed to open {}".format(uri), ex)
        return False
