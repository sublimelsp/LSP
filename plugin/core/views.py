import sublime
from .protocol import Point, Range


def point_to_offset(point: Point, view: sublime.View) -> int:
    return view.text_point(point.row, point.col)


def offset_to_point(view: sublime.View, offset: int) -> 'Point':
    return Point(*view.rowcol(offset))


def range_to_region(range: Range, view: sublime.View) -> 'sublime.Region':
    return sublime.Region(point_to_offset(range.start, view), point_to_offset(range.end, view))


def region_to_range(view: sublime.View, region: sublime.Region) -> 'Range':
    return Range(
        offset_to_point(view, region.begin()),
        offset_to_point(view, region.end())
    )
