import mdpopups
import sublime
import sublime_plugin
import webbrowser
import os
import textwrap
from html import escape
from .core.configurations import is_supported_syntax
from .diagnostics import filter_by_point, view_diagnostics
from .core.registry import session_for_view, LspTextCommand, windows
from .core.protocol import Request, DiagnosticSeverity, Diagnostic, DiagnosticRelatedInformation, Point
from .core.documents import get_document_position
from .core.popups import popups
from .code_actions import actions_manager, run_code_action_or_command
from .core.settings import client_configs, settings

try:
    from typing import List, Optional, Any, Dict
    from .code_actions import CodeActionOrCommand
    assert List and Optional and Any and Dict and Diagnostic and CodeActionOrCommand
except ImportError:
    pass


SUBLIME_WORD_MASK = 515


class HoverHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        self.view = view

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'hover' in settings.disabled_capabilities:
            return False
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        else:
            return False

    def on_hover(self, point: int, hover_zone: int) -> None:
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
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._base_dir = None   # type: Optional[str]

    def is_likely_at_symbol(self, point: int) -> bool:
        word_at_sel = self.view.classify(point)
        return bool(word_at_sel & SUBLIME_WORD_MASK)

    def run(self, edit: sublime.Edit, point: 'Optional[int]' = None) -> None:
        hover_point = point or self.view.sel()[0].begin()
        self._base_dir = windows.lookup(self.view.window()).get_project_path(self.view.file_name() or "")

        self._hover = None  # type: Optional[Any]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = {}  # type: Dict[str, List[Diagnostic]]

        if self.is_likely_at_symbol(hover_point):
            self.request_symbol_hover(hover_point)

        self._diagnostics_by_config = filter_by_point(view_diagnostics(self.view),
                                                      Point(*self.view.rowcol(hover_point)))
        if self._diagnostics_by_config:
            self.request_code_actions(hover_point)
            self.request_show_hover(hover_point)

    def request_symbol_hover(self, point: int) -> None:
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

    def request_code_actions(self, point: int) -> None:
        actions_manager.request(self.view, point, lambda response: self.handle_code_actions(response, point),
                                self._diagnostics_by_config)

    def handle_code_actions(self, responses: 'Dict[str, List[CodeActionOrCommand]]', point: int) -> None:
        self._actions_by_config = responses
        self.request_show_hover(point)

    def handle_response(self, response: 'Optional[Any]', point: int) -> None:
        self._hover = response
        self.request_show_hover(point)

    def symbol_actions_content(self) -> str:
        actions = []
        for goto_kind in goto_kinds:
            if self.has_client_with_capability(goto_kind.lsp_name + "Provider"):
                actions.append("<a href='{}'>{}</a>".format(goto_kind.lsp_name, goto_kind.label))
        if self.has_client_with_capability('referencesProvider'):
            actions.append("<a href='{}'>{}</a>".format('references', 'References'))
        if self.has_client_with_capability('renameProvider'):
            actions.append("<a href='{}'>{}</a>".format('rename', 'Rename'))
        return "<p>" + " | ".join(actions) + "</p>"

    def format_diagnostic_related_info(self, info: DiagnosticRelatedInformation) -> str:
        file_path = info.location.file_path
        if self._base_dir and file_path.startswith(self._base_dir):
            file_path = os.path.relpath(file_path, self._base_dir)
        location = "{}:{}:{}".format(file_path, info.location.range.start.row+1, info.location.range.start.col+1)
        return "<a href='location:{}'>{}</a>: {}".format(location, location, escape(info.message))

    def format_diagnostic(self, diagnostic: 'Diagnostic') -> str:
        diagnostic_message = escape(diagnostic.message, False).replace('\n', '<br>')
        related_infos = [self.format_diagnostic_related_info(info) for info in diagnostic.related_info]
        related_content = "<pre class='related_info'>" + "<br>".join(related_infos) + "</pre>" if related_infos else ""

        if diagnostic.source:
            return "<pre class=\"{}\">[{}] {}{}</pre>".format(class_for_severity[diagnostic.severity],
                                                              diagnostic.source, diagnostic_message, related_content)
        else:
            return "<pre class=\"{}\">{}{}</pre>".format(class_for_severity[diagnostic.severity], diagnostic_message,
                                                         related_content)

    def diagnostics_content(self) -> str:
        formatted = []
        for config_name in self._diagnostics_by_config:
            by_severity = {}  # type: Dict[int, List[str]]
            formatted.append("<div class='diagnostics'>")
            for diagnostic in self._diagnostics_by_config[config_name]:
                by_severity.setdefault(diagnostic.severity, []).append(self.format_diagnostic(diagnostic))

            for severity, items in by_severity.items():
                formatted.append("<div>")
                formatted.extend(items)
                formatted.append("</div>")

            if config_name in self._actions_by_config:
                action_count = len(self._actions_by_config[config_name])
                if action_count > 0:
                    formatted.append("<div class=\"actions\"><a href='{}:{}'>{} ({})</a></div>".format(
                        'code-actions', config_name, 'Code Actions', action_count))

            formatted.append("</div>")

        return "".join(formatted)

    def hover_content(self) -> str:
        contents = []  # type: List[Any]
        if isinstance(self._hover, dict):
            response_content = self._hover.get('contents')
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

            if '\n' not in value:
                value = "\n".join(textwrap.wrap(value, 80))

            if language:
                formatted.append("```{}\n{}\n```\n".format(language, value))
            else:
                formatted.append(value)

        if formatted:
            return mdpopups.md2html(self.view, "\n".join(formatted))

        return ""

    def request_show_hover(self, point: int) -> None:
        sublime.set_timeout(lambda: self.show_hover(point), 50)

    def show_hover(self, point: int) -> None:
        contents = self.diagnostics_content() + self.hover_content()
        if contents and settings.show_symbol_action_links:
            contents += self.symbol_actions_content()

        _test_contents.clear()
        _test_contents.append(contents)  # for testing only

        if contents:
            mdpopups.show_popup(
                self.view,
                contents,
                css=popups.stylesheet,
                md=False,
                flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                location=point,
                wrapper_class=popups.classname,
                max_width=800,
                on_navigate=lambda href: self.on_hover_navigate(href, point))

    def on_hover_navigate(self, href: str, point: int) -> None:
        for goto_kind in goto_kinds:
            if href == goto_kind.lsp_name:
                self.run_command_from_point(point, "lsp_symbol_" + goto_kind.subl_cmd_name)
                return
        if href == 'references':
            self.run_command_from_point(point, "lsp_symbol_references")
        elif href == 'rename':
            self.run_command_from_point(point, "lsp_symbol_rename")
        elif href.startswith('code-actions'):
            _, config_name = href.split(":")
            titles = [command["title"] for command in self._actions_by_config[config_name]]
            sel = self.view.sel()
            sel.clear()
            sel.add(sublime.Region(point, point))

            self.view.show_popup_menu(titles, lambda i: self.handle_code_action_select(config_name, i))
        elif href.startswith('location'):
            _, file_path, location = href.split(":", 2)
            file_path = os.path.join(self._base_dir, file_path) if self._base_dir else file_path
            window = self.view.window()
            if window:
                window.open_file(file_path + ":" + location, sublime.ENCODED_POSITION | sublime.TRANSIENT)
        else:
            webbrowser.open_new_tab(href)

    def handle_code_action_select(self, config_name: str, index: int) -> None:
        if index > -1:
            selected = self._actions_by_config[config_name][index]
            run_code_action_or_command(self.view, config_name, selected)

    def run_command_from_point(self, point: int, command_name: str, args: 'Optional[Any]' = None) -> None:
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command(command_name, args)
