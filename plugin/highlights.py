import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.protocol import Request, Range, DocumentHighlightKind
from .core.clients import client_for_view
from .core.documents import get_document_position
from .core.settings import settings

import sublime  # only for typing
try:
    from typing import List, Dict
    assert List and Dict
except ImportError:
    pass


_kind2name = {
    DocumentHighlightKind.Unknown: "unknown",
    DocumentHighlightKind.Text: "text",
    DocumentHighlightKind.Read: "read",
    DocumentHighlightKind.Write: "write"
}


class DocumentHighlightListener(sublime_plugin.ViewEventListener):

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._initialized = False
        self._enabled = False
        self._stored_point = -1

    def on_selection_modified_async(self) -> None:
        if not self._initialized:
            self._initialize()
        if self._enabled:
            self._clear_regions()
            self._queue()

    def _initialize(self) -> None:
        self._initialized = True
        client = client_for_view(self.view)
        if client:
            self._enabled = client.get_capability("documentHighlightProvider")

    def _queue(self) -> None:
        self._stored_point = self.view.sel()[0].begin()
        current_point = self._stored_point
        sublime.set_timeout_async(lambda: self._purge(current_point), 500)

    def _purge(self, current_point: int) -> None:
        if current_point == self._stored_point:
            self._on_document_highlight()

    def _clear_regions(self) -> None:
        for kind in settings.document_highlight_scopes.keys():
            self.view.erase_regions("lsp_highlight_{}".format(kind))

    def _on_document_highlight(self) -> None:
        self._clear_regions()
        if len(self.view.sel()) != 1:
            return
        point = self.view.sel()[0].begin()
        if self.view.match_selector(point, "comment"):
            # We're inside a comment, go home.
            return
        client = client_for_view(self.view)
        if client:
            params = get_document_position(self.view, point)
            if params:
                request = Request.documentHighlight(params)
                client.send_request(request, self._handle_response)

    def _handle_response(self, response: list) -> None:
        if not response:
            return
        kind2regions = {}  # type: Dict[str, List[sublime.Region]]
        for kind in range(0, 4):
            kind2regions[_kind2name[kind]] = []
        for highlight in response:
            if highlight:
                r = Range.from_lsp(highlight["range"]).to_region(self.view)
                kind = highlight.get("kind", DocumentHighlightKind.Unknown)
                kind2regions[_kind2name[kind]].append(r)
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        if settings.document_highlight_style == "underline":
            flags |= sublime.DRAW_SOLID_UNDERLINE
        elif settings.document_highlight_style == "stippled":
            flags |= sublime.DRAW_STIPPLED_UNDERLINE
        elif settings.document_highlight_style == "squiggly":
            flags |= sublime.DRAW_SQUIGGLY_UNDERLINE
        self._clear_regions()
        for kind_str, regions in kind2regions.items():
            if regions:
                scope = settings.document_highlight_scopes.get(kind_str, None)
                self.view.add_regions("lsp_highlight_{}".format(kind_str),
                                      regions, scope=scope, flags=flags)
