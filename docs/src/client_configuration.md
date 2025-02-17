# Client Configuration

## Custom client configuration

!!! Note
    The external LSP-* helper packages already come with their setting file and a client configuration and you don't need to add anything to the global LSP settings. This section is only relevant if you want to add a new client configuration for a server that doesn't have a corresponding helper package.

After you have installed a language server, the LSP settings need to be configured to enable communication between LSP and that server for suitable filetypes.
LSP ships with configurations for a few language servers, but these need to be enabled before they will start.
To globally enable a server, open the Command Palette and choose "LSP: Enable Language Server Globally".
This will add `"enabled": true` to the corresponding language server setting under the `"clients"` key in your user-settings file for LSP.
Your user-settings file is stored at `Packages/User/LSP.sublime-settings` and can be opened via "Preferences > Package Settings > LSP > Settings" from the menu or with the `Preferences: LSP Settings` command from the Command Palette.
If your language server is missing or not configured correctly, you need to add/override further settings which are explained below.

Below is an example of the `LSP.sublime-settings` file with configurations for the [Phpactor](https://phpactor.readthedocs.io/en/master/usage/language-server.html#language-server) server.

```jsonc title="Packages/User/LSP.sublime-settings"
{
  // General settings
  "show_diagnostics_panel_on_save": 0,

  // Language server configurations
  "clients": {
    "phpactor": {
      // enable this configuration
      "enabled": true,
      // the startup command -- what you would type in a terminal
      "command": ["PATH/TO/phpactor", "language-server"],
      // the selector that selects which type of buffers this language server attaches to
      "selector": "source.php"
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
| selector | This is _the_ connection between your files and language servers. It's a selector that is matched against the current view's base scope. If the selector matches with the base scope of the the file, the associated language server is started. For more information, see https://www.sublimetext.com/docs/3/selectors.html |
| priority_selector | Used to prioritize a certain language server when choosing which one to query on views with multiple servers active. Certain LSP actions have to pick which server to query and this setting can be used to decide which one to pick based on the current scopes at the cursor location. For example when having both HTML and PHP servers running on a PHP file, this can be used to give priority to the HTML one in HTML blocks and to PHP one otherwise. That would be done by setting "priority_selector" to `text.html` for HTML server and `source.php` to PHP server. Note: when the "priority_selector" is missing, it will be the same as the "document_selector".
| diagnostics_mode | Set to `"workspace"` (default is `"open_files"`) to ignore diagnostics for files that are not within the project (window) folders. If project has no folders then this option has no effect and diagnostics are shown for all files. If the server supports _pull diagnostics_ (`diagnosticProvider`), this setting also controls whether diagnostics are requested only for open files (`"open_files"`), or for all files in the project folders (`"workspace"`). |
| tcp_port | see instructions below |
| experimental_capabilities | Turn on experimental capabilities of a language server. This is a dictionary and differs per language server |
| disabled_capabilities | Disables specific capabilities of a language server. This is a dictionary with key being a capability key and being `true`. Refer to the `ServerCapabilities` structure in [LSP capabilities](https://microsoft.github.io/language-server-protocol/specifications/specification-current/#initialize) to find capabilities that you might want to disable. Note that the value should be `true` rather than `false` for capabilites that you want to disable. For example: `"signatureHelpProvider": true` |

You can figure out the scope of the current view with `Tools > Developer > Show Scope`.

## Subprocesses

A subprocess is _always_ started. There is no support for connecting to a remote language server.

## Transports

Communication with a language server subprocess can be achieved in different ways. See the table below for what's possible.

### Standard input/output (STDIO)

The vast majority of language servers can communicate over stdio. To use stdio, leave out `tcp_port` and use only `command` in the client configuration.

### TCP - localhost - subprocess acts as a TCP server

Some language servers can also act as a TCP server accepting incoming TCP connections. So: the language server subprocess is started by this package, and the subprocess will then open a TCP listener port. The editor can then connect as a client and initiate the communication. To use this mode, set `tcp_port` to a positive number designating the port to connect to on `localhost`.

Optionally in this case, you can omit the `command` setting if you don't want Sublime LSP to manage the language server process and you'll take care of it yourself. 

### TCP - localhost - editor acts as a TCP server

Some _LSP servers_ instead expect the _LSP client_ to act as a _TCP server_. The _LSP server_ will then connect as a _TCP client_, after which the _LSP client_ is expected to initiate the communication. To use this mode, set `tcp_port` to a negative number designating the port to bind to for accepting new TCP connections.

To use a fixed port number, use `-X` as the value for `tcp_port`, where `X` is the desired (positive) port number.

To select a random free port, use `-1` as the value for `tcp_port`.

The port number can be inserted into the server's startup `command` in your client configuration by using the `${port}` template variable. It will expand to the absolute value of the bound port.

## Per-project overrides

Global LSP settings (which currently are `lsp_format_on_save`, `lsp_format_on_paste` and `lsp_code_actions_on_save`) can be overridden per-project in `.sublime-project` file:

```jsonc
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

Also global language server settings can be added or overridden per-project by adding an `LSP` object within the `settings` object. A new server configurations can be added there or existing global configurations can be overridden (either fully or partially). Those can override server configurations defined within the `clients` key in `LSP.sublime-settings` or those provided by external helper packages.

> **Note**: The `settings` and `initializationOptions` objects for server configurations will be merged with globally defined server configurations so it's possible to override only certain properties from those objects.

```jsonc
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
      "LSP-eslint": {
        "settings": {
          "eslint.autoFixOnSave": true  // This property will be merged with original settings for
                                        // this client (potentially overriding original value).
        }
      }
    }
  }
}
```
