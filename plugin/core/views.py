from __future__ import annotations
from .constants import CODE_ACTION_KINDS
from .constants import SUBLIME_KIND_SCOPES
from .constants import SublimeKind
from .css import css as lsp_css
from .protocol import CodeAction
from .protocol import CodeActionContext
from .protocol import CodeActionKind
from .protocol import CodeActionParams
from .protocol import CodeActionTriggerKind
from .protocol import Color
from .protocol import ColorInformation
from .protocol import Command
from .protocol import Diagnostic
from .protocol import DiagnosticRelatedInformation
from .protocol import DiagnosticSeverity
from .protocol import DidChangeTextDocumentParams
from .protocol import DidCloseTextDocumentParams
from .protocol import DidOpenTextDocumentParams
from .protocol import DidSaveTextDocumentParams
from .protocol import DocumentColorParams
from .protocol import DocumentUri
from .protocol import LanguageKind
from .protocol import Location
from .protocol import LocationLink
from .protocol import MarkedString
from .protocol import MarkupContent
from .protocol import Notification
from .protocol import Point
from .protocol import Position
from .protocol import Range
from .protocol import Request
from .protocol import SelectionRangeParams
from .protocol import TextDocumentContentChangeEvent
from .protocol import TextDocumentIdentifier
from .protocol import TextDocumentItem
from .protocol import TextDocumentPositionParams
from .protocol import TextDocumentSaveReason
from .protocol import VersionedTextDocumentIdentifier
from .protocol import WillSaveTextDocumentParams
from .settings import userprefs
from .types import ClientConfig
from .url import parse_uri
from .workspace import is_subpath_of
from typing import Any, Callable, Dict, Iterable, Tuple
from typing import cast
import html
import itertools
import linecache
import mdpopups
import os
import re
import sublime
import sublime_plugin
import tempfile

MarkdownLangMap = Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]

_baseflags = sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_EMPTY_AS_OVERWRITE | sublime.RegionFlags.NO_UNDO  # noqa: E501
_multilineflags = sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO

DIAGNOSTIC_SEVERITY: list[tuple[str, str, str, str, sublime.RegionFlags, sublime.RegionFlags]] = [
    # Kind       CSS class   Scope for color                        Icon resource                    add_regions flags for single-line diagnostic  multi-line diagnostic   # noqa: E501
    ("error",   "errors",   "region.redish markup.error.lsp",      "Packages/LSP/icons/error.png",   _baseflags | sublime.RegionFlags.DRAW_SQUIGGLY_UNDERLINE, _multilineflags),  # noqa: E501
    ("warning", "warnings", "region.yellowish markup.warning.lsp", "Packages/LSP/icons/warning.png", _baseflags | sublime.RegionFlags.DRAW_SQUIGGLY_UNDERLINE, _multilineflags),  # noqa: E501
    ("info",    "info",     "region.bluish markup.info.lsp",       "Packages/LSP/icons/info.png",    _baseflags | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE, _multilineflags),  # noqa: E501
    ("hint",    "hints",    "region.bluish markup.info.hint.lsp",  "",                               _baseflags | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE, _multilineflags),  # noqa: E501
]


class DiagnosticSeverityData:

    __slots__ = ('regions', 'regions_with_tag', 'annotations', 'scope', 'icon')

    def __init__(self, severity: int) -> None:
        self.regions: list[sublime.Region] = []
        self.regions_with_tag: dict[int, list[sublime.Region]] = {}
        self.annotations: list[str] = []
        _, _, self.scope, self.icon, _, _ = DIAGNOSTIC_SEVERITY[severity - 1]
        if userprefs().diagnostics_gutter_marker != "sign":
            self.icon = "" if severity == DiagnosticSeverity.Hint else userprefs().diagnostics_gutter_marker


class InvalidUriSchemeException(Exception):
    def __init__(self, uri: str) -> None:
        self.uri = uri

    def __str__(self) -> str:
        return f"invalid URI scheme: {self.uri}"


def get_line(window: sublime.Window, file_name: str, row: int, strip: bool = True) -> str:
    '''
    Get the line from the buffer if the view is open, else get line from linecache.
    row - is 0 based. If you want to get the first line, you should pass 0.
    '''
    view = window.find_open_file(file_name)
    if view:
        # get from buffer
        point = view.text_point(row, 0)
        line = view.substr(view.line(point))
    else:
        # get from linecache
        # linecache row is not 0 based, so we increment it by 1 to get the correct line.
        line = linecache.getline(file_name, row + 1)
    return line.strip() if strip else line


def get_storage_path() -> str:
    """
    The "Package Storage" is a way to store server data without influencing the behavior of Sublime Text's "catalog".
    Its path is '$DATA/Package Storage', where $DATA means:

    - on macOS: ~/Library/Application Support/Sublime Text
    - on Windows: %LocalAppData%/Sublime Text
    - on Linux: ~/.cache/sublime-text
    """
    return os.path.abspath(os.path.join(sublime.cache_path(), "..", "Package Storage"))


def extract_variables(window: sublime.Window) -> dict[str, str]:
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


def position_to_offset(position: Position, view: sublime.View) -> int:
    return point_to_offset(Point.from_lsp(position), view)


def get_symbol_kind_from_scope(scope_name: str) -> SublimeKind:
    best_kind = sublime.KIND_AMBIGUOUS
    best_kind_score = 0
    for kind, selector in SUBLIME_KIND_SCOPES.items():
        score = sublime.score_selector(scope_name, selector)
        if score > best_kind_score:
            best_kind = kind
            best_kind_score = score
    return best_kind


def range_to_region(range: Range, view: sublime.View) -> sublime.Region:
    return sublime.Region(position_to_offset(range['start'], view), position_to_offset(range['end'], view))


def region_to_range(view: sublime.View, region: sublime.Region) -> Range:
    return {
        'start': offset_to_point(view, region.begin()).to_lsp(),
        'end': offset_to_point(view, region.end()).to_lsp(),
    }


def to_encoded_filename(path: str, position: Position) -> str:
    # WARNING: Cannot possibly do UTF-16 conversion :) Oh well.
    return '{}:{}:{}'.format(path, position['line'] + 1, position['character'] + 1)


def get_uri_and_range_from_location(location: Location | LocationLink) -> tuple[DocumentUri, Range]:
    if "targetUri" in location:
        location = cast(LocationLink, location)
        uri = location["targetUri"]
        r = location["targetSelectionRange"]
    else:
        location = cast(Location, location)
        uri = location["uri"]
        r = location["range"]
    return uri, r


def get_uri_and_position_from_location(location: Location | LocationLink) -> tuple[DocumentUri, Position]:
    if "targetUri" in location:
        location = cast(LocationLink, location)
        uri = location["targetUri"]
        position = location["targetSelectionRange"]["start"]
    else:
        location = cast(Location, location)
        uri = location["uri"]
        position = location["range"]["start"]
    return uri, position


def location_to_encoded_filename(location: Location | LocationLink) -> str:
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
        super().__init__(f"View {view_id} has no URI")
        self.view_id = view_id


def uri_from_view(view: sublime.View) -> DocumentUri:
    uri = view.settings().get("lsp_uri")
    if isinstance(uri, DocumentUri):
        return uri
    raise MissingUriError(view.id())


def text_document_identifier(view_or_uri: DocumentUri | sublime.View) -> TextDocumentIdentifier:
    if isinstance(view_or_uri, DocumentUri):
        uri = view_or_uri
    else:
        uri = uri_from_view(view_or_uri)
    return {"uri": uri}


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


def text_document_item(view: sublime.View, language_id: str) -> TextDocumentItem:
    language_id = cast(LanguageKind, language_id)
    return {
        "uri": uri_from_view(view),
        "languageId": language_id,
        "version": view.change_count(),
        "text": entire_content(view)
    }


def versioned_text_document_identifier(view: sublime.View, version: int) -> VersionedTextDocumentIdentifier:
    return {"uri": uri_from_view(view), "version": version}


def text_document_position_params(view: sublime.View, location: int) -> TextDocumentPositionParams:
    return {"textDocument": text_document_identifier(view), "position": position(view, location)}


def did_open_text_document_params(view: sublime.View, language_id: str) -> DidOpenTextDocumentParams:
    return {"textDocument": text_document_item(view, language_id)}


def render_text_change(change: sublime.TextChange) -> TextDocumentContentChangeEvent:
    # Note: cannot use protocol.Range because these are "historic" points.
    return {
        "range": {
            "start": {"line": change.a.row, "character": change.a.col_utf16},
            "end": {"line": change.b.row, "character": change.b.col_utf16}},
        "rangeLength": change.len_utf16,
        "text": change.str
    }


def did_change_text_document_params(
    view: sublime.View, version: int, changes: Iterable[sublime.TextChange] | None = None
) -> DidChangeTextDocumentParams:
    content_changes: list[TextDocumentContentChangeEvent] = []
    result: DidChangeTextDocumentParams = {
        "textDocument": versioned_text_document_identifier(view, version),
        "contentChanges": content_changes
    }
    if changes is None:
        # TextDocumentSyncKind.Full
        content_changes.append({"text": entire_content(view)})
    else:
        # TextDocumentSyncKind.Incremental
        for change in changes:
            content_changes.append(render_text_change(change))
    return result


def will_save_text_document_params(
    view_or_uri: DocumentUri | sublime.View, reason: TextDocumentSaveReason
) -> WillSaveTextDocumentParams:
    return {"textDocument": text_document_identifier(view_or_uri), "reason": reason}


def did_save_text_document_params(
    view: sublime.View, include_text: bool, uri: DocumentUri | None = None
) -> DidSaveTextDocumentParams:
    result: DidSaveTextDocumentParams = {
        "textDocument": text_document_identifier(uri if uri is not None else view)
    }
    if include_text:
        result["text"] = entire_content(view)
    return result


def did_close_text_document_params(uri: DocumentUri) -> DidCloseTextDocumentParams:
    return {"textDocument": text_document_identifier(uri)}


def did_open(view: sublime.View, language_id: str) -> Notification:
    return Notification.didOpen(did_open_text_document_params(view, language_id))


def did_change(view: sublime.View, version: int,
               changes: Iterable[sublime.TextChange] | None = None) -> Notification:
    return Notification.didChange(did_change_text_document_params(view, version, changes))


def will_save(uri: DocumentUri, reason: TextDocumentSaveReason) -> Notification:
    return Notification.willSave(will_save_text_document_params(uri, reason))


def will_save_wait_until(view: sublime.View, reason: TextDocumentSaveReason) -> Request:
    return Request.willSaveWaitUntil(will_save_text_document_params(view, reason), view)


def did_save(view: sublime.View, include_text: bool, uri: DocumentUri | None = None) -> Notification:
    return Notification.didSave(did_save_text_document_params(view, include_text, uri))


def did_close(uri: DocumentUri) -> Notification:
    return Notification.didClose(did_close_text_document_params(uri))


def formatting_options(settings: sublime.Settings) -> dict[str, Any]:
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
        "range": region_to_range(view, region)
    }, view, progress=True)


def text_document_ranges_formatting(view: sublime.View) -> Request:
    return Request("textDocument/rangesFormatting", {
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "ranges": [region_to_range(view, region) for region in view.sel() if not region.empty()]
    }, view, progress=True)


def selection_range_params(view: sublime.View) -> SelectionRangeParams:
    return {
        "textDocument": text_document_identifier(view),
        "positions": [position(view, r.b) for r in view.sel()]
    }


def text_document_code_action_params(
    view: sublime.View,
    region: sublime.Region,
    diagnostics: list[Diagnostic],
    only_kinds: list[CodeActionKind] | None = None,
    manual: bool = False
) -> CodeActionParams:
    trigger_kind = CodeActionTriggerKind.Invoked.value if manual else CodeActionTriggerKind.Automatic.value
    context: CodeActionContext = {
        "diagnostics": diagnostics,
        "triggerKind": cast(CodeActionTriggerKind, trigger_kind),
    }
    if only_kinds:
        context["only"] = only_kinds
    return {
        "textDocument": text_document_identifier(view),
        "range": region_to_range(view, region),
        "context": context
    }


# Workaround for limited margin-collapsing capabilities of the minihtml.
LSP_POPUP_SPACER_HTML = '<div class="lsp_popup--spacer"></div>'


def show_lsp_popup(
    view: sublime.View,
    contents: str,
    *,
    location: int = -1,
    md: bool = False,
    flags: sublime.PopupFlags = sublime.PopupFlags.NONE,
    css: str | None = None,
    wrapper_class: str | None = None,
    body_id: str | None = None,
    on_navigate: Callable[..., None] | None = None,
    on_hide: Callable[..., None] | None = None
) -> None:
    css = css if css is not None else lsp_css().popups
    wrapper_class = wrapper_class if wrapper_class is not None else lsp_css().popups_classname
    contents += LSP_POPUP_SPACER_HTML
    body_wrapper = f'<body id="{body_id}">{{}}</body>' if body_id else '<body>{}</body>'
    mdpopups.show_popup(
        view,
        body_wrapper.format(contents),
        css=css,
        md=md,
        flags=flags,
        location=location,
        wrapper_class=wrapper_class,
        max_width=int(view.em_width() * float(userprefs().popup_max_characters_width)),
        max_height=int(view.line_height() * float(userprefs().popup_max_characters_height)),
        on_navigate=on_navigate,
        on_hide=on_hide)


def update_lsp_popup(
    view: sublime.View,
    contents: str,
    *,
    md: bool = False,
    css: str | None = None,
    wrapper_class: str | None = None,
    body_id: str | None = None
) -> None:
    css = css if css is not None else lsp_css().popups
    wrapper_class = wrapper_class if wrapper_class is not None else lsp_css().popups_classname
    contents += LSP_POPUP_SPACER_HTML
    body_wrapper = f'<body id="{body_id}">{{}}</body>' if body_id else '<body>{}</body>'
    mdpopups.update_popup(view, body_wrapper.format(contents), css=css, md=md, wrapper_class=wrapper_class)


FORMAT_STRING = 0x1
FORMAT_MARKED_STRING = 0x2
FORMAT_MARKUP_CONTENT = 0x4


def minihtml(
    view: sublime.View,
    content: MarkedString | MarkupContent | list[MarkedString],
    allowed_formats: int,
    language_id_map: MarkdownLangMap | None = None
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
                formatted.append(f"```{language}\n{value}\n```\n")
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
            result = f"```{language}\n{value}\n```\n"
    if is_plain_text:
        return f"<p>{text2html(result)}</p>" if result else ''
    else:
        frontmatter = {
            "allow_code_wrap": True,
            "markdown_extensions": [
                "markdown.extensions.admonition",
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
        if isinstance(language_id_map, dict):
            frontmatter["language_map"] = language_id_map
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
        return f"<a href='{url}'>{url}</a>"
    return len(match.group('multispace')) * '&nbsp;'


def text2html(content: str) -> str:
    return re.sub(REPLACEMENT_RE, _replace_match, content)


def make_link(href: str, text: Any, class_name: str | None = None, tooltip: str | None = None) -> str:
    link = f"<a href='{href}'"
    if class_name:
        link += f" class='{class_name}'"
    if tooltip:
        link += f" title='{html.escape(tooltip)}'"
    text = text2html(str(text)).replace(' ', '&nbsp;')
    link += f">{text}</a>"
    return link


def make_command_link(
    command: str,
    text: str,
    command_args: dict[str, Any] | None = None,
    class_name: str | None = None,
    tooltip: str | None = None,
    view_id: int | None = None
) -> str:
    if view_id is not None:
        cmd = "lsp_run_text_command_helper"
        args: dict[str, Any] | None = {"view_id": view_id, "command": command, "args": command_args}
    else:
        cmd = command
        args = command_args
    return make_link(sublime.command_url(cmd, args), text, class_name, tooltip)


class LspRunTextCommandHelperCommand(sublime_plugin.WindowCommand):
    def run(self, view_id: int, command: str, args: dict[str, Any] | None = None) -> None:
        view = sublime.View(view_id)
        if view.is_valid():
            view.run_command(command, args)


COLOR_BOX_HTML = """
<style>
    html {{
        padding: 0;
        background-color: transparent;
    }}
    a {{
        display: inline-block;
        height: 0.8rem;
        width: 0.8rem;
        margin-top: 0.1em;
        border: 1px solid color(var(--foreground) alpha(0.25));
        background-color: {color};
        text-decoration: none;
    }}
</style>
<body id='lsp-color-box'>
    <a href='{command}'>&nbsp;</a>
</body>"""


def color_to_hex(color: Color) -> str:
    red = round(color['red'] * 255)
    green = round(color['green'] * 255)
    blue = round(color['blue'] * 255)
    alpha_dec = color['alpha']
    if alpha_dec < 1:
        return f"#{red:02x}{green:02x}{blue:02x}{round(alpha_dec * 255):02x}"
    return f"#{red:02x}{green:02x}{blue:02x}"


def lsp_color_to_html(color_info: ColorInformation) -> str:
    command = sublime.command_url('lsp_color_presentation', {'color_information': color_info})
    return COLOR_BOX_HTML.format(command=command, color=color_to_hex(color_info['color']))


def lsp_color_to_phantom(view: sublime.View, color_info: ColorInformation) -> sublime.Phantom:
    region = range_to_region(color_info['range'], view)
    return sublime.Phantom(region, lsp_color_to_html(color_info), sublime.PhantomLayout.INLINE)


def document_color_params(view: sublime.View) -> DocumentColorParams:
    return {"textDocument": text_document_identifier(view)}


def format_severity(severity: int) -> str:
    if 1 <= severity <= len(DIAGNOSTIC_SEVERITY):
        return DIAGNOSTIC_SEVERITY[severity - 1][0]
    return "???"


def diagnostic_severity(diagnostic: Diagnostic) -> DiagnosticSeverity:
    return diagnostic.get("severity", DiagnosticSeverity.Error)


def format_diagnostics_for_annotation(
    diagnostics: list[Diagnostic], severity: DiagnosticSeverity, view: sublime.View
) -> tuple[list[str], str]:
    css_class = DIAGNOSTIC_SEVERITY[severity - 1][1]
    scope = DIAGNOSTIC_SEVERITY[severity - 1][2]
    color = view.style_for_scope(scope).get('foreground') or 'red'
    annotations = []
    for diagnostic in diagnostics:
        message = text2html(diagnostic.get('message') or '')
        source = diagnostic.get('source')
        line = f"[{text2html(source)}] {message}" if source else message
        content = '<body id="annotation" class="{}"><style>{}</style><div class="{}">{}</div></body>'.format(
            lsp_css().annotations_classname, lsp_css().annotations, css_class, line)
        annotations.append(content)
    return (annotations, color)


def format_diagnostic_for_panel(diagnostic: Diagnostic) -> tuple[str, int | None, str | None, str | None]:
    """
    Turn an LSP diagnostic into a string suitable for an output panel.

    :param      diagnostic:  The diagnostic
    :returns:   Tuple of (content, optional offset, optional code, optional href)
                When the last three elements are optional, don't show an inline phantom
                When the last three elements are not optional, show an inline phantom
                using the information given.
    """
    formatted, code, href = diagnostic_source_and_code(diagnostic)
    lines = diagnostic["message"].splitlines() or [""]
    result = " {:>4}:{:<4}{:<8}{}".format(
        diagnostic["range"]["start"]["line"] + 1,
        diagnostic["range"]["start"]["character"] + 1,
        format_severity(diagnostic_severity(diagnostic)),
        lines[0]
    )
    if formatted != "" or code is not None:
        # \u200B is the zero-width space
        result += f" \u200B{formatted}"
    offset = len(result) if href else None
    for line in itertools.islice(lines, 1, None):
        result += "\n" + 18 * " " + line
    return result, offset, code, href


def format_diagnostic_source_and_code(diagnostic: Diagnostic) -> str:
    formatted, code, href = diagnostic_source_and_code(diagnostic)
    if href is None or code is None:
        return formatted
    return formatted + f"({code})"


def diagnostic_source_and_code(diagnostic: Diagnostic) -> tuple[str, str | None, str | None]:
    formatted = diagnostic.get("source", "")
    href = None
    code = diagnostic.get("code")
    if code is not None:
        code = str(code)
        code_description = diagnostic.get("codeDescription")
        if code_description:
            href = code_description["href"]
        else:
            formatted += f"({code})"
    return formatted, code, href


def location_to_human_readable(
    config: ClientConfig,
    base_dir: str | None,
    location: Location | LocationLink
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
    elif scheme == "res":
        fmt = "{}:{}"
        pathname = uri
    else:
        # https://tools.ietf.org/html/rfc5147
        fmt = "{}#line={}"
        pathname = uri
    return fmt.format(pathname, position["line"] + 1)


def location_to_href(config: ClientConfig, location: Location | LocationLink) -> str:
    """
    Encode an LSP Location (or LocationLink) into a string suitable as a hyperlink in minihtml
    """
    uri, position = get_uri_and_position_from_location(location)
    return "location:{}@{}#{},{}".format(config.name, uri, position["line"], position["character"])


def unpack_href_location(href: str) -> tuple[str, str, int, int]:
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
    base_dir: str | None = None
) -> str:
    location = info["location"]
    return '<a href="{}">{}</a>: {}'.format(
        location_to_href(config, location),
        text2html(location_to_human_readable(config, base_dir, location)),
        text2html(info["message"])
    )


def _html_element(name: str, text: str, class_name: str | None = None, escape: bool = True) -> str:
    return '<{0}{2}>{1}</{0}>'.format(
        name,
        text2html(text) if escape else text,
        f' class="{text2html(class_name)}"' if class_name else ''
    )


def format_diagnostic_for_html(config: ClientConfig, diagnostic: Diagnostic, base_dir: str | None = None) -> str:
    html = _html_element('span', diagnostic["message"])
    code = diagnostic.get("code")
    source = diagnostic.get("source")
    if source or code is not None:
        meta_info = ""
        if source:
            meta_info += text2html(source)
        if code is not None:
            code_description = diagnostic.get("codeDescription")
            meta_info += "({})".format(
                make_link(code_description["href"], str(code)) if code_description else text2html(str(code)))
        html += " " + _html_element("span", meta_info, class_name="color-muted", escape=False)
    related_infos = diagnostic.get("relatedInformation")
    if related_infos:
        info = "<br>".join(_format_diagnostic_related_info(config, info, base_dir) for info in related_infos)
        html += '<br>' + _html_element("pre", info, class_name="related_info", escape=False)
    severity_class = DIAGNOSTIC_SEVERITY[diagnostic_severity(diagnostic) - 1][1]
    return _html_element("pre", html, class_name=severity_class, escape=False)


def format_code_actions_for_quick_panel(
    session_actions: Iterable[tuple[str, CodeAction | Command]]
) -> tuple[list[sublime.QuickPanelItem], int]:
    items: list[sublime.QuickPanelItem] = []
    selected_index = -1
    for idx, (config_name, code_action) in enumerate(session_actions):
        lsp_kind = code_action.get("kind", "")
        first_kind_component = cast(CodeActionKind, str(lsp_kind).split(".")[0])
        kind = CODE_ACTION_KINDS.get(first_kind_component, sublime.KIND_AMBIGUOUS)
        items.append(sublime.QuickPanelItem(code_action["title"], annotation=config_name, kind=kind))
        if code_action.get('isPreferred', False):
            selected_index = idx
    return items, selected_index
