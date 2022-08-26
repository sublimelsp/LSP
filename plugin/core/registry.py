from .configurations import ConfigManager
from .sessions import AbstractViewListener
from .sessions import Session
from .settings import client_configs
from .types import toggled_capabilities
from .typing import Optional, Any, Dict, Generator, Iterable, List, Set, Tuple
from .windows import WindowRegistry
import sublime
import sublime_plugin


def best_session(view: sublime.View, sessions: Iterable[Session], point: Optional[int] = None) -> Optional[Session]:
    if point is None:
        try:
            point = view.sel()[0].b
        except IndexError:
            return None
    try:
        return max(sessions, key=lambda s: view.score_selector(point, s.config.priority_selector))  # type: ignore
    except ValueError:
        return None


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
windows = WindowRegistry(configs)


def get_position(view: sublime.View, event: Optional[dict] = None, point: Optional[int] = None) -> Optional[int]:
    if isinstance(point, int):
        return point
    if event:
        x, y = event.get("x"), event.get("y")
        if x is not None and y is not None:
            return view.window_to_text((x, y))
    try:
        return view.sel()[0].begin()
    except IndexError:
        return None


class LspWindowCommand(sublime_plugin.WindowCommand):
    """
    Inherit from this class to define requests which are not bound to a particular view. This allows to run requests
    for example from links in HtmlSheets or when an unrelated file has focus.
    """

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # capability attached to a view in the window.
    capability = ''

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # name attached to a view in the window.
    session_name = ''

    def is_enabled(self) -> bool:
        return self.session() is not None

    def session(self) -> Optional[Session]:
        for session in windows.lookup(self.window).get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            if self.session_name and session.config.name != self.session_name:
                continue
            return session
        else:
            return None

    def sessions(self) -> Generator[Session, None, None]:
        for session in windows.lookup(self.window).get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            yield session


class LspTextCommand(sublime_plugin.TextCommand):
    """
    Inherit from this class to define your requests that should be triggered via the command palette and/or a
    keybinding.
    """

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # capability attached to the active view.
    capability = ''

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # name attached to the active view.
    session_name = ''

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if self.capability:
            # At least one active session with the given capability must exist.
            position = get_position(self.view, event, point)
            if position is None:
                return False
            if not self.best_session(self.capability, position):
                return False
        if self.session_name:
            # There must exist an active session with the given (config) name.
            if not self.session_by_name(self.session_name):
                return False
        if not self.capability and not self.session_name:
            # Any session will do.
            return any(self.sessions())
        return True

    def want_event(self) -> bool:
        return True

    def get_listener(self) -> Optional[AbstractViewListener]:
        return windows.listener_for_view(self.view)

    def best_session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        listener = self.get_listener()
        return listener.session_async(capability, point) if listener else None

    def session_by_name(self, name: Optional[str] = None, capability_path: Optional[str] = None) -> Optional[Session]:
        target = name if name else self.session_name
        listener = self.get_listener()
        if listener:
            for sv in listener.session_views_async():
                if sv.session.config.name == target:
                    if capability_path is None or sv.has_capability_async(capability_path):
                        return sv.session
                    else:
                        return None
        return None

    def sessions(self, capability_path: Optional[str] = None) -> Generator[Session, None, None]:
        listener = self.get_listener()
        if listener:
            for sv in listener.session_views_async():
                if capability_path is None or sv.has_capability_async(capability_path):
                    yield sv.session


class LspRestartServerCommand(LspTextCommand):

    def run(self, edit: Any, config_name: str = None) -> None:
        window = self.view.window()
        if not window:
            return
        self._config_names = [session.config.name for session in self.sessions()] if not config_name else [config_name]
        if not self._config_names:
            return
        self._wm = windows.lookup(window)
        if len(self._config_names) == 1:
            self.restart_server(0)
        else:
            window.show_quick_panel(self._config_names, self.restart_server)

    def restart_server(self, index: int) -> None:
        if index < 0:
            return

        def run_async() -> None:
            config_name = self._config_names[index]
            if not config_name:
                return
            self._wm._end_sessions_async(config_name)
            listener = windows.listener_for_view(self.view)
            if listener:
                self._wm.register_listener_async(listener)

        sublime.set_timeout_async(run_async)


class LspRecheckSessionsCommand(sublime_plugin.WindowCommand):
    def run(self, config_name: Optional[str] = None) -> None:
        sublime.set_timeout_async(lambda: windows.lookup(self.window).restart_sessions_async(config_name))


# The server capabilities which are possible to toggle on/off.
# This should only contain the capabilities which are related to a certain feature.
# https://microsoft.github.io/language-server-protocol/specifications/specification-current/#serverCapabilities
SERVER_CAPABILITIES = {
    "completionProvider": "Auto Complete",
    "hoverProvider": "Hover",
    "signatureHelpProvider": "Signature Help",
    "declarationProvider": "Goto Declaration",
    "definitionProvider": "Goto Definition",
    "typeDefinitionProvider": "Goto Type Definition",
    "implementationProvider": "Goto Implementation",
    "referencesProvider": "Find References",
    "documentHighlightProvider": "Highlights",
    "documentSymbolProvider": "Goto Symbol",
    "codeActionProvider": "Code Actions",
    "codeLensProvider": "Code Lenses",
    "documentLinkProvider": "Links",
    "colorProvider": "Color Boxes",
    "documentFormattingProvider": "Formatting",
    "documentRangeFormattingProvider": "Range Formatting",
    # "documentOnTypeFormattingProvider": "On Type Formatting",  # not supported by this client
    "renameProvider": "Rename",
    # "foldingRangeProvider": "Folding",  # not supported by this client
    "executeCommandProvider": "Run Server Command",
    "selectionRangeProvider": "Expand Selection",
    # "linkedEditingRangeProvider": "Linked Editing",  # not supported by this client
    # "callHierarchyProvider": "Call Hierarchy",  # not supported by this client
    "semanticTokensProvider": "Semantic Highlighting",
    # "typeHierarchyProvider": "Type Hierarchy",  # not supported by this client
    "inlayHintProvider": "Inlay Hints",
    # "diagnosticProvider": "Pull Diagnostics",  # not supported by this client
    "workspaceSymbolProvider": "Goto Symbol in Project"
}


class LspToggleCapabilityCommand(LspWindowCommand):

    last_toggled = None

    def run(self, capability: str) -> None:
        global toggled_capabilities
        if capability not in SERVER_CAPABILITIES:
            raise ValueError("Invalid capability name: {}".format(capability))
        if capability in toggled_capabilities:
            toggled_capabilities.remove(capability)
            new_state = "on"
        else:
            toggled_capabilities.add(capability)
            new_state = "off"
        self.last_toggled = capability
        if capability == "hoverProvider":
            user_setting = sublime.load_settings("Preferences.sublime-settings").get("show_definitions")
            for session in self.sessions():
                for sv in session.session_views_async():
                    if new_state == "on":
                        sv.view.settings().set("show_definitions", False)
                    else:
                        sv.view.settings().set("show_definitions", user_setting)
        elif capability == "codeLensProvider":
            for session in self.sessions():
                for sv in session.session_views_async():
                    if new_state == "on":
                        sv.start_code_lenses_async()
                    else:
                        sv.clear_all_code_lenses()
        elif capability == "documentLinkProvider":
            for session in self.sessions():
                for sb in session.session_buffers_async():
                    if new_state == "on":
                        view = sb.some_view()
                        if view:
                            sb.do_document_link_async(view, view.change_count())
                    else:
                        sb.clear_all_document_links()
        elif capability == "colorProvider":
            for session in self.sessions():
                for sb in session.session_buffers_async():
                    if new_state == "on":
                        view = sb.some_view()
                        if view:
                            sb.do_color_boxes_async(view, view.change_count())
                    else:
                        sb.clear_all_color_boxes()
        elif capability == "semanticTokensProvider":
            for session in self.sessions():
                for sb in session.session_buffers_async():
                    if new_state == "on":
                        view = sb.some_view()
                        if view:
                            sb.do_semantic_tokens_async(view)
                    else:
                        sb.clear_semantic_token_regions()
        elif capability == "inlayHintProvider":
            for session in self.sessions():
                for sv in session.session_views_async():
                    if new_state == "on":
                        sv.session_buffer.do_inlay_hints_async(sv.view)
                    else:
                        sv.session_buffer.remove_all_inlay_hints()
        sublime.status_message("{} toggled {}".format(SERVER_CAPABILITIES[capability], new_state))

    def input(self, args: Dict[str, Any]) -> Optional[sublime_plugin.ListInputHandler]:
        if "capability" not in args:
            capabilities = set()  # type: Set[str]
            for session in self.sessions():
                for capability in SERVER_CAPABILITIES:
                    if session.has_capability(capability):
                        capabilities.add(capability)
            for capability in toggled_capabilities:
                capabilities.add(capability)
            sorted_capabilities = sorted(capabilities, key=lambda item: SERVER_CAPABILITIES[item])
            return CapabilityInputHandler(sorted_capabilities, self.last_toggled)
        return None


class CapabilityInputHandler(sublime_plugin.ListInputHandler):

    KIND_ENABLED = (sublime.KIND_ID_COLOR_GREENISH, "✓", "Enabled")
    KIND_DISABLED = (sublime.KIND_ID_COLOR_REDISH, "✗", "Disabled")

    def __init__(self, capabilities: List[str], last_toggled: Optional[str]) -> None:
        self.capabilities = capabilities
        self.last_toggled = last_toggled

    def list_items(self) -> Tuple[List[sublime.ListInputItem], int]:
        items = []  # type: List[sublime.ListInputItem]
        for capability in self.capabilities:
            kind = self.KIND_DISABLED if capability in toggled_capabilities else self.KIND_ENABLED
            items.append(sublime.ListInputItem(
                SERVER_CAPABILITIES[capability], value=capability, annotation=capability, kind=kind))
        if self.last_toggled:
            try:
                idx = self.capabilities.index(self.last_toggled)
            except ValueError:
                idx = 0
        else:
            idx = 0
        return (items, idx)
