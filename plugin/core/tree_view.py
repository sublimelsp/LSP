from .css import css
from .promise import Promise
from .typing import Dict, IntEnum, List, Optional, TypeVar
from .views import SublimeKind
from abc import ABCMeta
from abc import abstractmethod
from functools import partial
import html
import sublime
import uuid


T = TypeVar('T')


class TreeItemCollapsibleState(IntEnum):
    COLLAPSED = 1
    EXPANDED = 2


class TreeItem:

    def __init__(
        self,
        label: str,
        kind: SublimeKind = sublime.KIND_AMBIGUOUS,
        description: str = "",
        tooltip: str = "",
        command_url: str = ""
    ) -> None:
        self.label = label
        """ A human-readable string describing this item. """
        self.kind = kind
        """ A sublime.Kind tuple which is rendered as icon in front of the label. """
        self.description = description
        """ A human-readable string which is rendered less prominent. """
        self.tooltip = tooltip
        """ The tooltip text when you hover over this item. """
        self.command_url = command_url
        """ A HTML embeddable URL for a command that should be executed when the tree item label is clicked.
        Use the sublime.command_url function to generate this URL. """
        self.collapsible_state = TreeItemCollapsibleState.COLLAPSED
        self.id = str(uuid.uuid4())

    def html(self, sheet_name: str, indent_level: int) -> str:
        indent_html = '<span style="padding-left: {}rem;">&nbsp;</span>'.format(indent_level)
        if self.collapsible_state == TreeItemCollapsibleState.COLLAPSED:
            disclosure_button_html = '<a class="disclosure-button" href="{}">&#9654;</a>'.format(
                sublime.command_url('lsp_expand_tree_item', {'name': sheet_name, 'id': self.id}))
        elif self.collapsible_state == TreeItemCollapsibleState.EXPANDED:
            disclosure_button_html = '<a class="disclosure-button" href="{}">&#9660;</a>'.format(
                sublime.command_url('lsp_collapse_tree_item', {'name': sheet_name, 'id': self.id}))
        else:
            disclosure_button_html = '<span class="disclosure-button">&nbsp;</span>'
        icon_html = '<span class="{}" title="{}">{}</span>'.format(
            self._kind_class_name(self.kind[0]), self.kind[2], self.kind[1] if self.kind[1] else '&nbsp;')
        if self.command_url and self.tooltip:
            label_html = '<a class="label" href="{}" title="{}">{}</a>'.format(
                self.command_url, html.escape(self.tooltip), html.escape(self.label))
        elif self.command_url:
            label_html = '<a class="label" href="{}">{}</a>'.format(self.command_url, html.escape(self.label))
        elif self.tooltip:
            label_html = '<span class="label" title="{}">{}</span>'.format(
                html.escape(self.tooltip), html.escape(self.label))
        else:
            label_html = '<span class="label">{}</span>'.format(html.escape(self.label))
        description_html = '<span class="description">{}</span>'.format(html.escape(self.description)) if \
            self.description else ''
        return '<div class="tree-view-row">{}</div>'.format(
            indent_html + disclosure_button_html + icon_html + label_html + description_html)

    @staticmethod
    def _kind_class_name(kind_id: int) -> str:
        if kind_id == sublime.KIND_ID_KEYWORD:
            return "kind kind_keyword"
        if kind_id == sublime.KIND_ID_TYPE:
            return "kind kind_type"
        if kind_id == sublime.KIND_ID_FUNCTION:
            return "kind kind_function"
        if kind_id == sublime.KIND_ID_NAMESPACE:
            return "kind kind_namespace"
        if kind_id == sublime.KIND_ID_NAVIGATION:
            return "kind kind_navigation"
        if kind_id == sublime.KIND_ID_MARKUP:
            return "kind kind_markup"
        if kind_id == sublime.KIND_ID_VARIABLE:
            return "kind kind_variable"
        if kind_id == sublime.KIND_ID_SNIPPET:
            return "kind kind_snippet"
        return "kind kind_ambiguous"


class Node:

    __slots__ = ('element', 'tree_item', 'indent_level', 'children', 'is_resolved')

    def __init__(self, element: T, tree_item: TreeItem, indent_level: int = 0) -> None:  # pyright: ignore
        self.element = element
        self.tree_item = tree_item
        self.indent_level = indent_level
        self.children = []  # type: List[str]  # IDs of child nodes
        self.is_resolved = False


class TreeDataProvider(metaclass=ABCMeta):

    @abstractmethod
    def get_children(self, element: Optional[T]) -> Promise[List[T]]:
        """ Implement this to return the children for the given element or root (if no element is passed). """
        raise NotImplementedError()

    @abstractmethod
    def get_tree_item(self, element: T) -> TreeItem:  # pyright: ignore[reportInvalidTypeVarUse]
        """ Implement this to return the UI representation (TreeItem) of the element that gets displayed in the
        TreeViewSheet. """
        raise NotImplementedError()


class TreeViewSheet(sublime.HtmlSheet):
    """ A special HtmlSheet which can render interactive tree data structures. """

    def __init__(self, id: int, name: str, data_provider: TreeDataProvider, header: str = "") -> None:
        super().__init__(id)
        self.nodes = {}  # type: Dict[str, Node]
        self.root_nodes = []  # type: List[str]
        self.name = name
        self.data_provider = data_provider
        self.header = header
        self.data_provider.get_children(None).then(self._set_root_nodes)

    def __repr__(self) -> str:
        return 'TreeViewSheet(%r)' % self.sheet_id

    def set_provider(self, data_provider: TreeDataProvider, header: str = "") -> None:
        """ Use this method if you want to render an entire new tree. This allows to reuse a single HtmlSheet, e.g. when
        using a feature consecutively on different symbols. """
        self.nodes.clear()
        self.root_nodes.clear()
        self.data_provider = data_provider
        self.header = header
        self.data_provider.get_children(None).then(self._set_root_nodes)

    def _set_root_nodes(self, elements: List[T]) -> None:  # pyright: ignore[reportInvalidTypeVarUse]
        promises = []  # type: List[Promise[None]]
        for element in elements:
            tree_item = self.data_provider.get_tree_item(element)
            tree_item.collapsible_state = TreeItemCollapsibleState.EXPANDED
            self.nodes[tree_item.id] = Node(element, tree_item)
            self.root_nodes.append(tree_item.id)
            promises.append(self.data_provider.get_children(element).then(partial(self._add_children, tree_item.id)))
        Promise.all(promises).then(lambda _: self._update_contents())

    def _add_children(self, id: str, elements: List[T]) -> None:  # pyright: ignore[reportInvalidTypeVarUse]
        assert id in self.nodes
        node = self.nodes[id]
        for element in elements:
            tree_item = self.data_provider.get_tree_item(element)
            self.nodes[tree_item.id] = Node(element, tree_item, node.indent_level + 1)
            node.children.append(tree_item.id)
        node.is_resolved = True

    def expand_item(self, id: str) -> None:
        assert id in self.nodes
        node = self.nodes[id]
        node.tree_item.collapsible_state = TreeItemCollapsibleState.EXPANDED
        if node.is_resolved:
            self._update_contents()
            return
        else:
            self.data_provider.get_children(node.element) \
                .then(partial(self._add_children, id)) \
                .then(lambda _: self._update_contents())

    def collapse_item(self, id: str) -> None:
        assert id in self.nodes
        self.nodes[id].tree_item.collapsible_state = TreeItemCollapsibleState.COLLAPSED
        self._update_contents()

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
        </style>
        <body id="lsp-tree-view" class="lsp_sheet">
            <h3>{}</h3>
            <div class="tree-view">{}</div>
        </body>
        """.format(css().sheets, self.header, "".join([self._subtree_html(root_id) for root_id in self.root_nodes]))
        self.set_contents(contents)

    def _subtree_html(self, id: str) -> str:
        node = self.nodes[id]
        if node.tree_item.collapsible_state == TreeItemCollapsibleState.EXPANDED:
            return node.tree_item.html(self.name, node.indent_level) + "".join(
                [self._subtree_html(child_id) for child_id in node.children])
        return node.tree_item.html(self.name, node.indent_level)
