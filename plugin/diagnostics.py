from __future__ import annotations
from ..protocol import Diagnostic
from ..protocol import DiagnosticOptions
from ..protocol import DiagnosticRegistrationOptions
from ..protocol import DiagnosticSeverity
from ..protocol import DocumentUri
from .core.constants import DIAGNOSTIC_KINDS
from .core.constants import REGIONS_INITIALIZE_FLAGS
from .core.protocol import Point
from .core.settings import userprefs
from .core.types import DocumentSelector_
from .core.url import normalize_uri
from .core.views import diagnostic_severity
from .core.views import format_diagnostics_for_annotation
from functools import lru_cache
from typing import TYPE_CHECKING
from typing import Union
import itertools
import sublime


if TYPE_CHECKING:
    from .core.sessions import Session


DiagnosticsIdentifier = Union[str, None]

# Delay in milliseconds that applies when a pull diagnostics request is retriggered after being cancelled by the server
# with the retriggerRequest flag.
DOCUMENT_DIAGNOSTICS_RETRIGGER_DELAY = 500
WORKSPACE_DIAGNOSTICS_RETRIGGER_DELAY = 3000


@lru_cache
def get_diagnostics_identifiers(session: Session, view: sublime.View) -> set[DiagnosticsIdentifier]:
    return session.diagnostics.get_identifiers(view)


class DiagnosticsStorage:
    """ Per session storage for diagnostics from pull diangostics streams and from publishDiagnostics notifications. """

    def __init__(self) -> None:
        self._providers: dict[str | None, DiagnosticOptions | DiagnosticRegistrationOptions] = {}
        self._identifiers: set[DiagnosticsIdentifier] = set()
        self._workspace_diagnostics_identifiers: set[DiagnosticsIdentifier] = set()
        self._diagnostics: dict[DocumentUri, dict[DiagnosticsIdentifier, list[Diagnostic]]] = {}
        self.token_identifier_map: dict[str, DiagnosticsIdentifier] = {}  # maps identifiers to partial result tokens

    def get_identifiers(self, view: sublime.View) -> set[DiagnosticsIdentifier]:
        return set(
            diagnostic_options.get('identifier') for diagnostic_options in self._providers.values()
            if DocumentSelector_(diagnostic_options.get('documentSelector') or []).matches(view)
        )

    @property
    def workspace_diagnostics_identifiers(self) -> set[DiagnosticsIdentifier]:
        return self._workspace_diagnostics_identifiers

    def _update_identifiers(self) -> None:
        self._identifiers = set(options.get('identifier') for options in self._providers.values())
        self._workspace_diagnostics_identifiers = set(
            options.get('identifier') for options in self._providers.values() if options['workspaceDiagnostics']
        )
        get_diagnostics_identifiers.cache_clear()

    def register_provider(
        self, registration_id: str | None, options: DiagnosticOptions | DiagnosticRegistrationOptions
    ) -> None:
        # Note that the registration ID can be None when using static registration, in which case the provider cannot be
        # unregistered later.
        self._providers[registration_id] = options
        self._update_identifiers()

    def unregister_provider(self, registration_id: str) -> None:
        self._providers.pop(registration_id)
        self._update_identifiers()

    def set_diagnostics(
        self, uri: DocumentUri, identifier: DiagnosticsIdentifier, diagnostics: list[Diagnostic]
    ) -> None:
        if identifier is not None and identifier not in self._identifiers:
            raise ValueError(f'diagnostic stream with identifier {identifier} must be registered first')
        normalized_uri = normalize_uri(uri)
        self._diagnostics.setdefault(normalized_uri, {})[identifier] = diagnostics

    def _sorted_diagnostics_for_uri(self, uri: DocumentUri, max_severity: int) -> list[Diagnostic]:
        return sorted(
            (
                diagnostic for diagnostic
                in itertools.chain.from_iterable(self._diagnostics.get(uri, {}).values())
                if diagnostic_severity(diagnostic) <= max_severity
            ),
            key=lambda diagnostic: (Point.from_lsp(diagnostic['range']['start']), diagnostic_severity(diagnostic))
        )

    def get_diagnostics(self, max_severity: int = DiagnosticSeverity.Hint) -> dict[DocumentUri, list[Diagnostic]]:
        return {uri: self._sorted_diagnostics_for_uri(uri, max_severity) for uri in self._diagnostics}

    def get_diagnostics_for_uri(
        self, uri: DocumentUri, max_severity: int = DiagnosticSeverity.Hint
    ) -> list[Diagnostic]:
        return self._sorted_diagnostics_for_uri(normalize_uri(uri), max_severity)

    def total_errors_and_warnings(self) -> tuple[int, int]:
        total_errors = 0
        total_warnings = 0
        for diagnostics in self._diagnostics.values():
            for diagnostic in itertools.chain.from_iterable(diagnostics.values()):
                severity = diagnostic_severity(diagnostic)
                if severity == DiagnosticSeverity.Error:
                    total_errors += 1
                elif severity == DiagnosticSeverity.Warning:
                    total_warnings += 1
        return total_errors, total_warnings


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
