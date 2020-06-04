from .collections import DottedDict
from .protocol import Point, Range, Notification, Request
from .typing import Optional, Dict, Any, Iterable, List, Union
from .url import filename_to_uri
from .url import uri_to_filename
import linecache
import mdpopups
import os
import re
import sublime
import tempfile

SYMBOL_KINDS = [
    # Display Name     ST Scope
    ("File",           "comment"),
    ("Module",         "comment"),
    ("Namespace",      "keyword.control"),
    ("Package",        "comment"),
    ("Class",          "entity.name.class"),
    ("Method",         "entity.name.function"),
    ("Property",       "comment"),
    ("Field",          "comment"),
    ("Constructor",    "entity.name.function"),
    ("Enum",           "comment"),
    ("Interface",      "entity.name.class"),
    ("Function",       "entity.name.function"),
    ("Variable",       "variable"),
    ("Constant",       "constant"),
    ("String",         "string"),
    ("Number",         "constant.numeric"),
    ("Boolean",        "constant"),
    ("Array",          "variable"),
    ("Object",         "variable"),
    ("Key",            "comment"),
    ("Null",           "comment"),
    ("Enum Member",    "comment"),
    ("Struct",         "comment"),
    ("Event",          "comment"),
    ("Operator",       "comment"),
    ("Type Parameter", "comment"),
]

COMPLETION_KINDS = [
    # ST Kind                    Icon Display Name
    (sublime.KIND_ID_MARKUP,     "t", "Text"),
    (sublime.KIND_ID_FUNCTION,   "m", "Method"),
    (sublime.KIND_ID_FUNCTION,   "f", "Function"),
    (sublime.KIND_ID_FUNCTION,   "c", "Constructor"),
    (sublime.KIND_ID_VARIABLE,   "f", "Field"),
    (sublime.KIND_ID_VARIABLE,   "v", "Variable"),
    (sublime.KIND_ID_TYPE,       "c", "Class"),
    (sublime.KIND_ID_TYPE,       "i", "Interface"),
    (sublime.KIND_ID_NAMESPACE,  "m", "Module"),
    (sublime.KIND_ID_VARIABLE,   "p", "Property"),
    (sublime.KIND_ID_VARIABLE,   "u", "Unit"),
    (sublime.KIND_ID_VARIABLE,   "v", "Value"),
    (sublime.KIND_ID_TYPE,       "e", "Enum"),
    (sublime.KIND_ID_KEYWORD,    "k", "Keyword"),
    (sublime.KIND_ID_SNIPPET,    "s", "Snippet"),
    (sublime.KIND_ID_MARKUP,     "c", "Color"),
    (sublime.KIND_ID_NAVIGATION, "f", "File"),
    (sublime.KIND_ID_NAVIGATION, "r", "Reference"),
    (sublime.KIND_ID_NAMESPACE,  "f", "Folder"),
    (sublime.KIND_ID_VARIABLE,   "e", "Enum Member"),
    (sublime.KIND_ID_VARIABLE,   "c", "Constant"),
    (sublime.KIND_ID_TYPE,       "s", "Struct"),
    (sublime.KIND_ID_TYPE,       "e", "Event"),
    (sublime.KIND_ID_KEYWORD,    "o", "Operator"),
    (sublime.KIND_ID_TYPE,       "t", "Type Parameter"),
]


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
    # @see https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#position
    # If the character value is greater than the line length it defaults back to the line length.
    return min(view.text_point_utf16(point.row, point.col), view.line(view.text_point(point.row, 0)).b)


def offset_to_point(view: sublime.View, offset: int) -> Point:
    return Point(*view.rowcol_utf16(offset))


def position(view: sublime.View, offset: int) -> Dict[str, Any]:
    return offset_to_point(view, offset).to_lsp()


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


def did_change_configuration(d: DottedDict) -> Notification:
    return Notification.didChangeConfiguration({"settings": d.get()})


def selection_range_params(view: sublime.View) -> Dict[str, Any]:
    return {
        "textDocument": text_document_identifier(view),
        "positions": [position(view, r.b) for r in view.sel()]
    }


FORMAT_STRING = 0x1
FORMAT_MARKED_STRING = 0x2
FORMAT_MARKUP_CONTENT = 0x4


def minihtml(view: sublime.View, content: Union[str, Dict[str, str], list], allowed_formats: int) -> str:
    """
    Formats provided input content into markup accepted by minihtml.

    Content can be in one of those formats:
     - string: treated as plain text
     - MarkedString: string or { language: string; value: string }
     - MarkedString[]
     - MarkupContent: { kind: MarkupKind, value: string }

    We can't distinguish between plain text string and a MarkedString in a string form so
    FORMAT_STRING and FORMAT_MARKED_STRING can't both be specified at the same time.

    :param view
    :param content
    :param allowed_formats: Bitwise flag specifying which formats to parse.

    :returns: Formatted string
    """
    if allowed_formats == 0:
        raise ValueError("Must specify at least one format")
    parse_string = bool(allowed_formats & FORMAT_STRING)
    parse_marked_string = bool(allowed_formats & FORMAT_MARKED_STRING)
    parse_markup_content = bool(allowed_formats & FORMAT_MARKUP_CONTENT)
    if parse_string and parse_marked_string:
        raise ValueError("Not allowed to specify FORMAT_STRING and FORMAT_MARKED_STRING at the same time")
    is_plain_text = True
    result = ''
    if (parse_string or parse_marked_string) and isinstance(content, str):
        # plain text string or MarkedString
        is_plain_text = parse_string
        result = content
    if parse_marked_string and isinstance(content, list):
        # MarkedString[]
        formatted = []
        for item in content:
            value = ""
            language = None
            if isinstance(item, str):
                value = item
            else:
                value = item.get("value") or ""
                language = item.get("language")

            if language:
                formatted.append("```{}\n{}\n```\n".format(language, value))
            else:
                formatted.append(value)

        is_plain_text = False
        result = "\n".join(formatted)
    if (parse_marked_string or parse_markup_content) and isinstance(content, dict):
        # MarkupContent or MarkedString (dict)
        language = content.get("language")
        kind = content.get("kind")
        value = content.get("value") or ""
        if parse_markup_content and kind:
            # MarkupContent
            is_plain_text = kind != "markdown"
            result = value
        if parse_marked_string and language:
            # MarkedString (dict)
            is_plain_text = False
            result = "```{}\n{}\n```\n".format(language, value)
    if is_plain_text:
        return text2html(result)
    else:
        frontmatter_config = mdpopups.format_frontmatter({'allow_code_wrap': True})
        return mdpopups.md2html(view, frontmatter_config + result)


REPLACEMENT_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\t": 4 * "&nbsp;",
    "\n": "<br>",
    "\xa0": "&nbsp;",  # non-breaking space
    "\xc2": "&nbsp;",  # control character
}

PATTERNS = [
    r'(?P<special>[{}])'.format(''.join(REPLACEMENT_MAP.keys())),
    r'(?P<url>https?://(?:[\w\d:#@%/;$()~_?\+\-=\\\.&](?:#!)?)*)',
    r'(?P<multispace> {2,})',
]

REPLACEMENT_RE = re.compile('|'.join(PATTERNS), flags=re.IGNORECASE)


def _replace_match(match: Any) -> str:
    special_match = match.group('special')
    if special_match:
        return REPLACEMENT_MAP[special_match]
    url = match.group('url')
    if url:
        return "<a href='{}'>{}</a>".format(url, url)
    return len(match.group('multispace')) * '&nbsp;'


def text2html(content: str) -> str:
    return re.sub(REPLACEMENT_RE, _replace_match, content)


def make_link(href: str, text: str) -> str:
    return "<a href='{}'>{}</a>".format(href, text.replace(' ', '&nbsp;'))
