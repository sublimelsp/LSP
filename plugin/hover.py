import mdpopups
import sublime
import webbrowser
import os
from html import escape
from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .code_actions import run_code_action_or_command
from .core.popups import popups
from .core.protocol import Request, DiagnosticSeverity, Diagnostic, DiagnosticRelatedInformation
from .core.registry import LspTextCommand
from .core.registry import LSPViewEventListener
from .core.registry import windows
from .core.settings import settings
from .core.typing import List, Optional, Any, Dict
from .core.views import FORMAT_MARKED_STRING, FORMAT_MARKUP_CONTENT, minihtml
from .core.views import offset_to_point
from .core.views import make_link
from .core.views import text_document_position_params
from .diagnostics import filter_by_point, view_diagnostics


SUBLIME_WORD_MASK = 515


class HoverHandler(LSPViewEventListener):
    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'hover' in settings.disabled_capabilities:
            return False
        return cls.has_supported_syntax(view_settings)

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

    def run(self, edit: sublime.Edit, point: Optional[int] = None, event: Optional[dict] = None) -> None:
        hover_point = point or self.view.sel()[0].begin()
        window = self.view.window()
        if not window:
            return
        self._base_dir = windows.lookup(window).get_project_path(self.view.file_name() or "")

        self._hover = None  # type: Optional[Any]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = {}  # type: Dict[str, List[Diagnostic]]

        if self.is_likely_at_symbol(hover_point):
            self.request_symbol_hover(hover_point)

        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.
        request_point = offset_to_point(self.view, hover_point)
        self._diagnostics_by_config, code_actions_range = filter_by_point(view_diagnostics(self.view), request_point)
        if self._diagnostics_by_config:
            actions_manager.request_with_diagnostics(
                self.view, code_actions_range, self._diagnostics_by_config,
                lambda response: self.handle_code_actions(response, hover_point))
            self.show_hover(hover_point)

    def request_symbol_hover(self, point: int) -> None:
        session = self.session('hoverProvider', point)
        if session:
            document_position = text_document_position_params(self.view, point)
            session.send_request(
                Request.hover(document_position),
                lambda response: self.handle_response(response, point))

    def handle_code_actions(self, responses: Dict[str, List[CodeActionOrCommand]], point: int) -> None:
        self._actions_by_config = responses
        sublime.set_timeout(lambda: self.show_hover(point))

    def handle_response(self, response: Optional[Any], point: int) -> None:
        self._hover = response
        sublime.set_timeout(lambda: self.show_hover(point))

    def symbol_actions_content(self) -> str:
        actions = []
        for goto_kind in goto_kinds:
            if self.session(goto_kind.lsp_name + "Provider"):
                actions.append(make_link(goto_kind.lsp_name, goto_kind.label))
        if self.session('referencesProvider'):
            actions.append(make_link('references', 'References'))
        if self.session('renameProvider'):
            actions.append(make_link('rename', 'Rename'))
        return "<p class='actions'>" + " | ".join(actions) + "</p>"

    def format_diagnostic_related_info(self, info: DiagnosticRelatedInformation) -> str:
        file_path = info.location.file_path
        if self._base_dir and file_path.startswith(self._base_dir):
            file_path = os.path.relpath(file_path, self._base_dir)
        location = "{}:{}:{}".format(file_path, info.location.range.start.row+1, info.location.range.start.col+1)
        link = make_link("location:{}".format(location), location)
        return "{}: {}".format(link, escape(info.message))

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
                    href = "{}:{}".format('code-actions', config_name)
                    text = "{} ({})".format('Code Actions', action_count)
                    formatted.append("<div class=\"actions\">{}</div>".format(make_link(href, text)))

            formatted.append("</div>")

        return "".join(formatted)

    def hover_content(self) -> str:
        content = (self._hover.get('contents') or '') if isinstance(self._hover, dict) else ''
        return minihtml(self.view, content, allowed_formats=FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT)

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

    def run_command_from_point(self, point: int, command_name: str, args: Optional[Any] = None) -> None:
        sel = self.view.sel()
        sel.clear()
        sel.add(sublime.Region(point, point))
        self.view.run_command(command_name, args)
