from .protocol import CodeActionKind
from .protocol import CompletionItemKind
from .protocol import DiagnosticSeverity
from .protocol import DocumentHighlightKind
from .protocol import SymbolKind
from .typing import Dict, Tuple
import sublime


SublimeKind = Tuple[int, str, str]


# Keys for View.add_regions
HOVER_HIGHLIGHT_KEY = 'lsp_hover_highlight'

# Setting keys
CODE_LENS_ENABLED_KEY = 'lsp_show_code_lens'
HOVER_ENABLED_KEY = 'lsp_show_hover_popups'
HOVER_PROVIDER_COUNT_KEY = 'lsp_hover_provider_count'
SHOW_DEFINITIONS_KEY = 'show_definitions'

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

COMPLETION_KINDS = {
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
}  # type: Dict[CompletionItemKind, SublimeKind]

SYMBOL_KINDS = {
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
}  # type: Dict[SymbolKind, SublimeKind]

DIAGNOSTIC_KINDS = {
    DiagnosticSeverity.Error: KIND_ERROR,
    DiagnosticSeverity.Warning: KIND_WARNING,
    DiagnosticSeverity.Information: KIND_INFORMATION,
    DiagnosticSeverity.Hint: KIND_HINT
}  # type: Dict[DiagnosticSeverity, SublimeKind]

CODE_ACTION_KINDS = {
    CodeActionKind.QuickFix: KIND_QUICKFIX,
    CodeActionKind.Refactor: KIND_REFACTOR,
    CodeActionKind.Source: KIND_SOURCE
}  # type: Dict[CodeActionKind, SublimeKind]


DOCUMENT_HIGHLIGHT_KIND_NAMES = {
    DocumentHighlightKind.Text: "text",
    DocumentHighlightKind.Read: "read",
    DocumentHighlightKind.Write: "write"
}  # type: Dict[DocumentHighlightKind, str]
