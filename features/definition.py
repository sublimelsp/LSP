import sublime
import sublime_plugin

from ..core.configurations import is_supported_view
from ..core.clients import client_for_view
from ..core.protocol import Request, Point
from ..core.documents import get_document_position, get_position, is_at_word
from ..core.url import uri_to_filename
from ..core.logging import debug


class LspSymbolDefinitionCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        # TODO: check what kind of scope we're in.
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('definitionProvider'):
                return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
        client = client_for_view(self.view)
        if client:
            pos = get_position(self.view, event)
            document_position = get_document_position(self.view, pos)
            if document_position:
                request = Request.definition(document_position)
                client.send_request(
                    request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, position):
        window = sublime.active_window()
        if response:
            location = response if isinstance(response, dict) else response[0]
            file_path = uri_to_filename(location.get("uri"))
            start = Point.from_lsp(location['range']['start'])
            file_location = "{}:{}:{}".format(file_path, start.row + 1, start.col + 1)
            debug("opening location", location)
            window.open_file(file_location, sublime.ENCODED_POSITION)
            # TODO: can add region here.
        else:
            window.run_command("goto_definition")

    def want_event(self):
        return True
