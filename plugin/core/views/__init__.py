from __future__ import annotations

from ..constants import ST_CACHE_PATH
from ..constants import ST_STORAGE_PATH
from ..constants import SUBLIME_KIND_SCOPES
from ..constants import SublimeKind
from ._buffer import entire_content
from ._buffer import entire_content_range
from ._buffer import entire_content_region
from ._buffer import first_selection_region
from ._buffer import get_line
from ._buffer import has_single_nonempty_selection
from ._code_actions import format_code_actions_for_quick_panel
from ._code_actions import kind_contains_other_kind
from ._color import COLOR_BOX_HTML
from ._color import color_to_hex
from ._color import lsp_color_to_html
from ._color import lsp_color_to_phantom
from ._coordinates import offset_to_point
from ._coordinates import offset_to_text_position
from ._coordinates import point_to_offset
from ._coordinates import position
from ._coordinates import position_to_offset
from ._coordinates import range_to_region
from ._coordinates import region_to_range
from ._diagnostics import diagnostic_icon
from ._diagnostics import diagnostic_severity
from ._diagnostics import diagnostic_source_and_code
from ._diagnostics import DIAGNOSTIC_STYLES
from ._diagnostics import DiagnosticSeverityData
from ._diagnostics import DiagnosticStyle
from ._diagnostics import format_diagnostic_for_html
from ._diagnostics import format_diagnostic_for_panel
from ._diagnostics import format_diagnostics_for_annotation
from ._diagnostics import format_diagnostics_for_html
from ._html import FORMAT_MARKED_STRING
from ._html import FORMAT_MARKUP_CONTENT
from ._html import FORMAT_STRING
from ._html import html_wrapper
from ._html import lightbulb_html
from ._html import LspRunTextCommandHelperCommand
from ._html import make_command_link
from ._html import make_link
from ._html import minihtml
from ._html import PATTERNS
from ._html import REPLACEMENT_MAP
from ._html import REPLACEMENT_RE
from ._html import show_lsp_popup
from ._html import text2html
from ._html import update_lsp_popup
from ._protocol import did_change
from ._protocol import did_change_text_document_params
from ._protocol import did_close
from ._protocol import did_close_text_document_params
from ._protocol import did_open
from ._protocol import did_open_text_document_params
from ._protocol import did_save
from ._protocol import did_save_text_document_params
from ._protocol import document_color_params
from ._protocol import formatting_options
from ._protocol import render_text_change
from ._protocol import selection_range_params
from ._protocol import text_document_code_action_params
from ._protocol import text_document_formatting
from ._protocol import text_document_identifier
from ._protocol import text_document_item
from ._protocol import text_document_position_params
from ._protocol import text_document_range_formatting
from ._protocol import text_document_ranges_formatting
from ._protocol import versioned_text_document_identifier
from ._protocol import will_save
from ._protocol import will_save_text_document_params
from ._protocol import will_save_wait_until
from ._uri import get_uri_and_position_from_location
from ._uri import get_uri_and_range_from_location
from ._uri import InvalidUriSchemeError
from ._uri import is_location_href
from ._uri import location_to_encoded_filename
from ._uri import location_to_href
from ._uri import location_to_human_readable
from ._uri import MissingUriError
from ._uri import parse_uri
from ._uri import to_encoded_filename
from ._uri import unpack_href_location
from ._uri import uri_from_view
from os.path import expanduser
from typing import TYPE_CHECKING
import sublime
import tempfile

if TYPE_CHECKING:
    from ....protocol import DocumentHighlightKind


__all__ = [
    "COLOR_BOX_HTML",
    "DIAGNOSTIC_STYLES",
    "FORMAT_MARKED_STRING",
    "FORMAT_MARKUP_CONTENT",
    "FORMAT_STRING",
    "PATTERNS",
    "REPLACEMENT_MAP",
    "REPLACEMENT_RE",
    "DiagnosticSeverityData",
    "DiagnosticStyle",
    "InvalidUriSchemeError",
    "LspRunTextCommandHelperCommand",
    "MissingUriError",
    "color_to_hex",
    "diagnostic_icon",
    "diagnostic_severity",
    "diagnostic_source_and_code",
    "did_change",
    "did_change_text_document_params",
    "did_close",
    "did_close_text_document_params",
    "did_open",
    "did_open_text_document_params",
    "did_save",
    "did_save_text_document_params",
    "document_color_params",
    "entire_content",
    "entire_content_range",
    "entire_content_region",
    "first_selection_region",
    "format_code_actions_for_quick_panel",
    "format_diagnostic_for_html",
    "format_diagnostic_for_panel",
    "format_diagnostics_for_annotation",
    "format_diagnostics_for_html",
    "formatting_options",
    "get_line",
    "get_uri_and_position_from_location",
    "get_uri_and_range_from_location",
    "has_single_nonempty_selection",
    "html_wrapper",
    "is_location_href",
    "kind_contains_other_kind",
    "lightbulb_html",
    "location_to_encoded_filename",
    "location_to_href",
    "location_to_human_readable",
    "lsp_color_to_html",
    "lsp_color_to_phantom",
    "make_command_link",
    "make_link",
    "minihtml",
    "offset_to_point",
    "offset_to_text_position",
    "parse_uri",
    "point_to_offset",
    "position",
    "position_to_offset",
    "range_to_region",
    "region_to_range",
    "render_text_change",
    "selection_range_params",
    "show_lsp_popup",
    "text2html",
    "text_document_code_action_params",
    "text_document_formatting",
    "text_document_identifier",
    "text_document_item",
    "text_document_position_params",
    "text_document_range_formatting",
    "text_document_ranges_formatting",
    "to_encoded_filename",
    "unpack_href_location",
    "update_lsp_popup",
    "uri_from_view",
    "versioned_text_document_identifier",
    "will_save",
    "will_save_text_document_params",
    "will_save_wait_until",
]


def extract_variables(window: sublime.Window) -> dict[str, str]:
    variables = window.extract_variables()
    variables["storage_path"] = ST_STORAGE_PATH
    variables["cache_path"] = ST_CACHE_PATH
    variables["temp_dir"] = tempfile.gettempdir()
    variables["home"] = expanduser('~')
    return variables


def get_symbol_kind_from_scope(scope_name: str) -> SublimeKind:
    best_kind = sublime.KIND_AMBIGUOUS
    best_kind_score = 0
    for kind, selector in SUBLIME_KIND_SCOPES.items():
        score = sublime.score_selector(scope_name, selector)
        if score > best_kind_score:
            best_kind = kind
            best_kind_score = score
    return best_kind


def document_highlight_key(kind: DocumentHighlightKind, *, multiline: bool) -> str:
    return "lsp_highlight_{}{}".format(kind, "m" if multiline else "s")
