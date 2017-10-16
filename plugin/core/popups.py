popup_class = "lsp_popup"

popup_css = '''
    .lsp_popup {
        margin: 0.5rem 0.5rem 0 0.5rem;
    }
    .lsp_popup .highlight {
        border-width: 0;
        border-radius: 0;
    }
    .lsp_popup p {
        margin-bottom: 0.5rem;
        padding: 0 0.5rem;
        font-family: system;
    }
'''


def preserve_whitespace(contents: str) -> str:
    """Preserve empty lines and whitespace for markdown conversion."""
    contents = contents.replace('\t', '\u00A0' * 4)
    contents = contents.replace('  ', '\u00A0' * 2)
    return contents
