
## Commands and shortcuts

### Plugin commands

* Restart Servers: kills all language servers belonging to the active window
    * This command only works when in a supported document.
    * It may change in the future to be always available, or only kill the relevant language server.
* LSP Settings: Opens package settings.

### Document actions

* Show Code Actions: UNBOUND
* Symbol References: `shift+f12`
* Rename Symbol: UNBOUND
    * Recommendation: Override `F2` (next bookmark)
* Go to definition / type definition / declaration / implementation: UNBOUND
    * Recommendation: Override `f12` (built-in goto definition),
    * LSP falls back to ST3's built-in goto definition command in case LSP fails.
* Format Document: UNBOUND
* Format Selection: UNBOUND
* Document Symbols: UNBOUND

### Workspace actions

* Show Diagnostics Panel: `super+shift+M` / `ctr+alt+M`
* Next/Previous Diagnostic From panel: `F4` / `shift+F4`
* Workspace Symbol Search: via command Palette `LSP: workspace symbol`

### Execute server commands

For LSP servers that can handle [workspace/executeCommand](https://microsoft.github.io/language-server-protocol/specification#workspace_executeCommand), you can make these commands available in Sublime's Command Palette by adding an entry to your existing `*.sublime-commands` file or by creating a new one.

Example:

```js
[
  // ...
  {
    "caption": "Thread First",
    "command": "lsp_execute",
    "args": {
      "session_name": "LSP-pyright",
      "command_name": "thread-first",
      "command_args": ["${file_uri}", 0, 0]
    }
  }
]
```

Notes:

 - the `session_name` is required and needs to match the server's key within the `clients` configuration object.
 - the `command_args` is optional depending on the `workspace/executeCommand` that are supported by the LSP server.

You can include special variables in the `command_args` array that will be automatically expanded. Supported variables include Sublime's built-in ones (see the full list in the [Build Systems](http://www.sublimetext.com/docs/build_systems.html#variables) documentation) as well as additional variables listed below. Note that the built-in variables will be expanded regardless of where they are in the array and also within nested arrays or objects while the variables listed below will only be expanded in the top-level array values and only if those values match exactly (will not match if they are sub-strings of values):

| Variable | Type | Description |
| -------- | ---- | ----------- |
| `"$document_id"` or `"${document_id}"` | object | JSON object `{ 'uri': string }` containing the file URI of the active view, see [Document Identifier](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#textDocumentIdentifier) |
| `"$file_uri"` or `"${file_uri}"` | string | File URI of the active view |
| `"$selection"` or `"${selection}"` | string | Content of the (topmost) selection |
| `"$offset"` or `"${offset}"` | int | Character offset of the (topmost) cursor position |
| `"$selection_begin"` or `"${selection_begin}"` | int | Character offset of the begin of the (topmost) selection |
| `"$selection_end"` or `"${selection_end}"` | int | Character offset of the end of the (topmost) selection |
| `"$position"` or `"${position}"` | object | JSON object `{ 'line': int, 'character': int }` of the (topmost) cursor position, see [Position](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#position) |
| `"$range"` or `"${range}"` | object | JSON object with `'start'` and `'end'` positions of the (topmost) selection, see [Range](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#range) |

### Show autocomplete documentation

Some completion items can have documentation associated with them.

![documentation popup](images/show-docs-popup.png)

To show the documentation popup you can click the **More** link in the bottom of the autocomplete,
or you can use the default sublime keybinding <kbd>F12</kbd> to trigger it.
