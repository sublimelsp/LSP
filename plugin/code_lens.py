from __future__ import annotations

from ..protocol import CodeLens
from ..protocol import Command
from ..protocol import Range
from .core.constants import CODE_LENS_ENABLED_KEY
from .core.protocol import Error
from .core.protocol import ResolvedCodeLens
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.registry import windows
from .core.views import range_to_region
from functools import partial
from typing import cast
from typing_extensions import TypeGuard
import itertools
import sublime


def is_resolved(code_lens: CodeLens | ResolvedCodeLens) -> TypeGuard[ResolvedCodeLens]:
    return 'command' in code_lens


class HashableRange:

    def __init__(self, r: Range, /) -> None:
        start, end = r['start'], r['end']
        self.data = (start['line'], start['character'], end['line'], end['character'])

    def __hash__(self):
        return hash(self.data)

    def __eq__(self, rhs: object) -> bool:
        return isinstance(rhs, HashableRange) and self.data == rhs.data

    def __lt__(self, rhs: HashableRange) -> bool:
        return self.data < rhs.data


class CachedCodeLens:

    __slots__ = ('data', 'range', 'cached_command')

    def __init__(self, data: CodeLens) -> None:
        self.data: CodeLens | ResolvedCodeLens = data
        self.range = HashableRange(data['range'])
        self.cached_command = data.get('command')

    def on_resolve(self, response: CodeLens | Error) -> None:
        if isinstance(response, Error):
            return
        assert is_resolved(response)
        self.data = response
        self.range = HashableRange(response['range'])
        self.cached_command = response['command']


class CodeLensCache:

    def __init__(self) -> None:
        self.code_lenses: dict[HashableRange, list[CachedCodeLens]] = {}

    def handle_response_async(self, code_lenses: list[CodeLens]) -> None:
        new_code_lenses = [CachedCodeLens(code_lens) for code_lens in code_lenses]
        new_code_lenses.sort(key=lambda c: c.range)
        grouped_code_lenses = {
            range_: list(group) for range_, group in itertools.groupby(new_code_lenses, key=lambda c: c.range)
        }
        # Fast path: no extra work to do
        if not self.code_lenses:
            self.code_lenses = grouped_code_lenses
            return
        # Update new code lenses with cached data to prevent the editor from jumping around due to some code lenses
        # going from resolved to unresolved due to a requery of the document data.
        for range_, group in grouped_code_lenses.items():
            try:
                old_group = self.code_lenses[range_]
            except KeyError:
                continue
            # Use the number of code lenses as a heuristic whether the group still contains the same code lenses.
            if len(group) == len(old_group):
                for old, new in zip(old_group, group):
                    if is_resolved(new.data):
                        continue
                    # This assignment is only temporary, the resolve call in the future will fill in the actual command
                    # after resolve() is called on the CachedCodeLens. However reusing the previous command title if the
                    # code lens groups are the same makes the screen not jump from the phantoms moving around too much.
                    new.cached_command = old.data['command'] if is_resolved(old.data) else old.cached_command
        self.code_lenses = grouped_code_lenses

    def unresolved_visible_code_lenses(self, view: sublime.View) -> list[CachedCodeLens]:
        visible_region = view.visible_region()
        return [
            cl for cl in itertools.chain.from_iterable(self.code_lenses.values())
            if not is_resolved(cl.data) and range_to_region(cl.data['range'], view).intersects(visible_region)
        ]

    def code_lenses_with_command(self) -> list[ResolvedCodeLens]:
        """ Returns only the code lenses that are either resolved, or have a cached command. """
        code_lenses: list[ResolvedCodeLens] = []
        for cached_code_lens in itertools.chain.from_iterable(self.code_lenses.values()):
            code_lens = cached_code_lens.data.copy()
            if is_resolved(code_lens):
                code_lenses.append(code_lens)
            elif cached_command := cached_code_lens.cached_command:
                code_lens['command'] = cached_command
                code_lens = cast(ResolvedCodeLens, code_lens)
                code_lens['uses_cached_command'] = True
                code_lenses.append(code_lens)
        return code_lenses


class LspToggleCodeLensesCommand(LspWindowCommand):
    capability = 'codeLensProvider'

    @classmethod
    def are_enabled(cls, window: sublime.Window | None) -> bool:
        if not window:
            return False
        return bool(window.settings().get(CODE_LENS_ENABLED_KEY, True))

    def is_checked(self) -> bool:
        return self.are_enabled(self.window)

    def run(self) -> None:
        enable = not self.is_checked()
        self.window.settings().set(CODE_LENS_ENABLED_KEY, enable)
        sublime.set_timeout_async(partial(self._update_views_async, enable))

    def _update_views_async(self, enable: bool) -> None:
        window_manager = windows.lookup(self.window)
        if not window_manager:
            return
        for session in window_manager.get_sessions():
            for session_view in session.session_views_async():
                if enable:
                    session_view.session_buffer.do_code_lenses_async(session_view.view)
                else:
                    session_view.clear_code_lenses_async()


class LspCodeLensCommand(LspTextCommand):

    capability = 'codeLensProvider'

    def run(self, edit: sublime.Edit) -> None:
        listener = windows.listener_for_view(self.view)
        if not listener:
            return
        commands: list[tuple[str, Command]] = []
        for region in self.view.sel():
            for sv in listener.session_views_async():
                session_name = sv.session.config.name
                for command in sv.get_code_lenses_for_region(region):
                    commands.append((session_name, command))
        if not commands:
            return
        elif len(commands) == 1:
            self.on_select(commands, 0)
        elif window := self.view.window():
            window.show_quick_panel(
                [sublime.QuickPanelItem(cmd["title"], annotation=session_name) for session_name, cmd in commands],
                lambda index: self.on_select(commands, index)
            )

    def want_event(self) -> bool:
        return False

    def on_select(self, commands: list[tuple[str, Command]], index: int) -> None:
        try:
            session_name, command = commands[index]
        except IndexError:
            return
        args = {
            "session_name": session_name,
            "command_name": command["command"],
            "command_args": command.get("arguments")
        }
        self.view.run_command("lsp_execute", args)
