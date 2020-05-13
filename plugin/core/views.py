import html
import linecache
import mdpopups
import re
import sublime
from .protocol import Point, Range, Notification, Request
from .typing import Optional, Dict, Any, Iterable, List, Union
from .url import filename_to_uri


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
    # @see https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#position
    # If the character value is greater than the line length it defaults back to the line length.
    return min(view.text_point_utf16(point.row, point.col), view.line(view.text_point(point.row, 0)).b)


def offset_to_point(view: sublime.View, offset: int) -> Point:
    return Point(*view.rowcol_utf16(offset))


def range_to_region(range: Range, view: sublime.View) -> sublime.Region:
    return sublime.Region(point_to_offset(range.start, view), point_to_offset(range.end, view))


def region_to_range(view: sublime.View, region: sublime.Region) -> Range:
    return Range(
        offset_to_point(view, region.begin()),
        offset_to_point(view, region.end())
    )


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


def render_text_change(change: sublime.TextChange) -> Dict[str, Any]:
    # Note: cannot use protocol.Range because these are "historic" points.
    return {
        "range": {
            "start": {"line": change.a.row, "character": change.a.col_utf16},
            "end":   {"line": change.b.row, "character": change.b.col_utf16}},
        "rangeLength": abs(change.b.pt - change.a.pt),
        "text": change.str
    }


def did_change_text_document_params(view: sublime.View,
                                    changes: Optional[Iterable[sublime.TextChange]] = None) -> Dict[str, Any]:
    content_changes = []  # type: List[Dict[str, Any]]
    result = {"textDocument": versioned_text_document_identifier(view), "contentChanges": content_changes}
    if changes is None:
        # TextDocumentSyncKindFull
        content_changes.append({"text": entire_content(view)})
    else:
        # TextDocumentSyncKindIncremental
        for change in changes:
            content_changes.append(render_text_change(change))
    return result


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


def did_change(view: sublime.View, changes: Optional[Iterable[sublime.TextChange]] = None) -> Notification:
    return Notification.didChange(did_change_text_document_params(view, changes))


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


def minihtml(view: sublime.View, content: Union[str, dict]) -> str:
    """ Content can be a string or MarkupContent. """
    if isinstance(content, str):
        return text2html(content)
    elif isinstance(content, dict):
        value = content.get("value") or ""
        kind = content.get("kind")
        if kind == "markdown":
            return mdpopups.md2html(view, value)
        else:
            # must be plaintext
            return text2html(value)
    else:
        return ''


def text2html(content: str) -> str:
    content = html.escape(content).replace('\n', '<br>').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')

    def replace_nbsp(match: Any) -> str:
        spaces = match.group(0)
        return "&nbsp;" * len(spaces)

    # if there are 2 or more spaces, replace them with &nbsp;
    content = re.sub(r"( {2,})", replace_nbsp, content)

    def replace_url_with_link(match: Any) -> str:
        url = match.group(0)
        return "<a href='{}'>{}</a>".format(url, url)

    FIND_URL = re.compile(r'(https?://(?:[\w\d:#@%/;$()~_?\+\-=\\\.&](?:#!)?)*)', flags=re.IGNORECASE)
    return re.sub(FIND_URL, replace_url_with_link, content)
