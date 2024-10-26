from __future__ import annotations
from .core.constants import DIAGNOSTIC_KINDS
from .core.constants import REGIONS_INITIALIZE_FLAGS
from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.settings import userprefs
from .core.views import diagnostic_severity
from .core.views import format_diagnostics_for_annotation
import sublime


class DiagnosticsAnnotationsView:

    def __init__(self, view: sublime.View, config_name: str) -> None:
        self._view = view
        self._config_name = config_name

    def initialize_region_keys(self) -> None:
        r = [sublime.Region(0, 0)]
        for severity in DIAGNOSTIC_KINDS.keys():
            self._view.add_regions(self._annotation_region_key(severity), r, flags=REGIONS_INITIALIZE_FLAGS)

    def _annotation_region_key(self, severity: DiagnosticSeverity) -> str:
        return f'lsp_da-{severity}-{self._config_name}'

    def draw(self, diagnostics: list[tuple[Diagnostic, sublime.Region]]) -> None:
        flags = sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO
        max_severity_level = userprefs().show_diagnostics_annotations_severity_level
        # To achieve the correct order of annotations (most severe having priority) we have to add regions from the
        # most to the least severe.
        for severity in DIAGNOSTIC_KINDS.keys():
            if severity <= max_severity_level:
                matching_diagnostics: tuple[list[Diagnostic], list[sublime.Region]] = ([], [])
                for diagnostic, region in diagnostics:
                    if diagnostic_severity(diagnostic) != severity:
                        continue
                    matching_diagnostics[0].append(diagnostic)
                    matching_diagnostics[1].append(region)
                annotations, color = format_diagnostics_for_annotation(matching_diagnostics[0], severity, self._view)
                self._view.add_regions(
                    self._annotation_region_key(severity), matching_diagnostics[1], flags=flags,
                    annotations=annotations, annotation_color=color)
            else:
                self._view.erase_regions(self._annotation_region_key(severity))
