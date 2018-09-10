import sublime
import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.documents import get_document_position
from .core.events import global_events
from .core.protocol import Request
from .core.registry import LspTextCommand, client_for_view, session_for_view
from .core.settings import settings
from .core.url import filename_to_uri
from .core.views import region_to_range

# typing only
from .core.rpc import Client
assert Client

try:
    from typing import List, Optional
    assert List and Optional
except ImportError:
    pass


class LspFormatDocumentCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        return self.has_client_with_capability('documentFormattingProvider')

    def run(self, edit):
        client = client_for_view(self.view)
        if client:
            pos = self.view.sel()[0].begin()
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "options": get_formatting_options(self.view)
            }
            request = Request.formatting(params)
            client.send_request(
                request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        self.view.run_command('lsp_apply_document_edit',
                              {'changes': response})


class LspFormatDocumentRangeCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        if self.has_client_with_capability('documentRangeFormattingProvider'):
            if len(self.view.sel()) == 1:
                region = self.view.sel()[0]
                if region.begin() != region.end():
                    return True
        return False

    def run(self, _):
        client = client_for_view(self.view)
        if client:
            region = self.view.sel()[0]
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "range": region_to_range(self.view, region).to_lsp(),
                "options": get_formatting_options(self.view)
            }
            client.send_request(Request.rangeFormatting(params),
                                lambda response: self.view.run_command('lsp_apply_document_edit',
                                                                       {'changes': response}))


class DocumentOnTypeFormattingListener(sublime_plugin.ViewEventListener):

    @classmethod
    def is_applicable(cls, subl_settings: sublime.Settings) -> bool:
        syntax = subl_settings.get('syntax')
        if not syntax:
            return False
        elif not is_supported_syntax(syntax):
            return False
        return True

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._triggers = []  # type: List[str]
        self._client = None  # type: Optional[Client]
        self._initialized = False
        self._enabled = False
        self._undo_was_invoked = False

    def on_modified_async(self) -> None:
        if not settings.format_on_type:
            return
        if not self._initialized:
            self._initialize()
        if self._enabled:
            client = client_for_view(self.view)
            if client:
                if self._undo_was_invoked:
                    self._undo_was_invoked = False
                    return
                for region in self.view.sel():
                    self._on_type_formatting_async(client, region.begin())

    def _initialize(self) -> None:
        self._initialized = True
        session = session_for_view(self.view)
        if session:
            options = session.get_capability("documentOnTypeFormattingProvider")
            if options:
                firsttrigchar = options.get("firstTriggerCharacter", None)
                if firsttrigchar:
                    self._triggers = [firsttrigchar]
                    self._triggers.extend(options.get("moreTriggerCharacter", []))
                    self._enabled = True

    def _on_type_formatting_async(self, client: Client, point: int) -> None:
        previous_character = self.view.substr(point - 1)
        if previous_character not in self._triggers:
            return
        params = get_document_position(self.view, point)
        if not params:
            return
        params["ch"] = previous_character
        params["options"] = get_formatting_options(self.view)
        global_events.publish("view.on_purge_changes", self.view)
        client.send_request(Request.onTypeFormatting(params),
                            lambda response: self.view.run_command("lsp_apply_document_edit",
                                                                   {"changes": response}))

    def on_text_command(self, name, _) -> None:
        if name == "undo":
            self._undo_was_invoked = True


def get_formatting_options(view: sublime.View) -> dict:
    return {
        "tabSize": view.settings().get("tab_size", 4),
        "insertSpaces": view.settings().get("translate_tabs_to_spaces", True)
    }
