import mdpopups
import sublime
import sublime_plugin
import webbrowser

from .core.configurations import is_supported_syntax
from .core.diagnostics import get_point_diagnostics
from .core.clients import client_for_view
from .core.protocol import Request
from .core.documents import get_document_position
from .core.popups import popup_css, popup_class

SUBLIME_WORD_MASK = 515
NO_HOVER_SCOPES = 'comment, string'


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
        self.request_symbol_hover(point)
        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            self.show_hover(point, self.diagnostics_content(point_diagnostics))

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
        all_content = [self.hover_content(point, response)]

        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            all_content.extend(self.diagnostics_content(point_diagnostics))

        self.show_hover(point, all_content)

    def diagnostics_content(self, diagnostics):
        formatted = list("{}: {}".format(diagnostic.source, diagnostic.message) for diagnostic in diagnostics)
        formatted.append("[{}]({})".format('Code Actions', 'code-actions'))
        return formatted

    def hover_content(self, point, response):
        contents = ["No description available."]
        if isinstance(response, dict):
            # Flow returns None sometimes
            # See: https://github.com/flowtype/flow-language-server/issues/51
            response_content = response.get('contents')
            if response_content:
                if isinstance(response_content, list):
                    contents = response_content
                else:
                    contents = [response_content]

        formatted = []
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
                formatted.append(value)

        return "\n".join(formatted)

    def show_hover(self, point, contents):
        mdpopups.show_popup(
            self.view,
            "\n".join(contents),
            css=popup_css,
            md=True,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class=popup_class,
            max_width=800,
            on_navigate=lambda href: self.on_hover_navigate(href, point))

    def on_hover_navigate(self, href, point):
        if href == 'code-actions':
            sel = self.view.sel()
            sel.clear()
            sel.add(sublime.Region(point, point))
            self.view.run_command("lsp_code_actions")
        else:
            webbrowser.open_new_tab(href)
