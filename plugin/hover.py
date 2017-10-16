import mdpopups
import sublime
import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.diagnostics import get_point_diagnostics
from .core.clients import client_for_view
from .core.protocol import Request
from .core.documents import get_document_position
from .core.logging import debug
from .core.popups import preserve_whitespace, popup_css, popup_class

SUBLIME_WORD_MASK = 515
NO_HOVER_SCOPES = 'comment, constant, keyword, storage, string'


class HoverHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        return syntax and is_supported_syntax(syntax)

    def on_hover(self, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT or self.view.is_popup_visible():
            return
        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            self.show_diagnostics_hover(point, point_diagnostics)
        else:
            self.request_symbol_hover(point)

    def request_symbol_hover(self, point):
        if self.view.match_selector(point, NO_HOVER_SCOPES):
            return
        client = client_for_view(self.view)
        if client and client.has_capability('hoverProvider'):
            word_at_sel = self.view.classify(point)
            if word_at_sel & SUBLIME_WORD_MASK:
                document_position = get_document_position(self.view, point)
                if document_position:
                    client.send_request(
                        Request.hover(document_position),
                        lambda response: self.handle_response(response, point))

    def handle_response(self, response, point):
        debug(response)
        if self.view.is_popup_visible():
            return
        contents = "No description available."
        if isinstance(response, dict):
            # Flow returns None sometimes
            # See: https://github.com/flowtype/flow-language-server/issues/51
            contents = response.get('contents') or contents
        self.show_hover(point, contents)

    def show_diagnostics_hover(self, point, diagnostics):
        formatted = list("{}: {}".format(diagnostic.source, diagnostic.message) for diagnostic in diagnostics)
        formatted.append("[{}]({})".format('Code Actions', 'code-actions'))
        mdpopups.show_popup(
            self.view,
            "\n".join(formatted),
            css=popup_css,
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class=popup_class,
            max_width=800,
            on_navigate=lambda href: self.on_diagnostics_navigate(href, point, diagnostics))

    def on_diagnostics_navigate(self, href, point, diagnostics):
        # TODO: don't mess with the user's cursor.
        # Instead, pass code actions requested from phantoms & hovers should call lsp_code_actions with
        # diagnostics as args, positioning resulting UI close to the clicked link.
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command("lsp_code_actions")

    def show_hover(self, point, contents):
        formatted = []
        if not isinstance(contents, list):
            contents = [contents]

        for item in contents:
            value = ""
            language = None
            if isinstance(item, str):
                value = item
            else:
                value = item.get("value")
                language = item.get("language")
            if language:
                formatted.append("```{}\n{}\n```\n".format(language, value))
            else:
                formatted.append(preserve_whitespace(value))

        mdpopups.show_popup(
            self.view,
            "\n".join(formatted),
            css=popup_css,
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class=popup_class,
            max_width=800)
