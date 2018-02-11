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
    .lsp_popup li {
        font-family: system;
    }
    .lsp_popup .errors {
        border-width: 0;
        background-color: color(var(--redish) alpha(0.25));
        color: --whitish;
        margin-bottom: 0.5rem;
        padding: 0.5rem;
    }
    .lsp_popup .warnings {
        border-width: 0;
        background-color: color(var(--yellowish) alpha(0.25));
        color: --whitish;
        margin-bottom: 0.5rem;
        padding: 0.5rem;
    }

'''
