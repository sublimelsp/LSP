from __future__ import annotations

from .protocol import TextPosition
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protocol import Position
    import sublime

# TODO: Move these functions back into views.py once the deprecated variants with the old argument order are removed.


def point_to_offset(view: sublime.View, point: TextPosition) -> int:
    # @see https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#position
    # If the character value is greater than the line length it defaults back to the line length.
    return view.text_point_utf16(point.row, point.col, clamp_column=True)


def position_to_offset(view: sublime.View, position: Position) -> int:
    return point_to_offset(view, TextPosition.from_lsp(position))
