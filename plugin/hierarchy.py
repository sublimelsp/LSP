from __future__ import annotations
from .core.constants import SYMBOL_KINDS
from .core.paths import simple_path
from .core.promise import Promise
from .core.protocol import CallHierarchyIncomingCall
from .core.protocol import CallHierarchyItem
from .core.protocol import CallHierarchyOutgoingCall
from .core.protocol import CallHierarchyPrepareParams
from .core.protocol import Error
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import TextDocumentPositionParams
from .core.protocol import TypeHierarchyItem
from .core.protocol import TypeHierarchyPrepareParams
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.tree_view import new_tree_view_sheet
from .core.tree_view import TreeDataProvider
from .core.tree_view import TreeItem
from .core.views import make_command_link
from .core.views import text_document_position_params
from abc import ABCMeta
from abc import abstractmethod
from functools import partial
from typing import Callable, TypedDict, Union
from typing import cast
import sublime
import weakref


HierarchyItem = Union[CallHierarchyItem, TypeHierarchyItem]

HierarchyItemWrapper = TypedDict('HierarchyItemWrapper', {
    'item': HierarchyItem,
    'selectionRange': Range,
})


class HierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        weaksession: weakref.ref[Session],
        request: Callable[..., Request],
        request_handler: Callable[..., list[HierarchyItemWrapper]],
        root_elements: list[HierarchyItemWrapper]
    ) -> None:
        self.weaksession = weaksession
        self.request = request
        self.request_handler = request_handler
        self.root_elements = root_elements
        session = self.weaksession()
        self.session_name = session.config.name if session else None

    def get_children(self, element: HierarchyItemWrapper | None) -> Promise[list[HierarchyItemWrapper]]:
        if element is None:
            return Promise.resolve(self.root_elements)
        session = self.weaksession()
        if not session:
            return Promise.resolve([])
        return session.send_request_task(self.request({'item': element['item']})).then(self.request_handler)

    def get_tree_item(self, element: HierarchyItemWrapper) -> TreeItem:
        item = element['item']
        selectionRange = element['selectionRange']
        command_url = sublime.command_url('lsp_open_location', {
            'location': {
                'targetUri': item['uri'],
                'targetRange': item['range'],
                'targetSelectionRange': selectionRange
            },
            'session_name': self.session_name,
            'flags': sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.SEMI_TRANSIENT | sublime.NewFileFlags.CLEAR_TO_RIGHT  # noqa: E501
        })
        path = simple_path(self.weaksession(), item['uri'])
        return TreeItem(
            item['name'],
            kind=SYMBOL_KINDS.get(item['kind'], sublime.KIND_AMBIGUOUS),
            description=item.get('detail', ''),
            tooltip="{}:{}".format(path, item['selectionRange']['start']['line'] + 1),
            command_url=command_url
        )


def make_data_provider(
    weaksession: weakref.ref[Session], sheet_name: str, direction: int, response: list[HierarchyItemWrapper]
) -> HierarchyDataProvider:
    if sheet_name == "Call Hierarchy":
        request = Request.incomingCalls if direction == 1 else Request.outgoingCalls
        handler = incoming_calls_handler if direction == 1 else outgoing_calls_handler
    elif sheet_name == "Type Hierarchy":
        request = Request.supertypes if direction == 1 else Request.subtypes
        handler = type_hierarchy_handler
    else:
        raise NotImplementedError(f'{sheet_name} not implemented')
    return HierarchyDataProvider(weaksession, request, handler, response)


def incoming_calls_handler(response: list[CallHierarchyIncomingCall] | None | Error) -> list[HierarchyItemWrapper]:
    return [
        to_hierarchy_data(call['from'], call['fromRanges'][0] if call['fromRanges'] else None) for call in response
    ] if isinstance(response, list) else []


def outgoing_calls_handler(response: list[CallHierarchyOutgoingCall] | None | Error) -> list[HierarchyItemWrapper]:
    return [to_hierarchy_data(call['to']) for call in response] if isinstance(response, list) else []


def type_hierarchy_handler(response: list[TypeHierarchyItem] | None | Error) -> list[HierarchyItemWrapper]:
    return [to_hierarchy_data(item) for item in response] if isinstance(response, list) else []


def to_hierarchy_data(
    item: CallHierarchyItem | TypeHierarchyItem, selection_range: Range | None = None
) -> HierarchyItemWrapper:
    return {
        'item': item,
        'selectionRange': selection_range or item['selectionRange'],
    }


def make_header(session_name: str, sheet_name: str, direction: int, root_elements: list[HierarchyItem]) -> str:
    if sheet_name == "Call Hierarchy":
        label = "Callers of…" if direction == 1 else "Calls from…"
        tooltip = "Show Outgoing Calls" if direction == 1 else "Show Incoming Calls"
    elif sheet_name == "Type Hierarchy":
        label = "Supertypes of…" if direction == 1 else "Subtypes of…"
        tooltip = "Show Subtypes" if direction == 1 else "Show Supertypes"
    else:
        raise NotImplementedError(f'{sheet_name} not implemented')
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
    def request(
        cls, params: TextDocumentPositionParams, view: sublime.View
    ) -> Request[list[HierarchyItem] | Error | None]:
        """ A function that generates the initial request when this command is invoked. """
        raise NotImplementedError()

    def is_visible(self, event: dict | None = None, point: int | None = None) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point)
        return True

    def run(self, edit: sublime.Edit, event: dict | None = None, point: int | None = None) -> None:
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
        self, weaksession: weakref.ref[Session], response: list[HierarchyItem] | None
    ) -> None:
        if not self._window or not self._window.is_valid():
            return
        if self.capability == 'callHierarchyProvider':
            sheet_name = "Call Hierarchy"
        elif self.capability == 'typeHierarchyProvider':
            sheet_name = "Type Hierarchy"
        else:
            raise NotImplementedError(f'{self.capability} not implemented')
        if not response:
            self._window.status_message(f"{sheet_name} not available")
            return
        session = weaksession()
        if not session:
            return
        elements = [to_hierarchy_data(item) for item in response]
        header = make_header(session.config.name, sheet_name, 1, elements)
        data_provider = make_data_provider(weaksession, sheet_name, 1, elements)
        new_tree_view_sheet(self._window, sheet_name, data_provider, header)
        open_first(self._window, session.config.name, elements)


class LspHierarchyToggleCommand(LspWindowCommand):

    def run(
        self, session_name: str, sheet_name: str, direction: int, root_elements: list[HierarchyItemWrapper]
    ) -> None:
        session = self.session_by_name(session_name)
        if not session:
            return
        header = make_header(session_name, sheet_name, direction, root_elements)
        data_provider = make_data_provider(weakref.ref(session), sheet_name, direction, root_elements)
        new_tree_view_sheet(self.window, sheet_name, data_provider, header)
        open_first(self.window, session.config.name, root_elements)


def open_first(window: sublime.Window, session_name: str, items: list[HierarchyItemWrapper]) -> None:
    if items and window.is_valid():
        item = items[0]['item']
        window.run_command('lsp_open_location', {
            'location': {
                'targetUri': item['uri'],
                'targetRange': item['range'],
                'targetSelectionRange': item['selectionRange']
            },
            'session_name': session_name,
            'flags': sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.SEMI_TRANSIENT | sublime.NewFileFlags.CLEAR_TO_RIGHT  # noqa: E501
        })


class LspCallHierarchyCommand(LspHierarchyCommand):

    capability = 'callHierarchyProvider'

    @classmethod
    def request(
        cls, params: TextDocumentPositionParams, view: sublime.View
    ) -> Request[list[CallHierarchyItem] | Error | None]:
        return Request.prepareCallHierarchy(cast(CallHierarchyPrepareParams, params), view)


class LspTypeHierarchyCommand(LspHierarchyCommand):

    capability = 'typeHierarchyProvider'

    @classmethod
    def request(
        cls, params: TextDocumentPositionParams, view: sublime.View
    ) -> Request[list[TypeHierarchyItem] | Error | None]:
        return Request.prepareTypeHierarchy(cast(TypeHierarchyPrepareParams, params), view)
