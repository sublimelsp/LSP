from .logging import exception_log
from .promise import Promise
from .promise import ResolveFunc
from .protocol import DocumentUri
from .protocol import Range
from .protocol import RangeLsp
from .typing import Dict, Tuple, Optional
from .url import parse_uri
from .views import range_to_region
import os
import sublime
import subprocess


opening_files = {}  # type: Dict[str, Tuple[Promise[Optional[sublime.View]], ResolveFunc[Optional[sublime.View]]]]


def open_file(
    window: sublime.Window, uri: DocumentUri, flags: int = 0, group: int = -1
) -> Promise[Optional[sublime.View]]:
    """
    Open a file asynchronously.
    It is only safe to call this function from the UI thread.
    The provided uri MUST be a file URI
    """
    file = parse_uri(uri)[1]
    # window.open_file brings the file to focus if it's already opened, which we don't want (unless it's supposed
    # to open as a separate view).
    view = window.find_open_file(file)
    if view:
        view_group = window.get_view_index(view)[0]
        opens_in_desired_group = not bool(flags & sublime.FORCE_GROUP) or view_group == window.active_group()
        opens_as_new_selection = bool(flags & (sublime.ADD_TO_SELECTION | sublime.REPLACE_MRU))
        return_existing_view = opens_in_desired_group and not opens_as_new_selection
        if return_existing_view:
            return Promise.resolve(view)

    view = window.open_file(file, flags, group)
    if not view.is_loading():
        # It's already loaded. Possibly already open in a tab.
        return Promise.resolve(view)

    # Is the view opening right now? Then return the associated unresolved promise
    for fn, value in opening_files.items():
        if fn == file or os.path.samefile(fn, file):
            # Return the unresolved promise. A future on_load event will resolve the promise.
            return value[0]

    # Prepare a new promise to be resolved by a future on_load event (see the event listener in main.py)
    def fullfill(resolve: ResolveFunc[Optional[sublime.View]]) -> None:
        global opening_files
        # Save the promise in the first element of the tuple -- except we cannot yet do that here
        opening_files[file] = (None, resolve)  # type: ignore

    promise = Promise(fullfill)
    tup = opening_files[file]
    # Save the promise in the first element of the tuple so that the for-loop above can return it
    opening_files[file] = (promise, tup[1])
    return promise


def center_selection(v: sublime.View, r: RangeLsp) -> sublime.View:
    selection = range_to_region(Range.from_lsp(r), v)
    v.run_command("lsp_selection_set", {"regions": [(selection.a, selection.a)]})
    window = v.window()
    if window:
        window.focus_view(v)
    if int(sublime.version()) >= 4124:
        v.show_at_center(selection, animate=False)
    else:
        # TODO: remove later when a stable build lands
        v.show_at_center(selection)  # type: ignore
    return v


def open_externally(uri: str, take_focus: bool) -> bool:
    """
    A blocking function that invokes the OS's "open with default extension"
    """
    try:
        # TODO: handle take_focus
        if sublime.platform() == "windows":
            os.startfile(uri)  # type: ignore
        elif sublime.platform() == "osx":
            subprocess.check_call(("/usr/bin/open", uri))
        else:  # linux
            subprocess.check_call(("xdg-open", uri))
        return True
    except Exception as ex:
        exception_log("Failed to open {}".format(uri), ex)
        return False
