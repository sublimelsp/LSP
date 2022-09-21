from .sessions import Manager
from .protocol import Diagnostic, DocumentUri
from .typing import List, Optional, Tuple
from .url import parse_uri


class DiagnosticsManager():
    """Per-window diagnostics manager that gives access to combined diagnostics from all active sessions."""

    def __init__(self, manager: Manager) -> None:
        self._manager = manager

    def has_diagnostics(self, document_uri: Optional[DocumentUri]) -> bool:
        """
        Returns true if there are any diagnostics (optionally filtered by `document_uri`).
        """
        parsed_uri = parse_uri(document_uri) if document_uri else None
        for session in self._manager.get_sessions():
            if (parsed_uri and parsed_uri in session.diagnostics) or session.diagnostics:
                return True
        return False

    def diagnostics_by_document_uri(self, document_uri: DocumentUri) -> List[Diagnostic]:
        """
        Returns possibly empty list of diagnostic for `document_uri`.
        """
        diagnostics = []  # type: List[Diagnostic]
        for session in self._manager.get_sessions():
            diagnostics.extend(session.diagnostics.diagnostics_by_document_uri(document_uri))
        return diagnostics

    def sum_total_errors_and_warnings_async(self) -> Tuple[int, int]:
        """
        Returns `(total_errors, total_warnings)` count of all diagnostics for all sessions.
        """
        errors = 0
        warnings = 0
        for session in self._manager.get_sessions():
            session_errors, session_warnings = session.diagnostics.sum_total_errors_and_warnings_async()
            errors += session_errors
            warnings += session_warnings
        return (errors, warnings)
