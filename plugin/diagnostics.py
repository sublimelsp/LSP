from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.typing import Dict, List, Tuple
from .core.views import DIAGNOSTIC_KINDS
from .core.views import diagnostic_severity
from .core.views import format_diagnostics_for_annotation
from .core.views import RegionProvider
import sublime


class DiagnosticsView(RegionProvider):
    ANNOTATIONS_REGION_KEY = "lsp_d-annotations"

    @classmethod
    def initialize_region_keys(cls, view: sublime.View) -> None:
        r = [sublime.Region(0, 0)]
        for severity in DIAGNOSTIC_KINDS.keys():
            view.add_regions(cls._annotation_key(severity), r)

    @classmethod
    def _annotation_key(cls, severity: DiagnosticSeverity) -> str:
        return '{}-{}'.format(cls.ANNOTATIONS_REGION_KEY, severity)

    def __init__(self, view: sublime.View) -> None:
        self._view = view

    def clear_annotations(self) -> None:
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
