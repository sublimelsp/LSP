from .css import css
from .protocol import CodeLens
from .protocol import CompletionItemTag
from .protocol import Diagnostic
from .protocol import DiagnosticRelatedInformation
from .protocol import DiagnosticSeverity
from .protocol import InsertTextFormat
from .protocol import Notification
from .protocol import Point
from .protocol import Range
from .protocol import Request
from .typing import Optional, Dict, Any, Iterable, List, Union, Callable
from .url import filename_to_uri
from .url import uri_to_filename
import html
import linecache
import mdpopups
import os
import re
import sublime
import sublime_plugin
import tempfile

DIAGNOSTIC_SEVERITY = [
    # Kind       CSS class   Scope for color     Icon resource
    ("error",   "errors",   "region.redish",    "Packages/LSP/icons/error.png"),
    ("warning", "warnings", "region.yellowish", "Packages/LSP/icons/warning.png"),
    ("info",    "info",     "region.bluish",    "Packages/LSP/icons/info.png"),
    ("hint",    "hints",    "region.bluish",    "Packages/LSP/icons/info.png"),
]

# The scope names mainly come from http://www.sublimetext.com/docs/3/scope_naming.html
SYMBOL_KINDS = [
    # ST Kind                    Icon  Display Name      ST Scope
    (sublime.KIND_ID_NAVIGATION, "f", "File",           "string"),
    (sublime.KIND_ID_NAMESPACE,  "m", "Module",         "entity.name.namespace"),
    (sublime.KIND_ID_NAMESPACE,  "n", "Namespace",      "entity.name.namespace"),
    (sublime.KIND_ID_NAMESPACE,  "p", "Package",        "entity.name.namespace"),
    (sublime.KIND_ID_TYPE,       "c", "Class",          "entity.name.class"),
    (sublime.KIND_ID_FUNCTION,   "m", "Method",         "entity.name.function"),
    (sublime.KIND_ID_VARIABLE,   "p", "Property",       "variable.other.member"),
    (sublime.KIND_ID_VARIABLE,   "f", "Field",          "variable.other.member"),
    (sublime.KIND_ID_FUNCTION,   "c", "Constructor",    "entity.name.function.constructor"),
    (sublime.KIND_ID_TYPE,       "e", "Enum",           "entity.name.enum"),
    (sublime.KIND_ID_VARIABLE,   "i", "Interface",      "entity.name.interface"),
    (sublime.KIND_ID_FUNCTION,   "f", "Function",       "entity.name.function"),
    (sublime.KIND_ID_VARIABLE,   "v", "Variable",       "variable.other.readwrite"),
    (sublime.KIND_ID_VARIABLE,   "c", "Constant",       "variable.other.constant"),
    (sublime.KIND_ID_MARKUP,     "s", "String",         "string"),
    (sublime.KIND_ID_VARIABLE,   "n", "Number",         "constant.numeric"),
    (sublime.KIND_ID_VARIABLE,   "b", "Boolean",        "constant.language"),
    (sublime.KIND_ID_TYPE,       "a", "Array",          "meta.sequence"),  # [scope taken from JSON.sublime-syntax]
    (sublime.KIND_ID_TYPE,       "o", "Object",         "meta.mapping"),  # [scope taken from JSON.sublime-syntax]
    (sublime.KIND_ID_NAVIGATION, "k", "Key",            "meta.mapping.key string"),  # [from JSON.sublime-syntax]
    (sublime.KIND_ID_VARIABLE,   "n", "Null",           "constant.language"),
    (sublime.KIND_ID_VARIABLE,   "e", "Enum Member",    "constant.other.enum"),  # Based on {Java,C#}.sublime-syntax
    (sublime.KIND_ID_TYPE,       "s", "Struct",         "entity.name.struct"),
    (sublime.KIND_ID_TYPE,       "e", "Event",          "storage.modifier"),   # [scope taken from C#.sublime-syntax]
    (sublime.KIND_ID_FUNCTION,   "o", "Operator",       "keyword.operator"),
    (sublime.KIND_ID_TYPE,       "t", "Type Parameter", "storage.type"),
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


def get_storage_path() -> str:
    """
    The "Package Storage" is a way to store server data without influencing the behavior of Sublime Text's "catalog".
    Its path is '$DATA/Package Storage', where $DATA means:

    - on macOS: ~/Library/Application Support/Sublime Text
    - on Windows: %AppData%/Sublime Text/Roaming
    - on Linux: $XDG_CONFIG_DIR/sublime-text
    """
    return os.path.abspath(os.path.join(sublime.cache_path(), "..", "Package Storage"))


def extract_variables(window: sublime.Window) -> Dict[str, str]:
    variables = window.extract_variables()
    variables["storage_path"] = get_storage_path()
    variables["cache_path"] = sublime.cache_path()
    variables["temp_dir"] = tempfile.gettempdir()
    variables["home"] = os.path.expanduser('~')
    return variables


def point_to_offset(point: Point, view: sublime.View) -> int:
    # @see https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#position
    # If the character value is greater than the line length it defaults back to the line length.
    return view.text_point_utf16(point.row, point.col, clamp_column=True)


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


def text_document_identifier(view_or_file_name: Union[str, sublime.View]) -> Dict[str, Any]:
    if isinstance(view_or_file_name, str):
        uri = filename_to_uri(view_or_file_name)
    else:
        uri = uri_from_view(view_or_file_name)
    return {"uri": uri}


def entire_content_region(view: sublime.View) -> sublime.Region:
    return sublime.Region(0, view.size())


def entire_content(view: sublime.View) -> str:
    return view.substr(entire_content_region(view))


def entire_content_range(view: sublime.View) -> Range:
    return region_to_range(view, entire_content_region(view))


def text_document_item(view: sublime.View, language_id: str) -> Dict[str, Any]:
    return {
        "uri": uri_from_view(view),
        "languageId": language_id,
        "version": view.change_count(),
        "text": entire_content(view)
    }


def versioned_text_document_identifier(view: sublime.View, version: int) -> Dict[str, Any]:
    return {"uri": uri_from_view(view), "version": version}


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
        "rangeLength": change.len_utf16,
        "text": change.str
    }


def did_change_text_document_params(view: sublime.View, version: int,
                                    changes: Optional[Iterable[sublime.TextChange]] = None) -> Dict[str, Any]:
    content_changes = []  # type: List[Dict[str, Any]]
    result = {"textDocument": versioned_text_document_identifier(view, version), "contentChanges": content_changes}
    if changes is None:
        # TextDocumentSyncKindFull
        content_changes.append({"text": entire_content(view)})
    else:
        # TextDocumentSyncKindIncremental
        for change in changes:
            content_changes.append(render_text_change(change))
    return result


def will_save_text_document_params(view_or_file_name: Union[str, sublime.View], reason: int) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view_or_file_name), "reason": reason}


def did_save_text_document_params(
    view: sublime.View, include_text: bool, file_name: Optional[str] = None
) -> Dict[str, Any]:
    identifier = text_document_identifier(file_name if file_name is not None else view)
    result = {"textDocument": identifier}  # type: Dict[str, Any]
    if include_text:
        result["text"] = entire_content(view)
    return result


def did_close_text_document_params(file_name: str) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(file_name)}


def did_open(view: sublime.View, language_id: str) -> Notification:
    return Notification.didOpen(did_open_text_document_params(view, language_id))


def did_change(view: sublime.View, version: int,
               changes: Optional[Iterable[sublime.TextChange]] = None) -> Notification:
    return Notification.didChange(did_change_text_document_params(view, version, changes))


def will_save(file_name: str, reason: int) -> Notification:
    return Notification.willSave(will_save_text_document_params(file_name, reason))


def will_save_wait_until(view: sublime.View, reason: int) -> Request:
    return Request.willSaveWaitUntil(will_save_text_document_params(view, reason), view)


def did_save(view: sublime.View, include_text: bool, file_name: Optional[str] = None) -> Notification:
    return Notification.didSave(did_save_text_document_params(view, include_text, file_name))


def did_close(file_name: str) -> Notification:
    return Notification.didClose(did_close_text_document_params(file_name))


def formatting_options(settings: sublime.Settings) -> Dict[str, Any]:
    # Build 4085 allows "trim_trailing_white_space_on_save" to be a string so we have to account for that in a
    # backwards-compatible way.
    trim_trailing_white_space = settings.get("trim_trailing_white_space_on_save") not in (False, None, "none")
    return {
        # Size of a tab in spaces.
        "tabSize": settings.get("tab_size", 4),
        # Prefer spaces over tabs.
        "insertSpaces": settings.get("translate_tabs_to_spaces", False),
        # Trim trailing whitespace on a line. (since 3.15)
        "trimTrailingWhitespace": trim_trailing_white_space,
        # Insert a newline character at the end of the file if one does not exist. (since 3.15)
        "insertFinalNewline": settings.get("ensure_newline_at_eof_on_save", False),
        # Trim all newlines after the final newline at the end of the file. (sine 3.15)
        "trimFinalNewlines": settings.get("ensure_newline_at_eof_on_save", False)
    }


def text_document_formatting(view: sublime.View) -> Request:
    return Request.formatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings())
    }, view)


def text_document_range_formatting(view: sublime.View, region: sublime.Region) -> Request:
    return Request.rangeFormatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "range": region_to_range(view, region).to_lsp()
    }, view)


def selection_range_params(view: sublime.View) -> Dict[str, Any]:
    return {
        "textDocument": text_document_identifier(view),
        "positions": [position(view, r.b) for r in view.sel()]
    }


def text_document_code_action_params(
    view: sublime.View,
    file_name: str,
    range: Range,
    diagnostics: List[Diagnostic],
    on_save_actions: Optional[List[str]] = None
) -> Dict:
    params = {
        "textDocument": {
            "uri": filename_to_uri(file_name)
        },
        "range": range.to_lsp(),
        "context": {
            "diagnostics": list(diagnostic.to_lsp() for diagnostic in diagnostics)
        }
    }
    if on_save_actions:
        params['context']['only'] = on_save_actions
    return params


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
        return "<p>{}</p>".format(text2html(result)) if result else ''
    else:
        frontmatter = {
            "allow_code_wrap": True,
            "markdown_extensions": [
                {
                    "pymdownx.escapeall": {
                        "hardbreak": False,
                        "nbsp": False
                    }
                },
                {
                    "pymdownx.magiclink": {
                        # links are displayed without the initial ftp://, http://, https://, or ftps://.
                        "hide_protocol": True,
                        # GitHub, Bitbucket, and GitLab commit, pull, and issue links are are rendered in a shorthand
                        # syntax.
                        "repo_url_shortener": True
                    }
                }
            ]
        }
        # Workaround CommonMark deficiency: two spaces followed by a newline should result in a new paragraph.
        result = re.sub('(\\S)  \n', '\\1\n\n', result)
        return mdpopups.md2html(view, mdpopups.format_frontmatter(frontmatter) + result)


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


def make_link(href: str, text: str, class_name: Optional[str] = None) -> str:
    text = text.replace(' ', '&nbsp;')
    if class_name:
        return "<a href='{}' class='{}'>{}</a>".format(href, class_name, text)
    else:
        return "<a href='{}'>{}</a>".format(href, text)


def make_command_link(command: str, text: str, command_args: Optional[Dict[str, Any]] = None,
                      class_name: Optional[str] = None, view: Optional[sublime.View] = None) -> str:
    if view:
        cmd = "lsp_run_text_command_helper"
        args = {"view_id": view.id(), "command": command, "args": command_args}  # type: Optional[Dict[str, Any]]
    else:
        cmd = command
        args = command_args
    return make_link(sublime.command_url(cmd, args), text, class_name)


class LspRunTextCommandHelperCommand(sublime_plugin.WindowCommand):
    def run(self, view_id: int, command: str, args: Optional[Dict[str, Any]] = None) -> None:
        view = sublime.View(view_id)
        if view.is_valid():
            view.run_command(command, args)


COLOR_BOX_HTML = """
<style>html {{padding: 0; background-color: transparent}}</style>
<body id='lsp-color-box'>
<div style='padding: 0.4em;
            margin-top: 0.2em;
            border: 1px solid color(var(--foreground) alpha(0.25));
            background-color: rgba({}, {}, {}, {})'>
</div>
</body>"""


def lsp_color_to_html(color_info: Dict[str, Any]) -> str:
    color = color_info['color']
    red = color['red'] * 255
    green = color['green'] * 255
    blue = color['blue'] * 255
    alpha = color['alpha']
    return COLOR_BOX_HTML.format(red, green, blue, alpha)


def lsp_color_to_phantom(view: sublime.View, color_info: Dict[str, Any]) -> sublime.Phantom:
    region = range_to_region(Range.from_lsp(color_info['range']), view)
    return sublime.Phantom(region, lsp_color_to_html(color_info), sublime.LAYOUT_INLINE)


def document_color_params(view: sublime.View) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view)}


def format_severity(severity: int) -> str:
    if 1 <= severity <= len(DIAGNOSTIC_SEVERITY):
        return DIAGNOSTIC_SEVERITY[severity - 1][0]
    return "???"


def format_diagnostic_for_panel(diagnostic: Diagnostic) -> str:
    location = "{:>8}:{:<4}".format(diagnostic.range.start.row + 1, diagnostic.range.start.col + 1)
    lines = diagnostic.message.splitlines() or [""]
    severity = format_severity(diagnostic.severity)
    formatted = " {}\t{:<12}\t{:<10}\t{}".format(location, diagnostic.source, severity, lines[0])
    for line in lines[1:]:
        formatted = formatted + "\n {:<12}\t{:<12}\t{:<10}\t{}".format("", "", "", line)
    return formatted


def _format_diagnostic_related_info(info: DiagnosticRelatedInformation, base_dir: Optional[str] = None) -> str:
    file_path = info.location.file_path
    if base_dir and file_path.startswith(base_dir):
        file_path = os.path.relpath(file_path, base_dir)
    row = info.location.range.start.row + 1
    col = info.location.range.start.col + 1
    encoded_filename = "{}:{}:{}".format(info.location.file_path, row, col)
    file_path = "{}:{}:{}".format(file_path, row, col)
    return '<a href="location:{}">{}</a>: {}'.format(encoded_filename, text2html(file_path), text2html(info.message))


def format_diagnostic_for_html(diagnostic: Diagnostic, base_dir: Optional[str] = None) -> str:
    diagnostic_message = text2html(diagnostic.message)
    related_infos = [_format_diagnostic_related_info(info, base_dir) for info in diagnostic.related_info]
    related_content = "<pre class='related_info'>" + "<br>".join(related_infos) + "</pre>" if related_infos else ""
    if diagnostic.source:
        content = "[{}] {}{}".format(diagnostic.source, diagnostic_message, related_content)
    else:
        content = "{}{}".format(diagnostic_message, related_content)
    return '<pre class="{}">{}</pre>'.format(DIAGNOSTIC_SEVERITY[diagnostic.severity - 1][1], content)


def create_phantom_html(content: str, severity: str) -> str:
    return """<body id=inline-error>
                <style>{0}</style>
                <div class="{1}-arrow"></div>
                <div class="{1} container">
                    <div class="toolbar">
                        <a href="hide">×</a>
                        <a href="previous">↑</a>
                        <a href="next">↓</a>
                    </div>
                    <div class="content">{2}</div>
                </div>
            </body>""".format(css().phantoms, severity, content)


def diagnostic_to_phantom(
    view: sublime.View,
    diagnostic: Diagnostic,
    base_dir: Optional[str],
    on_navigate: Callable[[str], None]
) -> sublime.Phantom:
    """
    Creates a "cursor" phantom.

    The hyperref for the on_navigate callback can contain the following links:
    - "hide"
    - "previous"
    - "next"
    """
    region = range_to_region(diagnostic.range, view)
    message = text2html(diagnostic.message)
    if diagnostic.source:
        message = "<p>[{}] {}</p>".format(diagnostic.source, message)
    else:
        message = "<p>{}</p>".format(message)
    additional_infos = "<br>".join([_format_diagnostic_related_info(i, base_dir) for i in diagnostic.related_info])
    severity = "error" if diagnostic.severity == DiagnosticSeverity.Error else "warning"
    content = message + "<p class='additional'>" + additional_infos + "</p>" if additional_infos else message
    return sublime.Phantom(
        region,
        create_phantom_html(content, severity),
        sublime.LAYOUT_BELOW,
        on_navigate
    )


def _is_completion_item_deprecated(item: dict) -> bool:
    if item.get("deprecated", False):
        return True
    tags = item.get("tags")
    if isinstance(tags, list):
        return CompletionItemTag.Deprecated in tags
    return False


def format_completion(
    item: dict, index: int, can_resolve_completion_items: bool, session_name: str
) -> sublime.CompletionItem:
    # This is a hot function. Don't do heavy computations or IO in this function.
    item_kind = item.get("kind")
    if isinstance(item_kind, int) and 1 <= item_kind <= len(COMPLETION_KINDS):
        kind = COMPLETION_KINDS[item_kind - 1]
    else:
        kind = sublime.KIND_AMBIGUOUS

    if _is_completion_item_deprecated(item):
        kind = (kind[0], '⚠', "⚠ {} - Deprecated".format(kind[2]))

    lsp_label = item["label"]
    lsp_filter_text = item.get("filterText")
    lsp_detail = html.escape(item.get("detail") or "").replace('\n', ' ')

    if lsp_filter_text and lsp_filter_text != lsp_label:
        st_trigger = lsp_filter_text
        st_annotation = lsp_label
    else:
        st_trigger = lsp_label
        st_annotation = ""

    st_details = ""
    if can_resolve_completion_items or item.get("documentation"):
        st_details += make_command_link("lsp_resolve_docs", "More", {"index": index})
        st_details += " | " if lsp_detail else ""

    st_details += "<p>{}</p>".format(lsp_detail)

    # NOTE: Some servers return "textEdit": null. We have to check if it's truthy.
    if item.get("textEdit") or item.get("additionalTextEdits") or item.get("command"):
        command = "lsp_complete_text_edit" if item.get("textEdit") else "lsp_complete_insert_text"
        args = {"item": item}  # type: Dict[str, Any]
        if item.get("command"):
            # If there is a "command", we'll have to run the command on the same session so store the name.
            args["session_name"] = session_name
        completion = sublime.CompletionItem.command_completion(
            trigger=st_trigger,
            command=command,
            args=args,
            annotation=st_annotation,
            kind=kind,
            details=st_details)
        if item.get("textEdit"):
            completion.flags = sublime.COMPLETION_FLAG_KEEP_PREFIX
    else:
        # A plain old completion suffices for insertText with no additionalTextEdits and no command.
        if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.PlainText:
            st_format = sublime.COMPLETION_FORMAT_TEXT
        else:
            st_format = sublime.COMPLETION_FORMAT_SNIPPET
        completion = sublime.CompletionItem(
            trigger=st_trigger,
            annotation=st_annotation,
            completion=item.get("insertText") or item["label"],
            completion_format=st_format,
            kind=kind,
            details=st_details)

    return completion


def code_lens_to_phantom(view: sublime.View, session_name: str, code_lens: CodeLens) -> sublime.Phantom:
    region = range_to_region(Range.from_lsp(code_lens["range"]), view)
    command = code_lens.get("command")
    assert isinstance(command, dict)
    command_name = command["command"]
    title = command["title"]
    if command_name:
        args = {
            "command_name": command_name,
            "command_args": command.get("arguments"),
            "session_name": session_name
        }
        href = sublime.command_url("lsp_execute", args)
        content = make_link(href, title)
    else:
        content = '<i>{}</i>'.format(title)
    fmt = '<small style="font-family: system">{}</small>'
    return sublime.Phantom(region, fmt.format(content), sublime.LAYOUT_BELOW)


def code_lenses_to_phantoms(
    view: sublime.View,
    session_name: str,
    code_lenses: List[CodeLens]
) -> List[sublime.Phantom]:
    return [code_lens_to_phantom(view, session_name, code_lens) for code_lens in code_lenses]
