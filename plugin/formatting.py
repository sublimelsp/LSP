import sublime
import sublime_plugin
from .core.protocol import Request
from .core.configurations import is_supported_syntax
from .core.settings import client_configs
from .core.edit import parse_text_edit
from .core.registry import LspTextCommand, session_for_view, client_from_session
from .core.url import filename_to_uri
from .core.views import region_to_range
from .core.events import global_events

try:
    from typing import Dict, Any, List, Optional
    assert Dict and Any and List and Optional
except ImportError:
    pass


def options_for_view(view: sublime.View) -> 'Dict[str, Any]':
    return {"tabSize": view.settings().get("tab_size", 4), "insertSpaces": True}


def apply_response_to_view(response: 'Optional[List[dict]]', view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


class FormatOnSaveListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        return False

    def on_pre_save(self) -> None:
        if self.view.settings().get("lsp_format_on_save"):
            client = client_from_session(session_for_view(self.view, 'documentFormattingProvider'))
            if client:
                params = {
                    "textDocument": {
                        "uri": filename_to_uri(self.view.file_name())
                    },
                    "options": options_for_view(self.view)
                }
                request = Request.formatting(params)
                response = client.execute_request(request)
                if response:
                    apply_response_to_view(response, self.view)
                    global_events.publish("view.on_purge_changes", self.view)


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
