# Commands

## Commands and shortcuts

Apart from the commands listed in the [Keyboard Shortcuts](keyboard_shortcuts.md) section, LSP also provides more generic commands in the Command Palette:

* `LSP: Restart Server`: restarts running language server belonging to the active window
    * This command only works when in a document with a running server.
* `Preferences: LSP Settings`: opens LSP settings
* `Preferences: LSP Key Bindings`: opens LSP key bindings configuration - see [Keyboard Shortcuts](keyboard_shortcuts.md)
* `LSP: Enable / Disable Language Server Globally`: enables or disables chosen server globally (you can disable a server globally and enable it only per project, for example)
* `LSP: Enable / Disable Language Server in Project`: enables or disables chosen server for the current project (the project must be saved on disk first using `Project -> Save Project As...`)
* `LSP: Troubleshoot Server`: allows to troubleshoot chosen server to help diagnose issues
* `Preferences: LSP Language ID Mapping Overrides`: opens settings that define how to map the file's syntax scope to language server `languageId` identifier (advanced)

## Execute server commands

For LSP servers that can handle [workspace/executeCommand](https://microsoft.github.io/language-server-protocol/specification#workspace_executeCommand), you can make these commands available in Sublime's Command Palette by adding an entry to your existing `*.sublime-commands` file or by creating a new one.

Example:

```jsonc title="Packages/User/Default.sublime-commands"
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
| `"$document_id"` | object | JSON object `{ "uri": string }` containing the URI of the active view, see [TextDocumentIdentifier](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#textDocumentIdentifier) |
| `"$versioned_document_id"` | object | JSON object `{ "uri": string, "version": int }` containing the URI and version of the active view, see [VersionedTextDocumentIdentifier](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#versionedTextDocumentIdentifier) |
| `"$file_uri"` | string | File URI of the active view |
| `"$selection"` | string | Content of the (topmost) selection |
| `"$offset"` | int | Character offset of the (topmost) cursor position |
| `"$selection_begin"` | int | Character offset of the begin of the (topmost) selection |
| `"$selection_end"` | int | Character offset of the end of the (topmost) selection |
| `"$position"` | object | JSON object `{ "line": int, "character": int }` of the (topmost) cursor position, see [Position](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#position) |
| `"$line"` | int | Zero-based line number of the (topmost) cursor position, see [Position](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#position) |
| `"$character"` | int | Zero-based character offset relative to the current line of the (topmost) cursor position, see [Position](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#position) |
| `"$range"` | object | JSON object with `"start"` and `"end"` positions of the (topmost) selection, see [Range](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#range) |
| `"$text_document_position"` | object | JSON object with `"textDocument"` and `"position"` of the (topmost) selection, see [TextDocumentPositionParams](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#textDocumentPositionParams) |
