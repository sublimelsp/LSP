from __future__ import annotations

from ....protocol import DocumentUri
from ....protocol import Location
from ....protocol import LocationLink
from ....protocol import Position
from ....protocol import Range
from ..url import parse_uri
from ..workspace import is_subpath_of
from os.path import commonpath
from typing import cast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import ClientConfig
    import sublime


class InvalidUriSchemeError(Exception):
    def __init__(self, uri: str) -> None:
        super().__init__(f"invalid URI scheme: {uri}")


class MissingUriError(Exception):

    def __init__(self, view_id: int) -> None:
        super().__init__(f"View {view_id} has no URI")
        self.view_id = view_id


def uri_from_view(view: sublime.View) -> DocumentUri:
    uri = view.settings().get("lsp_uri")
    if isinstance(uri, DocumentUri):
        return uri
    raise MissingUriError(view.id())


def to_encoded_filename(path: str, position: Position) -> str:
    # WARNING: Cannot possibly do UTF-16 conversion :) Oh well.
    return '{}:{}:{}'.format(path, position['line'] + 1, position['character'] + 1)


def get_uri_and_range_from_location(location: Location | LocationLink) -> tuple[DocumentUri, Range]:
    if "targetUri" in location:
        location = cast('LocationLink', location)
        uri = location["targetUri"]
        r = location["targetSelectionRange"]
    else:
        location = cast('Location', location)
        uri = location["uri"]
        r = location["range"]
    return uri, r


def get_uri_and_position_from_location(location: Location | LocationLink) -> tuple[DocumentUri, Position]:
    if "targetUri" in location:
        location = cast('LocationLink', location)
        uri = location["targetUri"]
        position = location["targetSelectionRange"]["start"]
    else:
        location = cast('Location', location)
        uri = location["uri"]
        position = location["range"]["start"]
    return uri, position


def location_to_encoded_filename(location: Location | LocationLink) -> str:
    """DEPRECATED."""
    uri, position = get_uri_and_position_from_location(location)
    scheme, parsed = parse_uri(uri)
    if scheme == "file":
        return to_encoded_filename(parsed, position)
    raise InvalidUriSchemeError(uri)


def location_to_human_readable(
    config: ClientConfig,
    base_dir: str | None,
    location: Location | LocationLink
) -> str:
    """Format an LSP Location (or LocationLink) into a string suitable for a human to read."""
    uri, position = get_uri_and_position_from_location(location)
    scheme, _ = parse_uri(uri)
    if scheme == "file":
        fmt = "{}:{}"
        pathname = config.map_server_uri_to_client_path(uri)
        if base_dir and is_subpath_of(pathname, base_dir):
            pathname = pathname[len(commonpath((pathname, base_dir))) + 1:]
    elif scheme == "res":
        fmt = "{}:{}"
        pathname = uri
    else:
        # https://tools.ietf.org/html/rfc5147
        fmt = "{}#line={}"
        pathname = uri
    return fmt.format(pathname, position["line"] + 1)


def location_to_href(config: ClientConfig, location: Location | LocationLink) -> str:
    """Encode an LSP Location (or LocationLink) into a string suitable as a hyperlink in minihtml."""
    uri, position = get_uri_and_position_from_location(location)
    return "location:{}@{}#{},{}".format(config.name, uri, position["line"], position["character"])


def unpack_href_location(href: str) -> tuple[str, str, int, int]:
    """Return the session name, URI, row, and col_utf16 from an encoded href."""
    session_name, uri_with_fragment = href[len("location:"):].split("@")
    uri, fragment = uri_with_fragment.split("#")
    row, col_utf16 = map(int, fragment.split(","))
    return session_name, uri, row, col_utf16


def is_location_href(href: str) -> bool:
    """Check whether this href is an encoded location."""
    return href.startswith("location:")
