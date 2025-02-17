## Keyboard shortcuts (key bindings)

LSP's key bindings can be edited from the `Preferences: LSP Key Bindings` command in the Command Palette. Many of the default key bindings (visible in the left view) are disabled to avoid conflicts with default or user key bindings. To enable those, copy them to your user key bindings on the right, un-comment, and pick the key shortcut of your choice. Check also the overview of available [Keyboard Shortcuts](keyboard_shortcuts.md).

If you want to create a new key binding that is different from the ones that are already included, you might want to make it active only when there is a language server with a specific [LSP capability](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#initialize) (refer to the `ServerCapabilities` structure in that link) running. In that case, you can make use of the `lsp.session_with_capability` context. For example, the following key binding overrides `ctrl+r` to use LSP's symbol provider but only when the current view has a language server with the `documentSymbolProvider` capability and we're in a javascript or a typescript file:

```jsonc title="Packages/User/Default.sublime-keymap"
{
    "command": "lsp_document_symbols",
    "keys": [
        "ctrl+r"
    ],
    "context": [
        {
            "key": "lsp.session_with_capability",
            "operator": "equal",
            "operand": "documentSymbolProvider"
        },
        {
            "key": "selector",
            "operator": "equal",
            "operand": "source.ts, source.js"
        }
    ]
},
```

Generally, you should not need to restrict your key bindings to specific scopes and just rely on checking the capability context.

## Mouse map configuration

If you want to bind some action to a mouse, select `Preferences / Mouse Bindings` from the main menu and edit the file on the righthand side.

Here is an example of a mouse binding that triggers LSP's "go to symbol definition" command on pressing the <kbd>ctrl</kbd>+<kbd>left click</kbd>:

```jsonc title="Packages/User/Default.sublime-mousemap"
[
    {
        "button": "button1",
        "count": 1,
        "modifiers": ["ctrl"],
        "press_command": "drag_select",
        "command": "lsp_symbol_definition",
    }
]
```

## Hover popups

LSP uses [mdpopups](https://github.com/facelessuser/sublime-markdown-popups) to display the popup.
You can override its style by creating a `Packages/User/mdpopups.css` file.
In particular, to get the same font in the popup as your `"font_face"` setting in `Packages/User/Preferences.sublime-settings`, add

```css title="Packages/User/mdpopups.css"
html {
    --mdpopups-font-mono: "your desired font face";
}
```

See the [mdpopups documentation](http://facelessuser.github.io/sublime-markdown-popups/) for more details.

## Inlay Hints

The styles for inlay hints are defined in the [`inlay_hints.css`](https://github.com/sublimelsp/LSP/blob/main/inlay_hints.css) file in the root directory of the LSP package.
If you would like to adjust the inlay hints style, you can create an [override](https://www.sublimetext.com/docs/packages.html#overriding-files-from-a-zipped-package) for this file (a restart of Sublime Text is required to apply the changes).
But be aware that by doing this, you might miss out on future changes in this file, in case of updates in a new release of the LSP package.
So consider using a package like [OverrideAudit](https://packagecontrol.io/packages/OverrideAudit) to get a notification when that happens.

## Color scheme customizations

Some features use TextMate scopes to control the colors (underline, background or text color) of styled regions in a document or popup.
Colors can be customized by adding a rule for these scopes into your color scheme.
There is an example in the [official ST documentation](https://www.sublimetext.com/docs/color_schemes.html#customization) which explains how to do that.

The following tables give an overview of the scope names used by LSP.

### Semantic Highlighting

!!! note
    Semantic highlighting is disabled by default. To enable it, set `"semantic_highlighting": true` in your LSP user settings.

!!! info "This feature is only available if the server has the *semanticTokensProvider* capability."
    Language servers that support semantic highlighting are for example *clangd* and *rust-analyzer*.

In order to support semantic highlighting, the color scheme requires a special rule with a background color set for semantic tokens, which is (marginally) different from the original background.
LSP automatically adds such a rule to the built-in color schemes from Sublime Text.
If you use a custom color scheme, select `UI: Customize Color Scheme` from the Command Palette and add for example the following code:

```jsonc
{
    "rules": [
        {
            "scope": "meta.semantic-token",
            "background": "#00000101"
        },
    ]
}
```

Furthermore, it is possible to adjust the colors for semantic tokens by applying a foreground color to the individual token types:

| scope | [Semantic Token Type](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#semanticTokenTypes) |
| ----- | ------------------ |
| `meta.semantic-token.namespace` | namespace |
| `meta.semantic-token.type` | type |
| `meta.semantic-token.class` | class |
| `meta.semantic-token.enum` | enum |
| `meta.semantic-token.interface` | interface |
| `meta.semantic-token.struct` | struct |
| `meta.semantic-token.typeparameter` | typeParameter |
| `meta.semantic-token.parameter` | parameter |
| `meta.semantic-token.variable` | variable |
| `meta.semantic-token.property` | property |
| `meta.semantic-token.enummember` | enumMember |
| `meta.semantic-token.event` | event |
| `meta.semantic-token.function` | function |
| `meta.semantic-token.method` | method |
| `meta.semantic-token.macro` | macro |
| `meta.semantic-token.keyword` | keyword |
| `meta.semantic-token.modifier` | modifier |
| `meta.semantic-token.comment` | comment |
| `meta.semantic-token.string` | string |
| `meta.semantic-token.number` | number |
| `meta.semantic-token.regexp` | regexp |
| `meta.semantic-token.operator` | operator |
| `meta.semantic-token.decorator` | decorator |

By default, LSP will assign scopes based on the [scope naming guideline](https://www.sublimetext.com/docs/scope_naming.html) to each of these token types, but if you define color scheme rules for the scopes specified above, the latter will take precedence.

Language servers can also add their custom token types, which are not defined in the protocol.
An "LSP-\*" helper package (or user) can provide a `semantic_tokens` mapping in the server configuration for such additional token types, or to override the scopes used for the predefined tokens from the table above.
The keys of this mapping should be the token types and values should be the corresponding scopes.
Semantic tokens with exactly one [token modifier](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#semanticTokenModifiers) can be addressed by appending the modifier after a dot.

```jsonc
{
    "semantic_tokens": {
        "magicFunction": "support.function.builtin",
        "selfParameter": "variable.language",
        "type.defaultLibrary": "storage.type.builtin"
    }
}
```

The color for custom token types can also be adjusted via a color scheme rule for the scope `meta.semantic-token.<token-type>`, where `<token-type>` is the name of the custom token type, but with all letters lowercased (similar to the listed scopes in the table above).
To target tokens with one modifier, use the scope `meta.semantic-token.<token-type>.<token-modifier>` (all lowercase).
Currently, semantic tokens with more than one modifier cannot be styled reliably.

If neither a scope for a custom token type is defined, nor a color scheme rule for this token type exists, then it will only be highlighted via regular syntax highlighting.

### Document Highlights

!!! info "This feature is only available if the server has the *documentHighlightProvider* capability."
    Highlights other occurrences of the symbol at a given cursor position.

| scope | DocumentHighlightKind | description |
| ----- | --------------------- | ----------- |
| `markup.highlight.text.lsp` | Text | A textual occurrence |
| `markup.highlight.read.lsp` | Read | Read-access of a symbol, like reading a variable |
| `markup.highlight.write.lsp` | Write | Write-access of a symbol, like writing to a variable |

!!! note
    If `document_highlight_style` is set to "background" in the LSP settings, the highlighting color can be controlled via the "background" color from a color scheme rule for the listed scopes.

### Hover Highlights

Allows to highlight the word or range for which a hover popup is shown (disabled by default).

| scope |
| ----- |
| `markup.highlight.hover.lsp` |

!!! note
    If `hover_highlight_style` is set to "background" in the LSP settings, the highlighting color can be controlled via the "background" color from a color scheme rule.

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

Those scopes can be used to, for example, gray out the text color of unused code, if the server supports that.

For example, to add a custom rule for `Mariana` color scheme, select `UI: Customize Color Scheme` from the Command Palette and add the following rule:

```jsonc
{
    "rules": [
        {
            "scope": "markup.unnecessary.lsp",
            "foreground": "color(rgb(255, 255, 255) alpha(0.4))",
            "background": "#00000101"
        }
    ]
}
```

The color scheme rule only works if the "background" color is (marginally) different from the original color scheme background.

### Signature Help

| scope | description |
| ----- | ----------- |
| `entity.name.function.sighelp.lsp` | Function name in the signature help popup |
| `variable.parameter.sighelp.lsp` | Function argument in the signature help popup |
| `variable.parameter.sighelp.active.lsp` | Function argument which is currently highlighted in the signature help popup |

!!! note
    If there is no special rule for the active parameter in the color scheme, it will be rendered with bold and underlined font style.
    But if the color scheme defines a different `"foreground"` color for the active parameter, the style follows the `"font_style"` property from the color scheme rule.

### Annotations

| scope | description |
| ----- | ----------- |
| `markup.accent.codelens.lsp` | Accent color for code lens annotations |
| `markup.accent.codeaction.lsp` | Accent color for code action annotations |
