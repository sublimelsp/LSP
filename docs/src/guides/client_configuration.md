# Client Configuration

After you have installed a language server, the LSP settings need to be configured to enable communication between LSP and that server for suitable filetypes.
LSP ships with default configurations for a few language servers, but these need to be enabled before they will start.
To globally enable a server, open the Command Palette and choose "LSP: Enable Language Server Globally".
This will add `"enabled": true` to the corresponding language server setting under the `"clients"` key in your user-settings file for LSP.
Your user-settings file is stored at `Packages/User/LSP.sublime-settings` and can be opened via "Preferences > Package Settings > LSP > Settings" from the menu.
If your language server is missing or not configured correctly, you need to add/override further settings which are explained below.

Here is an example of the `LSP.sublime-settings` file with configurations for the JavaScript/TypeScript server:

```js
{
  // General settings
  "show_diagnostics_panel_on_save": 0,

  // Language server configurations
  "clients": {
    "lsp-tsserver": {
      "command": ["lsp-tsserver"],
      "enabled": true,
      "languageId": "typescript",
      "document_selector": "source.ts | source.tsx"
    }
  }
}
```

Some language servers support multiple languages, which can be specified in the following way:

```js
{
  // General settings
  "show_diagnostics_panel_on_save": 0,

  // Language server configurations
  "clients": {
    "lsp-tsserver": {
      "command": ["lsp-tsserver"],
      "enabled": true,
      "languages": [{
        "languageId": "javascript",
        "document_selector": "source.js | source.jsx"
      }, {
        "languageId": "typescript",
        "document_selector": "source.ts | source.tsx"
      }]
    }
  }
}
```

| Setting | Description |
| ------- | ----------- |
| enabled | enables a language server (default is disabled) |
| command | must be on PATH or specify a full path, add arguments (can be empty if starting manually, then TCP transport must be configured) |
| env | dict of environment variables to be injected into the language server's process (eg. PYTHONPATH) |
| settings | per-project settings (equivalent to VS Code's Workspace Settings) |
| initializationOptions | options to send to the server at startup (rarely used) |
| document_selector | This is _the_ connection between your files and language servers. It's a selector that is matched against the current view's base scope. If the selector matches with the base scope of the the file, the associated language server is started. If the selector happens to be of the form "source.{languageId}" (which it is in many cases), then you can omit this "document_selector" key altogether, and LSP will assume the selector is "source.{languageId}". For more information, see https://www.sublimetext.com/docs/3/selectors.html |
| feature_selector | Used to prioritize a certain language server when choosing which one to query on views with multiple servers active. Certain LSP actions have to pick which server to query and this setting can be used to decide which one to pick based on the current scopes at the cursor location. For example when having both HTML and PHP servers running on a PHP file, this can be used to give priority to the HTML one in HTML blocks and to PHP one otherwise. That would be done by setting "feature_selector" to `text.html` for HTML server and `source.php` to PHP server. Note: when the "feature_selector" is missing, it will be the same as the "document_selector".
| languageId | identifies the language for a document - see [LSP specifications](https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#textDocumentItem) |
| languages | group `document_selector` and `languageId` together for servers that support more than one language |
| tcp_port | see instructions below |
| tcp_host | see instructions below |
| tcp_mode | see instructions below |
| experimental_capabilities | Turn on experimental capabilities of a language server. This is a dictionary and differs per language server |

You can figure out the scope with Tools > Developer > Show Scope Name.
You can figure out the syntax by opening the ST console and running `view.settings().get("syntax")`.

The default transport is stdio, but TCP is also supported.
The port number can be inserted into the server's arguments by adding a `{port}` placeholder in `command`.

**Server-owned port**

Set `tcp_port` and optionally `tcp_host` if server running on another host.

**Editor-owned port** (servers based on vscode-languageserver-node):

Set `tcp_mode` to "host", leave `tcp_port` unset for automatic port selection.
`tcp_port` can be set if eg. debugging a server. You may want to check out the LSP source and extend the `TCP_CONNECT_TIMEOUT`.

### Per-project overrides

Global LSP settings (which currently are `lsp_format_on_save` and `lsp_code_actions_on_save`) can be overridden per-project in `.sublime-project` file:

```json
{
  "folders":
  [
    {
      "path": "."
    }
  ],
  "settings": {
    "lsp_format_on_save": true,
  }
}
```

Also global language server settings can be added or overridden per-project by adding an `LSP` object within the `settings` object. A new server configurations can be added there or existing global configurations can be overridden (either fully or partially). Those can override server configurations defined within the `clients` key in `LSP.sublime-settings` or those provided by external packages.

> **Note**: The `settings` and `initializationOptions` objects for server configurations will be merged with globally defined server configurations so it's possible to override only certain properties from those objects.

```json
{
  "folders":
  [
    {
      "path": "."
    }
  ],
  "settings": {
    "LSP": {
      "jsts": {
        "enabled": false,
      },
      "eslint": {
        "settings": {
          "eslint.autoFixOnSave": true  // This property will be merged with original settings for
                                        // this client (potentially overriding original value).
        }
      }
    }
  }
}
```
