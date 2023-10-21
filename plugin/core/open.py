from .logging import exception_log
from .promise import Promise
from .promise import ResolveFunc
from .protocol import DocumentUri
from .protocol import Range
from .protocol import UINT_MAX
from .typing import Dict, Tuple, Optional
from .typing import cast
from .url import parse_uri
from .views import range_to_region
from urllib.parse import unquote, urlparse
import os
import re
import sublime
import sublime_plugin
import subprocess
import webbrowser


opening_files = {}  # type: Dict[str, Tuple[Promise[Optional[sublime.View]], ResolveFunc[Optional[sublime.View]]]]
FRAGMENT_PATTERN = re.compile(r'^L?(\d+)(?:,(\d+))?(?:-L?(\d+)(?:,(\d+))?)?')


def lsp_range_from_uri_fragment(fragment: str) -> Optional[Range]:
    match = FRAGMENT_PATTERN.match(fragment)
    if match:
        selection = {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}}  # type: Range
        # Line and column numbers in the fragment are assumed to be 1-based and need to be converted to 0-based
        # numbers for the LSP Position structure.
        start_line, start_column, end_line, end_column = [max(0, int(g) - 1) if g else None for g in match.groups()]
        if start_line:
            selection['start']['line'] = start_line
            selection['end']['line'] = start_line
        if start_column:
            selection['start']['character'] = start_column
            selection['end']['character'] = start_column
        if end_line:
            selection['end']['line'] = end_line
            selection['end']['character'] = UINT_MAX
        if end_column is not None:
            selection['end']['character'] = end_column
        return selection
    return None


def open_file_uri(
    window: sublime.Window, uri: DocumentUri, flags: int = 0, group: int = -1
) -> Promise[Optional[sublime.View]]:

    decoded_uri = unquote(uri)  # decode percent-encoded characters
    parsed = urlparse(decoded_uri)
    open_promise = open_file(window, decoded_uri, flags, group)
    if parsed.fragment:
        selection = lsp_range_from_uri_fragment(parsed.fragment)
        if selection:
            return open_promise.then(lambda view: _select_and_center(view, cast(Range, selection)))
    return open_promise


def _select_and_center(view: Optional[sublime.View], r: Range) -> Optional[sublime.View]:
    if view:
        return center_selection(view, r)
    return None


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

    was_already_open = view is not None
    view = window.open_file(file, flags, group)
    if not view.is_loading():
        if was_already_open and (flags & sublime.SEMI_TRANSIENT):
            # workaround bug https://github.com/sublimehq/sublime_text/issues/2411 where transient view might not get
            # its view listeners initialized.
            sublime_plugin.check_view_event_listeners(view)  # type: ignore
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


def center_selection(v: sublime.View, r: Range) -> sublime.View:
    selection = range_to_region(r, v)
    v.run_command("lsp_selection_set", {"regions": [(selection.a, selection.a)]})
    window = v.window()
    if window:
        window.focus_view(v)
    if int(sublime.version()) >= 4124:
        v.show_at_center(selection.begin(), animate=False)
    else:
        # TODO: remove later when a stable build lands
        v.show_at_center(selection.begin())  # type: ignore
    return v


def open_in_browser(uri: str) -> None:
    # NOTE: Remove this check when on py3.8.
    if not uri.lower().startswith(("http://", "https://")):
        uri = "https://" + uri
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
