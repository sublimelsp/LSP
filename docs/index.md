# Sublime LSP Plugin Documentation

### Client configurations 

LSP ships with default client configuration for a few language servers that may not work for you. Do not modify the `default_clients`! If you want to change server configurations, you can override them in the `clients` setting. Example:

```jsonc
// LSP.sublime-settings -- LSP
{
  "default_clients":
    "rls":
    {
      "command": ["rustup", "run", "nightly", "rls"],
      "scopes": ["source.rust"],
      "syntaxes": ["Packages/Rust/Rust.sublime-syntax", "Packages/Rust Enhanced/RustEnhanced.sublime-syntax"],
      "languageId": "rls"
    },
    // other clients
}
```
Override the `rls` command to use `stable` instead of `nightly`.
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "rls": {
      "command": ["rustup", "run", "stable", "rls"]
    },
    // other clients
}
```

> **Note** Install and verify that Sublime Text can find the language server executable through the `PATH`, especially when using virtual environments with your interpreter.

You can also add a new client in the `clients` setting. Each new client has the following structure:

```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "pyls": {
      "command": ["pyls"],          // required
      "scopes": ["source.python"],  // required
      "syntaxes": ["Packages/Python/Python.sublime-syntax"], // required
      "languageId": "python",       // required
      "settings": { },              // optional
      "initializationOptions": { }, // optional
      "env": { },                   // optional
      "enabled": false              // defaults to false, but needs to be true for the server to start
    }
  }
}
```

* `pyls` - Is the client name. Can be any string.
* `command` - The command line required to run the server. If not specified then `tcp_port` must be specified.
* `tcp_port` - Sets the `tcp_port` to connect to. Else `stdin/out` is used. If no `command` is specified then it is assumed that some process is listing on this port.
* `scopes` - Scopes of the file. Example `source.python`. To get the scopes, from the menu chose `Tools/Developer/Show Scope Name`.
* `syntaxes` - Syntaxes enable LSP features on a document. To get the syntax name run in the sublime console: `view.settings().get("syntax")`.
* `languageId` - Used both by the language servers and to select a syntax highlighter for sublime popups. Look up the identifiers [here](https://code.visualstudio.com/docs/languages/identifiers).
* `enabled` - Boolean indicating if a server is enabled or disabled. You can enable a language server globally, or per-project.
* `settings` - Per-project settings (equivalent to VS Code's Workspace Settings). Sent to server once using `workspace/didConfigurationChange` notification.
* `env` - Dictionary of environment variables to be injected into the language server's process (eg. PYTHONPATH) Extra variables to override/add to language server's environment.
* `initializationOptions` - Options to send to the server at startup in initialize request.

You can define different languages for the same language server. The multi-language form has the following structure:

```jsonc 
{
  "clients": {
    "css": {
      "enabled": true,
      "command": ["css-languageserver", "--stdio"],
      "languages": [
        {
          "scopes": ["source.css"],
          "syntaxes": ["Packages/CSS/CSS.sublime-syntax"],
          "languageId": "css"
        },
        {
          "scopes": ["source.sass"],
          "syntaxes": ["Packages/Sass/Syntaxes/Sass.sublime-syntax"],
          "languageId": "scss"
        },
        {
          "scopes": ["source.css.less"],
          "syntaxes": ["Packages/LESS/LESS.sublime-syntax"],
          "languageId": "less"
        }
      ]
    }
  }
}
```

### Per-project overrides

Any fields in a client configuration can be overridden by adding an LSP settings block to your `.sublime-project` file:

```jsonc
{
  "folders": [
    {
      "path": "."
    }
  ],
  "settings": {
    "LSP": {
      "pyls": {
        "enabled": false,
      },
      "eslint": {
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
## List of configured languages
### Bash<a name="bash"></a>

Install [bash language server](https://github.com/mads-hartmann/bash-language-server) globally.

```npm i -g bash-language-server```

### C/C++ (Clangd)<a name="clangd"></a>

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
### CSS/LESS/SASS (SCSS only)<a name="css"></a>

Install [vscode-css-languageserver-bin](https://www.npmjs.com/package/vscode-css-languageserver-bin) globally.

`npm install -g vscode-css-languageserver-bin`

### Dart<a name="dart"></a>

Install [dart_language_server](https://github.com/natebosch/dart_language_server#installing) and  [Dart](https://packagecontrol.io/packages/Dart) from Package Control.

`pub global activate dart_language_server`

Override the dart configuration:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "dart": {
      "command": ["PATH_TO_PUB_BIN/dart_language_server" ]
    }
  }
}
```
### Flow (JavaScript)<a name="flow"></a>

Install [flow-language-server](https://github.com/flowtype/flow-language-server#installation) globally.

`npm install -g flow-language-server`

### Go<a name="go"></a>

Follow the [installation steps](https://github.com/sourcegraph/go-langserver).

You can pass additional initialization options:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "golsp": {
      "initializationOptions": {
        // funcSnippetEnabled enables the returning of argument snippets
        // on `func` completions, eg. func(foo string, arg2 bar).
        // Requires code completion to be enabled.
        //
        // Defaults to true if not specified.
        "funcSnippetEnabled": true,
        
        // gocodeCompletionEnabled enables code completion feature (using gocode).
        //
        // Defaults to false if not specified.
        "gocodeCompletionEnabled": false,

        // formatTool decides which tool is used to format documents. Supported: goimports and gofmt.
        // Values: "goimports" | "gofmt"
        // Defaults to goimports if not specified.
        "formatTool": "goimports",

        // lintTool decides which tool is used for linting documents. Supported: none and golint
        //
        // Diagnostics must be enabled for linting to work.
        // Values:  "none" | "golint"
        // Defaults to none if not specified.
        "lintTool": "none",

        // goimportsLocalPrefix sets the local prefix (comma-separated string) that goimports will use.
        //
        // Defaults to empty string if not specified.
        "goimportsLocalPrefix": "",

        // MaxParallelism controls the maximum number of goroutines that should be used
        // to fulfill requests. This is useful in editor environments where users do
        // not want results ASAP, but rather just semi quickly without eating all of
        // their CPU.
        //
        // Defaults to half of your CPU cores if not specified.
        //"maxParallelism": number,

        // useBinaryPkgCache controls whether or not $GOPATH/pkg binary .a files should
        // be used.
        //
        // Defaults to true if not specified.
        "useBinaryPkgCache": true,
    }
  }
}
```

### HTML<a name="html"></a>

Install [vscode-html-languageserver-bin](https://www.npmjs.com/package/vscode-html-languageserver-bin) globally.

`npm install -g vscode-html-languageserver-bin`

### Java<a name="java"></a>
Implementations:

* [Java (Eclipse)](https://lsp.readthedocs.io/en/latest/#eclipse)
* [Java (IntelliJ)](https://lsp.readthedocs.io/en/latest/#intellij)

### Java (Eclipse)<a name="eclipse"></a>

Follow the instructions in this [issue](https://github.com/tomv564/LSP/issues/344).

Override the `command` field:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "jdtls": {
      "command": ["java", "-jar",
        "PATH_TO_JDT_SERVER/plugins/org.eclipse.equinox.launcher_1.4.0.v20161219-1356.jar",
        "-configuration", "PATH_TO_CONFIG_DIR"
      ]
    }
  }
}
```

### Java (IntelliJ)<a name="intellij"></a>

Requires IntelliJ to be running.

See [intellij-lsp-server](https://github.com/Ruin0x11/intellij-lsp-server) for more information.


### JavaScript/TypeScript<a name="typescript"></a>

> **LanguageHandler** is available but not published to Package Control. Clone it from [tomv564/LSP-tss](https://github.com/tomv564/LSP-tss).

Install [tomv564/lsp-tsserver](https://github.com/tomv564/lsp-tsserver) globally.
From Package Control if you use TypeScript install `TypeScript Syntax`.
If you work with `jsx` install `Babel`. You don't need a separate configuration for JavaScript as this configuration will work for both languages. 


`npm install -g lsp-tsserver`


You can enable type checking in JavaScript by creating [`jsconfig.json`](https://code.visualstudio.com/docs/languages/jsconfig) file with the following content:
```jsonc      
{
  "compilerOptions": {
    "checkJs": true,
    "baseUrl": "."
  }
}
```


### JSON<a name="json"></a>

Install [vscode-json-languageserver-bin](https://www.npmjs.com/package/vscode-json-languageserver-bin) globally.

`npm install -g vscode-json-languageserver-bin`


### Julia<a name="julia"></a>

> **LanguageHandler** is available but not published to Package Control. Clone it from [randy3k/LSP-julia](https://github.com/randy3k/LSP-julia).

### Kotlin<a name="kotlin"></a>

Install [kotlin language server](https://github.com/fwcd/KotlinLanguageServer).
Requires [building](https://github.com/fwcd/KotlinLanguageServer/blob/master/BUILDING.md) first. Also install the [Kotlin sublime package](https://github.com/vkostyukov/kotlin-sublime-package) for syntax highlighting.

Override the kotlin configuration:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "kotlin": {
      "command": ["PATH_TO_KotlinLanguageServer/build/install/kotlin-language-server/bin/kotlin-language-server.bat"]
    }
  }
}
```

### PHP <a name="php"></a>
Implementations:
* [PHP (Felix Becker)](https://lsp.readthedocs.io/en/latest/#felix_becker)
* [PHP (Intelephense)](https://lsp.readthedocs.io/en/latest/#intelephense)

### PHP (Felix Becker)<a name="felix_becker"></a>

Modify `~/.composer/composer.json`.
```jsonc
{
    "minimum-stability": "dev",
    "prefer-stable": true,
    "require": {
        "felixfbecker/language-server": "5.4.2"
    },
    "scripts": {
        "parse-stubs": "LanguageServer\\ComposerScripts::parseStubs",
        "post-update-cmd": "@parse-stubs",
        "post-install-cmd": "@parse-stubs"
    }
}
```
* Run `composer global require felixfbecker/language-server`.
* Run `composer run-script --working-dir=~/.composer/vendor/felixfbecker/language-server parse-stubs`.

Override the configuration:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "phpls": {
      "command": ["php", "/PATH-TO-HOME-DIR/.composer/vendor/felixfbecker/language-server/bin/php-language-server.php"],
    }
  }
}
```

See [felixfbecker/php-language-server](https://github.com/felixfbecker/php-language-server) for more information.

### PHP (Intelephense)<a name="intelephense"></a>

Install globally [bmewburn/intelephense-server](https://www.npmjs.com/package/intelephense-server).

`npm install -g intelephense-server`

Override the configuration:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "intelephense": {
      "command": [
        "node",
        "PATH_TO_GLOBAL_NODE_MODULES/intelephense-server/lib/server.js",  // Configure
        "--stdio",
      ],
      "initializationOptions": {
        "storagePath": "/tmp/intelephense", // Configure
      }
    }
  }
}
```

### Polymer<a name="polymer"></a>

Install globally [polymer-editor-service](https://www.npmjs.com/package/polymer-editor-service).
For more info see [this](https://github.com/Polymer/tools/blob/master/packages/editor-service/docs/sublime.md).

`npm install -g polymer-editor-service`

### Python<a name="python"></a>
Implementations:
* [Python (Palantir Technologies)](https://lsp.readthedocs.io/en/latest/#python_palantir)
* [Python (Microsoft)](https://lsp.readthedocs.io/en/latest/#python_microsoft)

### Python (Palantir Technologies)<a name="python_palantir"></a>

Follow the [installation steps](https://github.com/palantir/python-language-server#installation).

### Python (Microsoft)<a name="python_microsoft"></a>

Microsoft's python language server using .NET Core runtime.
Follow the [installation steps](https://github.com/Microsoft/python-language-server/blob/master/Using_in_sublime_text.md).


### R<a name="r"></a>

Plugin available, see [installation steps](https://github.com/REditorSupport/sublime-ide-r).

### Reason/OCaml<a name="reason"></a>

See [installation steps](https://github.com/freebroccolo/ocaml-language-server).

You will need to install [sublime-reason](https://github.com/reasonml-editor/sublime-reason) and the dependencies listed in the repo, such as [ocaml-language-server](https://github.com/freebroccolo/ocaml-language-server). If you only use OCaml, you still need those listed dependencies, but not the sublime-reason plugin itself.

### Ruby<a name="ruby"></a>

See [installation steps](https://github.com/castwide/solargraph#installation).

### Rust<a name="rust"></a>

> **LanguageHandler** is available but not published to Package Control. Clone it from [tomv564/LSP-rust](https://github.com/tomv564/LSP-rust).

Follow the [installation steps](https://github.com/rust-lang-nursery/rls).

If `rls` doesn't start. Try to override the command to use `stable` instead of `nightly`.
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "rls": {
      "command": ["rustup", "run", "stable", "rls"]
    }
  }
}
```


### Scala<a name="scala"></a>

> **LanguageHandler** is available but not published to Package Control. Clone it from [tomv564/LSP-dotty](https://github.com/tomv564/LSP-dotty).

SBT 1.x supports limited language server functionality, setup is described here: [sbt server with Sublime Text 3](http://eed3si9n.com/sbt-server-with-sublime-text3).

Dotty, the future scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html). It is developed against VS Code, so ignore instructions related to VS Code.

Get the project compiling with dotty first (see https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)

At this point LSP should complain in the logs
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`

Then run `sbt configureIDE` to create the .dotty-ide.json file
Then the LSP plugin should launch as configured in LSP.sublime-settings using coursier.


### Vue (JavaScript)<a name="vue"></a>

Install globally [vue-language-server](https://www.npmjs.com/package/vue-language-server). Also install `Vue Syntax Highlight` from Package Control.

`npm install -g vue-language-server`

Client configuration:
```jsonc
// LSP.sublime-settings -- User
{
  "clients": {
    "vue": {
      "syntaxes": [
        // For ST3 builds < 3153
        "Packages/Vue Syntax Highlight/vue.tmLanguage"
        // For ST3 builds >= 3153
        // "Packages/Vue Syntax Highlight/Vue Component.sublime-syntax"
      ]
    }
  }
}
```

## Features<a name="features"></a>

Smart auto completions with snippet support.

Navigate code with `Go to Symbol Definition` and `Find Symbol References`.

Inline documentation from Hover and Signature Help popups.

![hover screenshot](https://raw.githubusercontent.com/tomv564/LSP/master/docs/images/screenshot-hover.png)

As-you-type diagnostics with support for code fixes (`F4` to select, `super+.` to trigger actions)

![diagnostics screenshot](https://raw.githubusercontent.com/tomv564/LSP/master/docs/images/screenshot-diagnostics-action.png)

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

More useful keybindings (OS-X), edit Package Settings -> LSP -> Key Bindings
```
  { "keys": ["f2"], "command": "lsp_symbol_rename" },
  { "keys": ["f12"], "command": "lsp_symbol_definition" },
  { "keys": ["super+option+r"], "command": "lsp_document_symbols" },
  { "keys": ["super+option+h"], "command": "lsp_hover"}
```

If you want to set goto definition with a mouse click see this [thread](https://stackoverflow.com/questions/16235706/sublime-3-set-key-map-for-function-goto-definition).

### Contributing<a name="contributing"></a>

Please create issues / pull requests so we can get support for more languages.

