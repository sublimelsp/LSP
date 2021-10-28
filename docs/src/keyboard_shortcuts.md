Below is a list of supported commands and the corresponding keyboard shortcut (if assigned). Most of those are also available from the Command Palette, the main menu and the mouse context menu.

Refer to the [Customization section](customization.md#keyboard-shortcuts-key-bindings) on how to modify or assign shortcuts to them.

!!! Mac
    If you using macOS, replace <kbd>ctrl</kbd> with <kbd>command</kbd>.

!!! Note
    If <kbd>F4</kbd> / <kbd>shift</kbd> <kbd>F4</kbd> stop working, double-click a diagnostic in the Diagnostics Panel. It should work again afterwards.

| Feature | Shortcut | Command |
| ------- | -------- | ------- |
| Auto Complete | <kbd>ctrl</kbd> <kbd>space</kbd> (also on macOS) | `auto_complete`
| Expand Selection | unbound | `lsp_expand_selection`
| Find References | <kbd>shift</kbd> <kbd>f12</kbd> | `lsp_symbol_references`
| Format File | unbound | `lsp_format_document`
| Format Selection | unbound | `lsp_format_document_range`
| Goto Declaration | unbound | `lsp_symbol_declaration`
| Goto Definition | unbound<br>suggested: <kbd>f12</kbd> | `lsp_symbol_definition`
| Goto Implementation | unbound | `lsp_symbol_implementation`
| Goto Symbol | unbound<br>suggested: <kbd>ctrl</kbd> <kbd>r</kbd> | `lsp_document_symbols`
| Goto Symbol in Project | unbound<br>suggested: <kbd>ctrl</kbd> <kbd>shift</kbd> <kbd>r</kbd> | `lsp_workspace_symbols`
| Goto Type Definition | unbound | `lsp_symbol_type_definition`
| Next Diagnostic | <kbd>F4</kbd> | -
| Previous Diagnostic | <kbd>shift</kbd> <kbd>F4</kbd> | -
| Rename | unbound | `lsp_symbol_rename`
| Restart Server | unbound | `lsp_restart_server`
| Run Code Action | unbound | `lsp_code_actions`
| Run Source Action | unbound | `lsp_code_actions` (with args: `{"only_kinds": ["source"]}`)
| Run Code Lens | unbound | `lsp_code_lens`
| Signature Help | <kbd>ctrl</kbd> <kbd>alt</kbd> <kbd>space</kbd> | -
| Hover Popup | unbound | `lsp_hover`
| Toggle Diagnostics Panel | <kbd>ctrl</kbd> <kbd>alt</kbd> <kbd>m</kbd> | `lsp_show_diagnostics_panel`
| Toggle Log Panel | unbound | `lsp_toggle_server_panel`
