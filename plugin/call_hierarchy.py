from .core.promise import Promise
from .core.protocol import CallHierarchyIncomingCall
from .core.protocol import CallHierarchyIncomingCallsParams
from .core.protocol import CallHierarchyItem
from .core.protocol import CallHierarchyOutgoingCall
from .core.protocol import CallHierarchyOutgoingCallsParams
from .core.protocol import CallHierarchyPrepareParams
from .core.protocol import Request
from .core.registry import new_tree_view_sheet
from .core.registry import windows
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.tree_view import TreeDataProvider
from .core.tree_view import TreeItem
from .core.typing import cast
from .core.typing import IntEnum, List, Optional
from .core.views import parse_uri
from .core.views import SYMBOL_KINDS
from .core.views import text_document_position_params
from functools import partial
import sublime


class CallHierarchyDirection(IntEnum):
    IncomingCalls = 1
    OutgoingCalls = 2


class CallHierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        window: sublime.Window,
        session_name: str,
        direction: CallHierarchyDirection,
        root_elements: List[CallHierarchyItem]
    ) -> None:
        self.window = window
        self.session_name = session_name
        self.direction = direction
        self.root_elements = root_elements

    def get_children(self, element: Optional[CallHierarchyItem]) -> Promise[List[CallHierarchyItem]]:
        if element is None:
            return Promise.resolve(self.root_elements)
        wm = windows.lookup(self.window)
        if not wm:
            return Promise.resolve([])
        for session in wm.get_sessions():
            if not session.has_capability('callHierarchyProvider'):
                continue
            if session.config.name == self.session_name:
                break
        else:
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
            'flags': sublime.SEMI_TRANSIENT | sublime.ADD_TO_SELECTION
        })
        return TreeItem(
            element['name'],
            kind=SYMBOL_KINDS.get(element['kind'], sublime.KIND_AMBIGUOUS),
            description=element.get('detail', ""),
            tooltip="{}:{}".format(parse_uri(element['uri'])[1], element['selectionRange']['start']['line'] + 1),
            command_url=command_url
        )

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
        session.send_request_async(request, partial(self._handle_response_async, session.config.name))

    def _handle_response_async(self, session_name: str, response: Optional[List[CallHierarchyItem]]) -> None:
        if not self._window or not self._window.is_valid():
            return
        if not response:
            self._window.status_message("Call hierarchy not available")
            return
        data_provider = CallHierarchyDataProvider(
            self._window, session_name, CallHierarchyDirection.IncomingCalls, response)
        header = 'Call Hierarchy: Callers of… <a href="{}" title="Show outgoing calls">&#8644;</a>'.format(
            make_toggle_command(session_name, CallHierarchyDirection.OutgoingCalls, response))
        new_tree_view_sheet(self._window, "Call Hierarchy", data_provider, header, flags=sublime.ADD_TO_SELECTION)


class LspCallHierarchyToggleCommand(LspWindowCommand):

    capability = 'callHierarchyProvider'

    def run(
        self, session_name: str, direction: CallHierarchyDirection, root_elements: List[CallHierarchyItem]
    ) -> None:
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
        header = 'Call Hierarchy: {} <a href="{}" title="{}">&#8644;</a>'.format(
            current_label, make_toggle_command(session_name, new_direction, root_elements), tooltip)
        data_provider = CallHierarchyDataProvider(self.window, session_name, direction, root_elements)
        new_tree_view_sheet(self.window, "Call Hierarchy", data_provider, header, flags=sublime.ADD_TO_SELECTION)


def make_toggle_command(
    session_name: str, direction: CallHierarchyDirection, root_elements: List[CallHierarchyItem]
) -> str:
    return sublime.command_url('lsp_call_hierarchy_toggle', {
        'session_name': session_name,
        'call_hierarchy_type': direction,
        'root_elements': root_elements
    })
