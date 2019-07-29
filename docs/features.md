
## Commands and shortcuts

**Plugin commands**

* Restart Servers: kills all language servers belonging to the active window
    * This command only works when in a supported document.
    * It may change in the future to be always available, or only kill the relevant language server.
* LSP Settings: Opens package settings.

**Document actions**

* Show Code Actions: `super+.`
* Symbol References: `shift+f12`
* Rename Symbol: UNBOUND
    * Recommendation: Override `F2` (next bookmark)
* Go to definition: UNBOUND
    * Recommendation: Override `f12` (built-in goto definition),
    * LSP falls back to ST3's built-in goto definition command in case LSP fails.
* Format Document: UNBOUND
* Format Selection: UNBOUND
* Document Symbols: UNBOUND

**Workspace actions**

* Show Diagnostics Panel: `super+shift+M` / `ctr+alt+M`
* Workspace Symbol Search: via command Palette `LSP: workspace symbol`

**Overriding keybindings**

Sublime's keybindings can be edited from the `Preferences: Key Bindings` command.
The following example overrides `f12` to use LSP's go to definition when in javascript/typescript:

```
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
```
  { "keys": ["f2"], "command": "lsp_symbol_rename" },
  { "keys": ["f12"], "command": "lsp_symbol_definition" },
  { "keys": ["super+option+r"], "command": "lsp_document_symbols" },
  { "keys": ["super+option+h"], "command": "lsp_hover"}
```

**Mouse map configuration**

See below link, but bind to `lsp_symbol_definition` command
https://stackoverflow.com/questions/16235706/sublime-3-set-key-map-for-function-goto-definition


## Configuring

Global plugin settings and settings defined at project level are merged together.

* `complete_all_chars` `true` *request completions for all characters, not just trigger characters*
* `only_show_lsp_completions` `false` *disable sublime word completion and snippets from autocomplete lists*
* `completion_hint_type` `"auto"` *override automatic completion hints with "detail", "kind" or "none"*
* `prefer_label_over_filter_text` `false` *always use the "label" key instead of the "filterText" key in CompletionItems*
* `show_references_in_quick_panel` `false` *show symbol references in Sublime's quick panel instead of the bottom panel*
* `quick_panel_monospace_font` `false` *use monospace font for the quick panel*
* `show_status_messages` `true` *show messages in the status bar for a few seconds*
* `show_view_status` `true` *show permanent language server status in the status bar*
* `auto_show_diagnostics_panel` `true` *open the diagnostics panel automatically if there are diagnostics*
* `show_diagnostics_phantoms` `false` *show diagnostics as phantoms while the file has no changes*
* `show_diagnostics_count_in_view_status` `false` *show errors and warnings count in the status bar*
* `show_diagnostics_in_view_status` `true` *when on a diagnostic with the cursor, show the text in the status bar*
* `diagnostics_highlight_style` `"underline"` *highlight style of code diagnostics, `"underline"` or `"box"`*
* `highlight_active_signature_parameter`: *highlight the active parameter of the currently active signature*
* `document_highlight_style`: *document highlight style: "underline", "stippled", "squiggly" or ""*
* `document_highlight_scopes`: *customize your sublime text scopes for document highlighting*
* `diagnostics_gutter_marker` `"dot"` *gutter marker for code diagnostics: "dot", "circle", "bookmark", "cross" or ""*
* `show_code_actions_bulb` `false` *show a bulb in the gutter when code actions are available*
* `log_debug` `false` *show debug logging in the sublime console*
* `log_server` `true` *show server/logMessage notifications from language servers in the console*
* `log_stderr` `false` *show language server stderr output in the console*
* `log_payloads` `false` *show full JSON-RPC responses in the console*


