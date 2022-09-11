from .logging import exception_log
from .promise import Promise
from .promise import ResolveFunc
from .protocol import DocumentUri
from .protocol import UINT_MAX
from .protocol import Range
from .protocol import RangeLsp
from .typing import Dict, Tuple, Optional
from .url import parse_uri
from .views import range_to_region
from urllib.parse import unquote, urlparse
import os
import re
import sublime
import subprocess
import webbrowser


opening_files = {}  # type: Dict[str, Tuple[Promise[Optional[sublime.View]], ResolveFunc[Optional[sublime.View]]]]
FRAGMENT_PATTERN = re.compile(r'^L?(\d+)(?:,(\d+))?(?:-L?(\d+)(?:,(\d+))?)?')


def open_file_uri(
    window: sublime.Window, uri: DocumentUri, flags: int = 0, group: int = -1
) -> Promise[Optional[sublime.View]]:

    def parse_int(s: Optional[str]) -> Optional[int]:
        if s:
            try:
                # assume that line and column numbers in the fragment are 1-based
                return max(1, int(s))
            except ValueError:
                return None
        return None

    def parse_fragment(fragment: str) -> RangeLsp:
        match = FRAGMENT_PATTERN.match(fragment)
        if match:
            start_line, start_column, end_line, end_column = [parse_int(g) for g in match.groups()]
            if start_line is not None:
                if end_line is not None:
                    if start_column is not None and end_column is not None:
                        return {
                            "start": {"line": start_line - 1, "character": start_column - 1},
                            "end": {"line": end_line - 1, "character": end_column - 1}
                        }
                    else:
                        return {
                            "start": {"line": start_line - 1, "character": 0},
                            "end": {"line": end_line - 1, "character": UINT_MAX}
                        }
                elif start_column is not None:
                    return {
                        "start": {"line": start_line - 1, "character": start_column - 1},
                        "end": {"line": start_line - 1, "character": start_column - 1}
                    }
                else:
                    return {
                        "start": {"line": start_line - 1, "character": 0},
                        "end": {"line": start_line - 1, "character": 0}
                    }
        return {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}

    decoded_uri = unquote(uri)  # decode percent-encoded characters
    parsed = urlparse(decoded_uri)
    if parsed.fragment:
        r = parse_fragment(parsed.fragment)

        def handle_continuation(view: Optional[sublime.View]) -> Promise[Optional[sublime.View]]:
            if view:
                center_selection(view, r)
                return Promise.resolve(view)
            return Promise.resolve(None)

        return open_file(window, decoded_uri, flags, group).then(handle_continuation)
    else:
        return open_file(window, decoded_uri, flags, group)


def _return_existing_view(flags: int, existing_view_group: int, active_group: int, specified_group: int) -> bool:
    if specified_group > -1:
        return existing_view_group == specified_group
    if bool(flags & (sublime.ADD_TO_SELECTION | sublime.REPLACE_MRU)):
        return False
    if existing_view_group == active_group:
        return True
    return not bool(flags & sublime.FORCE_GROUP)


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
    if view and _return_existing_view(flags, window.get_view_index(view)[0], window.active_group(), group):
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


def open_in_browser(uri: str) -> None:
    # NOTE: Remove this check when on py3.8.
    if not (uri.lower().startswith("http://") or uri.lower().startswith("https://")):
        uri = "http://" + uri
    if not webbrowser.open(uri):
        sublime.status_message("failed to open: " + uri)


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
