from __future__ import annotations

from ..constants import CODE_ACTION_KINDS
from typing import cast
from typing import Iterable
from typing import TYPE_CHECKING
import sublime

if TYPE_CHECKING:
    from ....protocol import CodeAction
    from ....protocol import CodeActionKind
    from ....protocol import Command


def kind_contains_other_kind(kind: str, other_kind: str) -> bool:
    """
    Check if `other_kind` is a sub-kind of `kind`.

    The kind `"refactor.extract"` for example contains `"refactor.extract"` and `"refactor.extract.function"`,
    but not `"unicorn.refactor.extract"`, or `"refactor.extractAll"` or `"refactor"`.
    """
    if kind == other_kind:
        return True
    kind_len = len(kind)
    return len(other_kind) > kind_len and other_kind.startswith(kind + '.')


def format_code_actions_for_quick_panel(
    session_actions: Iterable[tuple[str, CodeAction | Command]]
) -> tuple[list[sublime.QuickPanelItem], int]:
    items: list[sublime.QuickPanelItem] = []
    selected_index = -1
    for idx, (config_name, code_action) in enumerate(session_actions):
        lsp_kind = code_action.get("kind", "")
        first_kind_component = cast('CodeActionKind', str(lsp_kind).split(".")[0])
        kind = CODE_ACTION_KINDS.get(first_kind_component, sublime.KIND_AMBIGUOUS)
        items.append(sublime.QuickPanelItem(code_action["title"], annotation=config_name, kind=kind))
        if code_action.get('isPreferred', False):
            selected_index = idx
    return items, selected_index
