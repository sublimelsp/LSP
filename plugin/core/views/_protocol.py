from __future__ import annotations

from ....protocol import CodeActionContext
from ....protocol import CodeActionKind
from ....protocol import CodeActionParams
from ....protocol import CodeActionTriggerKind
from ....protocol import Diagnostic
from ....protocol import DidChangeTextDocumentParams
from ....protocol import DidCloseTextDocumentParams
from ....protocol import DidOpenTextDocumentParams
from ....protocol import DidSaveTextDocumentParams
from ....protocol import DocumentColorParams
from ....protocol import DocumentFormattingParams
from ....protocol import DocumentRangeFormattingParams
from ....protocol import DocumentRangesFormattingParams
from ....protocol import DocumentUri
from ....protocol import FormattingOptions
from ....protocol import LanguageKind
from ....protocol import SelectionRangeParams
from ....protocol import TextDocumentContentChangeEvent
from ....protocol import TextDocumentIdentifier
from ....protocol import TextDocumentItem
from ....protocol import TextDocumentPositionParams
from ....protocol import TextDocumentSaveReason
from ....protocol import TextEdit
from ....protocol import VersionedTextDocumentIdentifier
from ....protocol import WillSaveTextDocumentParams
from ..protocol import Notification
from ..protocol import Request
from ._buffer import entire_content
from ._coordinates import offset_to_text_position
from ._coordinates import region_to_range
from ._uri import uri_from_view
from typing import cast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sublime


def text_document_identifier(view_or_uri: DocumentUri | sublime.View) -> TextDocumentIdentifier:
    uri = view_or_uri if isinstance(view_or_uri, DocumentUri) else uri_from_view(view_or_uri)
    return {"uri": uri}


def versioned_text_document_identifier(view: sublime.View, version: int) -> VersionedTextDocumentIdentifier:
    return {"uri": uri_from_view(view), "version": version}


def text_document_item(view: sublime.View, language_id: str) -> TextDocumentItem:
    language_id = cast('LanguageKind', language_id)
    return {
        "uri": uri_from_view(view),
        "languageId": language_id,
        "version": view.change_count(),
        "text": entire_content(view)
    }


def text_document_position_params(view: sublime.View, location: int) -> TextDocumentPositionParams:
    return {"textDocument": text_document_identifier(view), "position": offset_to_text_position(view, location)}


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
    view: sublime.View, version: int, changes: list[sublime.TextChange] | None = None
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
        content_changes.extend(render_text_change(change) for change in changes)
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


def did_open(view: sublime.View, language_id: str) -> Notification[DidOpenTextDocumentParams]:
    return Notification.didOpen(did_open_text_document_params(view, language_id))


def did_change(view: sublime.View, version: int,
               changes: list[sublime.TextChange] | None = None) -> Notification[DidChangeTextDocumentParams]:
    return Notification.didChange(did_change_text_document_params(view, version, changes))


def will_save(uri: DocumentUri, reason: TextDocumentSaveReason) -> Notification[WillSaveTextDocumentParams]:
    return Notification.willSave(will_save_text_document_params(uri, reason))


def will_save_wait_until(
    view: sublime.View, reason: TextDocumentSaveReason
) -> Request[WillSaveTextDocumentParams, list[TextEdit] | None]:
    return Request.willSaveWaitUntil(will_save_text_document_params(view, reason), view)


def did_save(
    view: sublime.View, include_text: bool, uri: DocumentUri | None = None
) -> Notification[DidSaveTextDocumentParams]:
    return Notification.didSave(did_save_text_document_params(view, include_text, uri))


def did_close(uri: DocumentUri) -> Notification[DidCloseTextDocumentParams]:
    return Notification.didClose(did_close_text_document_params(uri))


def formatting_options(settings: sublime.Settings) -> FormattingOptions:
    # Build 4085 allows "trim_trailing_white_space_on_save" to be a string so we have to account for that in a
    # backwards-compatible way.
    trim_trailing_white_space = settings.get("trim_trailing_white_space_on_save") not in {False, None, "none"}
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


def text_document_formatting(view: sublime.View) -> Request[DocumentFormattingParams, list[TextEdit] | None]:
    return Request.formatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings())
    }, view)


def text_document_range_formatting(
    view: sublime.View, region: sublime.Region
) -> Request[DocumentRangeFormattingParams, list[TextEdit] | None]:
    return Request.range_formatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "range": region_to_range(view, region)
    }, view)


def text_document_ranges_formatting(
    view: sublime.View
) -> Request[DocumentRangesFormattingParams, list[TextEdit] | None]:
    return Request.ranges_formatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "ranges": [region_to_range(view, region) for region in view.sel() if not region.empty()]
    }, view)


def selection_range_params(view: sublime.View) -> SelectionRangeParams:
    return {
        "textDocument": text_document_identifier(view),
        "positions": [offset_to_text_position(view, r.b) for r in view.sel()]
    }


def text_document_code_action_params(
    view: sublime.View,
    region: sublime.Region,
    diagnostics: list[Diagnostic],
    only_kinds: list[str | CodeActionKind] | None = None,
    manual: bool = False
) -> CodeActionParams:
    trigger_kind = CodeActionTriggerKind.Invoked.value if manual else CodeActionTriggerKind.Automatic.value
    context: CodeActionContext = {
        "diagnostics": diagnostics,
        "triggerKind": cast('CodeActionTriggerKind', trigger_kind),
    }
    if only_kinds:
        context["only"] = only_kinds
    return {
        "textDocument": text_document_identifier(view),
        "range": region_to_range(view, region),
        "context": context
    }


def document_color_params(view: sublime.View) -> DocumentColorParams:
    return {"textDocument": text_document_identifier(view)}
