from .core.logging import debug
from .core.protocol import Location
from .core.protocol import LocationLink
from .core.sessions import Session
from .core.typing import Union, List
from .core.views import get_uri_and_position_from_location
from .core.workspace import is_subpath_of
from urllib.parse import urlparse
from urllib.request import url2pathname
import functools
import os
import re
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
        manager = session.manager()
        base_dir = manager.get_project_path(view.file_name() or "") if manager else None
        items = []
        for location in locations:
            uri, position = get_uri_and_position_from_location(location)
            parsed = urlparse(uri)
            if parsed.scheme == "file":
                fmt = "{}:{}"
                prefix = url2pathname(parsed.path)
                if os.name == "nt" and re.match(r'^/[a-zA-Z]:/', prefix):
                    prefix = prefix[1:]
                if base_dir and is_subpath_of(prefix, base_dir):
                    prefix = prefix[len(os.path.commonprefix((prefix, base_dir))) + 1:]
            else:
                # https://tools.ietf.org/html/rfc5147
                fmt = "{}#line={}"
                prefix = uri
            items.append(fmt.format(prefix, position['line'] + 1))
        self._window.show_quick_panel(
            items=items,
            on_select=self._select_entry,
            on_highlight=self._highlight_entry,
            flags=sublime.KEEP_OPEN_ON_FOCUS_LOST
        )

    def _open_location(self, location: Union[Location, LocationLink]) -> None:
        session = self._weaksession()
        if not session:
            return
        sublime.set_timeout_async(functools.partial(open_location_async, session, location, self._side_by_side))

    def _select_entry(self, index: int) -> None:
        if index >= 0:
            self._open_location(self._items[index])
        else:
            self._window.focus_view(self._view)

    def _highlight_entry(self, index: int) -> None:
        location = self._items[index]
        uri, pos = get_uri_and_position_from_location(location)
        parsed = urlparse(uri)
        if parsed.scheme == "file":
            self._window.open_file(
                "{}:{}:{}".format(url2pathname(parsed.path), pos["line"] + 1, pos["character"] + 1),
                group=self._window.active_group(),
                flags=sublime.TRANSIENT | sublime.ENCODED_POSITION
            )
        else:
            # TODO: Preview non-file uris?
            debug("no preview for", uri)
