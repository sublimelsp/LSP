from __future__ import annotations

from .constants import ST_PACKAGES_PATH
from .constants import ST_PLATFORM
from .constants import ST_VERSION
from .executors import executor_main
from .logging import exception_log
from .logging import trace
from .promise import Promise
from .promise import ResolveFunc
from .protocol import UINT_MAX
from .url import parse_uri
from .views import range_to_region
from typing import TYPE_CHECKING
from urllib.parse import unquote
from urllib.parse import urlparse
import asyncio
import os
import re
import sublime
import sublime_plugin
import subprocess
import webbrowser

if TYPE_CHECKING:
    from ...protocol import DocumentUri
    from ...protocol import Range

g_opening_files: dict[str, asyncio.Future[sublime.View | None]] = {}
g_opening_files_lock = asyncio.Lock()
FRAGMENT_PATTERN = re.compile(r'^L?(\d+)(?:,(\d+))?(?:-L?(\d+)(?:,(\d+))?)?')


def lsp_range_from_uri_fragment(fragment: str) -> Range | None:
    if match := FRAGMENT_PATTERN.match(fragment):
        selection: Range = {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}}
        # Line and column numbers in the fragment are assumed to be 1-based and need to be converted to 0-based
        # numbers for the LSP Position structure.
        start_line, start_column, end_line, end_column = (max(0, int(g) - 1) if g else None for g in match.groups())
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


async def open_file_uri(
    window: sublime.Window, uri: DocumentUri, flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE, group: int = -1
) -> sublime.View | None:
    decoded_uri = unquote(uri)  # decode percent-encoded characters
    view = await open_file(window, decoded_uri, flags, group)
    if view:
        if fragment := urlparse(decoded_uri).fragment:
            if selection := lsp_range_from_uri_fragment(fragment):
                center_selection(view, selection)
    return view


def _return_existing_view(flags: int, existing_view_group: int, active_group: int, specified_group: int) -> bool:
    if specified_group > -1:
        return existing_view_group == specified_group
    if bool(flags & (sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.REPLACE_MRU)):
        return False
    if existing_view_group == active_group:
        return True
    return not bool(flags & sublime.NewFileFlags.FORCE_GROUP)


def _find_open_file(window: sublime.Window, fname: str, group: int = -1) -> sublime.View | None:
    """A replacement for Window.find_open_file that prefers the active view instead of the leftmost one."""
    group_ = window.active_group() if group == -1 else group
    view = window.active_view_in_group(group_)
    if view and fname == view.file_name():
        return view
    return window.find_open_file(fname, group) if ST_VERSION >= 4136 else window.find_open_file(fname)


async def open_file(
    window: sublime.Window, uri: DocumentUri, flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE, group: int = -1
) -> sublime.View | None:
    """
    Open a file and wait for it to be done loading.
    The provided uri MUST be a file URI.
    """
    future: asyncio.Future[sublime.View | None] | None = None
    file = parse_uri(uri)[1]
    trace()
    async with g_opening_files_lock:
        trace()
        # Is the view opening right now? Then return the associated unresolved future
        for fn, fut in g_opening_files.items():
            trace()
            if fn == file or os.path.samefile(fn, file):
                trace()
                # Return the unresolved future. A future on_load event will resolve the future.
                future = fut
                trace()
                break
        if future is None:
            trace()
            loop = asyncio.get_running_loop()
            future = loop.create_future()

            def resolve_right_now(view: sublime.View | None) -> None:
                trace()
                future.set_result(view)

            def resolve_later() -> None:
                trace()
                g_opening_files[file] = future

            def on_main_thread() -> None:
                trace()

                # window.open_file brings the file to focus if it's already opened, which we don't want (unless it's supposed
                # to open as a separate view).
                view = _find_open_file(window, file)
                if view and _return_existing_view(flags, window.get_view_index(view)[0], window.active_group(), group):
                    loop.call_soon_threadsafe(lambda: resolve_right_now(view))
                    return

                was_already_open = view is not None
                view = window.open_file(file, flags, group)
                if not view.is_loading():
                    if was_already_open and (flags & sublime.NewFileFlags.SEMI_TRANSIENT):
                        # workaround bug https://github.com/sublimehq/sublime_text/issues/2411 where transient view might not
                        # get its view listeners initialized.
                        sublime_plugin.check_view_event_listeners(view)  # type: ignore
                    # It's already loaded. Possibly already open in a tab.
                    loop.call_soon_threadsafe(lambda: resolve_right_now(view))
                    return

                trace()
                loop.call_soon_threadsafe(resolve_later)

            trace()
            await loop.run_in_executor(executor_main, on_main_thread)
    trace()
    return await future


def open_resource(window: sublime.Window, uri: DocumentUri, group: int = -1) -> sublime.View | None:
    """
    Open a resource file.
    It is only safe to call this function from the UI thread.
    The provided uri MUST be a res URI.
    """
    prefix = 'res:/Packages/'
    if not uri.startswith(prefix):
        return None
    if group != -1:
        window.focus_group(group)
    resource_path = uri[len(prefix):]
    window.run_command('open_file', {'file': f'${{packages}}/{resource_path}'})
    file = os.path.join(ST_PACKAGES_PATH, *resource_path.split('/'))
    return _find_open_file(window, file, group)


def center_selection(view: sublime.View, r: Range) -> sublime.View:
    selection = range_to_region(r, view)
    view.run_command("lsp_selection_set", {"regions": [(selection.a, selection.a)]})
    if window := view.window():
        window.focus_view(view)
    view.show_at_center(selection.begin(), animate=False)
    return view


def open_in_browser(uri: str) -> None:
    # NOTE: Remove this check when on py3.8.
    if not uri.lower().startswith(("http://", "https://")):
        uri = "https://" + uri
    if not webbrowser.open(uri):
        sublime.status_message("failed to open: " + uri)


def open_externally(uri: str) -> bool:
    """A blocking function that invokes the OS's `open with default extension`."""
    try:
        if ST_PLATFORM == "windows":
            os.startfile(uri)  # type: ignore
        elif ST_PLATFORM == "osx":
            subprocess.check_call(("/usr/bin/open", uri))
        else:  # linux
            subprocess.check_call(("xdg-open", uri))  # noqa: S607
    except Exception as ex:
        exception_log(f"Failed to open {uri}", ex)
        return False
    return True
