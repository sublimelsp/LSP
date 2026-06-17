from __future__ import annotations

from .css import css
from .promise import Promise
from .registry import windows
from abc import ABC
from abc import abstractmethod
from enum import IntEnum
from functools import partial
from typing import Any
from typing import Literal
from typing import TYPE_CHECKING
from typing import TypeVar
import html
import sublime
import sublime_api  # pyright: ignore[reportMissingImports]
import sublime_plugin
import uuid

if TYPE_CHECKING:
    from .constants import SublimeKind

# pyright: reportInvalidTypeVarUse=false
T = TypeVar('T')

TreeViewAction = Literal['move_up', 'move_right', 'move_down', 'move_left', 'close', 'activate']

KIND_CLASS_NAMES: dict[int, str] = {
    sublime.KindId.KEYWORD: 'kind kind_keyword',
    sublime.KindId.TYPE: 'kind kind_type',
    sublime.KindId.FUNCTION: 'kind kind_function',
    sublime.KindId.NAMESPACE: 'kind kind_namespace',
    sublime.KindId.NAVIGATION: 'kind kind_navigation',
    sublime.KindId.MARKUP: 'kind kind_markup',
    sublime.KindId.VARIABLE: 'kind kind_variable',
    sublime.KindId.SNIPPET: 'kind kind_snippet'
}


class TreeItemCollapsibleState(IntEnum):
    NONE = 1
    COLLAPSED = 2
    EXPANDED = 3


class TreeItem:

    def __init__(
        self,
        label: str,
        kind: SublimeKind = sublime.KIND_AMBIGUOUS,
        description: str = "",
        tooltip: str = "",
        action_command: tuple[str, dict[str, Any]] | None = None,
    ) -> None:
        self.label = label
        """ A human-readable string describing this item. """
        self.kind = kind
        """ A sublime.Kind tuple which is rendered as icon in front of the label. """
        self.description = description
        """ A human-readable string which is rendered less prominent. """
        self.tooltip = tooltip
        """ The tooltip text when you hover over this item. """
        self.action_command = action_command
        """ The command and its arguments to be executed when the tree item label is clicked. """
        self.collapsible_state = TreeItemCollapsibleState.COLLAPSED
        self.id = str(uuid.uuid4())

    def html(self, sheet_name: str, indent_level: int, is_active: bool = False) -> str:
        indent_html = f'<span style="padding-left: {indent_level}rem;">&nbsp;</span>'
        if self.collapsible_state == TreeItemCollapsibleState.COLLAPSED:
            disclosure_button_html = '<a class="disclosure-button" href="{}">▶</a>'.format(
                sublime.command_url('lsp_expand_tree_item', {'name': sheet_name, 'node_id': self.id}))
        elif self.collapsible_state == TreeItemCollapsibleState.EXPANDED:
            disclosure_button_html = '<a class="disclosure-button" href="{}">▼</a>'.format(
                sublime.command_url('lsp_collapse_tree_item', {'name': sheet_name, 'node_id': self.id}))
        else:
            disclosure_button_html = '<span class="disclosure-button">&nbsp;</span>'
        kind_class_name = KIND_CLASS_NAMES.get(self.kind[0], 'kind kind_ambiguous')
        icon_html = '<span class="{}" title="{}">{}</span>'.format(
            kind_class_name, self.kind[2], self.kind[1] or '&nbsp;')
        escaped_tooltip = html.escape(self.tooltip)
        escaped_label = html.escape(self.label)
        command_url = (
            sublime.command_url('lsp_activate_tree_item', {'name': sheet_name, 'node_id': self.id})
            if self.action_command else None
        )
        if command_url and self.tooltip:
            label_html = f'<a class="label" href="{command_url}" title="{escaped_tooltip}">{escaped_label}</a>'
        elif command_url:
            label_html = f'<a class="label" href="{command_url}">{escaped_label}</a>'
        elif self.tooltip:
            label_html = f'<span class="label" title="{escaped_tooltip}">{escaped_label}</span>'
        else:
            label_html = f'<span class="label">{escaped_label}</span>'
        if is_active:
            label_html = f'<span class="active">{label_html}</span>'
        description_html = f'<span class="description">{html.escape(self.description)}</span>' if \
            self.description else ''
        content = indent_html + disclosure_button_html + icon_html + label_html + description_html
        return f'<div class="tree-view-row">{content}</div>'


class Node:

    __slots__ = ('element', 'tree_item', 'parent_node_id', 'indent_level', 'child_ids', 'is_resolved')

    def __init__(self, element: T, tree_item: TreeItem, parent_node_id: str | None, indent_level: int = 0) -> None:
        self.element = element
        self.tree_item = tree_item
        self.parent_node_id = parent_node_id
        self.indent_level = indent_level
        self.child_ids: list[str] = []
        self.is_resolved = False


class TreeDataProvider(ABC):

    @abstractmethod
    def get_children(self, element: T | None) -> Promise[list[T]]:
        """Implement this to return the children for the given element or root (if no element is passed)."""
        raise NotImplementedError

    @abstractmethod
    def get_tree_item(self, element: T) -> TreeItem:
        """
        Implement this to return the UI representation (TreeItem) of the element that gets displayed in the
        TreeViewSheet.
        """
        raise NotImplementedError


class TreeViewSheet(sublime.HtmlSheet):
    """A special HtmlSheet which can render interactive tree data structures."""

    def __init__(self, sheet_id: int, name: str, data_provider: TreeDataProvider, header: str = "") -> None:
        super().__init__(sheet_id)
        self.nodes: dict[str, Node] = {}
        self.selected_node_id: str | None = None
        self.ordered_node_ids: list[str] = []
        self.root_nodes: list[str] = []
        self.name = name
        self.data_provider = data_provider
        self.header = header
        self.data_provider.get_children(None).then(self._set_root_nodes)

    def __repr__(self) -> str:
        return f'TreeViewSheet({self.sheet_id!r})'

    def set_provider(self, data_provider: TreeDataProvider, header: str = "") -> None:
        """
        Use this method if you want to render an entire new tree. This allows to reuse a single HtmlSheet, e.g. when
        using a feature consecutively on different symbols.
        """
        self.nodes.clear()
        self.root_nodes.clear()
        self.data_provider = data_provider
        self.header = header
        self.data_provider.get_children(None).then(self._set_root_nodes)

    def _set_root_nodes(self, elements: list[T]) -> None:
        promises: list[Promise[None]] = []
        for element in elements:
            tree_item = self.data_provider.get_tree_item(element)
            tree_item.collapsible_state = TreeItemCollapsibleState.EXPANDED
            self.nodes[tree_item.id] = Node(element, tree_item, parent_node_id=None)
            self.root_nodes.append(tree_item.id)
            promises.append(self.data_provider.get_children(element).then(partial(self._add_children, tree_item.id)))
        if self.root_nodes:
            self.selected_node_id = self.root_nodes[0]
        Promise.all(promises).then(lambda _: self._update_contents())

    def _add_children(self, node_id: str, elements: list[T]) -> None:
        assert node_id in self.nodes
        node = self.nodes[node_id]
        for element in elements:
            tree_item = self.data_provider.get_tree_item(element)
            self.nodes[tree_item.id] = Node(element, tree_item, node_id, node.indent_level + 1)
            node.child_ids.append(tree_item.id)
        if len(elements) == 0:
            node.tree_item.collapsible_state = TreeItemCollapsibleState.NONE
        node.is_resolved = True

    def _resolve_children(self, node_id: str) -> None:
        assert node_id in self.nodes
        node = self.nodes[node_id]
        self.data_provider.get_children(node.element) \
            .then(partial(self._add_children, node_id)) \
            .then(lambda _: self._update_contents())

    def handle_action(self, action: TreeViewAction) -> None:
        if action == 'close':
            self.close()
            return
        if not self.selected_node_id or not (selected_node := self.nodes[self.selected_node_id]):
            return
        if action == 'move_down':
            current_index = self.ordered_node_ids.index(self.selected_node_id)
            next_index = min(len(self.ordered_node_ids) - 1, current_index + 1)
            if current_index == next_index:
                return
            next_node_id = self.ordered_node_ids[next_index]
            self.select_item(next_node_id)
        elif action == 'move_up':
            current_index = self.ordered_node_ids.index(self.selected_node_id)
            previous_index = max(0, current_index - 1)
            if current_index == previous_index:
                return
            previous_node_id = self.ordered_node_ids[previous_index]
            self.select_item(previous_node_id)
        elif action == 'move_left':
            if selected_node.tree_item.collapsible_state == TreeItemCollapsibleState.EXPANDED:
                self.collapse_item(self.selected_node_id)
            elif selected_node.parent_node_id and selected_node.tree_item.collapsible_state in {
                TreeItemCollapsibleState.COLLAPSED,
                TreeItemCollapsibleState.NONE
            }:
                self.select_item(selected_node.parent_node_id)
        elif action == 'move_right':
            if selected_node.tree_item.collapsible_state == TreeItemCollapsibleState.COLLAPSED:
                self.expand_item(self.selected_node_id)
        elif action == 'activate':
            self.activate_item(self.selected_node_id)

    def expand_item(self, node_id: str) -> None:
        assert node_id in self.nodes
        node = self.nodes[node_id]
        node.tree_item.collapsible_state = TreeItemCollapsibleState.EXPANDED
        if node.is_resolved:
            self._update_contents()
            return
        self._resolve_children(node_id)

    def collapse_item(self, node_id: str) -> None:
        assert node_id in self.nodes
        self.nodes[node_id].tree_item.collapsible_state = TreeItemCollapsibleState.COLLAPSED
        self._update_contents()

    def select_item(self, node_id: str) -> None:
        assert node_id in self.nodes
        self.selected_node_id = node_id
        node = self.nodes[node_id]
        if node.is_resolved:
            self._update_contents()
        else:
            self._resolve_children(node_id)

    def activate_item(self, node_id: str) -> None:
        self.select_item(node_id)
        assert node_id in self.nodes
        self.selected_node_id = node_id
        node = self.nodes[node_id]
        if action_command := node.tree_item.action_command:
            sublime.active_window().run_command(*action_command)

    def _update_contents(self) -> None:
        contents = """
        <style>
            html {{
                padding: 0;
            }}
            {}
            h3 a {{
                text-decoration: none;
            }}
            .tree-view {{
                padding: 0.5rem;
            }}
            .tree-view-row {{
                margin: 0.4rem;
            }}
            .disclosure-button {{
                color: color(var(--foreground) alpha(0.8));
                text-decoration: none;
            }}
            .kind {{
                font-weight: bold;
                font-style: italic;
                width: 1.5rem;
                display: inline-block;
                text-align: center;
                font-family: system;
                line-height: 1.3;
                border-radius: 2px;
                position: relative;
                top: 1px;
                margin-left: 6px;
                margin-right: 6px;
            }}
            .kind_ambiguous {{
                display: none;
            }}
            .kind_keyword {{
                background-color: color(var(--pinkish) a(0.2));
                color: var(--pinkish);
            }}
            .kind_type {{
                background-color: color(var(--purplish) a(0.2));
                color: var(--purplish);
            }}
            .kind_function {{
                background-color: color(var(--redish) a(0.2));
                color: var(--redish);
            }}
            .kind_namespace {{
                background-color: color(var(--bluish) a(0.2));
                color: var(--bluish);
            }}
            .kind_navigation {{
                background-color: color(var(--yellowish) a(0.2));
                color: var(--yellowish);
            }}
            .kind_markup {{
                background-color: color(var(--orangish) a(0.2));
                color: var(--orangish);
            }}
            .kind_variable {{
                background-color: color(var(--cyanish) a(0.2));
                color: var(--cyanish);
            }}
            .kind_snippet {{
                background-color: color(var(--greenish) a(0.2));
                color: var(--greenish);
            }}
            .label {{
                color: var(--foreground);
                text-decoration: none;
            }}
            .description {{
                color: color(var(--foreground) alpha(0.6));
                padding-left: 0.5rem;
            }}
            .active {{
                background-color: color(var(--accent));
            }}
        </style>
        <body id="lsp-tree-view" class="lsp_sheet">
            <h3>{}</h3>
            <div class="tree-view">{}</div>
        </body>
        """.format(css().sheets, self.header, "".join([self._subtree_html(root_id) for root_id in self.root_nodes]))
        self.set_contents(contents)
        self._update_ordered_node_ids()

    def _update_ordered_node_ids(self) -> None:
        # Iterative to avoid recursion.
        result: list[str] = []
        stack = list(reversed(self.root_nodes))
        while stack:
            node_id = stack.pop()
            node = self.nodes[node_id]
            result.append(node_id)
            if node.tree_item.collapsible_state == TreeItemCollapsibleState.EXPANDED:
                stack.extend(reversed(node.child_ids))
        self.ordered_node_ids = result

    def _subtree_html(self, node_id: str) -> str:
        node = self.nodes[node_id]
        html = node.tree_item.html(self.name, node.indent_level, node_id == self.selected_node_id)
        if node.tree_item.collapsible_state == TreeItemCollapsibleState.EXPANDED:
            html += "".join([self._subtree_html(child_id) for child_id in node.child_ids])
        return html


def new_tree_view_sheet(
    window: sublime.Window,
    name: str,
    data_provider: TreeDataProvider,
    header: str = "",
    flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
    group: int = -1
) -> TreeViewSheet | None:
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
            if flags & sublime.NewFileFlags.ADD_TO_SELECTION:
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


def toggle_tree_item(window: sublime.Window, name: str, node_id: str, expand: bool) -> None:
    wm = windows.lookup(window)
    if not wm:
        return
    sheet = wm.tree_view_sheets.get(name)
    if not sheet:
        return
    if expand:
        sheet.expand_item(node_id)
    else:
        sheet.collapse_item(node_id)


def activate_tree_item(window: sublime.Window, name: str, node_id: str) -> None:
    wm = windows.lookup(window)
    if not wm:
        return
    sheet = wm.tree_view_sheets.get(name)
    if not sheet:
        return
    sheet.activate_item(node_id)


class LspExpandTreeItemCommand(sublime_plugin.WindowCommand):

    def run(self, name: str, node_id: str) -> None:
        toggle_tree_item(self.window, name, node_id, True)


class LspCollapseTreeItemCommand(sublime_plugin.WindowCommand):

    def run(self, name: str, node_id: str) -> None:
        toggle_tree_item(self.window, name, node_id, False)


class LspActivateTreeItemCommand(sublime_plugin.WindowCommand):

    def run(self, name: str, node_id: str) -> None:
        activate_tree_item(self.window, name, node_id)


class LspHandleTreeViewActionCommand(sublime_plugin.WindowCommand):

    def run(self, action: TreeViewAction) -> None:
        if (
            (active_sheet := self.window.active_sheet()) and (wm := windows.lookup(self.window))
            and (sheet := next((sheet for sheet in wm.tree_view_sheets.values() if sheet == active_sheet), None))
        ):
            sheet.handle_action(action)
