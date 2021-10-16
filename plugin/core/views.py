from .css import css as lsp_css
from .protocol import CompletionItem
from .protocol import CompletionItemTag
from .protocol import Diagnostic
from .protocol import DiagnosticRelatedInformation
from .protocol import DiagnosticSeverity
from .protocol import DocumentUri
from .protocol import Location
from .protocol import LocationLink
from .protocol import MarkedString
from .protocol import MarkupContent
from .protocol import Notification
from .protocol import Point
from .protocol import Position
from .protocol import Range
from .protocol import RangeLsp
from .protocol import Request
from .protocol import TextDocumentIdentifier
from .protocol import TextDocumentPositionParams
from .settings import userprefs
from .types import ClientConfig
from .typing import Callable, Optional, Dict, Any, Iterable, List, Union, Tuple, Sequence, cast
from .url import parse_uri
from .workspace import is_subpath_of
import html
import itertools
import linecache
import mdpopups
import os
import re
import sublime
import sublime_plugin
import tempfile

_baseflags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_EMPTY_AS_OVERWRITE

DIAGNOSTIC_SEVERITY = [
    # Kind       CSS class   Scope for color                        Icon resource                    add_regions flags for single-line diagnostic  multi-line diagnostic   # noqa: E501
    ("error",   "errors",   "region.redish markup.error.lsp",      "Packages/LSP/icons/error.png",   _baseflags | sublime.DRAW_SQUIGGLY_UNDERLINE, sublime.DRAW_NO_FILL),  # noqa: E501
    ("warning", "warnings", "region.yellowish markup.warning.lsp", "Packages/LSP/icons/warning.png", _baseflags | sublime.DRAW_SQUIGGLY_UNDERLINE, sublime.DRAW_NO_FILL),  # noqa: E501
    ("info",    "info",     "region.bluish markup.info.lsp",       "Packages/LSP/icons/info.png",    _baseflags | sublime.DRAW_STIPPLED_UNDERLINE, sublime.DRAW_NO_FILL),  # noqa: E501
    ("hint",    "hints",    "region.bluish markup.info.hint.lsp",  "Packages/LSP/icons/info.png",    _baseflags | sublime.DRAW_STIPPLED_UNDERLINE, sublime.DRAW_NO_FILL),  # noqa: E501
]  # type: List[Tuple[str, str, str, str, int, int]]

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


class InvalidUriSchemeException(Exception):
    def __init__(self, uri: str) -> None:
        self.uri = uri

    def __str__(self) -> str:
        return "invalid URI scheme: {}".format(self.uri)


def get_line(window: sublime.Window, file_name: str, row: int) -> str:
    '''
    Get the line from the buffer if the view is open, else get line from linecache.
    row - is 0 based. If you want to get the first line, you should pass 0.
    '''
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


def position(view: sublime.View, offset: int) -> Position:
    return offset_to_point(view, offset).to_lsp()


def range_to_region(range: Range, view: sublime.View) -> sublime.Region:
    return sublime.Region(point_to_offset(range.start, view), point_to_offset(range.end, view))


def region_to_range(view: sublime.View, region: sublime.Region) -> Range:
    return Range(
        offset_to_point(view, region.begin()),
        offset_to_point(view, region.end())
    )


def to_encoded_filename(path: str, position: Position) -> str:
    # WARNING: Cannot possibly do UTF-16 conversion :) Oh well.
    return '{}:{}:{}'.format(path, position['line'] + 1, position['character'] + 1)


def get_uri_and_range_from_location(location: Union[Location, LocationLink]) -> Tuple[DocumentUri, RangeLsp]:
    if "targetUri" in location:
        location = cast(LocationLink, location)
        uri = location["targetUri"]
        r = location["targetSelectionRange"]
    else:
        location = cast(Location, location)
        uri = location["uri"]
        r = location["range"]
    return uri, r


def get_uri_and_position_from_location(location: Union[Location, LocationLink]) -> Tuple[DocumentUri, Position]:
    if "targetUri" in location:
        location = cast(LocationLink, location)
        uri = location["targetUri"]
        position = location["targetSelectionRange"]["start"]
    else:
        location = cast(Location, location)
        uri = location["uri"]
        position = location["range"]["start"]
    return uri, position


def location_to_encoded_filename(location: Union[Location, LocationLink]) -> str:
    """
    DEPRECATED
    """
    uri, position = get_uri_and_position_from_location(location)
    scheme, parsed = parse_uri(uri)
    if scheme == "file":
        return to_encoded_filename(parsed, position)
    raise InvalidUriSchemeException(uri)


class MissingUriError(Exception):

    def __init__(self, view_id: int) -> None:
        super().__init__("View {} has no URI".format(view_id))
        self.view_id = view_id


def uri_from_view(view: sublime.View) -> DocumentUri:
    uri = view.settings().get("lsp_uri")
    if isinstance(uri, DocumentUri):
        return uri
    raise MissingUriError(view.id())


def text_document_identifier(view_or_uri: Union[DocumentUri, sublime.View]) -> TextDocumentIdentifier:
    if isinstance(view_or_uri, DocumentUri):
        uri = view_or_uri
    else:
        uri = uri_from_view(view_or_uri)
    return {"uri": uri}


def first_selection_region(view: sublime.View) -> Optional[sublime.Region]:
    try:
        return view.sel()[0]
    except IndexError:
        return None


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


def text_document_position_params(view: sublime.View, location: int) -> TextDocumentPositionParams:
    return {"textDocument": text_document_identifier(view), "position": position(view, location)}


def did_open_text_document_params(view: sublime.View, language_id: str) -> Dict[str, Any]:
    return {"textDocument": text_document_item(view, language_id)}


def render_text_change(change: sublime.TextChange) -> Dict[str, Any]:
    # Note: cannot use protocol.Range because these are "historic" points.
    return {
        "range": {
            "start": {"line": change.a.row, "character": change.a.col_utf16},
            "end": {"line": change.b.row, "character": change.b.col_utf16}},
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


def will_save_text_document_params(view_or_uri: Union[DocumentUri, sublime.View], reason: int) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view_or_uri), "reason": reason}


def did_save_text_document_params(
    view: sublime.View, include_text: bool, uri: Optional[DocumentUri] = None
) -> Dict[str, Any]:
    identifier = text_document_identifier(uri if uri is not None else view)
    result = {"textDocument": identifier}  # type: Dict[str, Any]
    if include_text:
        result["text"] = entire_content(view)
    return result


def did_close_text_document_params(uri: DocumentUri) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(uri)}


def did_open(view: sublime.View, language_id: str) -> Notification:
    return Notification.didOpen(did_open_text_document_params(view, language_id))


def did_change(view: sublime.View, version: int,
               changes: Optional[Iterable[sublime.TextChange]] = None) -> Notification:
    return Notification.didChange(did_change_text_document_params(view, version, changes))


def will_save(uri: DocumentUri, reason: int) -> Notification:
    return Notification.willSave(will_save_text_document_params(uri, reason))


def will_save_wait_until(view: sublime.View, reason: int) -> Request:
    return Request.willSaveWaitUntil(will_save_text_document_params(view, reason), view)


def did_save(view: sublime.View, include_text: bool, uri: Optional[DocumentUri] = None) -> Notification:
    return Notification.didSave(did_save_text_document_params(view, include_text, uri))


def did_close(uri: DocumentUri) -> Notification:
    return Notification.didClose(did_close_text_document_params(uri))


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
    return Request("textDocument/formatting", {
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings())
    }, view, progress=True)


def text_document_range_formatting(view: sublime.View, region: sublime.Region) -> Request:
    return Request("textDocument/rangeFormatting", {
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "range": region_to_range(view, region).to_lsp()
    }, view, progress=True)


def selection_range_params(view: sublime.View) -> Dict[str, Any]:
    return {
        "textDocument": text_document_identifier(view),
        "positions": [position(view, r.b) for r in view.sel()]
    }


def text_document_code_action_params(
    view: sublime.View,
    region: sublime.Region,
    diagnostics: Sequence[Diagnostic],
    on_save_actions: Optional[Sequence[str]] = None
) -> Dict[str, Any]:
    context = {
        "diagnostics": diagnostics
    }  # type: Dict[str, Any]
    if on_save_actions:
        context['only'] = on_save_actions
    return {
        "textDocument": text_document_identifier(view),
        "range": region_to_range(view, region).to_lsp(),
        "context": context
    }


# Workaround for a limited margin-collapsing capabilities of the minihtml.
LSP_POPUP_SPACER_HTML = '<div class="lsp_popup--spacer"></div>'


def show_lsp_popup(view: sublime.View, contents: str, location: int = -1, md: bool = False, flags: int = 0,
                   css: Optional[str] = None, wrapper_class: Optional[str] = None,
                   on_navigate: Optional[Callable] = None, on_hide: Optional[Callable] = None) -> None:
    css = css if css is not None else lsp_css().popups
    wrapper_class = wrapper_class if wrapper_class is not None else lsp_css().popups_classname
    contents += LSP_POPUP_SPACER_HTML
    mdpopups.show_popup(
        view,
        contents,
        css=css,
        md=md,
        flags=flags,
        location=location,
        wrapper_class=wrapper_class,
        max_width=int(view.em_width() * float(userprefs().popup_max_characters_width)),
        max_height=int(view.line_height() * float(userprefs().popup_max_characters_height)),
        on_navigate=on_navigate)


def update_lsp_popup(view: sublime.View, contents: str, md: bool = False, css: Optional[str] = None,
                     wrapper_class: Optional[str] = None) -> None:
    css = css if css is not None else lsp_css().popups
    wrapper_class = wrapper_class if wrapper_class is not None else lsp_css().popups_classname
    contents += LSP_POPUP_SPACER_HTML
    mdpopups.update_popup(view, contents, css=css, md=md, wrapper_class=wrapper_class)


FORMAT_STRING = 0x1
FORMAT_MARKED_STRING = 0x2
FORMAT_MARKUP_CONTENT = 0x4


def minihtml(
    view: sublime.View,
    content: Union[MarkedString, MarkupContent, List[MarkedString]],
    allowed_formats: int
) -> str:
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
                        "hardbreak": True,
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


def make_link(href: str, text: Any, class_name: Optional[str] = None) -> str:
    if isinstance(text, str):
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


def diagnostic_severity(diagnostic: Diagnostic) -> int:
    return diagnostic.get("severity", DiagnosticSeverity.Error)


def diagnostic_source(diagnostic: Diagnostic) -> str:
    return diagnostic.get("source", "unknown-source")


def format_diagnostic_for_panel(diagnostic: Diagnostic) -> Tuple[str, Optional[int], Optional[str], Optional[str]]:
    """
    Turn an LSP diagnostic into a string suitable for an output panel.

    :param      diagnostic:  The diagnostic
    :returns:   Tuple of (content, optional offset, optional code, optional href)
                When the last three elements are optional, don't show an inline phantom
                When the last three elemenst are not optional, show an inline phantom
                using the information given.
    """
    formatted = [diagnostic_source(diagnostic)]
    offset = None
    href = None
    code = diagnostic.get("code")
    if code is not None:
        code = str(code)
        formatted.append(":")
        code_description = diagnostic.get("codeDescription")
        if code_description:
            href = code_description["href"]
        else:
            formatted.append(code)
    lines = diagnostic["message"].splitlines() or [""]
    # \u200B is the zero-width space
    result = "{:>5}:{:<4}{:<8}{} \u200B{}".format(
        diagnostic["range"]["start"]["line"] + 1,
        diagnostic["range"]["start"]["character"] + 1,
        format_severity(diagnostic_severity(diagnostic)),
        lines[0],
        "".join(formatted)
    )
    if href:
        offset = len(result)
    for line in itertools.islice(lines, 1, None):
        result += "\n" + 17 * " " + line
    return result, offset, code, href


def location_to_human_readable(
    config: ClientConfig,
    base_dir: Optional[str],
    location: Union[Location, LocationLink]
) -> str:
    """
    Format an LSP Location (or LocationLink) into a string suitable for a human to read
    """
    uri, position = get_uri_and_position_from_location(location)
    scheme, _ = parse_uri(uri)
    if scheme == "file":
        fmt = "{}:{}"
        pathname = config.map_server_uri_to_client_path(uri)
        if base_dir and is_subpath_of(pathname, base_dir):
            pathname = pathname[len(os.path.commonprefix((pathname, base_dir))) + 1:]
    else:
        # https://tools.ietf.org/html/rfc5147
        fmt = "{}#line={}"
        pathname = uri
    return fmt.format(pathname, position["line"] + 1)


def location_to_href(config: ClientConfig, location: Union[Location, LocationLink]) -> str:
    """
    Encode an LSP Location (or LocationLink) into a string suitable as a hyperlink in minihtml
    """
    uri, position = get_uri_and_position_from_location(location)
    return "location:{}@{}#{},{}".format(config.name, uri, position["line"], position["character"])


def unpack_href_location(href: str) -> Tuple[str, str, int, int]:
    """
    Return the session name, URI, row, and col_utf16 from an encoded href.
    """
    session_name, uri_with_fragment = href[len("location:"):].split("@")
    uri, fragment = uri_with_fragment.split("#")
    row, col_utf16 = map(int, fragment.split(","))
    return session_name, uri, row, col_utf16


def is_location_href(href: str) -> bool:
    """
    Check whether this href is an encoded location.
    """
    return href.startswith("location:")


def _format_diagnostic_related_info(
    config: ClientConfig,
    info: DiagnosticRelatedInformation,
    base_dir: Optional[str] = None
) -> str:
    location = info["location"]
    return '<a href="{}">{}</a>: {}'.format(
        location_to_href(config, location),
        location_to_human_readable(config, base_dir, location),
        info["message"]
    )


def _with_color(text: Any, hexcolor: str) -> str:
    return '<span style="color: {};">{}</span>'.format(hexcolor, text)


def _with_scope_color(view: sublime.View, text: Any, scope: str) -> str:
    return _with_color(text, view.style_for_scope(scope)["foreground"])


def format_diagnostic_for_html(
    view: sublime.View,
    config: ClientConfig,
    diagnostic: Diagnostic,
    base_dir: Optional[str] = None
) -> str:
    formatted = [
        '<pre class="',
        DIAGNOSTIC_SEVERITY[diagnostic_severity(diagnostic) - 1][1],
        '">',
        text2html(diagnostic["message"])
    ]
    code_description = diagnostic.get("codeDescription")
    if code_description:
        code = make_link(code_description["href"], diagnostic["code"])  # type: Optional[str]
    elif "code" in diagnostic:
        code = _with_color(diagnostic["code"], "color(var(--foreground) alpha(0.6))")
    else:
        code = None
    source = diagnostic_source(diagnostic)
    formatted.extend((" ", _with_color(source, "color(var(--foreground) alpha(0.6))")))
    if code:
        formatted.extend((_with_scope_color(view, ":", "punctuation.separator.lsp"), code))
    related_infos = diagnostic.get("relatedInformation")
    if related_infos:
        formatted.append('<pre class="related_info">')
        formatted.append("<br>".join(_format_diagnostic_related_info(config, info, base_dir)
                                     for info in related_infos))
        formatted.append("</pre>")
    formatted.append("</pre>")
    return "".join(formatted)


def _is_completion_item_deprecated(item: CompletionItem) -> bool:
    if item.get("deprecated", False):
        return True
    tags = item.get("tags")
    if isinstance(tags, list):
        return CompletionItemTag.Deprecated in tags
    return False


def _wrap_in_tags(tag: str, item: str) -> str:
    return "<{0}>{1}</{0}>".format(tag, html.escape(item))


def format_completion(
    item: CompletionItem, index: int, can_resolve_completion_items: bool, session_name: str
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
    lsp_label_details = item.get("labelDetails")
    lsp_filter_text = item.get("filterText")
    st_annotation = (item.get("detail") or "").replace('\n', ' ')

    st_details = ""
    if can_resolve_completion_items or item.get("documentation"):
        st_details += make_command_link("lsp_resolve_docs", "More", {"index": index, "session_name": session_name})
    if lsp_label_details:
        if st_details:
            st_details += " | "
        lsp_label_detail = lsp_label_details.get("detail")
        lsp_label_description = lsp_label_details.get("description")
        st_details += "<p>"
        # `label` should be rendered most prominent.
        st_details += _wrap_in_tags("b", lsp_label)
        if isinstance(lsp_label_detail, str):
            # `detail` should be rendered less prominent than `label`.
            # The string is appended directly after `label`, with no additional white space applied.
            st_details += html.escape(lsp_label_detail)
        if isinstance(lsp_label_description, str):
            # `description` should be rendered less prominent than `detail`.
            # Additional separation is added.
            st_details += " - {}".format(_wrap_in_tags("i", lsp_label_description))
        st_details += "</p>"
    elif lsp_filter_text and lsp_filter_text != lsp_label:
        if st_details:
            st_details += " | "
        st_details += _wrap_in_tags("p", lsp_label)

    completion = sublime.CompletionItem.command_completion(
        trigger=lsp_filter_text or lsp_label,
        command="lsp_select_completion_item",
        args={"item": item, "session_name": session_name},
        annotation=st_annotation,
        kind=kind,
        details=st_details)
    if item.get("textEdit"):
        completion.flags = sublime.COMPLETION_FLAG_KEEP_PREFIX
    return completion
