from .protocol import CodeActionKind
from .protocol import CompletionItemKind
from .protocol import DiagnosticSeverity
from .protocol import DocumentHighlightKind
from .protocol import SymbolKind
from .typing import Dict, Tuple
import sublime


SublimeKind = Tuple[int, str, str]


ST_VERSION = int(sublime.version())

# Keys for View.add_regions
HOVER_HIGHLIGHT_KEY = 'lsp_hover_highlight'

# Setting keys
CODE_LENS_ENABLED_KEY = 'lsp_show_code_lens'
HOVER_ENABLED_KEY = 'lsp_show_hover_popups'
SHOW_DEFINITIONS_KEY = 'show_definitions'

# Region flags
DOCUMENT_LINK_FLAGS = sublime.HIDE_ON_MINIMAP | sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE | sublime.NO_UNDO  # noqa: E501
REGIONS_INITIALIZE_FLAGS = sublime.HIDDEN | sublime.NO_UNDO
SEMANTIC_TOKEN_FLAGS = sublime.DRAW_NO_OUTLINE | sublime.NO_UNDO

# sublime.Kind tuples for sublime.CompletionItem, sublime.QuickPanelItem, sublime.ListInputItem
# https://www.sublimetext.com/docs/api_reference.html#sublime.Kind
KIND_ARRAY = (sublime.KIND_ID_TYPE, "a", "Array")
KIND_BOOLEAN = (sublime.KIND_ID_VARIABLE, "b", "Boolean")
KIND_CLASS = (sublime.KIND_ID_TYPE, "c", "Class")
KIND_COLOR = (sublime.KIND_ID_MARKUP, "c", "Color")
KIND_CONSTANT = (sublime.KIND_ID_VARIABLE, "c", "Constant")
KIND_CONSTRUCTOR = (sublime.KIND_ID_FUNCTION, "c", "Constructor")
KIND_ENUM = (sublime.KIND_ID_TYPE, "e", "Enum")
KIND_ENUMMEMBER = (sublime.KIND_ID_VARIABLE, "e", "Enum Member")
KIND_EVENT = (sublime.KIND_ID_FUNCTION, "e", "Event")
KIND_FIELD = (sublime.KIND_ID_VARIABLE, "f", "Field")
KIND_FILE = (sublime.KIND_ID_NAVIGATION, "f", "File")
KIND_FOLDER = (sublime.KIND_ID_NAVIGATION, "f", "Folder")
KIND_FUNCTION = (sublime.KIND_ID_FUNCTION, "f", "Function")
KIND_INTERFACE = (sublime.KIND_ID_TYPE, "i", "Interface")
KIND_KEY = (sublime.KIND_ID_NAVIGATION, "k", "Key")
KIND_KEYWORD = (sublime.KIND_ID_KEYWORD, "k", "Keyword")
KIND_METHOD = (sublime.KIND_ID_FUNCTION, "m", "Method")
KIND_MODULE = (sublime.KIND_ID_NAMESPACE, "m", "Module")
KIND_NAMESPACE = (sublime.KIND_ID_NAMESPACE, "n", "Namespace")
KIND_NULL = (sublime.KIND_ID_VARIABLE, "n", "Null")
KIND_NUMBER = (sublime.KIND_ID_VARIABLE, "n", "Number")
KIND_OBJECT = (sublime.KIND_ID_TYPE, "o", "Object")
KIND_OPERATOR = (sublime.KIND_ID_KEYWORD, "o", "Operator")
KIND_PACKAGE = (sublime.KIND_ID_NAMESPACE, "p", "Package")
KIND_PROPERTY = (sublime.KIND_ID_VARIABLE, "p", "Property")
KIND_REFERENCE = (sublime.KIND_ID_NAVIGATION, "r", "Reference")
KIND_SNIPPET = (sublime.KIND_ID_SNIPPET, "s", "Snippet")
KIND_STRING = (sublime.KIND_ID_VARIABLE, "s", "String")
KIND_STRUCT = (sublime.KIND_ID_TYPE, "s", "Struct")
KIND_TEXT = (sublime.KIND_ID_MARKUP, "t", "Text")
KIND_TYPEPARAMETER = (sublime.KIND_ID_TYPE, "t", "Type Parameter")
KIND_UNIT = (sublime.KIND_ID_VARIABLE, "u", "Unit")
KIND_VALUE = (sublime.KIND_ID_VARIABLE, "v", "Value")
KIND_VARIABLE = (sublime.KIND_ID_VARIABLE, "v", "Variable")

KIND_ERROR = (sublime.KIND_ID_COLOR_REDISH, "e", "Error")
KIND_WARNING = (sublime.KIND_ID_COLOR_YELLOWISH, "w", "Warning")
KIND_INFORMATION = (sublime.KIND_ID_COLOR_BLUISH, "i", "Information")
KIND_HINT = (sublime.KIND_ID_COLOR_BLUISH, "h", "Hint")

KIND_QUICKFIX = (sublime.KIND_ID_COLOR_YELLOWISH, "f", "QuickFix")
KIND_REFACTOR = (sublime.KIND_ID_COLOR_CYANISH, "r", "Refactor")
KIND_SOURCE = (sublime.KIND_ID_COLOR_PURPLISH, "s", "Source")

COMPLETION_KINDS: Dict[CompletionItemKind, SublimeKind] = {
    CompletionItemKind.Text: KIND_TEXT,
    CompletionItemKind.Method: KIND_METHOD,
    CompletionItemKind.Function: KIND_FUNCTION,
    CompletionItemKind.Constructor: KIND_CONSTRUCTOR,
    CompletionItemKind.Field: KIND_FIELD,
    CompletionItemKind.Variable: KIND_VARIABLE,
    CompletionItemKind.Class: KIND_CLASS,
    CompletionItemKind.Interface: KIND_INTERFACE,
    CompletionItemKind.Module: KIND_MODULE,
    CompletionItemKind.Property: KIND_PROPERTY,
    CompletionItemKind.Unit: KIND_UNIT,
    CompletionItemKind.Value: KIND_VALUE,
    CompletionItemKind.Enum: KIND_ENUM,
    CompletionItemKind.Keyword: KIND_KEYWORD,
    CompletionItemKind.Snippet: KIND_SNIPPET,
    CompletionItemKind.Color: KIND_COLOR,
    CompletionItemKind.File: KIND_FILE,
    CompletionItemKind.Reference: KIND_REFERENCE,
    CompletionItemKind.Folder: KIND_FOLDER,
    CompletionItemKind.EnumMember: KIND_ENUMMEMBER,
    CompletionItemKind.Constant: KIND_CONSTANT,
    CompletionItemKind.Struct: KIND_STRUCT,
    CompletionItemKind.Event: KIND_EVENT,
    CompletionItemKind.Operator: KIND_OPERATOR,
    CompletionItemKind.TypeParameter: KIND_TYPEPARAMETER
}

SYMBOL_KINDS: Dict[SymbolKind, SublimeKind] = {
    SymbolKind.File: KIND_FILE,
    SymbolKind.Module: KIND_MODULE,
    SymbolKind.Namespace: KIND_NAMESPACE,
    SymbolKind.Package: KIND_PACKAGE,
    SymbolKind.Class: KIND_CLASS,
    SymbolKind.Method: KIND_METHOD,
    SymbolKind.Property: KIND_PROPERTY,
    SymbolKind.Field: KIND_FIELD,
    SymbolKind.Constructor: KIND_CONSTRUCTOR,
    SymbolKind.Enum: KIND_ENUM,
    SymbolKind.Interface: KIND_INTERFACE,
    SymbolKind.Function: KIND_FUNCTION,
    SymbolKind.Variable: KIND_VARIABLE,
    SymbolKind.Constant: KIND_CONSTANT,
    SymbolKind.String: KIND_STRING,
    SymbolKind.Number: KIND_NUMBER,
    SymbolKind.Boolean: KIND_BOOLEAN,
    SymbolKind.Array: KIND_ARRAY,
    SymbolKind.Object: KIND_OBJECT,
    SymbolKind.Key: KIND_KEY,
    SymbolKind.Null: KIND_NULL,
    SymbolKind.EnumMember: KIND_ENUMMEMBER,
    SymbolKind.Struct: KIND_STRUCT,
    SymbolKind.Event: KIND_EVENT,
    SymbolKind.Operator: KIND_OPERATOR,
    SymbolKind.TypeParameter: KIND_TYPEPARAMETER
}

DIAGNOSTIC_KINDS: Dict[DiagnosticSeverity, SublimeKind] = {
    DiagnosticSeverity.Error: KIND_ERROR,
    DiagnosticSeverity.Warning: KIND_WARNING,
    DiagnosticSeverity.Information: KIND_INFORMATION,
    DiagnosticSeverity.Hint: KIND_HINT
}

CODE_ACTION_KINDS: Dict[CodeActionKind, SublimeKind] = {
    CodeActionKind.QuickFix: KIND_QUICKFIX,
    CodeActionKind.Refactor: KIND_REFACTOR,
    CodeActionKind.Source: KIND_SOURCE
}


DOCUMENT_HIGHLIGHT_KIND_NAMES: Dict[DocumentHighlightKind, str] = {
    DocumentHighlightKind.Text: "text",
    DocumentHighlightKind.Read: "read",
    DocumentHighlightKind.Write: "write"
}


# Symbol scope to kind mapping, based on https://github.com/sublimetext-io/docs.sublimetext.io/issues/30
SUBLIME_KIND_SCOPES: Dict[SublimeKind, str] = {
    sublime.KIND_KEYWORD: "keyword | storage.modifier | storage.type | keyword.declaration | variable.language | constant.language",  # noqa: E501
    sublime.KIND_TYPE: "entity.name.type | entity.name.class | entity.name.enum | entity.name.trait | entity.name.struct | entity.name.impl | entity.name.interface | entity.name.union | support.type | support.class",  # noqa: E501
    sublime.KIND_FUNCTION: "entity.name.function | entity.name.method | entity.name.macro | meta.method entity.name.function | support.function | meta.function-call variable.function | meta.function-call support.function | support.method | meta.method-call variable.function",  # noqa: E501
    sublime.KIND_NAMESPACE: "entity.name.module | entity.name.namespace | support.module | support.namespace",
    sublime.KIND_NAVIGATION: "entity.name.definition | entity.name.label | entity.name.section",
    sublime.KIND_MARKUP: "entity.other.attribute-name | entity.name.tag | meta.toc-list.id.html",
    sublime.KIND_VARIABLE: "entity.name.constant | constant.other | support.constant | variable.other | variable.parameter | variable.other.member | variable.other.readwrite.member"  # noqa: E501
}

DOCUMENT_HIGHLIGHT_KIND_SCOPES: Dict[DocumentHighlightKind, str] = {
    DocumentHighlightKind.Text: "region.bluish markup.highlight.text.lsp",
    DocumentHighlightKind.Read: "region.greenish markup.highlight.read.lsp",
    DocumentHighlightKind.Write: "region.yellowish markup.highlight.write.lsp"
}

SEMANTIC_TOKENS_MAP = {
    "namespace": "variable.other.namespace.lsp",
    "namespace.declaration": "entity.name.namespace.lsp",
    "namespace.definition": "entity.name.namespace.lsp",
    "type": "storage.type.lsp",
    "type.declaration": "entity.name.type.lsp",
    "type.defaultLibrary": "support.type.lsp",
    "type.definition": "entity.name.type.lsp",
    "class": "storage.type.class.lsp",
    "class.declaration": "entity.name.class.lsp",
    "class.defaultLibrary": "support.class.lsp",
    "class.definition": "entity.name.class.lsp",
    "enum": "variable.other.enum.lsp",
    "enum.declaration": "entity.name.enum.lsp",
    "enum.definition": "entity.name.enum.lsp",
    "interface": "entity.other.inherited-class.lsp",
    "interface.declaration": "entity.name.interface.lsp",
    "interface.definition": "entity.name.interface.lsp",
    "struct": "storage.type.struct.lsp",
    "struct.declaration": "entity.name.struct.lsp",
    "struct.defaultLibrary": "support.struct.lsp",
    "struct.definition": "entity.name.struct.lsp",
    "typeParameter": "variable.parameter.generic.lsp",
    "parameter": "variable.parameter.lsp",
    "variable": "variable.other.lsp",
    "variable.readonly": "variable.other.constant.lsp",
    "property": "variable.other.property.lsp",
    "enumMember": "constant.other.enum.lsp",
    "event": "entity.name.function.lsp",
    "function": "variable.function.lsp",
    "function.declaration": "entity.name.function.lsp",
    "function.defaultLibrary": "support.function.builtin.lsp",
    "function.definition": "entity.name.function.lsp",
    "method": "variable.function.lsp",
    "method.declaration": "entity.name.function.lsp",
    "method.defaultLibrary": "support.function.builtin.lsp",
    "method.definition": "entity.name.function.lsp",
    "macro": "variable.macro.lsp",
    "macro.declaration": "entity.name.macro.lsp",
    "macro.defaultLibrary": "support.macro.lsp",
    "macro.definition": "entity.name.macro.lsp",
    "keyword": "keyword.lsp",
    "modifier": "storage.modifier.lsp",
    "comment": "comment.lsp",
    "comment.documentation": "comment.block.documentation.lsp",
    "string": "string.lsp",
    "number": "constant.numeric.lsp",
    "regexp": "string.regexp.lsp",
    "operator": "keyword.operator.lsp",
    "decorator": "variable.annotation.lsp",
}
