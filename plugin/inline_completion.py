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
from typing import Optional
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
</style>
<body id="lsp-inline-completion">
    <div class="completion-content">{content}</div>
</body>"""


class InlineCompletionData:

    def __init__(self, view: sublime.View, key: str) -> None:
        self.visible = False
        self.index = 0
        self.position = 0
        self.items: list[tuple[str, sublime.Region, str, Optional[Command]]] = []
        self._view = view
        self._phantom_set = sublime.PhantomSet(view, key)

    def render_async(self, index: int) -> None:
        style = self._view.style_for_scope('comment meta.inline-completion.lsp')
        color = style['foreground']
        font_style = 'italic' if style['italic'] else 'normal'
        font_weight = 'bold' if style['bold'] else 'normal'
        region = sublime.Region(self.position)
        item = self.items[index]
        first_line, *more_lines = item[2][len(item[1]):].splitlines()
        phantoms = [sublime.Phantom(
            region,
            PHANTOM_HTML.format(
                color=color,
                font_style=font_style,
                font_weight=font_weight,
                content=self._normalize_html(first_line)
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
                        content='<br>'.join(self._normalize_html(line) for line in more_lines)
                    ),
                    sublime.PhantomLayout.BLOCK
                )
            )
        sublime.set_timeout(lambda: self._render(phantoms, index))
        self.visible = True

    def _render(self, phantoms: list[sublime.Phantom], index: int) -> None:
        self.index = index
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
        if view_version != self.view.change_count():
            return
        listener = self.get_listener()
        if not listener:
            return
        listener.inline_completion.items.clear()
        for item in items:
            insert_text = item['insertText']
            if not insert_text:
                continue
            if isinstance(insert_text, dict):  # StringValue
                debug('Snippet completions from the 3.18 specs not yet supported')
                continue
            range_ = item.get('range')
            region = range_to_region(range_, self.view) if range_ else sublime.Region(position)
            region_length = len(region)
            if region_length > len(insert_text):
                continue
            listener.inline_completion.items.append((session_name, region, insert_text, item.get('command')))
        listener.inline_completion.position = position
        listener.inline_completion.render_async(0)

        # filter_text = item.get('filterText', insert_text)  # ignored for now


class LspNextInlineCompletionCommand(LspTextCommand):

    capability = 'inlineCompletionProvider'

    def is_enabled(self, event: dict | None = None, point: int | None = None, **kwargs) -> bool:
        if not super().is_enabled(event, point):
            return False
        listener = self.get_listener()
        if not listener:
            return False
        return listener.inline_completion.visible

    def run(
        self, edit: sublime.Edit, event: dict | None = None, point: int | None = None, forward: bool = True
    ) -> None:
        listener = self.get_listener()
        if not listener:
            return
        item_count = len(listener.inline_completion.items)
        if item_count < 2:
            return
        new_index = (listener.inline_completion.index - 1 + 2 * forward) % item_count
        listener.inline_completion.render_async(new_index)


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
        session_name, region, text, command = listener.inline_completion.items[listener.inline_completion.index]
        self.view.replace(edit, region, text)
        selection = self.view.sel()
        pt = selection[0].b
        selection.clear()
        selection.add(pt)
        if command:
            self.view.run_command('lsp_execute', {
                "command_name": command['command'],
                "command_args": command.get('arguments'),
                "session_name": session_name
            })
