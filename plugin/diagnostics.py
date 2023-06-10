from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.typing import Dict, List, NotRequired, Optional, Tuple, TypedDict, Union
from .core.views import DIAGNOSTIC_KINDS
from .core.views import diagnostic_severity
from .core.views import format_diagnostics_for_annotation
from .core.views import range_to_region
from itertools import chain
import html
import sublime


class StackItemBlank:

    __slots__ = ('diagnostic', )

    def __init__(self, diagnostic: Diagnostic) -> None:
        self.diagnostic = diagnostic


class StackItemDiagnostic:

    __slots__ = ('diagnostic', )

    def __init__(self, diagnostic: Diagnostic) -> None:
        self.diagnostic = diagnostic


class StackItemOverlap:

    __slots__ = ()


class StackItemSpace:

    __slots__ = ('text', )

    def __init__(self, text: str) -> None:
        self.text = text


StackItem = Union[StackItemDiagnostic, StackItemSpace, StackItemOverlap]

LineStack = TypedDict('LineStack', {
    'region': Optional[sublime.Region],
    'stack': List[StackItem]
})

StackMap = Dict[int, LineStack]

Line = TypedDict('Line', {
    'class': str,
    'content': NotRequired[str],
})

DiagnosticBlock = TypedDict('DiagnosticBlock', {
    'content': List[List[Line]],
    'line': int,
    'region': sublime.Region,
})


class DiagnosticLines:

    CSS = '''
        .inline-block {
            display: inline-block;
        }
        .d_error {
            color: color(var(--redish) alpha(0.85))
        }
        .d_error_bg {
            background-color: color(var(--redish) alpha(0.1))
        }
        .d_warning {
            color: color(var(--yellowish) alpha(0.85))
        }
        .d_warning_bg {
            background-color: color(var(--yellowish) alpha(0.1))
        }
        .d_info {
            color: color(var(--bluish) alpha(0.85))
        }
        .d_info_bg {
            background-color: color(var(--bluish) alpha(0.1))
        }
        .d_hint {
            color: color(var(--greenish) alpha(0.85))
        }
        .d_hint_bg {
            background-color: color(var(--greenish) alpha(0.1))
        }
    '''.strip()

    HIGHLIGHTS = {
        1: 'error',
        2: 'warning',
        3: 'info',
        4: 'hint'
    }

    COLORS = {
        'error': 'var(--redish)',
        'warning': 'var(--yellowish)',
        'info': 'var(--blueish)',
        'hint': 'var(--greenish)',
        '': 'transparent',
    }

    SYMBOLS = {
        'BOTTOM_LEFT': '└',
        'UPSIDE_DOWN_T': '┴',
        'MIDDLE_CROSS': '┼',
        'MIDDLE_RIGHT_CENTER': '├',
        'VERTICAL': '│',
        'HORIZONTAL': '─'
    }

    def __init__(self, view: sublime.View, highlight_line_background: bool = False) -> None:
        self._view = view
        self._highlight_line_background = highlight_line_background
        self._phantoms = sublime.PhantomSet(view, 'lsp_lines')

    def update_async(self, diagnostics: List[Tuple[Diagnostic, sublime.Region]]) -> None:
        sorted_diagnostics = self._sort_diagnostics(self._preprocess_diagnostic(diagnostics))
        line_stacks = self._generate_line_stacks(sorted_diagnostics)
        blocks = self._generate_diagnostic_blocks(line_stacks)
        phantoms = []  # type: List[sublime.Phantom]
        for block in blocks:
            content = self._generate_region_html(block)
            phantoms.append(sublime.Phantom(block['region'], content, sublime.LAYOUT_BELOW))
        sublime.set_timeout(lambda: self._update_sync(phantoms))

    def _update_sync(self, phantoms: List[sublime.Phantom]) -> None:
        _, y_before = self._view.text_to_layout(self._view.sel()[0].begin())
        x, y_viewport_before = self._view.viewport_position()
        self._phantoms.update(phantoms)
        _, y_after = self._view.text_to_layout(self._view.sel()[0].begin())
        y_shift = y_after - y_before
        if y_shift != 0:
            new_y = y_viewport_before + y_shift
            self._view.set_viewport_position((x, new_y), animate=False)

    def clear(self) -> None:
        self._phantoms = sublime.PhantomSet(self._view, 'lsp-lines')

    def _generate_region_html(self, block: DiagnosticBlock) -> str:
        lines = [
            '<style>{}</style>'.format(self.CSS)
        ]
        for line in block["content"]:
            row_items = []
            for item in line:
                item_class = 'd_{0}'.format(item['class'])
                css_classes = ['inline-block', item_class]
                if self._highlight_line_background:
                    css_classes.append('{0}_bg'.format(item_class))
                row_items.append('<div class="{0}">{1}</div>'.format(
                    ' '.join(css_classes), html.escape(item.get('content', '')).replace(" ", "&nbsp;")))
            lines.append('<div>{0}</div>'.format(''.join(row_items)))
        return '\n'.join(lines)

    def _preprocess_diagnostic(self, diagnostics: List[Tuple[Diagnostic, sublime.Region]]):
        return [diagnostic[0] for diagnostic in diagnostics]

    def _sort_diagnostics(self, diagnostics: List[Diagnostic]):
        return sorted(diagnostics, key=lambda x: (x['range']['start']['line'], x['range']['start']['character']))

    def _generate_line_stacks(self, diagnostics: List[Diagnostic]) -> StackMap:
        # Initialize an empty dictionary to store line stacks
        line_stacks = {}  # type: StackMap
        # Set the initial values for the previous line number and previous column
        prev_lnum = -1
        prev_col = 0
        # Iterate over the diagnostics
        for diagnostic in diagnostics:
            if not diagnostic['message'].strip():
                # Skip diagnostics with empty message.
                continue
            range_start = diagnostic['range']['start']
            current_line = range_start['line']
            current_col = range_start['character']
            # Create an empty list for the current line if it doesn't already exist in the dictionary
            line_stacks.setdefault(current_line, {'region': None, 'stack': []})
            if line_stacks[current_line]['region'] is None:
                region = range_to_region(diagnostic['range'], self._view)
                region.b = region.a
                line_stacks[current_line]['region'] = region
            # Get the current stack for the current line
            stack = line_stacks[current_line]['stack']
            # Check if the diagnostic is on a new line
            if current_line != prev_lnum:
                # If so, add an empty space to the stack
                stack.append(StackItemSpace(''))
            elif current_col != prev_col:
                # If not on a new line but on a new column, add spacing to the stack
                # Calculate the spacing by subtracting the previous column from the current column, minus 1 (to account
                # for 0-based index)
                spacing = (current_col - prev_col) - 1
                stack.append(StackItemSpace(' ' * spacing))
            else:
                # If the diagnostic is on the same exact spot as the previous one, add an overlap to the stack
                stack.append(StackItemOverlap())
            # If not blank, add the diagnostic to the stack
            stack.append(StackItemDiagnostic(diagnostic))
            # Update the previous line number and column for the next iteration
            prev_lnum = current_line
            prev_col = current_col
        return line_stacks

    def _generate_diagnostic_blocks(self, stacks: StackMap) -> List[DiagnosticBlock]:
        """
        Generates the diagnostic blocks from the given stacks
        """
        blocks = []
        for key, line in stacks.items():
            block = {'line': key, 'content': [], 'region': line['region']}
            for i, item in enumerate(reversed(line['stack'])):
                if not isinstance(item, StackItemDiagnostic):
                    continue
                diagnostic = item.diagnostic
                index = len(line['stack']) - 1 - i
                left, overlap, multi = self._generate_left_side(line['stack'], index, diagnostic)
                center = self._generate_center(overlap, multi, diagnostic)
                for msg_line in diagnostic['message'].split('\n'):
                    block['content'].append(list(chain(left, center, [{
                        'content': msg_line,
                        'class': self.HIGHLIGHTS[diagnostic_severity(diagnostic)]
                    }])))
                    if overlap:
                        center = [
                            {
                                'class': self.HIGHLIGHTS[diagnostic_severity(diagnostic)],
                                'content': self.SYMBOLS['VERTICAL']
                            },
                            {'class': '', 'content': '     '},
                        ]
                    else:
                        center = [{'class': '', 'content': '      '}]
            blocks.append(block)
        return blocks

    def _generate_left_side(
        self, line: List[StackItem], index: int, diagnostic: Diagnostic
    ) -> Tuple[List[Line], bool, int]:
        """
        Generates the left side of the diagnostic block for a given line
        """
        left = []
        overlap = False
        multi = 0
        current_index = 0
        while current_index < index:
            item = line[current_index]
            if isinstance(item, StackItemSpace):
                if multi == 0:
                    left.append({'class': '', 'content': item.text})
                else:
                    left.append({
                        'class': self.HIGHLIGHTS[diagnostic_severity(diagnostic)],
                        'content': self.SYMBOLS['HORIZONTAL'] * len(item.text)
                    })
            elif isinstance(item, StackItemDiagnostic):
                next_item = line[current_index + 1]
                if current_index + 1 != len(line) and not isinstance(next_item, StackItemOverlap):
                    left.append(
                        {
                            "class": self.HIGHLIGHTS[diagnostic_severity(item.diagnostic)],
                            "content": self.SYMBOLS['VERTICAL'],
                        }
                    )
                overlap = False
            elif isinstance(item, StackItemBlank):
                if multi == 0:
                    left.append(
                        {
                            "class": self.HIGHLIGHTS[diagnostic_severity(item.diagnostic)],
                            "content": self.SYMBOLS['BOTTOM_LEFT'],
                        }
                    )
                else:
                    left.append(
                        {
                            "class": self.HIGHLIGHTS[diagnostic_severity(item.diagnostic)],
                            "content": self.SYMBOLS['UPSIDE_DOWN_T'],
                        }
                    )
                multi += 1
            elif isinstance(item, StackItemOverlap):
                overlap = True
            current_index += 1
        return left, overlap, multi

    def _generate_center(self, overlap: bool, multi: int, diagnostic: Diagnostic) -> List[Line]:
        """
        Generates the center symbol of the diagnostic block
        """
        center_symbol = ''
        if overlap and multi > 0:
            center_symbol = self.SYMBOLS['MIDDLE_CROSS']
        elif overlap:
            center_symbol = self.SYMBOLS['MIDDLE_RIGHT_CENTER']
        elif multi > 0:
            center_symbol = self.SYMBOLS['UPSIDE_DOWN_T']
        else:
            center_symbol = self.SYMBOLS['BOTTOM_LEFT']
        return [
            {
                "class": self.HIGHLIGHTS[diagnostic_severity(diagnostic)],
                "content": '{0}{1} '.format(center_symbol, self.SYMBOLS['HORIZONTAL'] * 4),
            }
        ]


class DiagnosticsView():
    ANNOTATIONS_REGION_KEY = "lsp_d-annotations"

    @classmethod
    def _annotation_key(cls, severity: DiagnosticSeverity) -> str:
        return '{}-{}'.format(cls.ANNOTATIONS_REGION_KEY, severity)

    def __init__(self, view: sublime.View) -> None:
        self._view = view

    def clear_annotations_async(self) -> None:
        for severity in DIAGNOSTIC_KINDS.keys():
            self._view.erase_regions(self._annotation_key(severity))

    def update_diagnostic_annotations_async(self, diagnostics: List[Tuple[Diagnostic, sublime.Region]]) -> None:
        # To achieve the correct order of annotations (most severe shown first) and have the color of annotation
        # match the diagnostic severity, we have to separately add regions for each severity, from most to least severe.
        diagnostics_per_severity = {}  # type: Dict[DiagnosticSeverity, List[Tuple[Diagnostic, sublime.Region]]]
        for severity in DIAGNOSTIC_KINDS.keys():
            diagnostics_per_severity[severity] = []
        for diagnostic, region in diagnostics:
            diagnostics_per_severity[diagnostic_severity(diagnostic)].append((diagnostic, region))
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        for severity, diagnostics in diagnostics_per_severity.items():
            if not diagnostics:
                continue
            all_diagnostics = []
            regions = []
            for diagnostic, region in diagnostics:
                all_diagnostics.append(diagnostic)
                regions.append(region)
            annotations, color = format_diagnostics_for_annotation(all_diagnostics, severity, self._view)
            self._view.add_regions(
                self._annotation_key(severity), regions, flags=flags, annotations=annotations, annotation_color=color)
