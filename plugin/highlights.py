import sublime
import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.protocol import Request, Range, DocumentHighlightKind
from .core.registry import session_for_view, client_from_session
from .core.documents import get_document_position
from .core.settings import settings, client_configs
from .core.views import range_to_region
try:
    from typing import List, Dict, Optional
    assert List and Dict and Optional
except ImportError:
    pass

SUBLIME_WORD_MASK = 515
NO_HIGHLIGHT_SCOPES = 'comment, string'

_kind2name = {
    DocumentHighlightKind.Unknown: "unknown",
    DocumentHighlightKind.Text: "text",
    DocumentHighlightKind.Read: "read",
    DocumentHighlightKind.Write: "write"
}


def remove_highlights(view: sublime.View) -> None:
    for kind in settings.document_highlight_scopes.keys():
        view.erase_regions("lsp_highlight_{}".format(kind))


class DocumentHighlightListener(sublime_plugin.ViewEventListener):

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'documentHighlight' in settings.disabled_capabilities:
            return False
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        else:
            return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._initialized = False
        self._enabled = False
        self._stored_point = -1

    def on_selection_modified_async(self) -> None:
        if not self._initialized:
            self._initialize()
        if self._enabled:
            if settings.document_highlight_style:
                self._queue()

    def _initialize(self) -> None:
        self._initialized = True
        session = session_for_view(self.view, "documentHighlightProvider")
        if session:
            self._enabled = True

    def _queue(self) -> None:
        current_point = self.view.sel()[0].begin()
        if self._stored_point != current_point:
            self._clear_regions()
            self._stored_point = current_point
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
        word_at_sel = self.view.classify(point)
        if word_at_sel & SUBLIME_WORD_MASK:
            if self.view.match_selector(point, NO_HIGHLIGHT_SCOPES):
                return
            client = client_from_session(session_for_view(self.view, "documentHighlightProvider"))
            if client:
                params = get_document_position(self.view, point)
                if params:
                    request = Request.documentHighlight(params)
                    client.send_request(request, self._handle_response)

    def _handle_response(self, response: 'Optional[List]') -> None:
        if not response:
            return
        kind2regions = {}  # type: Dict[str, List[sublime.Region]]
        for kind in range(0, 4):
            kind2regions[_kind2name[kind]] = []
        for highlight in response:
            r = range_to_region(Range.from_lsp(highlight["range"]), self.view)
            kind = highlight.get("kind", DocumentHighlightKind.Unknown)
            if kind is not None:
                kind2regions[_kind2name[kind]].append(r)
        if settings.document_highlight_style == "fill":
            flags = 0
        elif settings.document_highlight_style == "box":
            flags = sublime.DRAW_NO_FILL
        else:
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
                if scope:
                    self.view.add_regions("lsp_highlight_{}".format(kind_str),
                                          regions, scope=scope, flags=flags)
