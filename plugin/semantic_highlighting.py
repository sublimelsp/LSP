from __future__ import annotations
from .core.registry import LspTextCommand
from typing import Any, List, Tuple
from typing import cast
import sublime
import os

SemanticTokensInfo = List[Tuple[str, str, str]]


def copy(view: sublime.View, text: str) -> None:
    sublime.set_clipboard(text)
    view.hide_popup()
    sublime.status_message('Scope name copied to clipboard')


class LspShowScopeNameCommand(LspTextCommand):
    """
    Like the builtin show_scope_name command from Default/show_scope_name.py,
    but will also show semantic tokens if applicable.
    """

    capability = 'semanticTokensProvider'

    def want_event(self) -> bool:
        return False

    def run(self, _: sublime.Edit) -> None:
        point = self.view.sel()[-1].b
        scope = self.view.scope_name(point).rstrip()
        scope_list = scope.replace(' ', '<br>')
        stack = self.view.context_backtrace(point)
        semantic_info = self._get_semantic_info(point)
        if isinstance(stack, list) and len(stack) > 0 and not isinstance(stack[0], str):
            self._render_with_fancy_stackframes(
                scope,
                scope_list,
                cast(List[sublime.ContextStackFrame], stack),
                semantic_info,
            )
        else:
            self._render_with_plain_string_stackframes(
                scope,
                scope_list,
                cast(List[str], stack),
                semantic_info
            )

    def _get_semantic_info(self, point: int) -> SemanticTokensInfo:
        info: SemanticTokensInfo = []
        for session in self.sessions('semanticTokensProvider'):
            for sv in session.session_views_async():
                if self.view == sv.view:
                    for token in sv.session_buffer.get_semantic_tokens():
                        if token.region.contains(point) and point < token.region.end():
                            token_modifiers = ', '.join(token.modifiers) if token.modifiers else '-'
                            info.append((token.type, token_modifiers, session.config.name))
        return info

    def _render_with_plain_string_stackframes(
        self,
        scope: str,
        scope_list: str,
        stack: list[str],
        semantic_info: SemanticTokensInfo,
    ) -> None:
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
            backtrace += f'<div>{nums}{ctx}</div>'

        semantic_tokens_html = ''
        for info in semantic_info:
            semantic_tokens_html += f'<p>Type: {info[0]}, Modifiers: {info[1]} <a>{info[2]}</a>'

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
                %s
            </body>
        """ % (digits_len, scope, scope_list, backtrace, semantic_info)

        self.view.show_popup(html, max_width=512, max_height=512, on_navigate=lambda x: copy(self.view, x))

    def _render_with_fancy_stackframes(
        self,
        scope: str,
        scope_list: str,
        stack: list[Any],
        semantic_info: SemanticTokensInfo,
    ) -> None:
        backtrace = ''
        digits_len = 1
        for i, frame in enumerate(reversed(stack)):
            digits = '%s' % (i + 1)
            digits_len = max(len(digits), digits_len)
            nums = '<span class=nums>%s.</span>' % digits

            if frame.context_name.startswith("anonymous context "):
                context_name = '<em>%s</em>' % frame.context_name
            else:
                context_name = frame.context_name
            ctx = '<span class=context>%s</span>' % context_name

            resource_path = frame.source_file
            display_path = os.path.splitext(frame.source_file)[0]
            if resource_path.startswith('Packages/'):
                resource_path = '${packages}/' + resource_path[9:]
                display_path = display_path[9:]

            if frame.source_location[0] > 0:
                href = '%s:%d:%d' % (resource_path, frame.source_location[0], frame.source_location[1])
                location = '%s:%d:%d' % (display_path, frame.source_location[0], frame.source_location[1])
            else:
                href = resource_path
                location = display_path
            link = f'<a href="o:{href}">{location}</a>'

            if backtrace:
                backtrace += '\n'
            backtrace += f'<div>{nums}{ctx}{link}</div>'

        semantic_tokens_html = ''
        for info in semantic_info:
            semantic_tokens_html += f'<p>Type: {info[0]}, Modifiers: {info[1]} <a>{info[2]}</a>'

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
                <h1>Scope Name <a href="c:%s">Copy</a></h1>
                <p>%s</p>
                <h1>Context Backtrace</h1>
                %s
                <br>
                <h1>Semantic Token</h1>
                %s
            </body>
        """ % (digits_len, scope, scope_list, backtrace, semantic_tokens_html)

        self.view.show_popup(html, max_width=512, max_height=512, on_navigate=self.on_navigate)

    def on_navigate(self, link: str) -> None:
        if link.startswith('o:'):
            if window := self.view.window():
                window.run_command('open_file', {'file': link[2:], 'encoded_position': True})
        else:
            copy(self.view, link[2:])
