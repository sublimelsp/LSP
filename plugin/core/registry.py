from .paths import simple_path
from .promise import Promise
from .protocol import CallHierarchyItem
from .protocol import CallHierarchyPrepareParams
from .protocol import Diagnostic
from .protocol import Location
from .protocol import LocationLink
from .protocol import Point
from .protocol import Request
from .protocol import TextDocumentPositionParams
from .protocol import TypeHierarchyItem
from .protocol import TypeHierarchyPrepareParams
from .sessions import AbstractViewListener
from .sessions import Session
from .tree_view import TreeDataProvider
from .tree_view import TreeItem
from .tree_view import TreeViewSheet
from .typing import Callable, Optional, Any, Generator, Iterable, List, Union
from .typing import cast
from .views import first_selection_region
from .views import get_uri_and_position_from_location
from .views import make_command_link
from .views import MissingUriError
from .views import point_to_offset
from .views import SYMBOL_KINDS
from .views import text_document_position_params
from .views import uri_from_view
from .windows import WindowManager
from .windows import WindowRegistry
from abc import ABCMeta
from abc import abstractmethod
from functools import partial
import operator
import sublime
import sublime_api  # pyright: ignore[reportMissingImports]
import sublime_plugin
import weakref


windows = WindowRegistry()


def new_tree_view_sheet(
    window: sublime.Window,
    name: str,
    data_provider: TreeDataProvider,
    header: str = "",
    flags: int = 0,
    group: int = -1
) -> Optional[TreeViewSheet]:
    """
    Use this function to create a new TreeView in form of a special HtmlSheet (TreeViewSheet). Only one TreeViewSheet
    with the given name is allowed per window. If there already exists a TreeViewSheet with the same name, its content
    will be replaced with the new data. The header argument is allowed to contain minihtml markup.
    """
    wm = windows.lookup(window)
    if not wm:
        return None
    if name in wm.tree_view_sheets:
        tree_view_sheet = wm.tree_view_sheets[name]
        sheet_id = tree_view_sheet.id()
        if tree_view_sheet.window():
            tree_view_sheet.set_provider(data_provider, header)
            if flags & sublime.ADD_TO_SELECTION:
                # add to selected sheets if not already selected
                selected_sheets = window.selected_sheets()
                for sheet in window.sheets():
                    if isinstance(sheet, sublime.HtmlSheet) and sheet.id() == sheet_id:
                        if sheet not in selected_sheets:
                            selected_sheets.append(sheet)
                            window.select_sheets(selected_sheets)
                        break
            else:
                window.focus_sheet(tree_view_sheet)
            return tree_view_sheet
    tree_view_sheet = TreeViewSheet(
        sublime_api.window_new_html_sheet(window.window_id, name, "", flags, group),
        name,
        data_provider,
        header
    )
    wm.tree_view_sheets[name] = tree_view_sheet
    return tree_view_sheet


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
        wm = windows.lookup(self.window)
        if not wm:
            return None
        for session in wm.get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            if self.session_name and session.config.name != self.session_name:
                continue
            return session
        else:
            return None

    def session_by_name(self, session_name: str) -> Optional[Session]:
        wm = windows.lookup(self.window)
        if not wm:
            return None
        for session in wm.get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            if session.config.name == session_name:
                return session
        else:
            return None


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

    @staticmethod
    def applies_to_context_menu(event: Optional[dict]) -> bool:
        return event is not None and 'x' in event

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


class LspOpenLocationCommand(LspWindowCommand):
    """
    A command to be used by third-party ST packages that need to open an URI with some abstract scheme.
    """

    def run(
        self,
        location: Union[Location, LocationLink],
        session_name: Optional[str] = None,
        flags: int = 0,
        group: int = -1,
        event: Optional[dict] = None
    ) -> None:
        if event:
            modifier_keys = event.get('modifier_keys')
            if modifier_keys:
                if 'primary' in modifier_keys:
                    flags |= sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT | sublime.CLEAR_TO_RIGHT
                elif 'shift' in modifier_keys:
                    flags |= sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT
        sublime.set_timeout_async(lambda: self._run_async(location, session_name, flags, group))

    def want_event(self) -> bool:
        return True

    def _run_async(
        self, location: Union[Location, LocationLink], session_name: Optional[str], flags: int, group: int
    ) -> None:
        session = self.session_by_name(session_name) if session_name else self.session()
        if session:
            session.open_location_async(location, flags, group) \
                .then(lambda view: self._handle_continuation(location, view is not None))

    def _handle_continuation(self, location: Union[Location, LocationLink], success: bool) -> None:
        if not success:
            uri, _ = get_uri_and_position_from_location(location)
            message = "Failed to open {}".format(uri)
            sublime.status_message(message)


class LspRestartServerCommand(LspTextCommand):

    def run(self, edit: Any, config_name: Optional[str] = None) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        self._config_names = [session.config.name for session in self.sessions()] if not config_name else [config_name]
        if not self._config_names:
            return
        if len(self._config_names) == 1:
            self.restart_server(wm, 0)
        else:
            wm.window.show_quick_panel(self._config_names, partial(self.restart_server, wm))

    def restart_server(self, wm: WindowManager, index: int) -> None:
        if index == -1:
            return

        def run_async() -> None:
            config_name = self._config_names[index]
            if config_name:
                wm.restart_sessions_async(config_name)

        sublime.set_timeout_async(run_async)


class LspRecheckSessionsCommand(sublime_plugin.WindowCommand):
    def run(self, config_name: Optional[str] = None) -> None:

        def run_async() -> None:
            wm = windows.lookup(self.window)
            if wm:
                wm.restart_sessions_async(config_name)

        sublime.set_timeout_async(run_async)


def navigate_diagnostics(view: sublime.View, point: Optional[int], forward: bool = True) -> None:
    try:
        uri = uri_from_view(view)
    except MissingUriError:
        return
    wm = windows.lookup(view.window())
    if not wm:
        return
    diagnostics = []  # type: List[Diagnostic]
    for session in wm.get_sessions():
        diagnostics.extend(session.diagnostics.diagnostics_by_document_uri(uri))
    if not diagnostics:
        return
    # Sort diagnostics by location
    diagnostics.sort(key=lambda d: operator.itemgetter('line', 'character')(d['range']['start']), reverse=not forward)
    if point is None:
        region = first_selection_region(view)
        point = region.b if region is not None else 0
    # Find next/previous diagnostic or wrap around and jump to the first/last one, if there are no more diagnostics in
    # this view after/before the cursor
    op_func = operator.gt if forward else operator.lt
    for diagnostic in diagnostics:
        diag_pos = point_to_offset(Point.from_lsp(diagnostic['range']['start']), view)
        if op_func(diag_pos, point):
            break
    else:
        diag_pos = point_to_offset(Point.from_lsp(diagnostics[0]['range']['start']), view)
    view.run_command('lsp_selection_set', {'regions': [(diag_pos, diag_pos)]})
    view.show_at_center(diag_pos)
    # We need a small delay before showing the popup to wait for the scrolling animation to finish. Otherwise ST would
    # immediately hide the popup.
    sublime.set_timeout_async(lambda: view.run_command('lsp_hover', {'only_diagnostics': True, 'point': diag_pos}), 200)


class LspNextDiagnosticCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, point: Optional[int] = None) -> None:
        navigate_diagnostics(self.view, point, forward=True)


class LspPrevDiagnosticCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, point: Optional[int] = None) -> None:
        navigate_diagnostics(self.view, point, forward=False)


def toggle_tree_item(window: sublime.Window, name: str, id: str, expand: bool) -> None:
    wm = windows.lookup(window)
    if not wm:
        return
    sheet = wm.tree_view_sheets.get(name)
    if not sheet:
        return
    if expand:
        sheet.expand_item(id)
    else:
        sheet.collapse_item(id)


class LspExpandTreeItemCommand(LspWindowCommand):

    def run(self, name: str, id: str) -> None:
        toggle_tree_item(self.window, name, id, True)


class LspCollapseTreeItemCommand(LspWindowCommand):

    def run(self, name: str, id: str) -> None:
        toggle_tree_item(self.window, name, id, False)


HierarchyItem = Union[CallHierarchyItem, TypeHierarchyItem]


class HierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        weaksession: 'weakref.ref[Session]',
        request1: Callable[..., Request],
        request2: Callable[..., Request],
        request_handler1: Callable[..., List[HierarchyItem]],
        request_handler2: Callable[..., List[HierarchyItem]],
        direction: int,
        root_elements: List[HierarchyItem]
    ) -> None:
        self.weaksession = weaksession
        self.request1 = request1
        self.request2 = request2
        self.request_handler1 = request_handler1
        self.request_handler2 = request_handler2
        self.direction = direction
        self.root_elements = root_elements
        session = self.weaksession()
        self.session_name = session.config.name if session else None

    def get_children(self, element: Optional[HierarchyItem]) -> Promise[List[HierarchyItem]]:
        if element is None:
            return Promise.resolve(self.root_elements)
        session = self.weaksession()
        if not session:
            return Promise.resolve([])
        if self.direction == 1:
            return session.send_request_task(self.request1({'item': element})).then(self.request_handler1)
        if self.direction == 2:
            return session.send_request_task(self.request2({'item': element})).then(self.request_handler2)
        return Promise.resolve([])

    def get_tree_item(self, element: HierarchyItem) -> TreeItem:
        command_url = sublime.command_url('lsp_open_location', {
            'location': {
                'targetUri': element['uri'],
                'targetRange': element['range'],
                'targetSelectionRange': element['selectionRange']
            },
            'session_name': self.session_name,
            'flags': sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT | sublime.CLEAR_TO_RIGHT
        })
        path = simple_path(self.weaksession(), element['uri'])
        return TreeItem(
            element['name'],
            kind=SYMBOL_KINDS.get(element['kind'], sublime.KIND_AMBIGUOUS),
            description=element.get('detail', ""),
            tooltip="{}:{}".format(path, element['selectionRange']['start']['line'] + 1),
            command_url=command_url
        )


def make_data_provider(
    weaksession: 'weakref.ref[Session]', sheet_name: str, direction: int, response: List[HierarchyItem]
) -> HierarchyDataProvider:
    if sheet_name == "Call Hierarchy":
        request1 = Request.incomingCalls
        request2 = Request.outgoingCalls
        handler1 = lambda response: [incoming_call['from'] for incoming_call in response] if isinstance(response, list) else []  # noqa: E501,E731
        handler2 = lambda response: [outgoing_call['to'] for outgoing_call in response] if isinstance(response, list) else []  # noqa: E501,E731
    elif sheet_name == "Type Hierarchy":
        request1 = Request.supertypes
        request2 = Request.subtypes
        handler1 = handler2 = lambda response: response if isinstance(response, list) else []  # noqa: E731
    else:
        raise NotImplementedError('{} not implemented'.format(sheet_name))
    return HierarchyDataProvider(weaksession, request1, request2, handler1, handler2, direction, response)


def make_header(session_name: str, sheet_name: str, direction: int, root_elements: List[HierarchyItem]) -> str:
    if sheet_name == "Call Hierarchy":
        label = "Callers of…" if direction == 1 else "Calls from…"
        tooltip = "Show outgoing calls" if direction == 1 else "Show Incoming Calls"
    elif sheet_name == "Type Hierarchy":
        label = "Supertypes of…" if direction == 1 else "Subtypes of…"
        tooltip = "Show Subtypes" if direction == 1 else "Show Supertypes"
    else:
        raise NotImplementedError('{} not implemented'.format(sheet_name))
    new_direction = 2 if direction == 1 else 1
    return '{}: {} {}'.format(sheet_name, label, make_command_link('lsp_hierarchy_toggle', "⇄", {
            'session_name': session_name,
            'sheet_name': sheet_name,
            'direction': new_direction,
            'root_elements': root_elements
        }, tooltip=tooltip))


class LspHierarchyCommand(LspTextCommand, metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def request(cls, params: TextDocumentPositionParams, view: sublime.View) -> Request:
        """ A function that generates the initial request when this command is invoked. """
        raise NotImplementedError()

    def is_visible(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point)
        return True

    def run(self, edit: sublime.Edit, event: Optional[dict] = None, point: Optional[int] = None) -> None:
        self._window = self.view.window()
        session = self.best_session(self.capability)
        if not session:
            return
        position = get_position(self.view, event, point)
        if position is None:
            return
        params = text_document_position_params(self.view, position)
        session.send_request_async(
            self.request(params, self.view), partial(self._handle_response_async, weakref.ref(session)))

    def _handle_response_async(
        self, weaksession: 'weakref.ref[Session]', response: Optional[List[HierarchyItem]]
    ) -> None:
        if not self._window or not self._window.is_valid():
            return
        if self.capability == 'callHierarchyProvider':
            sheet_name = "Call Hierarchy"
        elif self.capability == 'typeHierarchyProvider':
            sheet_name = "Type Hierarchy"
        else:
            raise NotImplementedError('{} not implemented'.format(self.capability))
        if not response:
            self._window.status_message("{} not available".format(sheet_name))
            return
        session = weaksession()
        if not session:
            return
        header = make_header(session.config.name, sheet_name, 1, response)
        data_provider = make_data_provider(weaksession, sheet_name, 1, response)
        new_tree_view_sheet(self._window, sheet_name, data_provider, header)
        open_first(self._window, session.config.name, response)


class LspHierarchyToggleCommand(LspWindowCommand):

    def run(
        self, session_name: str, sheet_name: str, direction: int, root_elements: List[HierarchyItem]
    ) -> None:
        session = self.session_by_name(session_name)
        if not session:
            return
        header = make_header(session_name, sheet_name, direction, root_elements)
        data_provider = make_data_provider(weakref.ref(session), sheet_name, direction, root_elements)
        new_tree_view_sheet(self.window, sheet_name, data_provider, header)
        open_first(self.window, session.config.name, root_elements)


def open_first(window: sublime.Window, session_name: str, items: List[HierarchyItem]) -> None:
    if items and window.is_valid():
        item = items[0]
        window.run_command('lsp_open_location', {
            'location': {
                'targetUri': item['uri'],
                'targetRange': item['range'],
                'targetSelectionRange': item['selectionRange']
            },
            'session_name': session_name,
            'flags': sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT | sublime.CLEAR_TO_RIGHT
        })


class LspCallHierarchyCommand(LspHierarchyCommand):

    capability = 'callHierarchyProvider'

    @classmethod
    def request(cls, params: TextDocumentPositionParams, view: sublime.View) -> Request:
        return Request.prepareCallHierarchy(cast(CallHierarchyPrepareParams, params), view)


class LspTypeHierarchyCommand(LspHierarchyCommand):

    capability = 'typeHierarchyProvider'

    @classmethod
    def request(cls, params: TextDocumentPositionParams, view: sublime.View) -> Request:
        return Request.prepareTypeHierarchy(cast(TypeHierarchyPrepareParams, params), view)
