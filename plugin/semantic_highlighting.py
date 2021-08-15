from .core.registry import LspTextCommand
from .core.typing import List
import sublime


class SemanticTokenTypes:
    Namespace = "namespace"
    Type = "type"
    Class = "class"
    Enum = "enum"
    Interface = "interface"
    Struct = "struct"
    TypeParameter = "typeParameter"
    Parameter = "parameter"
    Variable = "variable"
    Property = "property"
    EnumMember = "enumMember"
    Event = "event"
    Function = "function"
    Method = "method"
    Macro = "macro"
    Keyword = "keyword"
    Modifier = "modifier"
    Comment = "comment"
    String = "string"
    Number = "number"
    Regexp = "regexp"
    Operator = "operator"


class SemanticTokenModifiers:
    Declaration = "declaration"
    Definition = "definition"
    Readonly = "readonly"
    Static = "static"
    Deprecated = "deprecated"
    Abstract = "abstract"
    Async = "async"
    Modification = "modification"
    Documentation = "documentation"
    DefaultLibrary = "defaultLibrary"


SEMANTIC_TOKENS_MAP = {
    "namespace": "variable.other.namespace.lsp",
    "type": "storage.type.lsp",
    "class": "storage.type.class.lsp",
    "enum": "variable.other.enum.lsp",
    "interface": "entity.other.inherited-class.lsp",
    "struct": "storage.type.struct.lsp",
    "typeParameter": "variable.parameter.generic.lsp",
    "parameter": "variable.parameter.lsp",
    "variable": "variable.other.lsp",
    "property": "variable.other.lsp",
    "enumMember": "constant.other.enum.lsp",
    "event": "entity.name.function.lsp",
    "function": "variable.function.lsp",
    "method": "variable.function.lsp",
    "macro": "variable.macro.lsp",
    "keyword": "keyword.lsp",
    "modifier": "storage.modifier.lsp",
    "comment": "comment.lsp",
    "string": "string.lsp",
    "number": "constant.numeric.lsp",
    "regexp": "string.regexp.lsp",
    "operator": "keyword.operator.lsp"
}

# overrides for the scope names above, which should apply in combination with certain modifiers
SEMANTIC_TOKENS_WITH_MODIFIERS_MAP = [
#    tokenType    tokenModifier     scope
    ("namespace", "declaration",    "entity.name.namespace.lsp"),
    ("namespace", "definition",     "entity.name.namespace.lsp"),
    ("type",      "declaration",    "entity.name.type.lsp"),
    ("type",      "definition",     "entity.name.type.lsp"),
    ("type",      "defaultLibrary", "support.type.lsp"),
    ("class",     "declaration",    "entity.name.class.lsp"),
    ("class",     "definition",     "entity.name.class.lsp"),
    ("class",     "defaultLibrary", "support.class.lsp"),
    ("enum",      "declaration",    "entity.name.enum.lsp"),
    ("enum",      "definition",     "entity.name.enum.lsp"),
    ("interface", "declaration",    "entity.name.interface.lsp"),
    ("interface", "definition",     "entity.name.interface.lsp"),
    ("struct",    "declaration",    "entity.name.struct.lsp"),
    ("struct",    "definition",     "entity.name.struct.lsp"),
    ("struct",    "defaultLibrary", "support.struct.lsp"),
    ("variable",  "readonly",       "constant.other.lsp"),
    ("function",  "declaration",    "entity.name.function.lsp"),
    ("function",  "definition",     "entity.name.function.lsp"),
    ("function",  "defaultLibrary", "support.function.builtin.lsp"),
    ("method",    "declaration",    "entity.name.function.lsp"),
    ("method",    "definition",     "entity.name.function.lsp"),
    ("method",    "defaultLibrary", "support.function.builtin.lsp"),
    ("macro",     "declaration",    "entity.name.macro.lsp"),
    ("macro",     "definition",     "entity.name.macro.lsp"),
    ("macro",     "defaultLibrary", "support.macro.lsp"),
    ("comment",   "documentation",  "comment.block.documentation.lsp")
]


class SemanticToken:

    __slots__ = ("region", "type", "modifiers")

    def __init__(self, region: sublime.Region, type: str, modifiers: List[str]):
        self.region = region
        self.type = type
        self.modifiers = modifiers


class LspShowScopeNameCommand(LspTextCommand):
    """
    Like the builtin show_scope_name command from Default/show_scope_name.py,
    but will also show semantic tokens if applicable.
    """

    capability = 'semanticTokensProvider'

    def run(self, edit: sublime.Edit) -> None:
        point = self.view.sel()[-1].b

        scope = self.view.scope_name(point).rstrip()
        scope_list = scope.replace(' ', '<br>')

        stack = self.view.context_backtrace(point)

        backtrace = ''
        digits_len = 1
        for i, ctx in enumerate(reversed(stack)):
            digits = '%s' % (i + 1)
            digits_len = max(len(digits), digits_len)
            nums = '<span class=nums>%s.</span>' % digits

            if ctx.startswith("anonymous context "):
                ctx = '<em>%s</em>' % ctx
            ctx = '<span class=context>%s</span>' % ctx

            if backtrace:
                backtrace += '\n'
            backtrace += '<div>%s%s</div>' % (nums, ctx)

        # ------------------------------------------------------

        session = self.best_session('semanticTokensProvider')
        session_buffer = None
        if session:
            for sv in session.session_views_async():
                if self.view == sv.view:
                    session_buffer = sv.session_buffer
                    break

        token_type = '-'
        token_modifiers = '-'

        if session_buffer:
            for token in session_buffer.semantic_tokens:
                if token.region.contains(point):
                    token_type = token.type
                    if token.modifiers:
                        token_modifiers = ', '.join(token.modifiers)
                    break

        html = """
            <body id=show-scope>
                <style>
                    h1 {
                        font-size: 1.1rem;
                        font-weight: 500;
                        margin: 0 0 0.5em 0;
                        font-family: system;
                    }
                    p {
                        margin-top: 0;
                    }
                    a {
                        font-weight: normal;
                        font-style: italic;
                        padding-left: 1em;
                        font-size: 1.0rem;
                    }
                    span.nums {
                        display: inline-block;
                        text-align: right;
                        width: %dem;
                        color: color(var(--foreground) a(0.8))
                    }
                    span.context {
                        padding-left: 0.5em;
                    }
                </style>
                <h1>Scope Name <a href="%s">Copy</a></h1>
                <p>%s</p>
                <h1>Context Backtrace</h1>
                %s
                <br>
                <h1>Semantic Token</h1>
                <p>Type: %s</p>
                <p>Modifiers: %s</p>
            </body>
        """ % (digits_len, scope, scope_list, backtrace, token_type, token_modifiers)

        def copy(view, text: str) -> None:
            sublime.set_clipboard(text)
            view.hide_popup()
            sublime.status_message('Scope name copied to clipboard')

        self.view.show_popup(html, max_width=512, max_height=512, on_navigate=lambda x: copy(self.view, x))
