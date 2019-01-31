import sublime_plugin
import sublime
import time
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


class SymbolListHandler(sublime_plugin.ListInputHandler):
    def __init__(self, symbols):
        self._symbols = symbols
        self._items = list(map(lambda s: (self._format(s), s), self._symbols))

    def _format(self, s: 'Dict[str, Any]') -> str:
        file_name = os.path.basename(s['location']['uri'])
        name = "{} - {} -- {}".format(s['name'], s.get('containerName', ""), file_name)
        return name

    def list_items(self):
        return self._items

    def preview(self, s):
        return format_symbol_kind(s["kind"])


class QueryHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view):
        self.view = view
        self.client = client_for_view(self.view)
        self._symbols = []  # type: 'List[Dict]'
        self._completed_request = False
        self._request_time = 0

    def _timeout(self) -> bool:
        return self._request_time > 3

    def _handle_response(self, symbols: 'Optional[List[Dict[str, Any]]]') -> None:
        if symbols:
            self._symbols = symbols
            self._completed_request = True

    def _handle_error(self, error: 'Dict[str, Any]') -> None:
        reason = error.get("message", "none provided by server :(")
        msg = "command 'workspace/symbol' failed. Reason: {}".format(reason)
        self._completed_request = True
        sublime.error_message(msg)

    def validate(self, txt):
        return txt != ""

    def confirm(self, txt):
        self._completed_request = False
        self._request_time = 0
        request = Request.workspaceSymbol({"query": txt})
        if self.client:
            self.client.send_request(request, self._handle_response, self._handle_error)

        # wait for request to complete
        while not self._completed_request or not self._timeout:
            time.sleep(0.25)
            self._request_time += 0.25

        return len(self._symbols) != 0

    def placeholder(self):
        return "Symbol"

    def next_input(self, args):
        return SymbolListHandler(self._symbols)


class LspWorkspaceSymbolsCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        return self.has_client_with_capability('workspaceSymbolProvider')

    def input(self, args):
        return QueryHandler(self.view)

    def run(self, edit=None, symbol_list_handler: 'Optional[Dict[str, Any]]'=None,
            query_handler: 'Optional[str]'=None) -> None:

        if symbol_list_handler:
                start = symbol_list_handler['location']['range']['start']
                file_name = uri_to_filename(symbol_list_handler['location']['uri'])
                encoded_file_name = "{}:{}:{}".format(file_name, start['line'], start['character'])
                self.view.window().open_file(encoded_file_name, sublime.ENCODED_POSITION)
