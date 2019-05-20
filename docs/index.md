### Sublime LSP Plugin Documentation

# Configuration

## LSP Settings

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

## Language Specific Setup

Install and verify Sublime Text can find the language server executable through the PATH, especially when using virtual environments with your interpreter.

Run "LSP: Enable Language Server" from Sublime's Command Palette to allow LSP to start a server when a document with a certain syntax is opened/activated.

LSP registers a server's supported trigger characters with Sublime Text.
If completion on `.` or `->`, is not working, you may need to add the listed `auto_complete_triggers` to your User or Syntax-specific settings.

The default LSP.sublime-settings contains some default LSP client configuration that may not work for you. See [Client Config](#client-config) for explanations for the available settings.

### Javascript/Typescript<a name="jsts"></a>

Different servers wrapping microsoft's typescript services, most support plain javascript:

Theia's [typescript-language-server](https://github.com/theia-ide/typescript-language-server)

`npm install -g typescript-language-server`

My own [tomv564/lsp-tsserver](https://github.com/tomv564/lsp-tsserver)

`npm install -g lsp-tsserver`

Sourcegraph's [javascript-typescript-langserver](https://github.com/sourcegraph/javascript-typescript-langserver)

`npm install -g javascript-typescript-langserver`


### Flow (Javascript)<a name="flow"></a>

See: [github](https://github.com/flowtype/flow-language-server)


### Vue (Javascript)<a name="vue"></a>

See: [npm package](https://www.npmjs.com/package/vue-language-server)

Client configuration:
```
"vue-ls":{
  "command": [
    "node",
    "/ABSOLUTE/PATH/TO/SERVER/.npm-global/bin/vls"
  ],
  "enabled": true,
  "languageId": "vue",
  "scopes": [
    "text.html.vue"
  ],
  "syntaxes": [
    // For ST3 builds < 3153
    "Packages/Vue Syntax Highlight/vue.tmLanguage"
    // For ST3 builds >= 3153
    // "Packages/Vue Syntax Highlight/Vue Component.sublime-syntax"
  ]
}
```

Be sure to install "Vue Syntax Highlight" from Package Control.

### Python<a name="python"></a>

`pip install python-language-server`

See: [github:palantir/python-language-server](https://github.com/palantir/python-language-server)

Alternatively, Microsoft's python language server (using .NET Core runtime)

[Instructions here](https://github.com/Microsoft/python-language-server/blob/master/Using_in_sublime_text.md)

### PHP<a name="php"></a>

#### Intelephense

`npm i intelephense -g`

See [bmewburn/intelephense-docs](https://github.com/bmewburn/intelephense-docs)


#### PHP Language server

See: [github:felixfbecker/php-language-server](https://github.com/felixfbecker/php-language-server)

1. modify `~/.composer/composer.json` to set
```
"minimum-stability": "dev",
"prefer-stable": true,
```
2. run `composer global require felixfbecker/language-server`
3. run `composer run-script --working-dir=~/.composer/vendor/felixfbecker/language-server parse-stubs`
4. modify `LSP.sublime-settings - User`
```
{
  "clients": {
    "phpls": {
      "command": ["php", "/PATH-TO-HOME-DIR/.composer/vendor/felixfbecker/language-server/bin/php-language-server.php"],
      "scopes": ["source.php"],
      "syntaxes": ["Packages/PHP/PHP.sublime-syntax"],
      "languageId": "php"
    }
  }
}
```

### Ruby / Ruby on Rails<a name="ruby"></a>

Requires the solargraph gem:

    gem install solargraph

See [github.com:castwide/solargraph](https://github.com/castwide/solargraph) for up-to-date installation instructions.


### Rust<a name="rust"></a>

Goes well with the [Rust Enhanced package](https://github.com/rust-lang/rust-enhanced) which uses the RLS server: [github:rust-lang-nursery/rls](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.

Alternatively, a newer [rust-analyzer](https://github.com/rust-analyzer/rust-analyzer) server is under development, also supported by LSP.


### Scala<a name="scala"></a>

*  **[Metals](https://scalameta.org/metals/)**: Most complete LSP server for Scala, see instructions [here](https://scalameta.org/metals/docs/editors/sublime.html) for installation.
* **[SBT](https://www.scala-sbt.org/)**: Version 1.x supports limited and *unmaintained* language server functionalities, setup is described [here](http://eed3si9n.com/sbt-server-with-sublime-text3).
* **[Dotty](http://dotty.epfl.ch/)**: The future Scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html).
It is developed against VS Code, so ignore instructions related to VS Code.
Get the project compiling with dotty first (see [instructions](https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)).
At this point LSP should complain in the logs
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`
Then run `sbt configureIDE` to create the `.dotty-ide.json` file
Then the LSP plugin should launch as configured in `LSP.sublime-settings` using coursier.


### C/C++

See the dedicated <a href="cplusplus"/>C/C++</a> guide for using ccls, cquery or clangd.

### Ocaml/Reason<a name="reason"></a>

You will need to install [sublime-reason](https://github.com/reasonml-editor/sublime-reason) and the dependencies listed in the repo, such as [ocaml-language-server](https://github.com/freebroccolo/ocaml-language-server). If you only use OCaml, you still need those listed dependencies, but not the sublime-reason plugin itself.

### Go<a name="go"></a>

Gopls

`go get -u golang.org/x/tools/cmd/gopls`

[Official go language server](https://github.com/golang/go/wiki/gopls), under development.

Sourcegraph's go-langserver

`go get github.com/sourcegraph/go-langserver`

See: [github:palantir/sourcegraphgo-langserver](https://github.com/sourcegraph/go-langserver)


### CSS<a name="css"></a>

Using the CSS language server from VS Code

`npm install -g vscode-css-languageserver-bin`


### Polymer<a name="polymer"></a>

    npm install -g polymer-editor-service

> Note: requires an up to date version of NodeJS. v6 is the minimum supported
  version as of 2017.

Features:

 * typeahead completions for elements, attributes, and css custom properties
 * typeahead completions for elements, attributes, and css custom properties
 * documentation on hover for elements and attributes
 * jump to definition for elements, attributes, and css custom properties
 * linting, configured through `polymer.json` at your workspace root.

More info: https://github.com/Polymer/polymer-editor-service


### Dart<a name="dart"></a>

`pub global activate dart_language_server`

Make sure the pub bin directory is part of your path.

See: [natebosch/dart_language_server](https://github.com/natebosch/dart_language_server)

### Kotlin


Install from [kotlin language server](https://github.com/fwcd/KotlinLanguageServer)
Requires [building](https://github.com/fwcd/KotlinLanguageServer/blob/master/BUILDING.md) first.

```json
"kotlinls":
{
    "command":
    [
        "PATH_TO_KotlinLanguageServer/build/install/kotlin-language-server/bin/kotlin-language-server.bat" // adjust this path!
    ],
    "enabled": true,
    "languageId": "kotlin",
    "scopes":
    [
        "source.Kotlin"
    ],
    "syntaxes":
    [
        "Packages/kotlin/Kotlin.tmLanguage"
    ]
}
```

Additionally, install the [Kotlin sublime package](https://github.com/vkostyukov/kotlin-sublime-package) for syntax highlighting.

### Bash

Install the [bash language server](https://github.com/mads-hartmann/bash-language-server)

```npm i -g bash-language-server```

### IntelliJ

Requires IntelliJ to be running.

```
"intellij":{
  "tcp_port": 8080 // default port
  "command": [],
  "languageId": "java",
  "scopes": [
    "source.java"
  ],
  "syntaxes": [
    "Packages/Java/Java.sublime-syntax"
  ]
}
```

### Other<a name="other"></a>

Please create issues / pull requests so we can get support for more languages.

### Client Configuration<a name="client-config"></a>

LSP ships with default client configuration for a few language servers.
These configurations need to be enabled before they will start.

Here is an example for the Javascript/Typescript server:

```json
"jsts": {
    "command": ["lsp-tsserver"],
    "scopes": ["source.ts", "source.tsx"],
    "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"],
    "languageId": "typescript"
}
```

Client configurations can be customized as follows by adding an override in the User LSP.sublime-settings

* `command` - specify a full paths, add arguments (if not specified then tcp_port must be specified)
* `tcp_port` - if not specified then stdin/out are used else sets the tcpport to connect to (if no command is specified then it is assumed that some process is listing on this port)
* `scopes` - add language flavours, eg. `source.js`, `source.jsx`.
* `syntaxes` - syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage`
* `languageId` - used both by the language servers and to select a syntax highlighter for sublime popups.
* `enabled` - enable a language server globally, or per-project
* `settings` - per-project settings (equivalent to VS Code's Workspace Settings)
* `env` - dict of environment variables to be injected into the language server's process (eg. PYTHONPATH)
* `initializationOptions` - options to send to the server at startup (rarely used)

## Per-project overrides

Any fields in a client configuration can be overridden by adding an LSP settings block to your `.sublime-project` file:

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
      "eslintls": {
        "settings": {
          "eslint": {
            "autoFixOnSave": true
          }
        }
      }
    }
  }
}
```


# Features

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

# Troubleshooting

First step should be to set the `log_debug` setting to `true`, restart sublime and examine the output in the Sublime console.
`log_stderr` can also be set to `true` to see the language server's own logging.

**LSP doesn't try to start my language server**

* Make sure you have a folder added in your Sublime workspace.
* Make sure the document you are opening lives under that folder.

Your client configuration requires two settings to match the document your are editing:

* Scope (eg. `source.php`): Verify this is correct by running "Show Scope Name" from the developer menu.
* Syntax (eg. `Packages\PHP\PHP.sublime-syntax`): Verify by running `sublime.active_window().active_view().settings().get("syntax")` in the console.

**LSP cannot find my language server through PATH on OS-X**

This issue can be solved in a few ways:

* Install the [SublimeFixMacPath](https://github.com/int3h/SublimeFixMacPath) package
* Or always launch sublime from the command line (so it inherits your shell's environment)
* Use `launchctl setenv` to set PATH for OS-X UI applications.
