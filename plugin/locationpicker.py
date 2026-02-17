from __future__ import annotations

from ..protocol import DocumentUri
from ..protocol import Location
from ..protocol import LocationLink
from ..protocol import Position
from .core.constants import ST_PACKAGES_PATH
from .core.constants import SublimeKind
from .core.logging import debug
from .core.sessions import Session
from .core.views import get_uri_and_position_from_location
from .core.views import location_to_human_readable
from .core.views import to_encoded_filename
from urllib.request import url2pathname
import functools
import sublime
import weakref


def open_location_async(
    session: Session,
    location: Location | LocationLink,
    side_by_side: bool,
    force_group: bool,
    group: int = -1
) -> None:
    flags = sublime.NewFileFlags.ENCODED_POSITION
    if force_group:
        flags |= sublime.NewFileFlags.FORCE_GROUP
    if side_by_side:
        flags |= sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.SEMI_TRANSIENT

    def check_success_async(view: sublime.View | None) -> None:
        if not view:
            uri = get_uri_and_position_from_location(location)[0]
            msg = f"Unable to open URI {uri}"
            debug(msg)
            session.window.status_message(msg)

    session.open_location_async(location, flags, group).then(check_success_async)


def open_basic_file(
    session: Session,
    uri: str,
    position: Position,
    flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
    group: int | None = None
) -> sublime.View | None:
    if group is None:
        group = session.window.active_group()
    if uri.startswith("file:"):
        filename = session.config.map_server_uri_to_client_path(uri)
    else:
        prefix = 'res:/Packages'  # Note: keep in sync with core/url.py#_to_resource_uri
        assert uri.startswith(prefix)
        filename = ST_PACKAGES_PATH + url2pathname(uri[len(prefix):])
        # Window.open_file can only focus and scroll to a location in a resource file if it is already opened
        if not session.window.find_open_file(filename):
            return None
    return session.window.open_file(to_encoded_filename(filename, position), flags=flags, group=group)


class LocationPicker:

    def __init__(
        self,
        view: sublime.View,
        session: Session,
        locations: list[Location] | list[LocationLink],
        side_by_side: bool,
        force_group: bool = True,
        group: int = -1,
        placeholder: str = "",
        kind: SublimeKind = sublime.KIND_AMBIGUOUS,
        selected_index: int = -1
    ) -> None:
        self._view = view
        self._view_states = ([r.to_tuple() for r in view.sel()], view.viewport_position())
        window = view.window()
        if not window:
            raise ValueError("missing window")
        self._window = window
        self._weaksession = weakref.ref(session)
        self._side_by_side = side_by_side
        self._force_group = force_group
        self._group = group
        self._items = locations
        self._highlighted_view: sublime.View | None = None
        manager = session.manager()
        base_dir = manager.get_project_path(view.file_name() or "") if manager else None
        self._window.focus_group(group)
        config_name = session.config.name
        self._window.show_quick_panel(
            items=[
                sublime.QuickPanelItem(
                    location_to_human_readable(session.config, base_dir, location), annotation=config_name, kind=kind)
                for location in locations
            ],
            on_select=self._select_entry,
            flags=sublime.QuickPanelFlags.KEEP_OPEN_ON_FOCUS_LOST,
            selected_index=selected_index,
            on_highlight=self._highlight_entry,
            placeholder=placeholder
        )

    def _unpack(self, index: int) -> tuple[Session | None, Location | LocationLink, DocumentUri, Position]:
        location = self._items[index]
        uri, position = get_uri_and_position_from_location(location)
        return self._weaksession(), location, uri, position

    def _select_entry(self, index: int) -> None:
        if self._view.is_valid() and not self._side_by_side:
            self._view.set_viewport_position(self._view_states[1])
            self._view.run_command('lsp_selection_set', {'regions': self._view_states[0]})
        if index >= 0 and self._view.is_valid():
            session, location, uri, position = self._unpack(index)
            if not session:
                return
            # Note: this has to run on the main thread (and not via open_location_async)
            # otherwise the bevior feels weird. It's the only reason why open_basic_file exists.
            if uri.startswith(("file:", "res:")):
                flags = sublime.NewFileFlags.ENCODED_POSITION
                if not self._side_by_side:
                    if not open_basic_file(session, uri, position, flags):
                        self._window.status_message(f"Unable to open {uri}")
            else:
                sublime.set_timeout_async(
                    functools.partial(
                        open_location_async, session, location, self._side_by_side, self._force_group, self._group))
        else:
            self._window.focus_view(self._view)
            # When a group was specified close the current highlighted
            # sheet upon canceling if the sheet is transient
            if self._group > -1 and self._highlighted_view:
                sheet = self._highlighted_view.sheet()
                if sheet and sheet.is_transient():
                    self._highlighted_view.close()
            # When in side-by-side mode close the current highlighted
            # sheet upon canceling if the sheet is semi-transient
            if self._side_by_side and self._highlighted_view:
                sheet = self._highlighted_view.sheet()
                if sheet and sheet.is_semi_transient():
                    self._highlighted_view.close()

    def _highlight_entry(self, index: int) -> None:
        session, _, uri, position = self._unpack(index)
        if not session:
            return
        if uri.startswith(("file:", "res:")):
            flags = sublime.NewFileFlags.ENCODED_POSITION | sublime.NewFileFlags.FORCE_GROUP
            if self._side_by_side:
                if self._highlighted_view and self._highlighted_view.is_valid():
                    # Replacing the MRU is done relative to the current highlighted sheet
                    self._window.focus_view(self._highlighted_view)
                    flags |= sublime.NewFileFlags.REPLACE_MRU | sublime.NewFileFlags.SEMI_TRANSIENT
                else:
                    flags |= sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.SEMI_TRANSIENT
            else:
                flags |= sublime.NewFileFlags.TRANSIENT
            # Don't overwrite self._highlighted_view if resource uri can't preview, so that side-by-side view will still
            # be closed upon canceling
            if view := open_basic_file(session, uri, position, flags, self._window.active_group()):
                self._highlighted_view = view
        else:
            # TODO: Preview for other uri schemes?
            debug("no preview for", uri)
