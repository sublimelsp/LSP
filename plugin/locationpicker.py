from .core.logging import debug
from .core.protocol import DocumentUri, Location, Position
from .core.protocol import LocationLink
from .core.sessions import Session
from .core.typing import Any, Callable, Dict, List, Optional, Tuple, Union
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

    def check_success_async(success: bool) -> None:
        if not success:
            sublime.error_message("Unable to open URI")

    session.open_location_async(location, flags).then(check_success_async)


def open_basic_file(
    session: Session,
    uri: str,
    position: Position,
    flags: int = 0,
    group: Optional[int] = None
) -> None:
    filename = session.config.map_server_uri_to_client_path(uri)
    if group is None:
        group = session.window.active_group()
    session.window.open_file(to_encoded_filename(filename, position), flags=flags, group=group)


def LocationPicker(
    view: sublime.View,
    session: Session,
    locations: Union[List[Location], List[LocationLink]],
    side_by_side: bool
) -> None:
    manager = session.manager()
    base_dir = manager.get_project_path(view.file_name() or "") if manager else None
    weaksession = weakref.ref(session)
    EnhancedLocationPicker(
        view,
        [(weaksession, location) for location in locations],
        [location_to_human_readable(session.config, base_dir, location) for location in locations],
        side_by_side,
        flags=sublime.KEEP_OPEN_ON_FOCUS_LOST,
    )


OnModifierKeysAcitonMap = Dict[
    frozenset,
    Callable[[sublime.View, Session, Union[Location, LocationLink], DocumentUri, Position], None]
]


class EnhancedLocationPicker:

    def __init__(
        self,
        view: sublime.View,
        locations: List[Tuple[weakref.ReferenceType, Union[Location, LocationLink]]],
        items: List[Any],
        side_by_side: bool,
        on_modifier_keys: OnModifierKeysAcitonMap = {},
        flags: int = 0
    ) -> None:
        self._view = view
        window = view.window()
        if not window:
            raise ValueError("missing window")
        self._window = window
        self._side_by_side = side_by_side
        self._items = locations
        self._on_modifier_keys = on_modifier_keys
        self._window.show_quick_panel(
            items=items,
            on_select=self._select_entry,
            on_highlight=self._highlight_entry,
            flags=flags | sublime.WANT_EVENT
        )

    def _unpack(self, index: int) -> Tuple[Optional[Session], Union[Location, LocationLink], DocumentUri, Position]:
        weaksession, location = self._items[index]
        uri, position = get_uri_and_position_from_location(location)
        return weaksession(), location, uri, position

    def _select_entry(self, index: int, event: dict) -> None:
        if index >= 0 and self._view.is_valid():
            session, location, uri, position = self._unpack(index)
            if not session:
                return
            modifier_keys = frozenset(event.get("modifier_keys", {}))
            if modifier_keys:
                try:
                    action = self._on_modifier_keys[modifier_keys]
                except KeyError:
                    return
                action(self._view, session, location, uri, position)
            else:
                self._goto_location(session, location, uri, position)
        else:
            self._window.focus_view(self._view)

    def _goto_location(
        self,
        session: Session,
        location: Union[Location, LocationLink],
        uri: DocumentUri,
        position: Position
    ) -> None:
        # Note: this has to run on the main thread (and not via open_location_async)
        # otherwise the bevior feels weird. It's the only reason why open_basic_file exists.
        if uri.startswith("file:"):
            flags = sublime.ENCODED_POSITION
            if self._side_by_side:
                flags |= sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT
            open_basic_file(session, uri, position, flags)
        else:
            sublime.set_timeout_async(functools.partial(open_location_async, session, location, self._side_by_side))

    def _highlight_entry(self, index: int) -> None:
        session, _, uri, position = self._unpack(index)
        if not session:
            return
        if uri.startswith("file:"):
            open_basic_file(session, uri, position, sublime.TRANSIENT | sublime.ENCODED_POSITION)
        else:
            # TODO: Preview non-file uris?
            debug("no preview for", uri)
