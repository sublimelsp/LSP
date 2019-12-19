import sublime
from .core.logging import debug, printf
from .core.protocol import Request
from .core.configurations import is_supported_syntax
from .core.settings import client_configs
from .core.edit import parse_text_edit
from .core.registry import (
    LspTextCommand, LSPViewEventListener, session_for_view, client_from_session, sessions_for_view
)
from .core.url import filename_to_uri
from .core.sessions import Session
from .core.views import region_to_range

try:
    from typing import Dict, Any, List, Optional, Callable
    assert Dict and Any and List and Optional and Callable
except ImportError:
    pass


def options_for_view(view: sublime.View) -> 'Dict[str, Any]':
    return {"tabSize": view.settings().get("tab_size", 4), "insertSpaces": True}


def apply_response_to_view(response: 'Optional[List[dict]]', view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


def wants_will_save_wait_until(session: Session) -> bool:
    sync_options = session.capabilities.get("textDocumentSync")
    if isinstance(sync_options, dict):
        if sync_options.get('willSaveWaitUntil'):
            return True
    return False


def strandify(f: 'Callable[[Any], None]') -> 'Callable[[Any], None]':
    return lambda p: sublime.set_timeout_async(lambda: f(p), 0)


IDLE = 0
SAVING_NON_FORMATTED = 1
SAVED_NON_FORMATTED = 2
SAVING_FORMATTED = 3

INVALID_STATE = "invalid state :("


class FormatOnSaveListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._set_status(IDLE)
        self.received = False
        self.changes = None  # type: Optional[list]

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        return False

    def on_pre_save_async(self) -> None:
        if self.status == IDLE:
            # debug("on_pre_save", "IDLE")
            self.start_format_on_save()
        elif self.status == SAVING_NON_FORMATTED:
            self._handle_error(INVALID_STATE)
        elif self.status == SAVED_NON_FORMATTED:
            self._handle_error(INVALID_STATE)
        elif self.status == SAVING_FORMATTED:
            # debug("on_pre_save", "SAVING_FORMATTED")
            self._set_status(IDLE)

    def on_post_save_async(self) -> None:
        if self.status == IDLE:
            # debug("on_post_save", "IDLE")
            return
        elif self.status == SAVING_NON_FORMATTED:
            # debug("on_post_save", "SAVING_NON_FORMATTED")
            if self.received:
                if self.changes:
                    apply_response_to_view(self.changes, self.view)
                    self._view_maybe_dirty = True
                    self.changes = None
                    self._set_status(SAVING_FORMATTED)
                    self.received = False
                    self.view.run_command("save")
                else:
                    self.changes = None
                    self._set_status(IDLE)
                    self.received = False
            else:
                self._set_status(SAVED_NON_FORMATTED)
        elif self.status == SAVED_NON_FORMATTED:
            self._handle_error(INVALID_STATE)
        elif self.status == SAVING_FORMATTED:
            self._handle_error(INVALID_STATE)

    def start_format_on_save(self) -> None:
        file_path = self.view.file_name()
        if not file_path:
            return

        self._view_maybe_dirty = True
        found_provider = False
        num_sessions = 0
        for session in sessions_for_view(self.view):
            if wants_will_save_wait_until(session) and not found_provider:
                self._purge_changes_if_needed()
                self._will_save_wait_until(file_path, session)
                found_provider = True
            num_sessions += 1

        if found_provider and num_sessions > 1:
            printf("WARNING: Can only run formatting for the first language server active")

        if self.view.settings().get("lsp_format_on_save"):
            self._purge_changes_if_needed()
            self._format_on_save(file_path)

    def _purge_changes_if_needed(self) -> None:
        if self._view_maybe_dirty:
            self.manager.documents.purge_changes(self.view)
            self._view_maybe_dirty = False

    def _will_save_wait_until(self, file_path: str, session: Session) -> None:
        client = client_from_session(session)
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(file_path)
                },
                "reason": 1  # TextDocumentSaveReason.Manual
            }
            request = Request.willSaveWaitUntil(params)
            self._set_status(SAVING_NON_FORMATTED)

            client.send_request(request, strandify(self._handle_response), strandify(self._handle_error))

    def _format_on_save(self, file_path: str) -> None:
        client = client_from_session(session_for_view(self.view, 'documentFormattingProvider'))
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(file_path)
                },
                "options": options_for_view(self.view)
            }
            request = Request.formatting(params)
            self._set_status(SAVING_NON_FORMATTED)
            client.send_request(request, strandify(self._handle_response), strandify(self._handle_error))

    def _set_status(self, status: int) -> None:
        if status == IDLE:
            self.view.erase_status("lsp_save_status")
        else:
            self.view.set_status("lsp_save_status", "formatting...")
        self.status = status

    def _handle_error(self, error: 'Any') -> None:
        self._set_status(IDLE)
        self.changes = None
        self.received = False
        debug(error)

    def _handle_response(self, params: 'Any') -> None:
        if self.status == IDLE:
            self._handle_error(INVALID_STATE)
        elif self.status == SAVING_NON_FORMATTED:
            # debug("handle_response", "SAVING_NON_FORMATTED")
            self.changes = params
            self.received = True
        elif self.status == SAVED_NON_FORMATTED:
            # debug("handle_response", "SAVED_NON_FORMATTED")
            if params:
                apply_response_to_view(params, self.view)
                self._view_maybe_dirty = True
                self.changes = None
                self._set_status(SAVING_FORMATTED)
                self.view.run_command("save")
            else:
                self._set_status(IDLE)
                self.changes = None
        elif self.status == SAVING_FORMATTED:
            self._handle_error(INVALID_STATE)


class LspFormatDocumentCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        return self.has_client_with_capability('documentFormattingProvider')

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentFormattingProvider')
        file_path = self.view.file_name()
        if client and file_path:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(file_path)
                },
                "options": options_for_view(self.view)
            }
            request = Request.formatting(params)
            client.send_request(request, lambda response: apply_response_to_view(response, self.view))


class LspFormatDocumentRangeCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        if self.has_client_with_capability('documentRangeFormattingProvider'):
            if len(self.view.sel()) == 1:
                region = self.view.sel()[0]
                if region.begin() != region.end():
                    return True
        return False

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentRangeFormattingProvider')
        file_path = self.view.file_name()
        if client and file_path:
            region = self.view.sel()[0]
            params = {
                "textDocument": {
                    "uri": filename_to_uri(file_path)
                },
                "range": region_to_range(self.view, region).to_lsp(),
                "options": options_for_view(self.view)
            }
            client.send_request(
                Request.rangeFormatting(params), lambda response: apply_response_to_view(response, self.view))
