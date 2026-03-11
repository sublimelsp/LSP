## Keyboard shortcuts (key bindings)

LSP's key bindings can be edited from the `Preferences: LSP Key Bindings` command in the Command Palette. Many of the default key bindings (visible in the left view) are disabled to avoid conflicts with default or user key bindings. To enable those, copy them to your user key bindings on the right, un-comment, and pick the key shortcut of your choice.

If you want to create a new key binding that is different from the ones that are already included, you might want to make it active only when there is a language server with a specific [LSP capability](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#initialize) (refer to the `ServerCapabilities` structure in that link) running. In that case, you can make use of the `lsp.session_with_capability` context. For example, the following key binding overrides <kbd>Ctrl</kbd>+<kbd>R</kbd> to use LSP's symbol provider but only when the current view has a language server with the `documentSymbolProvider` capability and we're in a javascript or a typescript file:

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

Here is an example of a mouse binding that triggers LSP's "Goto Definition" command on pressing <kbd>Ctrl</kbd>+<kbd>left click</kbd>:

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


## Commands

Below is a list of supported commands and the corresponding keyboard shortcut (if assigned). Most of those are also available from the Command Palette, the main menu and the mouse context menu.

!!! Mac
    If you using macOS, replace <kbd>Ctrl</kbd> with <kbd>Command</kbd>.

| Feature | Shortcut | Command |
| ------- | -------- | ------- |
| Auto Complete | <kbd>Ctrl</kbd> <kbd>Space</kbd> (also on macOS) | `auto_complete`
| Expand Selection | unbound | `lsp_expand_selection`
| Find References | <kbd>Shift</kbd> <kbd>F12</kbd> | `lsp_symbol_references`<br>Supports optional args: `{"include_declaration": true | false, "output_mode": "output_panel" | "quick_panel"}`.<br>Triggering from context menus while holding <kbd>Ctrl</kbd> opens in "side by side" mode. Holding <kbd>Shift</kbd> triggers opposite behavior relative to what `show_references_in_quick_panel` is set to.
| Fold | unbound | `lsp_fold`<br>Supports optional args: `{"strict": true/false}` - to configure whether to fold only when the caret is contained within the folded region (`true`), or even when it is anywhere on the starting line (`false`).
| Fold All | unbound | `lsp_fold_all`<br>Supports optional args: `{"kind": "comment" | "imports" | "region"}`.
| Follow Link | unbound | `lsp_open_link`
| Format File | unbound | `lsp_format_document`
| Format Selection | unbound | `lsp_format_document_range`
| Goto Declaration | unbound | `lsp_symbol_declaration`
| Goto Definition | unbound<br>suggested: <kbd>F12</kbd> | `lsp_symbol_definition`
| Goto Diagnostic | unbound<br>suggested: <kbd>F8</kbd> | `lsp_goto_diagnostic`.
| Goto Implementation | unbound | `lsp_symbol_implementation`
| Goto Symbol in Project | unbound<br>suggested: <kbd>Ctrl</kbd> <kbd>Shift</kbd> <kbd>R</kbd> | `lsp_workspace_symbols`
| Goto Symbol | unbound<br>suggested: <kbd>Ctrl</kbd> <kbd>R</kbd> | `lsp_document_symbols`
| Goto Type Definition | unbound | `lsp_symbol_type_definition`
| Hover Popup | unbound | `lsp_hover`
| Insert/Replace Completions | <kbd>Alt</kbd> <kbd>Enter</kbd> | `lsp_commit_completion_with_opposite_insert_mode`
| Next Diagnostic | unbound | `lsp_next_diagnostic`
| Previous Diagnostic | unbound | `lsp_prev_diagnostic`
| Rename | unbound | `lsp_symbol_rename`
| Restart Server | unbound | `lsp_restart_server`
| Run Code Action | unbound | `lsp_code_actions`
| Run Code Lens | unbound | `lsp_code_lens`
| Run Refactor Action | unbound | `lsp_code_actions`<br>With args: `{"only_kinds": ["refactor"]}`.
| Run Source Action | unbound | `lsp_code_actions`<br>With args: `{"only_kinds": ["source"]}`.
| Save All | unbound | `lsp_save_all`<br>Supports optional args `{"only_files": true | false}` - whether to ignore buffers which have no associated file on disk.
| Show Call Hierarchy | unbound | `lsp_call_hierarchy`
| Show Type Hierarchy | unbound | `lsp_type_hierarchy`
| Signature Help | <kbd>Ctrl</kbd> <kbd>Alt</kbd> <kbd>Space</kbd> | `lsp_signature_help_show`
| Toggle Diagnostics Panel | <kbd>Ctrl</kbd> <kbd>Alt</kbd> <kbd>M</kbd> | `lsp_show_diagnostics_panel`
| Toggle Inlay Hints | unbound | `lsp_toggle_inlay_hints`<br>Supports optional args: `{"enable": true | false}`.
| Toggle Log Panel | unbound | `lsp_toggle_server_panel`
