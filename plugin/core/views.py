import sublime
import linecache
from .protocol import Point, Range
from .typing import Optional


def get_line(window: Optional[sublime.Window], file_name: str, row: int) -> str:
    '''
    Get the line from the buffer if the view is open, else get line from linecache.
    row - is 0 based. If you want to get the first line, you should pass 0.
    '''
    if not window:
        return ''

    view = window.find_open_file(file_name)
    if view:
        # get from buffer
        point = view.text_point(row, 0)
        return view.substr(view.line(point)).strip()
    else:
        # get from linecache
        # linecache row is not 0 based, so we increment it by 1 to get the correct line.
        return linecache.getline(file_name, row + 1).strip()


def point_to_offset(point: Point, view: sublime.View) -> int:
    return view.text_point(point.row, point.col)


def offset_to_point(view: sublime.View, offset: int) -> Point:
    return Point(*view.rowcol(offset))


def range_to_region(range: Range, view: sublime.View) -> sublime.Region:
    return sublime.Region(point_to_offset(range.start, view), point_to_offset(range.end, view))


def region_to_range(view: sublime.View, region: sublime.Region) -> Range:
    return Range(
        offset_to_point(view, region.begin()),
        offset_to_point(view, region.end())
    )
