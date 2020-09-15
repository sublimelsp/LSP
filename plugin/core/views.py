from .protocol import Point, Range, Notification, Request
from .typing import Optional, Dict, Any
from .url import filename_to_uri
from .url import uri_to_filename
import linecache
import os
import sublime
import tempfile


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


def extract_variables(window: sublime.Window) -> Dict[str, str]:
    variables = window.extract_variables()
    variables["cache_path"] = sublime.cache_path()
    variables["temp_dir"] = tempfile.gettempdir()
    variables["home"] = os.path.expanduser('~')
    return variables


def point_to_offset(point: Point, view: sublime.View) -> int:
    return view.text_point(
        point.row,
        # @see https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#position
        # If the character value is greater than the line length it defaults back to the line length.
        min(point.col, len(view.line(view.text_point(point.row, 0))))
    )


def offset_to_point(view: sublime.View, offset: int) -> Point:
    return Point(*view.rowcol(offset))


def range_to_region(range: Range, view: sublime.View) -> sublime.Region:
    return sublime.Region(point_to_offset(range.start, view), point_to_offset(range.end, view))


def region_to_range(view: sublime.View, region: sublime.Region) -> Range:
    return Range(
        offset_to_point(view, region.begin()),
        offset_to_point(view, region.end())
    )


def location_to_encoded_filename(location: Dict[str, Any]) -> str:
    if "targetUri" in location:
        uri = location["targetUri"]
        position = location["targetSelectionRange"]["start"]
    else:
        uri = location["uri"]
        position = location["range"]["start"]
    # WARNING: Cannot possibly do UTF-16 conversion :) Oh well.
    return '{}:{}:{}'.format(uri_to_filename(uri), position['line'] + 1, position['character'] + 1)


class MissingFilenameError(Exception):

    def __init__(self, view_id: int) -> None:
        super().__init__("View {} has no filename".format(view_id))
        self.view_id = view_id


def uri_from_view(view: sublime.View) -> str:
    file_name = view.file_name()
    if file_name:
        return filename_to_uri(file_name)
    raise MissingFilenameError(view.id())


def text_document_identifier(view: sublime.View) -> Dict[str, Any]:
    return {"uri": uri_from_view(view)}


def entire_content(view: sublime.View) -> str:
    return view.substr(sublime.Region(0, view.size()))


def text_document_item(view: sublime.View, language_id: str) -> Dict[str, Any]:
    return {
        "uri": uri_from_view(view),
        "languageId": language_id,
        "version": view.change_count(),
        "text": entire_content(view)
    }


def versioned_text_document_identifier(view: sublime.View) -> Dict[str, Any]:
    return {"uri": uri_from_view(view), "version": view.change_count()}


def text_document_position_params(view: sublime.View, location: int) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view), "position": offset_to_point(view, location).to_lsp()}


def did_open_text_document_params(view: sublime.View, language_id: str) -> Dict[str, Any]:
    return {"textDocument": text_document_item(view, language_id)}


def did_change_text_document_params(view: sublime.View) -> Dict[str, Any]:
    return {
        "textDocument": versioned_text_document_identifier(view),
        "contentChanges": [{"text": entire_content(view)}]
    }


def will_save_text_document_params(view: sublime.View, reason: int) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view), "reason": reason}


def did_save_text_document_params(view: sublime.View, include_text: bool) -> Dict[str, Any]:
    result = {"textDocument": text_document_identifier(view)}  # type: Dict[str, Any]
    if include_text:
        result["text"] = entire_content(view)
    return result


def did_close_text_document_params(view: sublime.View) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view)}


def did_open(view: sublime.View, language_id: str) -> Notification:
    return Notification.didOpen(did_open_text_document_params(view, language_id))


def did_change(view: sublime.View) -> Notification:
    return Notification.didChange(did_change_text_document_params(view))


def will_save(view: sublime.View, reason: int) -> Notification:
    return Notification.willSave(will_save_text_document_params(view, reason))


def will_save_wait_until(view: sublime.View, reason: int) -> Request:
    return Request.willSaveWaitUntil(will_save_text_document_params(view, reason))


def did_save(view: sublime.View, include_text: bool) -> Notification:
    return Notification.didSave(did_save_text_document_params(view, include_text))


def did_close(view: sublime.View) -> Notification:
    return Notification.didClose(did_close_text_document_params(view))


def formatting_options(settings: sublime.Settings) -> Dict[str, Any]:
    return {
        "tabSize": settings.get("tab_size", 4),
        "insertSpaces": settings.get("translate_tabs_to_spaces", False)
    }


def text_document_formatting(view: sublime.View) -> Request:
    return Request.formatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings())
    })


def text_document_range_formatting(view: sublime.View, region: sublime.Region) -> Request:
    return Request.rangeFormatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "range": region_to_range(view, region).to_lsp()
    })


def make_link(href: str, text: str) -> str:
    return "<a href='{}'>{}</a>".format(href, text.replace(' ', '&nbsp;'))
