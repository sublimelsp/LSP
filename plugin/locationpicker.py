from .core.logging import debug
from .core.protocol import DocumentUri, Location, Position
from .core.protocol import LocationLink
from .core.sessions import Session
from .core.typing import Union, List, Optional, Tuple
from .core.views import get_uri_and_position_from_location
from .core.views import location_to_human_readable
from .core.views import to_encoded_filename
import functools
import sublime
import weakref


def open_location_async(session: Session, location: Union[Location, LocationLink], side_by_side: bool) -> None:
    flags = sublime.ENCODED_POSITION
    if side_by_side:
        flags |= sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT

    def check_success_async(view: Optional[sublime.View]) -> None:
        if not view:
            sublime.error_message("Unable to open URI")

    session.open_location_async(location, flags).then(check_success_async)


def open_basic_file(
    session: Session,
    uri: str,
    position: Position,
    flags: int = 0,
    group: Optional[int] = None
) -> sublime.View:
    filename = session.config.map_server_uri_to_client_path(uri)
    if group is None:
        group = session.window.active_group()
    return session.window.open_file(to_encoded_filename(filename, position), flags=flags, group=group)


class LocationPicker:

    def __init__(
        self,
        view: sublime.View,
        session: Session,
        locations: Union[List[Location], List[LocationLink]],
        side_by_side: bool
    ) -> None:
        self._view = view
        window = view.window()
        if not window:
            raise ValueError("missing window")
        self._window = window
        self._weaksession = weakref.ref(session)
        self._side_by_side = side_by_side
        self._items = locations
        self._highlighted_view = None  # type: Optional[sublime.View]
        manager = session.manager()
        base_dir = manager.get_project_path(view.file_name() or "") if manager else None
        self._window.show_quick_panel(
            items=[location_to_human_readable(session.config, base_dir, location) for location in locations],
            on_select=self._select_entry,
            on_highlight=self._highlight_entry,
            flags=sublime.KEEP_OPEN_ON_FOCUS_LOST
        )

    def _unpack(self, index: int) -> Tuple[Optional[Session], Union[Location, LocationLink], DocumentUri, Position]:
        location = self._items[index]
        uri, position = get_uri_and_position_from_location(location)
        return self._weaksession(), location, uri, position

    def _select_entry(self, index: int) -> None:
        if index >= 0 and self._view.is_valid():
            session, location, uri, position = self._unpack(index)
            if not session:
                return
            # Note: this has to run on the main thread (and not via open_location_async)
            # otherwise the bevior feels weird. It's the only reason why open_basic_file exists.
            if uri.startswith("file:"):
                flags = sublime.ENCODED_POSITION
                if not self._side_by_side:
                    open_basic_file(session, uri, position, flags)
            else:
                sublime.set_timeout_async(functools.partial(open_location_async, session, location, self._side_by_side))
        else:
            self._window.focus_view(self._view)
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
        if uri.startswith("file:"):
            flags = sublime.ENCODED_POSITION | sublime.FORCE_GROUP
            if self._side_by_side:
                if self._highlighted_view and self._highlighted_view.is_valid():
                    # Replacing the MRU is done relative to the current highlighted sheet
                    self._window.focus_view(self._highlighted_view)
                    flags |= sublime.REPLACE_MRU | sublime.SEMI_TRANSIENT
                else:
                    flags |= sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT
            else:
                flags |= sublime.TRANSIENT
            self._highlighted_view = open_basic_file(session, uri, position, flags, self._window.active_group())
        else:
            # TODO: Preview non-file uris?
            debug("no preview for", uri)
