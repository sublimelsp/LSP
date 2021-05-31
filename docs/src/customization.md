## Hover popups

LSP uses [mdpopups](https://github.com/facelessuser/sublime-markdown-popups) to display the popup.
You can override its style by creating a `Packages/User/mdpopups.css` file.
See the [mdpopups documentation](http://facelessuser.github.io/sublime-markdown-popups/) for more details.

## Color scheme customizations

Some features use TextMate scopes to control the colors (underline, background or text color) of styled regions in a document or popup.
Colors can be customized by adding a rule for these scopes into your color scheme.
There is an example in the [official ST documentation](https://www.sublimetext.com/docs/color_schemes.html#customization) which explains how to do that.

The following tables give an overview about the scope names used by LSP.

### Document Highlights

!!! info "This feature is only available if the server has the *documentHighlightProvider* capability."
    Highlights other occurrences of the symbol at a given cursor position.

| scope | DocumentHighlightKind | description |
| ----- | --------------------- | ----------- |
| `markup.highlight.text.lsp` | Text | A textual occurrence |
| `markup.highlight.read.lsp` | Read | Read-access of a symbol, like reading a variable |
| `markup.highlight.write.lsp` | Write | Write-access of a symbol, like writing to a variable |

!!! note
    If `document_highlight_style` is set to "fill" in the LSP settings, the highlighting color can be controlled via the "background" color from a color scheme rule for the listed scopes.

### Diagnostics

| scope | DiagnosticSeverity | description | drawn as
| ----- | ------------------ | ----------- | --------
| `markup.error.lsp` | Error | Reports an error | Squiggly underlines
| `markup.warning.lsp` | Warning | Reports a warning | Squiggly underlines
| `markup.info.lsp` | Information | Reports an information | Stippled underlines
| `markup.info.hint.lsp` | Hint | Reports a hint | Stippled underlines

When the region of the diagnostic spans more than one line, the diagnostic is always drawn as a box.

Diagnostics will also optionally include the following scopes:

| scope                    | diagnostic tag name | description                 |
| ------------------------ | ------------------- | --------------------------- |
| `markup.unnecessary.lsp` | Unnecessary         | Unused or unnecessary code  |
| `markup.deprecated.lsp`  | Deprecated          | Deprecated or obsolete code |

Those scopes can be used to, for example, gray-out the text color of unused code, if the server supports that.

For example, to add a custom rule for `Mariana` color scheme, select `UI: Customize Color Scheme` from the Command Palette and add the following rule:

```json
{
    "rules": [
        {
            "scope": "markup.unnecessary.lsp",
            "foreground": "color(rgb(255, 255, 255) alpha(0.4))",
            "background": "color(var(blue3) alpha(0.9))"
        }
    ]
}
```

The color scheme rule only works if the "background" color is different from the global background of the scheme. So for other color schemes, ideally pick a background color that is as close as possible, but marginally different from the original background.

### Signature Help

| scope | description |
| ----- | ----------- |
| `entity.name.function.sighelp.lsp` | Function name in the signature help popup |
| `variable.parameter.sighelp.lsp` | Function argument in the signature help popup |

### Annotations

| scope | description |
| ----- | ----------- |
| `markup.accent.codelens.lsp` | Accent color for code lens annotations |
| `markup.accent.codeaction.lsp` | Accent color for code action annotations |
