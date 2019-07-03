
## Commands and shortcuts

### Plugin commands

|Command|Description|
|:------|:----------|
|Restart Servers|kills all language servers belonging to the active window, this command only works when in a supported document, It may change in the future to be always available, or only kill the relevant language server.|
|LSP Settings|Opens package settings.|

### Document actions
|Command|Trigger|
|:------|:--------:|
|Show Code Actions|<kbd>super</kbd>+<kbd>.</kbd>|
|Symbol References|<kbd>shift</kbd>+<kbd>f12</kbd>|
|Rename Symbol|`UNBOUND` Recommended: <kbd>F2</kbd> (next bookmark)|
|Go to definition|`UNBOUND` Recommended: <kbd>f12</kbd> (built-in goto definition) LSP falls back to ST3's built-in goto definition command in case LSP fails.|
|Format Document|`UNBOUND`|
|Format Selection|`UNBOUND`|
|Document Symbols|`UNBOUND`|

### Workspace actions

|Command|Trigger|
|:------|:------|
|Show Diagnostics Panel|<kbd>super</kbd>+<kbd>shift</kbd>+<kbd>M</kbd> / <kbd>ctrl</kbd>+<kbd>alt</kbd>+<kbd>M</kbd>|
|Workspace Symbol Search|via command Palette `LSP: workspace symbol`|

### Overriding keybindings

Sublime's keybindings can be edited from the `Preferences: Key Bindings` command.
The following example overrides <kbd>f12</kbd> to use LSP's go to definition when in javascript/typescript:

```json
{
    "keys": ["f12"],
    "command": "lsp_symbol_definition",
    "context": [
        {
            "key": "selector",
            "operator": "equal",
            "operand": "source.ts, source.js"
        }
    ]
}
```

More useful keybindings (OS-X), edit Package Settings -> LSP -> Key Bindings

```json
    { "keys": ["f2"], "command": "lsp_symbol_rename" },
    { "keys": ["f12"], "command": "lsp_symbol_definition" },
    { "keys": ["super+option+r"], "command": "lsp_document_symbols" },
    { "keys": ["super+option+h"], "command": "lsp_hover"}
```

### Mouse map configuration

Add this to your "Default.sublime-mousemap" to bind LSP's goto definition command to <kbd>alt</kbd> + click
```json
{
  "button": "button1",
  "count": 1,
  "modifiers": ["alt"],
  "command": "lsp_symbol_definition",
  "press_command": "drag_select",
}
```

## Configurations

Global plugin settings and settings defined at project level are merged together.

|Setting|Default|Options|Description|
|:------|:-----:|:-----:|:----------|
|complete\_all\_chars|`true`||Request completions for all characters, not just trigger characters.|
|only\_show\_lsp\_completions|`false`||Disable sublime word completion and snippets in autocomplete lists.|
|completion\_hint\_type|`"auto"`|`"auto"`, `"detail"`, `"kind"` or `"none"`|Override automatic completion hints.|
|prefer\_label\_over\_filter\_text|`false`||Always use the `"label"` key instead of the `"filterText"` key in CompletionItems.|
|show\_references\_in\_quick\_panel|`false`||Show symbol references in Sublime's quick panel instead of the bottom panel.|
|quick\_panel\_monospace\_font|`false`||Use monospace font for the quick panel.|
|show\_status\_messages|`true`||Show messages in the status bar for a few seconds.|
|show\_view\_status|`true`||Show permanent language server status in the status bar.|
|auto\_show\_diagnostics\_panel|`true`||Open the diagnostics panel automatically if there are diagnostics.|
|show\_diagnostics\_phantoms|`false`||Show diagnostics as phantoms while the file has no changes.|
|show\_diagnostics\_count\_in\_view\_status|`false`||Show errors and warnings count in the status bar.|
|show\_diagnostics\_in\_view\_status|`true`||When the cursor is on a diagnostic, show the text in the status bar.|
|diagnostics\_highlight\_style|`"underline"`|`"underline"` or `"box"`|highlight style of code diagnostics.|
|document\_highlight\_style|`"underline"`|`"fill"`, `"box"`, `"underline"`, `"stippled"`, `"squiggly"` or `""`|Highlight style of "highlights": accentuating nearby text entities that are related to the one under your cursor.|
|document\_highlight\_scopes|`{"unknown": "text", "text": "text", "read": "markup.inserted", "write": "markup.changed"}`||Customize your sublime text scopes for document highlighting.|
|diagnostics\_gutter\_marker|`"dot"`|`"dot"`, `"circle"`, `"bookmark"`, `"cross"` or `""`|Gutter marker for code diagnostics.|
|show\_code\_actions\_bulb|`false`||Show a bulb in the gutter when code actions are available.|
|log\_debug|`false`||Show debug logging in the sublime console.|
|log\_server|`true`||Show `server/logMessage` notifications from language servers in the console.|
|log\_stderr|`false`||Show language server stderr output in the console.|
|log\_payloads|`false`||Show full JSON-RPC responses in the console.|

