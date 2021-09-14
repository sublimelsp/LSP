from .core.registry import LspTextCommand
from .core.typing import List
import sublime


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
            for token in session_buffer.semantic_tokens.tokens:
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
                <p>Type: %s<br>Modifiers: %s</p>
            </body>
        """ % (digits_len, scope, scope_list, backtrace, token_type, token_modifiers)

        def copy(view: sublime.View, text: str) -> None:
            sublime.set_clipboard(text)
            view.hide_popup()
            sublime.status_message('Scope name copied to clipboard')

        self.view.show_popup(html, max_width=512, max_height=512, on_navigate=lambda x: copy(self.view, x))
