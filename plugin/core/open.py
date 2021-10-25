from .logging import exception_log
from .promise import PackagedTask
from .promise import Promise
from .promise import ResolveFunc
from .protocol import Range, RangeLsp
from .typing import Dict, Tuple, Optional
from .url import uri_to_filename
from .views import range_to_region
import os
import sublime
import subprocess
import webbrowser


opening_files = {}  # type: Dict[str, Tuple[Promise[Optional[sublime.View]], ResolveFunc[Optional[sublime.View]]]]


def open_file(
    window: sublime.Window, file_path: str, flags: int = 0, group: int = -1
) -> Promise[Optional[sublime.View]]:
    """Open a file asynchronously. It is only safe to call this function from the UI thread."""

    # window.open_file brings the file to focus if it's already opened, which we don't want.
    # So we first check if there's already a view for that file.
    view = window.find_open_file(file_path)
    if view:
        return Promise.resolve(view)

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
    def fullfill(resolve: ResolveFunc[Optional[sublime.View]]) -> None:
        global opening_files
        # Save the promise in the first element of the tuple -- except we cannot yet do that here
        opening_files[file_path] = (None, resolve)  # type: ignore

    promise = Promise(fullfill)
    tup = opening_files[file_path]
    # Save the promise in the first element of the tuple so that the for-loop above can return it
    opening_files[file_path] = (promise, tup[1])
    return promise


def center_selection(v: sublime.View, r: RangeLsp) -> sublime.View:
    selection = range_to_region(Range.from_lsp(r), v)
    v.run_command("lsp_selection_set", {"regions": [(selection.a, selection.a)]})
    window = v.window()
    if window:
        window.focus_view(v)
    v.show_at_center(selection)
    return v


def open_file_and_center(window: sublime.Window, file_path: str, r: Optional[RangeLsp], flags: int = 0,
                         group: int = -1) -> Promise[Optional[sublime.View]]:
    """Open a file asynchronously and center the range. It is only safe to call this function from the UI thread."""

    def center(v: Optional[sublime.View]) -> Optional[sublime.View]:
        if v and v.is_valid():
            return center_selection(v, r) if r else v
        return None

    # TODO: ST API does not allow us to say "do not focus this new view"
    return open_file(window, file_path, flags, group).then(center)


def open_file_and_center_async(window: sublime.Window, file_path: str, r: Optional[RangeLsp], flags: int = 0,
                               group: int = -1) -> Promise[Optional[sublime.View]]:
    """Open a file asynchronously and center the range, worker thread version."""
    pair = Promise.packaged_task()  # type: PackagedTask[Optional[sublime.View]]
    sublime.set_timeout(
        lambda: open_file_and_center(window, file_path, r, flags, group).then(
            lambda view: sublime.set_timeout_async(
                lambda: pair[1](view)
            )
        )
    )
    return pair[0]


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
