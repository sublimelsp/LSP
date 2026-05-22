from __future__ import annotations

from ..protocol import Point
from typing import TYPE_CHECKING
from typing_extensions import deprecated
import sublime

if TYPE_CHECKING:
    from ....protocol import Position
    from ....protocol import Range


def point_to_offset(point: Point, view: sublime.View) -> int:
    # @see https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#position
    # If the character value is greater than the line length it defaults back to the line length.
    return view.text_point_utf16(point.row, point.col, clamp_column=True)


def offset_to_point(view: sublime.View, offset: int) -> Point:
    return Point(*view.rowcol_utf16(offset))


def offset_to_text_position(view: sublime.View, offset: int) -> Position:
    return offset_to_point(view, offset).to_lsp()


@deprecated('Use offset_to_text_position() instead')
def position(view: sublime.View, offset: int) -> Position:
    return offset_to_text_position(view, offset)


def position_to_offset(position: Position, view: sublime.View) -> int:
    return point_to_offset(Point.from_lsp(position), view)


def range_to_region(lsp_range: Range, view: sublime.View) -> sublime.Region:
    return sublime.Region(position_to_offset(lsp_range['start'], view), position_to_offset(lsp_range['end'], view))


def region_to_range(view: sublime.View, region: sublime.Region) -> Range:
    return {
        'start': offset_to_point(view, region.begin()).to_lsp(),
        'end': offset_to_point(view, region.end()).to_lsp(),
    }
