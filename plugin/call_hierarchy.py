from .core.promise import Promise
from .core.protocol import CallHierarchyIncomingCall
from .core.protocol import CallHierarchyIncomingCallsParams
from .core.protocol import CallHierarchyItem
from .core.protocol import CallHierarchyOutgoingCall
from .core.protocol import CallHierarchyOutgoingCallsParams
from .core.protocol import CallHierarchyPrepareParams
from .core.protocol import DocumentUri
from .core.protocol import Request
from .core.registry import new_tree_view_sheet
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.tree_view import TreeDataProvider
from .core.tree_view import TreeItem
from .core.typing import cast
from .core.typing import IntEnum, List, Optional
from .core.views import make_command_link
from .core.views import parse_uri
from .core.views import SYMBOL_KINDS
from .core.views import text_document_position_params
from .goto_diagnostic import simple_project_path
from functools import partial
from pathlib import Path
import sublime
import weakref


class CallHierarchyDirection(IntEnum):
    IncomingCalls = 1
    OutgoingCalls = 2


class CallHierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        weaksession: 'weakref.ref[Session]',
        direction: CallHierarchyDirection,
        root_elements: List[CallHierarchyItem]
    ) -> None:
        self.weaksession = weaksession
        self.direction = direction
        self.root_elements = root_elements
        session = self.weaksession()
        self.session_name = session.config.name if session else None

    def get_children(self, element: Optional[CallHierarchyItem]) -> Promise[List[CallHierarchyItem]]:
        if element is None:
            return Promise.resolve(self.root_elements)
        session = self.weaksession()
        if not session:
            return Promise.resolve([])
        if self.direction == CallHierarchyDirection.IncomingCalls:
            params = cast(CallHierarchyIncomingCallsParams, {'item': element})
            return session.send_request_task(Request.incomingCalls(params)).then(self._handle_incoming_calls_async)
        elif self.direction == CallHierarchyDirection.OutgoingCalls:
            params = cast(CallHierarchyOutgoingCallsParams, {'item': element})
            return session.send_request_task(Request.outgoingCalls(params)).then(self._handle_outgoing_calls_async)
        return Promise.resolve([])

    def get_tree_item(self, element: CallHierarchyItem) -> TreeItem:
        command_url = sublime.command_url('lsp_open_location', {
            'location': {
                'targetUri': element['uri'],
                'targetRange': element['range'],
                'targetSelectionRange': element['selectionRange']
            },
            'session_name': self.session_name,
            'flags': sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT | sublime.CLEAR_TO_RIGHT
        })
        return TreeItem(
            element['name'],
            kind=SYMBOL_KINDS.get(element['kind'], sublime.KIND_AMBIGUOUS),
            description=element.get('detail', ""),
            tooltip="{}:{}".format(self._simple_path(element['uri']), element['selectionRange']['start']['line'] + 1),
            command_url=command_url
        )

    def _simple_path(self, uri: DocumentUri) -> str:
        scheme, path = parse_uri(uri)
        session = self.weaksession()
        if not session or scheme != 'file':
            return path
        simple_path = simple_project_path([Path(folder.path) for folder in session.get_workspace_folders()], Path(path))
        return str(simple_path) if simple_path else path

    def _handle_incoming_calls_async(
        self, response: Optional[List[CallHierarchyIncomingCall]]
    ) -> List[CallHierarchyItem]:
        return [incoming_call['from'] for incoming_call in response] if response else []

    def _handle_outgoing_calls_async(
        self, response: Optional[List[CallHierarchyOutgoingCall]]
    ) -> List[CallHierarchyItem]:
        return [outgoing_call['to'] for outgoing_call in response] if response else []


class LspCallHierarchyCommand(LspTextCommand):

    capability = 'callHierarchyProvider'

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
        params = cast(CallHierarchyPrepareParams, text_document_position_params(self.view, position))
        request = Request.prepareCallHierarchy(params, self.view)
        session.send_request_async(request, partial(self._handle_response_async, weakref.ref(session)))

    def _handle_response_async(
        self, weaksession: 'weakref.ref[Session]', response: Optional[List[CallHierarchyItem]]
    ) -> None:
        if not self._window or not self._window.is_valid():
            return
        if not response:
            self._window.status_message("Call hierarchy not available")
            return
        session = weaksession()
        if not session:
            return
        data_provider = CallHierarchyDataProvider(weaksession, CallHierarchyDirection.IncomingCalls, response)
        header = 'Call Hierarchy: Callers of… {}'.format(
            make_command_link('lsp_call_hierarchy_toggle', "⇄", {
                'session_name': session.config.name,
                'direction': CallHierarchyDirection.OutgoingCalls,
                'root_elements': response
            }, tooltip="Show outgoing calls"))
        new_tree_view_sheet(self._window, "Call Hierarchy", data_provider, header)
        data_provider.get_children(None).then(partial(open_first, self._window, session.config.name))


class LspCallHierarchyToggleCommand(LspWindowCommand):

    capability = 'callHierarchyProvider'

    def run(
        self, session_name: str, direction: CallHierarchyDirection, root_elements: List[CallHierarchyItem]
    ) -> None:
        session = self.session_by_name(session_name)
        if not session:
            return
        if direction == CallHierarchyDirection.IncomingCalls:
            current_label = 'Callers of…'
            new_direction = CallHierarchyDirection.OutgoingCalls
            tooltip = 'Show Outgoing Calls'
        elif direction == CallHierarchyDirection.OutgoingCalls:
            current_label = 'Calls from…'
            new_direction = CallHierarchyDirection.IncomingCalls
            tooltip = 'Show Incoming Calls'
        else:
            return
        header = 'Call Hierarchy: {} {}'.format(
            current_label, make_command_link('lsp_call_hierarchy_toggle', "⇄", {
                'session_name': session_name,
                'direction': new_direction,
                'root_elements': root_elements
            }, tooltip=tooltip))
        data_provider = CallHierarchyDataProvider(weakref.ref(session), direction, root_elements)
        new_tree_view_sheet(self.window, "Call Hierarchy", data_provider, header)
        data_provider.get_children(None).then(partial(open_first, self.window, session.config.name))


def open_first(window: sublime.Window, session_name: str, items: List[CallHierarchyItem]) -> None:
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
