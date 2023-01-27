from .core.paths import simple_path
from .core.promise import Promise
from .core.protocol import TypeHierarchyItem
from .core.protocol import TypeHierarchyPrepareParams
from .core.protocol import TypeHierarchySubtypesParams
from .core.protocol import TypeHierarchySupertypesParams
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
from .core.views import SYMBOL_KINDS
from .core.views import text_document_position_params
from functools import partial
import sublime
import weakref


class TypeHierarchyDirection(IntEnum):
    Supertypes = 1
    Subtypes = 2


class TypeHierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        weaksession: 'weakref.ref[Session]',
        direction: TypeHierarchyDirection,
        root_elements: List[TypeHierarchyItem]
    ) -> None:
        self.weaksession = weaksession
        self.direction = direction
        self.root_elements = root_elements
        session = self.weaksession()
        self.session_name = session.config.name if session else None

    def get_children(self, element: Optional[TypeHierarchyItem]) -> Promise[List[TypeHierarchyItem]]:
        if element is None:
            return Promise.resolve(self.root_elements)
        session = self.weaksession()
        if not session:
            return Promise.resolve([])
        if self.direction == TypeHierarchyDirection.Supertypes:
            params = cast(TypeHierarchySupertypesParams, {'item': element})
            return session.send_request_task(Request.supertypes(params)).then(self._ensure_list)
        elif self.direction == TypeHierarchyDirection.Subtypes:
            params = cast(TypeHierarchySubtypesParams, {'item': element})
            return session.send_request_task(Request.subtypes(params)).then(self._ensure_list)
        return Promise.resolve([])

    def get_tree_item(self, element: TypeHierarchyItem) -> TreeItem:
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

    def _ensure_list(self, response: Optional[List[TypeHierarchyItem]]) -> List[TypeHierarchyItem]:
        return response or []


class LspTypeHierarchyCommand(LspTextCommand):

    capability = 'typeHierarchyProvider'

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
        params = cast(TypeHierarchyPrepareParams, text_document_position_params(self.view, position))
        request = Request.prepareTypeHierarchy(params, self.view)
        session.send_request_async(request, partial(self._handle_response_async, weakref.ref(session)))

    def _handle_response_async(
        self, weaksession: 'weakref.ref[Session]', response: Optional[List[TypeHierarchyItem]]
    ) -> None:
        if not self._window or not self._window.is_valid():
            return
        if not response:
            self._window.status_message("Type hierarchy not available")
            return
        session = weaksession()
        if not session:
            return
        data_provider = TypeHierarchyDataProvider(weaksession, TypeHierarchyDirection.Supertypes, response)
        header = 'Type Hierarchy: Supertypes of… {}'.format(
            make_command_link('lsp_type_hierarchy_toggle', "⇄", {
                'session_name': session.config.name,
                'direction': TypeHierarchyDirection.Subtypes,
                'root_elements': response
            }, tooltip="Show subtypes"))
        new_tree_view_sheet(self._window, "Type Hierarchy", data_provider, header)
        data_provider.get_children(None).then(partial(open_first, self._window, session.config.name))


class LspTypeHierarchyToggleCommand(LspWindowCommand):

    capability = 'typeHierarchyProvider'

    def run(
        self, session_name: str, direction: TypeHierarchyDirection, root_elements: List[TypeHierarchyItem]
    ) -> None:
        session = self.session_by_name(session_name)
        if not session:
            return
        if direction == TypeHierarchyDirection.Supertypes:
            current_label = 'Supertypes of…'
            new_direction = TypeHierarchyDirection.Subtypes
            tooltip = 'Show Subtypes'
        elif direction == TypeHierarchyDirection.Subtypes:
            current_label = 'Subtypes of…'
            new_direction = TypeHierarchyDirection.Supertypes
            tooltip = 'Show Supertypes'
        else:
            return
        header = 'Type Hierarchy: {} {}'.format(
            current_label, make_command_link('lsp_type_hierarchy_toggle', "⇄", {
                'session_name': session_name,
                'direction': new_direction,
                'root_elements': root_elements
            }, tooltip=tooltip))
        data_provider = TypeHierarchyDataProvider(weakref.ref(session), direction, root_elements)
        new_tree_view_sheet(self.window, "Type Hierarchy", data_provider, header)
        data_provider.get_children(None).then(partial(open_first, self.window, session.config.name))


def open_first(window: sublime.Window, session_name: str, items: List[TypeHierarchyItem]) -> None:
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
