class Settings(object):

    def __init__(self):
        self.show_status_messages = True
        self.show_view_status = True
        self.auto_show_diagnostics_panel = True
        self.show_diagnostics_phantoms = False
        self.show_diagnostics_count_in_view_status = False
        self.show_diagnostics_in_view_status = True
        self.show_diagnostics_severity_level = 3
        self.only_show_lsp_completions = False
        self.diagnostics_highlight_style = "underline"
        self.highlight_active_signature_parameter = True
        self.document_highlight_style = "stippled"
        self.document_highlight_scopes = {
            "unknown": "text",
            "text": "text",
            "read": "markup.inserted",
            "write": "markup.changed"
        }
        self.diagnostics_gutter_marker = "dot"
        self.complete_all_chars = False
        self.completion_hint_type = "auto"
        self.resolve_completion_for_snippets = False
        self.log_debug = True
        self.log_server = True
        self.log_stderr = False
        self.log_payloads = False
