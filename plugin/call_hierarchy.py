from .core.promise import Promise
from .core.protocol import CallHierarchyIncomingCall
from .core.protocol import CallHierarchyIncomingCallsParams
from .core.protocol import CallHierarchyItem
from .core.protocol import CallHierarchyOutgoingCall
from .core.protocol import CallHierarchyOutgoingCallsParams
from .core.protocol import CallHierarchyPrepareParams
from .core.protocol import Request
from .core.registry import windows
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.tree_view import new_tree_view_sheet
from .core.tree_view import TreeDataProvider
from .core.tree_view import TreeItem
from .core.typing import cast
from .core.typing import IntEnum, List, Optional
from .core.views import SYMBOL_KINDS
from .core.views import text_document_position_params
from functools import partial
import sublime


class CallHierarchyType(IntEnum):
    IncomingCalls = 1
    OutgoingCalls = 2


class CallHierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        window: sublime.Window,
        session_name: str,
        call_hierarchy_type: CallHierarchyType,
        root_elements: List[CallHierarchyItem]
    ) -> None:
        self.window = window
        self.session_name = session_name
        self.call_hierarchy_type = call_hierarchy_type
        self.root_elements = root_elements

    def get_children(self, element: Optional[CallHierarchyItem]) -> Promise[List[CallHierarchyItem]]:
        # print("get_children", element)
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
        if self.call_hierarchy_type == CallHierarchyType.IncomingCalls:
            params = cast(CallHierarchyIncomingCallsParams, {'item': element})
            return session.send_request_task(Request.incomingCalls(params)).then(self._handle_incoming_calls_async)
        elif self.call_hierarchy_type == CallHierarchyType.OutgoingCalls:
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
            'session_name': self.session_name
        })
        return TreeItem(
            element['name'],
            kind=SYMBOL_KINDS.get(element['kind'], sublime.KIND_AMBIGUOUS),
            description=element.get('detail', ""),
            tooltip="Open source location",
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
        data_provider = CallHierarchyDataProvider(self._window, session_name, CallHierarchyType.IncomingCalls, response)
        new_tree_view_sheet(
            self._window,
            "Call Hierarchy",
            data_provider,
            header="Call Hierarchy: Incoming Calls",
            flags=sublime.ADD_TO_SELECTION)
