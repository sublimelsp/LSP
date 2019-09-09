import mdpopups
import sublime
import sublime_plugin
import webbrowser
from html import escape
try:
    from typing import List, Optional, Any, Dict
    assert List and Optional and Any and Dict
except ImportError:
    pass

from .core.configurations import is_supported_syntax
from .diagnostics import get_point_diagnostics
from .core.registry import session_for_view, LspTextCommand
from .core.protocol import Request, DiagnosticSeverity
from .core.documents import get_document_position
from .core.popups import popup_css, popup_class
from .core.settings import client_configs, settings

SUBLIME_WORD_MASK = 515


class HoverHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, view_settings):
        if 'hover' in settings.disabled_capabilities:
            return False
        syntax = view_settings.get('syntax')
        return syntax and is_supported_syntax(syntax, client_configs.all)

    def on_hover(self, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT or self.view.is_popup_visible():
            return
        self.view.run_command("lsp_hover", {"point": point})


_test_contents = []  # type: List[str]


class_for_severity = {
    DiagnosticSeverity.Error: 'errors',
    DiagnosticSeverity.Warning: 'warnings',
    DiagnosticSeverity.Information: 'info',
    DiagnosticSeverity.Hint: 'hints'
}


class GotoKind:

    __slots__ = ("lsp_name", "label", "subl_cmd_name")

    def __init__(self, lsp_name: str, label: str, subl_cmd_name: str) -> None:
        self.lsp_name = lsp_name
        self.label = label
        self.subl_cmd_name = subl_cmd_name


goto_kinds = [
    GotoKind("definition", "Definition", "definition"),
    GotoKind("typeDefinition", "Type Definition", "type_definition"),
    GotoKind("declaration", "Declaration", "declaration"),
    GotoKind("implementation", "Implementation", "implementation")
]


class LspHoverCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_likely_at_symbol(self, point):
        word_at_sel = self.view.classify(point)
        return word_at_sel & SUBLIME_WORD_MASK

    def run(self, edit, point=None):
        if point is None:
            point = self.view.sel()[0].begin()
        if self.is_likely_at_symbol(point):
            self.request_symbol_hover(point)
        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            self.show_hover(point, self.diagnostics_content(point_diagnostics))

    def request_symbol_hover(self, point) -> None:
        # todo: session_for_view looks up windowmanager twice (config and for sessions)
        # can we memoize some part (eg. where no point is provided?)
        session = session_for_view(self.view, 'hoverProvider', point)
        if session:
            document_position = get_document_position(self.view, point)
            if document_position:
                if session.client:
                    session.client.send_request(
                        Request.hover(document_position),
                        lambda response: self.handle_response(response, point))

    def handle_response(self, response: 'Optional[Any]', point) -> None:
        all_content = ""

        point_diagnostics = get_point_diagnostics(self.view, point)
        if point_diagnostics:
            all_content += self.diagnostics_content(point_diagnostics)

        all_content += self.hover_content(point, response)
        if all_content:
            all_content += self.symbol_actions_content()

        _test_contents.clear()
        _test_contents.append(all_content)  # for testing only

        if all_content:
            self.show_hover(point, all_content)

    def symbol_actions_content(self):
        actions = []
        for goto_kind in goto_kinds:
            if self.has_client_with_capability(goto_kind.lsp_name + "Provider"):
                actions.append("<a href='{}'>{}</a>".format(goto_kind.lsp_name, goto_kind.label))
        if self.has_client_with_capability('referencesProvider'):
            actions.append("<a href='{}'>{}</a>".format('references', 'References'))
        if self.has_client_with_capability('renameProvider'):
            actions.append("<a href='{}'>{}</a>".format('rename', 'Rename'))
        return "<p>" + " | ".join(actions) + "</p>"

    def format_diagnostic(self, diagnostic):
        diagnostic_message = escape(diagnostic.message, False).replace('\n', '<br>')
        if diagnostic.source:
            return "<pre>[{}] {}</pre>".format(diagnostic.source, diagnostic_message)
        else:
            return "<pre>{}</pre>".format(diagnostic_message)

    def diagnostics_content(self, diagnostics):
        by_severity = {}  # type: Dict[int, List[str]]
        for diagnostic in diagnostics:
            by_severity.setdefault(diagnostic.severity, []).append(self.format_diagnostic(diagnostic))
        formatted = []
        for severity, items in by_severity.items():
            formatted.append("<div class='{}'>".format(class_for_severity[severity]))
            formatted.extend(items)
            formatted.append("<a href='{}'>{}</a>".format('code-actions',
                                                          'Code Actions'))
            formatted.append("</div>")

        return "".join(formatted)

    def hover_content(self, point, response: 'Optional[Any]') -> str:
        contents = []  # type: List[Any]
        if isinstance(response, dict):
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

        if formatted:
            return mdpopups.md2html(self.view, "\n".join(formatted))

        return ""

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
        for goto_kind in goto_kinds:
            if href == goto_kind.lsp_name:
                self.run_command_from_point(point, "lsp_symbol_" + goto_kind.subl_cmd_name)
                return
        if href == 'references':
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
