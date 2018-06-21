import mdpopups
import sublime
import sublime_plugin
import webbrowser

from .core.configurations import is_supported_syntax
from .core.diagnostics import get_point_diagnostics
from .core.clients import LspTextCommand, session_for_view
from .core.protocol import Request, DiagnosticSeverity
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
        self.view.run_command("lsp_hover", {"point": point})


class LspHoverCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_likely_at_symbol(self, point):
        word_at_sel = self.view.classify(point)
        return word_at_sel & SUBLIME_WORD_MASK and not self.view.match_selector(point, NO_HOVER_SCOPES)

    def run(self, edit, point=None):
        if point is None:
            point = self.view.sel()[0].begin()
        if self.is_likely_at_symbol(point):
            self.request_symbol_hover(point)
        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            self.show_hover(point, self.diagnostics_content(point_diagnostics))

    def request_symbol_hover(self, point):
        session = session_for_view(self.view)
        if session:
            if session.has_capability('hoverProvider'):
                document_position = get_document_position(self.view, point)
                if document_position:
                    if session.client:
                        session.client.send_request(
                            Request.hover(document_position),
                            lambda response: self.handle_response(response, point))

    def handle_response(self, response, point):
        all_content = ""

        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            all_content += self.diagnostics_content(point_diagnostics)

        all_content += self.hover_content(point, response)
        all_content += self.symbol_actions_content()

        self.show_hover(point, all_content)

    def symbol_actions_content(self):
        actions = []
        # TODO: filter by client capabilities
        actions.append("<a href='{}'>{}</a>".format('definition', 'Definition'))
        actions.append("<a href='{}'>{}</a>".format('references', 'References'))
        actions.append("<a href='{}'>{}</a>".format('rename', 'Rename'))
        return "<p>" + " | ".join(actions) + "</p>"

    def diagnostics_content(self, diagnostics):
        formatted_errors = list(
            "<pre>{}</pre>".format("[{}] {}".format(diagnostic.source, diagnostic.message) if diagnostic.source else "{}".format(diagnostic.message))
            for diagnostic in diagnostics
            if diagnostic.severity == DiagnosticSeverity.Error)
        formatted = []
        if len(formatted_errors) > 0:
            formatted.append("<div class='errors'>")
            formatted.extend(formatted_errors)
            formatted.append("<a href='{}'>{}</a>".format('code-actions',
                                                          'Code Actions'))
            formatted.append("</div>")

        formatted_warnings = list(
            "<pre>{}</pre>".format("[{}] {}".format(diagnostic.source, diagnostic.message) if diagnostic.source else "{}".format(diagnostic.message))
            for diagnostic in diagnostics
            if diagnostic.severity == DiagnosticSeverity.Warning)

        if len(formatted_warnings) > 0:
            formatted.append("<div class='warnings'>")
            formatted.extend(formatted_warnings)
            formatted.append("<a href='{}'>{}</a>".format('code-actions',
                                                          'Code Actions'))
            formatted.append("</div>")

        return "".join(formatted)

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

        return mdpopups.md2html(self.view, "\n".join(formatted))

    def show_hover(self, point, contents):
        mdpopups.show_popup(
            self.view,
            contents,
            css=popup_css,
            md=False,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            wrapper_class=popup_class,
            max_width=800,
            on_navigate=lambda href: self.on_hover_navigate(href, point))

    def on_hover_navigate(self, href, point):
        if href == 'definition':
            self.run_command_from_point(point, "lsp_symbol_definition")
        elif href == 'references':
            self.run_command_from_point(point, "lsp_symbol_references")
        elif href == 'rename':
            self.run_command_from_point(point, "lsp_symbol_rename")
        elif href == 'code-actions':
            self.run_command_from_point(point, "lsp_code_actions")
        else:
            webbrowser.open_new_tab(href)

    def run_command_from_point(self, point, command_name):
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command(command_name)
