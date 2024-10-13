from __future__ import annotations
from .core.logging import debug
from .core.protocol import Command
from .core.protocol import InlineCompletionItem
from .core.protocol import InlineCompletionList
from .core.protocol import InlineCompletionParams
from .core.protocol import InlineCompletionTriggerKind
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.views import range_to_region
from .core.views import text_document_position_params
from functools import partial
import html
import sublime


PHANTOM_HTML = """
<style>
    html {{
        padding: 0;
        background-color: transparent;
    }}
    .completion-content {{
        display: inline;
        color: {color};
        font-style: {font_style};
        font-weight: {font_weight};
    }}
    .key-hint {{
        display: inline;
        padding-left: 2em;
        font-size: 0.9rem;
        color: color(var(--foreground) alpha(0.8));
    }}
    kbd {{
        font-family: monospace;
        font-size: 0.75rem;
        color: color(var(--foreground) alpha(0.8));
        background-color: color(var(--foreground) alpha(0.08));
        border: 1px solid color(var(--foreground) alpha(0.5));
        border-radius: 4px;
        padding: 0px 3px;
    }}
</style>
<body id="lsp-inline-completion">
    <div class="completion-content">{content}</div>{suffix}
</body>"""


class InlineCompletionData:

    def __init__(self, view: sublime.View, key: str) -> None:
        self.visible = False
        self.region = sublime.Region(0, 0)
        self.text = ''
        self.command: Command | None = None
        self.session_name = ''
        self._view = view
        self._phantom_set = sublime.PhantomSet(view, key)

    def render_async(self, location: int, text: str) -> None:
        style = self._view.style_for_scope('comment meta.inline-completion.lsp')
        color = style['foreground']
        font_style = 'italic' if style['italic'] else 'normal'
        font_weight = 'bold' if style['bold'] else 'normal'
        region = sublime.Region(location)
        is_at_eol = self._view.line(location).b == location
        first_line, *more_lines = text.splitlines()
        suffix = '<div class="key-hint"><kbd>Alt</kbd> + <kbd>Enter</kbd> to complete</div>' if is_at_eol or \
            more_lines else ''
        phantoms = [sublime.Phantom(
            region,
            PHANTOM_HTML.format(
                color=color,
                font_style=font_style,
                font_weight=font_weight,
                content=self._normalize_html(first_line),
                suffix=suffix
            ),
            sublime.PhantomLayout.INLINE
        )]
        if more_lines:
            phantoms.append(
                sublime.Phantom(
                    region,
                    PHANTOM_HTML.format(
                        color=color,
                        font_style=font_style,
                        font_weight=font_weight,
                        content='<br>'.join(self._normalize_html(line) for line in more_lines),
                        suffix=''
                    ),
                    sublime.PhantomLayout.BLOCK
                )
            )
        sublime.set_timeout(lambda: self._render(phantoms))
        self.visible = True

    def _render(self, phantoms: list[sublime.Phantom]) -> None:
        self._phantom_set.update(phantoms)

    def clear_async(self) -> None:
        if self.visible:
            sublime.set_timeout(self._clear)
            self.visible = False

    def _clear(self) -> None:
        self._phantom_set.update([])

    def _normalize_html(self, content: str) -> str:
        return html.escape(content).replace(' ', '&nbsp;')


class LspInlineCompletionCommand(LspTextCommand):

    capability = 'inlineCompletionProvider'

    def run(self, edit: sublime.Edit, event: dict | None = None, point: int | None = None) -> None:
        sublime.set_timeout_async(partial(self._run_async, event, point))

    def _run_async(self, event: dict | None = None, point: int | None = None) -> None:
        position = get_position(self.view, event, point)
        if position is None:
            return
        session = self.best_session(self.capability, point)
        if not session:
            return
        if self.view.settings().get('mini_auto_complete', False):
            return
        position_params = text_document_position_params(self.view, position)
        params: InlineCompletionParams = {
            'textDocument': position_params['textDocument'],
            'position': position_params['position'],
            'context': {
                'triggerKind': InlineCompletionTriggerKind.Invoked
            }
        }
        session.send_request_async(
            Request('textDocument/inlineCompletion', params),
            partial(self._handle_response_async, session.config.name, self.view.change_count(), position)
        )

    def _handle_response_async(
        self,
        session_name: str,
        view_version: int,
        position: int,
        response: list[InlineCompletionItem] | InlineCompletionList | None
    ) -> None:
        if response is None:
            return
        items = response['items'] if isinstance(response, dict) else response
        if not items:
            return
        item = items[0]
        insert_text = item['insertText']
        if not insert_text:
            return
        if isinstance(insert_text, dict):  # StringValue
            debug('Snippet completions from the 3.18 specs not yet supported')
            return
        if view_version != self.view.change_count():
            return
        listener = self.get_listener()
        if not listener:
            return
        range_ = item.get('range')
        region = range_to_region(range_, self.view) if range_ else sublime.Region(position)
        region_length = len(region)
        if region_length > len(insert_text):
            return
        listener.inline_completion.region = region
        listener.inline_completion.text = insert_text
        listener.inline_completion.command = item.get('command')
        listener.inline_completion.session_name = session_name
        listener.inline_completion.render_async(position, insert_text[region_length:])

        # listener.inline_completion.text = lines[0] + '\n'
        # listener.inline_completion.render_async(position, lines[0])

        # filter_text = item.get('filterText', insert_text)  # ignored for now


class LspCommitInlineCompletionCommand(LspTextCommand):

    capability = 'inlineCompletionProvider'

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
        if not super().is_enabled(event, point):
            return False
        listener = self.get_listener()
        if not listener:
            return False
        return listener.inline_completion.visible

    def run(self, edit: sublime.Edit, event: dict | None = None, point: int | None = None) -> None:
        listener = self.get_listener()
        if not listener:
            return
        self.view.replace(edit, listener.inline_completion.region, listener.inline_completion.text)
        selection = self.view.sel()
        pt = selection[0].b
        selection.clear()
        selection.add(pt)
        command = listener.inline_completion.command
        if command:
            self.view.run_command('lsp_execute', {
                "command_name": command['command'],
                "command_args": command.get('arguments'),
                "session_name": listener.inline_completion.session_name
            })
