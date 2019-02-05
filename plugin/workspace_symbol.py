import sublime_plugin
import sublime
from .core.protocol import Request
from .core.registry import client_for_view, LspTextCommand
from .core.url import uri_to_filename
from .symbols import format_symbol_kind
import os

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
except ImportError:
    pass


class QueryHandler(sublime_plugin.TextInputHandler):

    def validate(self, txt) -> bool:
        return txt != ""

    def placeholder(self):
        return "Symbol"


class LspWorkspaceSymbolsCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def _format(self, s: 'Dict[str, Any]') -> str:
        file_name = os.path.basename(s['location']['uri'])
        symbol_kind = format_symbol_kind(s["kind"])
        name = "{} ({}) - {} -- {}".format(s['name'], symbol_kind, s.get('containerName', ""), file_name)
        return name

    def _open_file(self, symbols: 'List[Dict[str, Any]]', index: int) -> None:
        if index != -1:
            symbol = symbols[index]
            start = symbol['location']['range']['start']
            file_name = uri_to_filename(symbol['location']['uri'])
            encoded_file_name = "{}:{}:{}".format(file_name, start['line'], start['character'])
            self.view.window().open_file(encoded_file_name, sublime.ENCODED_POSITION)

    def _handle_response(self, query: str, matches: 'Optional[List[Dict[str, Any]]]') -> None:
        self.view.erase_status("lsp_wokspace_symbols")
        if matches:
            choices = list(map(lambda s: self._format(s), matches))
            self.view.window().show_quick_panel(choices, lambda i: self._open_file(matches, i))
        else:
            sublime.message_dialog("No matches found for query string: '{}'".format(query))

    def _handle_error(self, error: 'Dict[str, Any]') -> None:
        reason = error.get("message", "none provided by server :(")
        msg = "command 'workspace/symbol' failed. Reason: {}".format(reason)
        sublime.error_message(msg)

    def is_enabled(self, event=None):
        return self.has_client_with_capability('workspaceSymbolProvider')

    def input(self, args):
        return QueryHandler()

    def run(self, edit, query_handler: str = "") -> None:
        if query_handler:
            request = Request.workspaceSymbol({"query": query_handler})
            client = client_for_view(self.view)
            if client:
                self.view.set_status("lsp_wokspace_symbols", "sending request")
                client.send_request(request, lambda r: self._handle_response(query_handler, r), self._handle_error)
