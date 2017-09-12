### Sublime LSP Plugin Documentation

# Configuration


## Sublime Settings

* `mdpopups.use_sublime_highlighter` `true` *correct syntax highlighting in hover popups*

## LSP Settings

* `complete_all_chars` `true` *request completions for all characters, not just trigger characters*
* `only_show_lsp_completions` `false` *disable sublime word completion and snippets from autcomplete lists*
* `show_status_messages` `true` *show messages in the status bar for a few seconds*
* `show_view_status` `true` *show permanent language server status in the status bar*
* `auto_show_diagnostics_panel` `true` *open and close the diagnostics panel automatically*
* `show_diagnostics_phantoms` `false` *show diagnostics as phantoms while the file has no changes*
* `show_diagnostics_in_view_status` `true` *when on a diagnostic with the cursor, show the text in the status bar*
* `diagnostics_highlight_style` `"underline"` *highlight style of code diagnostics, `"underline"` or `"box"`*
* `log_debug` `false` *show debug logging in the sublime console*
* `log_server` `true` *show server/logMessage notifications from language servers in the console*
* `log_stderr` `false` *show language server stderr output in the console*

## Language Specific Setup

For any of these components it is important that Sublime Text can find the language server executable through the path, especially when using virtual environments.

For autocomplete to trigger on eg. `.` or `->`, you may need to add the listed `autocomplete_triggers` to your User or Syntax-specific settings.

The default LSP.sublime-settings contains some default LSP client configuration that may not work for you. See [Client Config](#client-config) for explanations for the available settings.

### Javascript/Typescript<a name="jsts"></a>

`npm install -g javascript-typescript-langserver`

See: [github:sourcegraph/javascript-typescript-langserver](https://github.com/sourcegraph/javascript-typescript-langserver)

On windows you will need to override client config to launch `javascript-typescript-stdio.cmd` instead.

See: [github](https://github.com/sourcegraph/javascript-typescript-langserver)

```
"auto_complete_triggers": [
        {
            "characters": ".",
            "selector": "source.js"
        },
        {
            "characters": ".",
            "selector": "source.ts"
        }
]
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


### Python<a name="python"></a>

`pip install python-language-server`

See: [github:palantir/python-language-server](https://github.com/palantir/python-language-server)

Autocomplete triggers:

```
"auto_complete_triggers": [ {"selector": "source.python", "characters": "."} ],
```

### PHP<a name="php"></a>

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

5. add triggers to `Preferences.sublime-settings - User`
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


### Rust<a name="rust"></a>

Requires Rust Nightly.

See [github:rust-lang-nursery/rls](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.

Autocomplete triggers:

```
"auto_complete_triggers": [ {"selector": "source.rust", "characters": ".:"} ]
```


### Scala<a name="scala"></a>

Dotty, the future scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html). It is developed against VS Code, so ignore instructions related to VS Code.

Get the project compiling with dotty first (see https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)

At this point LSP should complain in the logs
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`

Then run `sbt configureIDE` to create the .dotty-ide.json file
Then the LSP plugin should launch as configured in LSP.sublime-settings using coursier.


### C/C++ (Clangd)<a name="clang"></a>

You will need to build from source, see [instructions](https://clang.llvm.org/extra/clangd.html)

```
"auto_complete_triggers": [ {"selector": "source.c++", "characters": ".>:" }]
```

### Ocaml/Reason<a name="reason"></a>

You will need to install [sublime-reason](https://github.com/reasonml-editor/sublime-reason) and the dependencies listed in the repo, such as [ocaml-language-server](https://github.com/freebroccolo/ocaml-language-server). If you only use OCaml, you still need those listed dependencies, but not the sublime-reason plugin itself.

### Other<a name="other"></a>

Please create issues / pull requests so we can get support for more languages.

### Client Configuration<a name="client-config"></a>

LSP ships with default client configuration for a few language servers. Here is an example for the Javascript/Typescript server:

```json
"jsts": {
    "command": ["javascript-typescript-stdio"],
    "scopes": ["source.ts", "source.tsx"],
    "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"],
    "languageId": "typescript"
}
```

These can be customized as follows by adding an override in the User LSP.sublime-settings

* `command` - specify a full paths, add arguments
* `scopes` - add language flavours, eg. `source.js`, `source.jsx`.
* `syntaxes` - syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage`
* `languageId` - used both by the language servers and to select a syntax highlighter for sublime popups.
* `enabled` - disable a language server globally, or per-project
* `settings` - per-project settings (equivalent to VS Code's Workspace Settings)
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
* Document Symbols: UNBOUND

**Workspace actions**

Show Diagnostics Panel: `super+shift+M` / `ctr+alt+M`

**Mouse map configuration**

See below link, but bind to `lsp_symbol_definition` command
https://stackoverflow.com/questions/16235706/sublime-3-set-key-map-for-function-goto-definition


