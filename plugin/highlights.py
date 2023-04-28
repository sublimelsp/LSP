from .core.registry import LspTextCommand
from .core.typing import Optional
from .core.views import DOCUMENT_HIGHLIGHT_KINDS
import itertools
import sublime


class LspFindAllUnderCommand(LspTextCommand):

    capability = 'documentHighlightProvider'

    def run(self, edit: sublime.Edit) -> None:
        highlight_regions = itertools.chain.from_iterable(
            [self.view.get_regions("lsp_highlight_{}s".format(kind)) for kind in DOCUMENT_HIGHLIGHT_KINDS.values()]
        )
        self.view.sel().add_all(highlight_regions)

    def want_event(self) -> bool:
        return False


class LspFindUnderExpandCommand(LspTextCommand):

    capability = 'documentHighlightProvider'

    last_sel_idx = 0
    region = None  # type: Optional[sublime.Region]

    def run(self, edit: sublime.Edit, skip: bool = False) -> None:
        highlight_regions = sorted(itertools.chain.from_iterable(
            [self.view.get_regions("lsp_highlight_{}s".format(kind)) for kind in DOCUMENT_HIGHLIGHT_KINDS.values()]
        ))
        selections = self.view.sel()
        if len(selections) == 1:
            self.last_sel_idx = 0
        last_selection_region = selections[self.last_sel_idx] if self.last_sel_idx < len(selections) else selections[-1]
        if last_selection_region.empty():
            for region in highlight_regions:
                if region.contains(last_selection_region.b):
                    selections.add(region)
                    self.region = region
                    return
        else:
            if last_selection_region != self.region:
                self.region = None
                self.view.run_command('find_under_expand_skip' if skip else 'find_under_expand')
                return
            for idx, region in enumerate(highlight_regions):
                if region == last_selection_region:
                    break
            else:
                self.region = None
                self.view.run_command('find_under_expand_skip' if skip else 'find_under_expand')
                return
            if skip:
                selections.subtract(region)
            if idx + 1 < len(highlight_regions):
                self.region = highlight_regions[idx + 1]
                self.last_sel_idx += 1

            else:
                self.region = highlight_regions[0]
                self.last_sel_idx = 0
            selections.add(self.region)

    def want_event(self) -> bool:
        return False


class LspFindUnderExpandSkipCommand(LspTextCommand):

    capability = 'documentHighlightProvider'

    def run(self, edit: sublime.Edit) -> None:
        self.view.run_command('lsp_find_under_expand', {'skip': True})

    def want_event(self) -> bool:
        return False
