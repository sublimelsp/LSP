from __future__ import annotations

from ._coordinates import region_to_range
from typing import TYPE_CHECKING
import linecache
import sublime

if TYPE_CHECKING:
    from ....protocol import Range


def get_line(window: sublime.Window, file_name: str, row: int, strip: bool = True) -> str:
    """
    Get the line from the buffer if the view is open, else get line from linecache.
    row - is 0 based. If you want to get the first line, you should pass 0.
    """
    if view := window.find_open_file(file_name):
        # get from buffer
        point = view.text_point(row, 0)
        line = view.substr(view.line(point))
    else:
        # get from linecache
        # linecache row is not 0 based, so we increment it by 1 to get the correct line.
        line = linecache.getline(file_name, row + 1)
    return line.strip() if strip else line


def first_selection_region(view: sublime.View) -> sublime.Region | None:
    try:
        return view.sel()[0]
    except IndexError:
        return None


def has_single_nonempty_selection(view: sublime.View) -> bool:
    selections = view.sel()
    return len(selections) == 1 and not selections[0].empty()


def entire_content_region(view: sublime.View) -> sublime.Region:
    return sublime.Region(0, view.size())


def entire_content(view: sublime.View) -> str:
    return view.substr(entire_content_region(view))


def entire_content_range(view: sublime.View) -> Range:
    return region_to_range(view, entire_content_region(view))
