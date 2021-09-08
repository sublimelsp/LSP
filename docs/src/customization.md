## Hover popups

LSP uses [mdpopups](https://github.com/facelessuser/sublime-markdown-popups) to display the popup.
You can override its style by creating a `Packages/User/mdpopups.css` file.
In particular, to get the same font in the popup as your `"font_face"` setting in `Packages/User/Preferences.sublime-settings`, add

```css
html {
    --mdpopups-font-mono: "your desired font face";
}
```

to `Packages/User/mdpopups.css`.
See the [mdpopups documentation](http://facelessuser.github.io/sublime-markdown-popups/) for more details.

## Keyboard shortcuts (key bindings)

LSP's key bindings can be edited from the `Preferences: LSP Key Bindings` command in the Command Palette. Many of the default key bindings (visible in the left view) are disabled to avoid conflicts with default or user key bindings. To enable those, copy them to your user key bindings on the right, un-comment, and pick the key shortcut of your choice.

If you want to create a new key binding that is different from the ones that are already included, you might want to make it active only when there is a language server with a specific [LSP capability](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#initialize) (refer to the `ServerCapabilities` structure in that link) running. In that case, you can make use of the `lsp.session_with_capability` context. For example, the following key binding overrides `ctrl+r` to use LSP's symbol provider but only when the current view has a language server with the `documentSymbolProvider` capability and we're in a javascript or a typescript file:

```js
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

If you want to bind some action to a mouse, open `Preferences / Browser Packages` from the main menu and create a sublime-mousemap file in the following location within the Packages folder:

| Platform | Path |
| -------- | ---- |
| Windows  | `/User/Default (Windows).sublime-mousemap` |
| Linux    | `/User/Default (Linux).sublime-mousemap` |
| Mac      | `/User/Default (OSX).sublime-mousemap` |

Here is an example mouse binding that triggers LSP's "go to symbol definition" command on pressing the <kbd>ctrl</kbd>+<kbd>left click</kbd>:

```js
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

## Color scheme customizations

Some features use TextMate scopes to control the colors (underline, background or text color) of styled regions in a document or popup.
Colors can be customized by adding a rule for these scopes into your color scheme.
There is an example in the [official ST documentation](https://www.sublimetext.com/docs/color_schemes.html#customization) which explains how to do that.

The following tables give an overview about the scope names used by LSP.

### Semantic Highlighting

!!! info "This feature is only available if the server has the *semanticTokensProvider* capability."
    Language servers which support semantic highlighting are for example *clangd*, *rust-analyzer* and *lua-language-server*.

In order to support semantic highlighting, the color scheme requires a special rule with a background color set for semantic tokens, which is (marginally) different from the original background.
To add such a rule to your color scheme, select `UI: Customize Color Scheme` from the Command Palette and add for example the following code:

```json
{
    "rules": [
        {
            "scope": "meta.semantic-token",
            "background": "#00000101"
        },
    ]
}
```

Furthermore it is possible to adjust the colors for semantic tokens by applying a foreground color to the individual token types:

| scope | [SemanticTokenTypes](https://microsoft.github.io/language-server-protocol/specifications/specification-3-17/#semanticTokenTypes) |
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

By default, LSP will assign scopes based on the [scope naming guideline](https://www.sublimetext.com/docs/scope_naming.html) to each of these token types, but if you define rules for the scopes specified above, the latter will take precedence.

Language servers can also add their own custom token types, which are not defined in the protocol.
A "LSP-*" helper package (or user) can provide a "semantic_tokens" mapping in the server configuration for such additional token types.
Keys of this mapping should be the token types and values should be the corresponding scopes, for example:

```json
{
    "semantic_tokens": {
        "magicFunction": "support.function.builtin",
        "selfParameter": "variable.language.self"
    }
}
```

If no scope for a custom token type is defined, it will only be highlighted via the regular syntax highlighting.

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
