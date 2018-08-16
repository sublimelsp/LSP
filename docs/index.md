### Sublime LSP Plugin Documentation

# Configuration


## Sublime Settings

*TODO: document any settings LSP depends on here*

## LSP Settings

* `complete_all_chars` `true` *request completions for all characters, not just trigger characters*
* `only_show_lsp_completions` `false` *disable sublime word completion and snippets from autocomplete lists*
* `completion_hint_type` `"auto"` *override automatic completion hints with "detail", "kind" or "none"*
* `resolve_completion_for_snippets` `false` *resolve completions and apply snippet if received*
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
* `log_debug` `false` *show debug logging in the sublime console*
* `log_server` `true` *show server/logMessage notifications from language servers in the console*
* `log_stderr` `false` *show language server stderr output in the console*
* `log_payloads` `false` *show full JSON-RPC responses in the console*
* `merge_client_env` `false` *merge project env with global env, override if false*
* `merge_client_settings` `false` *merge project settings with global settings, override if false*

## Language Specific Setup

For any of these components it is important that Sublime Text can find the language server executable through the path, especially when using virtual environments.

LSP registers a server's supported trigger characters with Sublime Text.
If completion on `.` or `->`, is not working, you may need to add the listed `auto_complete_triggers` to your User or Syntax-specific settings.

The default LSP.sublime-settings contains some default LSP client configuration that may not work for you. See [Client Config](#client-config) for explanations for the available settings.

### Javascript/Typescript<a name="jsts"></a>

You need to have [tomv564/lsp-tsserver](https://github.com/tomv564/lsp-tsserver) installed globally for the completions to work.

`npm install -g lsp-tsserver`

Client configuration:

```
{
    "js": {
        "command": ["lsp-tsserver"],
        "enabled": true,
        "languageId": "javascript",
        "scopes": ["source.js"],
        "syntaxes": ["Packages/JavaScript/JavaScript.sublime-syntax"]
    },
    "jsts": {
        "command": ["lsp-tsserver"],
        "enabled": true,
        "languageId": "typescript"
        "scopes": ["source.ts", "source.tsx"],
        "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"],
    }
}
```

### Flow (Javascript)<a name="flow"></a>

See: [github](https://github.com/flowtype/flow-language-server)

Client configuration:
```
      "flow":
      {
        "command": ["flow-language-server", "--stdio"],
        "scopes": ["source.js"],
        "syntaxes": ["Packages/Babel/JavaScript (Babel).sublime-syntax", "Packages/JavaScript/JavaScript.sublime-syntax"],
        "languageId": "javascript"
      }
```

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

### PHP<a name="php"></a>

UPDATE: Some new options for PHP language servers are discussed in [this issue](https://github.com/tomv564/LSP/issues/259)

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

5. (optional) add triggers to `Preferences.sublime-settings - User`
```
"auto_complete_triggers":
[
  {
    "characters": "$>:\\",
    "selector": "source.php"
  }
]
```


See: [github:felixfbecker/php-language-server](https://github.com/felixfbecker/php-language-server)


### Ruby / Ruby on Rails<a name="ruby"></a>

Requires the solargraph gem:

    gem install solargraph

See [github.com:castwide/solargraph](https://github.com/castwide/solargraph) for up-to-date installation instructions.

Client configuration:

```
"ruby": {
	"command":
	[
		"solargraph",
		"socket"
	],
	"enabled": true,
	"languageId": "ruby",
	"scopes":
	[
		"source.ruby",
		"source.ruby.rails"
	],
	"syntaxes":
	[
		"Packages/Ruby/Ruby.sublime-syntax",
		"Packages/Rails/Ruby on Rails.sublime-syntax",
		"Packages/Rails/HTML (Rails).sublime-syntax"
	],
	"tcp_port": 7658
},
```


### Rust<a name="rust"></a>

Requires Rust Nightly.

See [github:rust-lang-nursery/rls](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.


### Scala<a name="scala"></a>

SBT 1.x supports limited language server functionality, setup is described here: [sbt server with Sublime Text 3](http://eed3si9n.com/sbt-server-with-sublime-text3).

Dotty, the future scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html). It is developed against VS Code, so ignore instructions related to VS Code.

Get the project compiling with dotty first (see https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)

At this point LSP should complain in the logs
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`

Then run `sbt configureIDE` to create the .dotty-ide.json file
Then the LSP plugin should launch as configured in LSP.sublime-settings using coursier.


### C/C++ (Clangd)<a name="clang"></a>

You will need to build from source, see [instructions](https://clang.llvm.org/extra/clangd.html)

For any project of non-trivial size, you probably have a build system in place
to compile your source files. The compilation command passed to your compiler
might include things like:

* Include directories,
* Define directives,
* Compiler-specific flags.

Like any language server, clangd works on a per-file (or per-buffer) basis. But
unlike most other language servers, it must also be aware of the exact compile
flags that you pass to your compiler. For this reason, people have come up with
the idea of a [*compilation database*](https://clang.llvm.org/docs/JSONCompilationDatabase.html).
At this time, this is just a simple JSON file that describes for each
*translation unit* (i.e. a `.cpp`, `.c`, `.m` or `.mm` file) the exact
compilation flags that you pass to your compiler.

It's pretty much standardized that this file should be called
`compile_commands.json`. **clangd searches for this file up in parent
directories from the currently active document**. If you don't have such a file
present, most likely clangd will spit out nonsense errors and diagnostics about
your code.

As it turns out, CMake can generate this file *for you* if you pass it the
cache variable `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` when invoking CMake. It will
be present in your build directory, and you can copy that file to the root of
your project. Make sure to ignore this file in your version control system.

Since header files are (usually) not passed to a compiler, they don't have
compile commands. So even with a compilation database in place, clangd will
*still* spit out nonsense in header files. You can try to remedy this by
enhancing your compilation database with your header files using [this project called compdb](https://github.com/Sarcasm/compdb).

To generate headers with compdb, read [this closed issue](https://github.com/Sarcasm/compdb/issues/2).

You can also read about attempts to address this [on the CMake issue tracker](https://gitlab.kitware.com/cmake/cmake/issues/16285), along with the problem
of treating header files as translation units.

### Ocaml/Reason<a name="reason"></a>

You will need to install [sublime-reason](https://github.com/reasonml-editor/sublime-reason) and the dependencies listed in the repo, such as [ocaml-language-server](https://github.com/freebroccolo/ocaml-language-server). If you only use OCaml, you still need those listed dependencies, but not the sublime-reason plugin itself.

### Go<a name="go"></a>

NOTE: This language server is missing completions and diagnostics support. You may be better served by the [GoSublime](https://github.com/DisposaBoy/GoSublime) package.

`go get github.com/sourcegraph/go-langserver`

See: [github:palantir/sourcegraphgo-langserver](https://github.com/sourcegraph/go-langserver)

Client configuration:
```
"golsp":
{
  "command": ["go-langserver"],
  "scopes": ["source.go"],
  "syntaxes": ["Packages/Go/Go.sublime-syntax"],
  "languageId": "go"
},
```

### CSS<a name="css"></a>

Using the VS Code CSS language server:

`npm install -g vscode-css-languageserver-bin`

Then add to your LSP settings (replace PATH_TO_NODE_MODULES):

```
"vscode-css":
  {
    "command": ["node", "PATH_TO_NODE_MODULES/vscode-css-languageserver-bin/cssServerMain.js", "--stdio"],
    "scopes": ["source.css"],
    "syntaxes": ["Packages/CSS/CSS.sublime-syntax"],
    "languageId": "css"
  },
```

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

See: [natebosch/dart_language_server](https://github.com/natebosch/dart_language_server)

Client configuration (replace PATH_TO_PUB_BIN):
```
"dart": {
  "command": [
    "PATH_TO_PUB_BIN/dart_language_server"
  ],
  "enabled": true,
  "languageId": "dart",
  "scopes": [
    "source.dart"
  ],
  "syntaxes": [
    "Packages/Dart/Dart.tmLanguage"
  ]
}
```


### Other<a name="other"></a>

Please create issues / pull requests so we can get support for more languages.

### Client Configuration<a name="client-config"></a>

LSP ships with default client configuration for a few language servers. Here is an example for the Javascript/Typescript server:

```json
"jsts": {
    "command": ["lsp-tsserver"],
    "scopes": ["source.ts", "source.tsx"],
    "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"],
    "languageId": "typescript"
}
```

These can be customized as follows by adding an override in the User LSP.sublime-settings

* `command` - specify a full paths, add arguments (if not specified then tcp_port must be specifed)
* `tcp_port` - if not specified then stdin/out are used else sets the tcpport to connect to (if no command is specified then it is assumed that some process is listing on this port)
* `scopes` - add language flavours, eg. `source.js`, `source.jsx`.
* `syntaxes` - syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage`
* `languageId` - used both by the language servers and to select a syntax highlighter for sublime popups.
* `enabled` - disable a language server globally, or per-project
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

Show Diagnostics Panel: `super+shift+M` / `ctr+alt+M`

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
