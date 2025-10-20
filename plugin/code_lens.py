from __future__ import annotations
from .core.constants import CODE_LENS_ENABLED_KEY
from .core.protocol import CodeLens
from .core.protocol import CodeLensExtended
from .core.protocol import Error
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.registry import windows
from .core.views import make_command_link
from .core.views import range_to_region
from html import escape as html_escape
from functools import partial
from typing import Generator, Iterable
from typing import cast
import itertools
import sublime


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
                    session_view.start_code_lenses_async()
                else:
                    session_view.clear_code_lenses_async()


class CodeLensData:
    __slots__ = (
        'data',
        'region',
        'session_name',
        'annotation',
        'is_resolve_error',
    )

    def __init__(self, data: CodeLens, view: sublime.View, session_name: str) -> None:
        self.data = data
        self.region = range_to_region(data['range'], view)
        self.session_name = session_name
        self.annotation = '...'
        self.resolve_annotation(view.id())
        self.is_resolve_error = False

    def __repr__(self) -> str:
        return f'CodeLensData(resolved={self.is_resolved()}, region={self.region!r})'

    def is_resolved(self) -> bool:
        """A code lens is considered resolved if the inner data contains the 'command' key."""
        return 'command' in self.data or self.is_resolve_error

    def to_lsp(self) -> CodeLensExtended:
        copy = cast(CodeLensExtended, self.data.copy())
        copy['session_name'] = self.session_name
        return copy

    @property
    def small_html(self) -> str:
        return f'<small style="font-family: system">{self.annotation}</small>'

    def resolve_annotation(self, view_id: int) -> None:
        command = self.data.get('command')
        if command is not None:
            command_name = command.get('command')
            if command_name:
                self.annotation = make_command_link('lsp_execute', command['title'], {
                    'session_name': self.session_name,
                    'command_name': command_name,
                    'command_args': command.get('arguments', []),
                }, view_id=view_id)
            else:
                self.annotation = html_escape(command['title'])
        else:
            self.annotation = '...'

    def resolve(self, view: sublime.View, code_lens_or_error: CodeLens | Error) -> None:
        if isinstance(code_lens_or_error, Error):
            self.is_resolve_error = True
            self.annotation = '<span style="color: color(var(--redish)">error</span>'
            return
        self.data = code_lens_or_error
        self.region = range_to_region(code_lens_or_error['range'], view)
        self.resolve_annotation(view.id())


class CodeLensView:
    CODE_LENS_KEY = 'lsp_code_lens'

    def __init__(self, view: sublime.View) -> None:
        self.view = view
        self._init = False
        self._phantom = sublime.PhantomSet(view, self.CODE_LENS_KEY)
        self._code_lenses: dict[tuple[int, int], list[CodeLensData]] = {}

    def clear(self) -> None:
        self._code_lenses.clear()

    def is_empty(self) -> bool:
        return not self._code_lenses

    def is_initialized(self) -> bool:
        return self._init

    def _clear_annotations(self) -> None:
        for index, lens in enumerate(self._flat_iteration()):
            self.view.erase_regions(self._region_key(lens.session_name, index))

    def _region_key(self, session_name: str, index: int) -> str:
        return f'{self.CODE_LENS_KEY}.{session_name}.{index}'

    def clear_view(self) -> None:
        self._phantom.update([])
        self._clear_annotations()

    def handle_response(self, session_name: str, response: list[CodeLens]) -> None:
        self._init = True
        responses = [CodeLensData(data, self.view, session_name) for data in response]
        responses.sort(key=lambda c: c.region)
        result: dict[tuple[int, int], list[CodeLensData]] = {
            region.to_tuple(): list(groups)
            for region, groups in itertools.groupby(responses, key=lambda c: c.region)
        }

        # Fast path: no extra work to do
        if self.is_empty():
            self._code_lenses = result
            return

        # Update new code lenses with cached data to prevent the editor
        # from jumping around due to some code lenses going from resolved
        # to unresolved due to a requery of the document data
        for key, groups in result.items():
            try:
                old_groups = self._code_lenses[key]
            except KeyError:
                continue

            # It's only really safe to do this when both groups are the same
            if len(groups) == len(old_groups):
                for old, new in zip(old_groups, groups):
                    # This assignment is only temporary, the resolve call in the future
                    # will fill it in with the actual data after resolve_annotation() is called
                    # However assigning the annotation if they're the same makes the screen not jump
                    # from the phantoms moving around too much
                    new.annotation = old.annotation

        self._code_lenses = result

    def _flat_iteration(self) -> Iterable[CodeLensData]:
        for group in self._code_lenses.values():
            yield from group

    def unresolved_visible_code_lenses(self, visible: sublime.Region) -> Iterable[CodeLensData]:
        for lens in self._flat_iteration():
            if not lens.is_resolved() and visible.intersects(lens.region):
                yield lens

    def _get_phantom_region(self, region: sublime.Region) -> sublime.Region:
        line = self.view.line(region)
        code = self.view.substr(line)
        offset = 0
        for ch in code:
            if ch.isspace():
                offset += 1
            else:
                break
        return sublime.Region(line.a + offset, line.b)

    def render(self, mode: str) -> None:
        if mode == 'phantom':
            phantoms = []
            for key, group in self._code_lenses.items():
                region = sublime.Region(*key)
                phantom_region = self._get_phantom_region(region)
                html = '<body id="lsp-code-lens">{}</body>'.format(
                    '\n<small style="font-family: system">|</small>\n'.join(lens.small_html for lens in group))
                phantoms.append(sublime.Phantom(phantom_region, html, sublime.PhantomLayout.BELOW))
            self._phantom.update(phantoms)
        else:  # 'annotation'
            self._clear_annotations()
            flags = sublime.RegionFlags.NO_UNDO
            accent = self.view.style_for_scope("region.greenish markup.accent.codelens.lsp")["foreground"]
            for index, lens in enumerate(self._flat_iteration()):
                self.view.add_regions(
                    self._region_key(lens.session_name, index), [lens.region], "", "", flags, [lens.small_html], accent)

    def get_resolved_code_lenses_for_region(self, region: sublime.Region) -> Generator[CodeLensExtended, None, None]:
        region = self.view.line(region)
        for lens in self._flat_iteration():
            if lens.is_resolved() and lens.region.intersects(region):
                yield lens.to_lsp()


class LspCodeLensCommand(LspTextCommand):

    def run(self, edit: sublime.Edit) -> None:
        listener = windows.listener_for_view(self.view)
        if not listener:
            return
        code_lenses: list[CodeLensExtended] = []
        for region in self.view.sel():
            for sv in listener.session_views_async():
                code_lenses.extend(sv.get_resolved_code_lenses_for_region(region))
        if not code_lenses:
            return
        elif len(code_lenses) == 1:
            command = code_lenses[0].get("command")
            assert command
            if not command:
                return
            args = {
                "session_name": code_lenses[0]["session_name"],
                "command_name": command["command"],
                "command_args": command.get("arguments")
            }
            self.view.run_command("lsp_execute", args)
        else:
            self.view.show_popup_menu(
                [c["command"]["title"] for c in code_lenses],  # type: ignore
                lambda i: self.on_select(code_lenses, i)
            )

    def want_event(self) -> bool:
        return False

    def on_select(self, code_lenses: list[CodeLensExtended], index: int) -> None:
        try:
            code_lens = code_lenses[index]
        except IndexError:
            return
        command = code_lens.get("command")
        assert command
        if not command:
            return
        args = {
            "session_name": code_lens["session_name"],
            "command_name": command["command"],
            "command_args": command.get("arguments")
        }
        self.view.run_command("lsp_execute", args)
