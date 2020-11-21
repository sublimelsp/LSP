# Language Servers

The following list can help you to install and configure language servers for use with LSP.
Please remember to put the configurations in a `"clients"` dictionary in your `LSP.sublime-settings` file, as shown in the example above.
If you use or would like to use language servers that are not in this list, please create issues or pull requests, so we can add support for more languages.

!!! tip
    We recommend installing [LSP-json](https://packagecontrol.io/packages/LSP-json), as it suggest smart settings completions and report errors when inside the `LSP.sublime-settings` file.

## Angular

Follow installation instructions on [LSP-angular](https://github.com/sublimelsp/LSP-angular).

## Bash
1. Make sure you have `node` installed.
2. Download the [LSP-bash](https://packagecontrol.io/packages/LSP-bash) helper package.

## C/C++

See the dedicated <a href="/guides/cplusplus"/>C/C++ guide</a> for using ccls or clangd.

## C\#

1. [Download](https://github.com/OmniSharp/omnisharp-roslyn/releases) or build [OmniSharp](https://github.com/OmniSharp/omnisharp-roslyn).
2. Add to LSP settings' clients:

```js
"omnisharp": {
  "command": [
    "/home/tb/prebuilt/omnisharp/OmniSharp.exe", // or eg. /usr/local/opt/omnisharp/run
    "-lsp"
  ],
  "enabled": true,
  "languageId": "csharp",
  "document_selector": "source.cs"
}
```

## CMake

Follow installation instructions on [LSP-cmake](https://github.com/sublimelsp/LSP-cmake). (not available on Package Control)

## Clojure

1. Download [clojure-lsp](https://github.com/snoe/clojure-lsp).
2. Add to LSP settings' clients:

```js
"clojure-lsp": {
  "command": ["java", "-jar", "/PATH/TO/clojure-lsp"],
  "enabled": true,
  "initializationOptions": {},
  "languageId": "clojure" // will match source.clojure
}
```

clojure-lsp has a [rich set of initializationOptions](https://github.com/snoe/clojure-lsp#initializationoptions).

## CSS

1. Install the CSS language server from VS Code:

        npm install -g vscode-css-languageserver-bin

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `vscode-css`.

## D

1. Install the [D Language Server](https://github.com/d-language-server/dls):

        dub fetch dls
        dub run dls:bootstrap

2. Add to LSP settings' clients:

```js
"dls": {
  "command": ["<PATH TO DLS EXECUTABLE>"],
  "enabled": true,
  "languageId": "d" // will match source.d
}
```

## Dart

1. Install the [Dartlight](https://packagecontrol.io/packages/Dartlight) package from Package Control for syntax highlighting.
2. Install the [Dart SDK](https://dart.dev/get-dart) and locate path to `analysis_server.dart.snapshot` in the "snapshots/bin" directory.
3. Add to LSP settings' clients (adjust the path if necessary):

```js
"dart": {
  "command": ["dart", "/usr/local/opt/dart/libexec/bin/snapshots/analysis_server.dart.snapshot", "--lsp"],
  "enabled": true,
  "languageId": "dart" // will match source.dart
}
```

> **Note**: The older [natebosch/dart_language_server](https://github.com/natebosch/dart_language_server) is now deprecated.

## Dockerfile

1. Install the [Dockerfile Syntax Highlighting](https://packagecontrol.io/packages/Dockerfile%20Syntax%20Highlighting) package from Package Control for syntax highlighting.
2. Install the [Dockerfile Language Server](https://github.com/rcjsuen/dockerfile-language-server-nodejs):

        npm install -g dockerfile-language-server-nodejs

3. Add to LSP settings' clients:

```js
"docker-langserver": {
  "command": ["docker-langserver", "--stdio"],
  "enabled": true,
  "languageId": "dockerfile", // will match source.dockerfile
  "settings": {
    // string values must be equal to "ignore", "warning", or "error"
    "docker.languageserver.diagnostics.deprecatedMaintainer": "warning",
    "docker.languageserver.diagnostics.directiveCasing": "warning",
    "docker.languageserver.diagnostics.emptyContinuationLine": "warning",
    "docker.languageserver.diagnostics.instructionCasing": "warning",
    "docker.languageserver.diagnostics.instructionCmdMultiple": "warning",
    "docker.languageserver.diagnostics.instructionEntrypointMultiple": "warning",
    "docker.languageserver.diagnostics.instructionHealthcheckMultiple": "warning",
    "docker.languageserver.diagnostics.instructionJSONInSingleQuotes": "warning"
  },
}
```

## Elixir

1. Install the [Elixir](https://packagecontrol.io/packages/Elixir) package from Package Control for syntax highlighting.
2. Download the prebuilt binaries or compile [elixir-ls](https://github.com/elixir-lsp/elixir-ls).
   This will get you a folder containing `language_server.sh` among other things.
3. Add to LSP settings' clients (adjust the path if necessary):

```js
"elixir-ls": {
  "command": ["/home/someUser/somePlace/elixir-ls/release/language_server.sh"],
  "enabled": true,
  "languageId": "elixir" // will match source.elixir
}
```

## Elm

1. Install the [Elm Syntax Highlighting](https://packagecontrol.io/packages/Elm%20Syntax%20Highlighting) package from Package Control for syntax highlighting.
2. See instructions for installing the [elm-language-server](https://github.com/elm-tooling/elm-language-server).
3. Add to LSP settings' clients:

```js
"elm": {
  "command": ["elm-language-server", "--stdio"],
  "enabled": true,
  "initializationOptions": {
    "elmAnalyseTrigger": "change"
  },
  "languageId": "elm" // will match source.elm
}
```

## Erlang

1. See instructions for installing the [Erlang Language Server](https://github.com/erlang-ls/erlang_ls).
2. Add to LSP settings' clients:

```json
"erlang-ls": {
  "command"   : [ "/path/to/my/erlang_ls", "--transport", "stdio" ],
  "enabled"   : true,
  "languageId": "erlang" // will match source.erlang
}
```

## ESLint

1. Make sure you have `node` installed.
2. Install the [LSP-eslint](https://packagecontrol.io/packages/LSP-eslint) helper package. It will install the server for you in $DATA/Cache.

## Flow (JavaScript)

Official part of [flow-bin](https://github.com/facebook/flow):

```sh
npm install -g flow-bin
```

Older [flow-language-server](https://github.com/flowtype/flow-language-server):

```sh
npm install -g flow-language-server
```

## Fortran

1. Install the [Fortran](https://packagecontrol.io/packages/Fortran) package from Package Control for syntax highlighting.
2. Install the [Fortran Language Server](https://github.com/hansec/fortran-language-server) (requires Python):

        pip install fortran-language-server

3. Add to LSP settings' clients:

```json
"fortls": {
  "command": ["fortls"],
  "enabled": true,
  "languageId": "fortran",
  "document_selector": "source.modern-fortran | source.fixedform-fortran"
}
```

> **Note**: See the [Language server settings](https://github.com/hansec/fortran-language-server#language-server-settings)
  documentation for a detailed description of available configuration options, for example
  `"command": ["fortls", "--lowercase_intrinsics"]` to use lowercase for autocomplete suggestions.

## Go

### Gopls

1. Install [gopls](https://github.com/golang/tools/tree/master/gopls), the official language server for the Go language:

        go get golang.org/x/tools/gopls@latest

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `gopls`.

> **Note**: See the [User guide](https://github.com/golang/tools/blob/master/gopls/doc/user.md#user-guide) for detailed installation instructions and configurations.

### Sourcegraph's go-langserver

1. Install Sourcegraph's [Go Language Server](https://github.com/sourcegraph/go-langserver):

        go get github.com/sourcegraph/go-langserver

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `golsp`.

> **Note**: Work on this language server has been deprioritized in favor of the gopls language server mentioned above.

## GraphQL

Follow installation instructions on [LSP-graphql](https://github.com/sublimelsp/LSP-graphql).

## Haskell

1. Install [haskell-language-server](https://github.com/haskell/haskell-language-server).
2. Add to LSP settings' clients:

```js
"haskell-language-server": {
  "enabled": true
  "command": [
    "haskell-language-server-wrapper",
    "--lsp"
  ],
  "languageId": "haskell",
  "scopes": [
    "source.haskell"
  ],
  "syntaxes": [
    "Packages/Haskell/Haskell.sublime-syntax"
  ],
}
```

## HTML

Follow installation instructions on [LSP-html](https://github.com/sublimelsp/LSP-html).

## Java

### Eclipse JDT Language Server

1. Download and extract Eclipse's [jdt-ls](https://download.eclipse.org/jdtls/snapshots/jdt-language-server-latest.tar.gz).
2. Add to LSP settings' clients:

```js
"jdtls": {
  "command": [
    "java",
    "--add-modules=ALL-SYSTEM",
    "--add-opens",
    "java.base/java.util=ALL-UNNAMED",
    "--add-opens",
    "java.base/java.lang=ALL-UNNAMED",
    "-Declipse.application=org.eclipse.jdt.ls.core.id1",
    "-Dosgi.bundles.defaultStartLevel=4",
    "-Declipse.product=org.eclipse.jdt.ls.core.product",
    "-Dfile.encoding=UTF-8",
    "-DwatchParentProcess={true|false}",  // false on windows, true other OSs
    "-noverify",
    "-Xmx1G",
    "-XX:+UseG1GC",
    "-XX:+UseStringDeduplication",
    "-jar",
    "PATH/TO/jdt-language-server-latest/plugins/org.eclipse.equinox.launcher_*.jar" // 1. replace the PATH/TO with your own 2. replace * with the file version
    "-configuration",
    "PATH/TO/jdt-language-server-latest/config_{win|mac|linux}", // 1. replace the PATH/TO with your own 2. choose the config folder based on the OS
    "-data",
    "<TEMP_DIR>/${project_base_name}/jdt_ws" // replace <TEMP_DIR> with the temp folder in your system. macOS: echo $TMPDIR
  ],
  "enabled": true,
  "languageId": "java" // will match source.java
}
```

### IntelliJ

Requires IntelliJ to be running.

```js
"intellij": {
  "command": [],
  "languageId": "java", // will match source.java
  "tcp_port": 8080 // default port
}
```

## JavaScript/TypeScript

1. Make sure you have `node` installed.
2. Install the [LSP-typescript](https://packagecontrol.io/packages/LSP-typescript) helper package. It will install the
   server for you in $DATA/Cache.

## JSON

Follow installation instructions on [LSP-json](https://github.com/sublimelsp/LSP-json).

## Julia

1. Install the [Julia](https://packagecontrol.io/packages/Julia) package from Package Control for syntax highlighting.
2. Install the `LanguageServer` and `SymbolServer` packages from the Julia REPL:

        import Pkg;
        Pkg.add("LanguageServer")
        Pkg.add("SymbolServer")

3. Add to LSP settings' clients:

```js
"julials": {
  "command": ["bash", "PATH_TO_JULIA_SERVER/LanguageServer/contrib/languageserver.sh"], // on Linux/macOS
  // "command": ["julia", "--startup-file=no", "--history-file=no", "-e", "using Pkg; using LanguageServer; using LanguageServer.SymbolServer; env_path=dirname(Pkg.Types.Context().env.project_file); server=LanguageServer.LanguageServerInstance(stdin,stdout,false,env_path); run(server)"], // on Windows
  "languageId": "julia",
  "settings": {
    // Default values from VS Code:
    "julia.format.calls": true,      // Format function calls
    "julia.format.comments": true,   // Format comments
    "julia.format.curly": true,      // Format braces
    "julia.format.docs": true,       // Format inline documentation
    "julia.format.indent": 4,        // Indent size for formatting
    "julia.format.indents": true,    // Format file indents
    "julia.format.iterOps": true,    // Format loop iterators
    "julia.format.kw": true,         // Remove spaces around = in function keywords
    "julia.format.lineends": false,  // [undocumented]
    "julia.format.ops": true,        // Format whitespace around operators
    "julia.format.tuples": true,     // Format tuples
    "julia.lint.call": false,        // Check calls against existing methods (experimental)
    "julia.lint.constif": true,      // Check for constant conditionals of if statements
    "julia.lint.datadecl": false,    // [undocumented]
    "julia.lint.iter": true,         // Check iterator syntax of loops
    "julia.lint.lazy": true,         // Check for deterministic lazy boolean operators
    "julia.lint.modname": true,      // Check for invalid submodule names
    "julia.lint.nothingcomp": false, // [undocumented]
    "julia.lint.pirates": true,      // Check for type piracy
    "julia.lint.run": true,          // run the linter on active files
    "julia.lint.typeparam": true     // Check for unused DataType parameters
  }
}
```

<!-- Alternatively, install the [LSP-julia](https://github.com/randy3k/LSP-julia) package for Sublime Text. -->
<!-- (Currently doesn't work with newest release of Julia's LanguageServer) -->

## Kotlin

1. Install the [Kotlin](https://packagecontrol.io/packages/Kotlin) package from Package Control for syntax highlighting.
2. Install the [Kotlin Language Server](https://github.com/fwcd/KotlinLanguageServer) (requires [building](https://github.com/fwcd/KotlinLanguageServer/blob/master/BUILDING.md) first).
3. Add to LSP settings' clients:

```js
"kotlinls": {
  "command": ["PATH/TO/KotlinLanguageServer/build/install/kotlin-language-server/bin/kotlin-language-server.bat"],
  "enabled": true,
  "languageId": "kotlin", // will match source.kotlin
  "settings": {
    "kotlin": {
      // put your server settings here
    }
  }
}
```

## LaTeX

1. Download a [precompiled binary](https://github.com/latex-lsp/texlab/releases) (Windows/Linux/macOS) of the [TexLab](https://texlab.netlify.com/) language server.
2. Add to LSP settings' clients:

```json
"texlab": {
  "command": ["PATH/TO/texlab"],
  "enabled": true,
  "languages": [{
    "languageId": "latex",
    "document_selector": "text.tex.latex"
  }, {
    "languageId": "bibtex",
    "document_selector": "text.bibtex"
  }]
}
```

> **Note**: To enable code completions while typing, ensure to have `text.tex.latex` (for LaTeX files) and/or `text.bibtex`
  (for BibTeX files) included in the `auto_complete_selector` setting in your `Preferences.sublime-settings` file.
  For further requirements see the [TexLab Docs](https://texlab.netlify.com/docs#requirements).

## Lisp

1. Install [cc-lsp](https://github.com/cxxxr/cl-lsp) using Roswell.
2. Add to LSP settings' clients:

```js
"cc-lsp": {
  "command": ["cl-lsp", "stdio"],
  "enabled": true,
  "languageId": "lisp" // will match source.lisp
}
```

## Lua

1. Download the [VS Code extension](https://marketplace.visualstudio.com/items?itemName=sumneko.lua).
2. Add to LSP settings' clients:

```js
"lua-ls": {
  "command": [
    "PATH/TO/sumneko.lua-#.#.#/extension/server/bin/lua-language-server",
    "-E", "PATH/TO/sumneko.lua-#.#.#/extension/server/main.lua"
  ],
  "enabled": true,
  "languageId": "lua" // will match source.lua
}
```

Alternatively you can use the less maintained [lua-lsp](https://github.com/Alloyed/lua-lsp).

## OCaml/Reason

1. Install the [Reason](https://packagecontrol.io/packages/Reason) package from Package Control for syntax highlighting.
2. Install the [Reason Language Server](https://github.com/jaredly/reason-language-server#sublime-text).
3. Add to LSP settings' clients:

```json
"reason": {
  "command": ["PATH/TO/reason-language-server.exe"],
  "enabled": true,
  "languageId": "reason",
  "document_selector": "source.ocaml | source.reason"
}
```

## PromQL

Follow installation instructions on [LSP-promql](https://github.com/prometheus-community/sublimelsp-promql).

## PHP

### Intelephense

1. Make sure you have `node` installed.
2. Install the [LSP-intelephense](https://packagecontrol.io/packages/LSP-intelephense) helper package. It installs
   and updates the server for you in $DATA/Cache.

## Polymer

```sh
npm install -g polymer-editor-service
```

> **Note**: requires an up to date version of NodeJS. v6 is the minimum supported version as of 2017.

Features:

* typeahead completions for elements, attributes, and css custom properties
* documentation on hover for elements and attributes
* jump to definition for elements, attributes, and css custom properties
* linting, configured through `polymer.json` at your workspace root

More info: [Polymer/polymer-editor-service](https://github.com/Polymer/polymer-editor-service)

## PowerShell

1. Install the [PowerShell](https://packagecontrol.io/packages/PowerShell) package from Package Control for syntax highlighting.
2. Download and extract the [latest release](https://github.com/PowerShell/PowerShellEditorServices/releases) PowerShellEditorServices.
3. Make sure PowerShell help files are up to date by running `Update-Help` in the PowerShell console (the one you're using in the command below).
4. Add to LSP settings' clients:

```js
"powershell-ls": {
  "command": [
    "powershell", // or pwsh for PowerShell Core
    "-NoLogo",
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass", // Windows only
    "-Command", "PATH/TO/PowerShellEditorServices/PowerShellEditorServices/Start-EditorServices.ps1",
    "-LogPath", "PATH/TO/pses.log", // specify a path where a logfile should be stored
    "-LogLevel", "Normal",
    "-SessionDetailsPath", "PATH/TO/session.json", // specify a path where a file for session details should be stored
    "-FeatureFlags", "@()",
    "-HostName", "'Sublime Text'",
    "-HostProfileId", "subl",
    "-HostVersion", "1.0.0",
    "-AdditionalModules", "@()",
    "-BundledModulesPath", "PATH/TO/PowerShellEditorServices",
    "-Stdio"
  ],
  "enabled": true,
  "languageId": "powershell" // will match source.powershell
}
```

> **Note**: For more details see this [issue](https://github.com/PowerShell/PowerShellEditorServices/issues/1057).

## Python

There are at least two language servers, use either one.

### Palantir's Python Language Server

```sh
pip install 'python-language-server[all]'
```

Make sure you can run `pyls` in your terminal. If you've installed it into a virtualenv, you might need to override the path to `pyls` in global LSP settings (Package Settings -> LSP -> Settings):

```js
"pyls": {
  "command": ["/Users/mike/.virtualenvs/pyls-virtual-env/bin/pyls"], // example path, adjust it for your use case
  "enabled": true // if you want to enable Python Language Server globally
}
```

If you use a virtualenv for your current project, add a path to it in your [project configuration](https://www.sublimetext.com/docs/3/projects.html) (Project -> Edit Project):

```js
{
  "settings": {
    "LSP": {
      "pyls": {
        "enabled": true, // if you want to enable Python Language Server for current project only
        "env": {
          // example path, adjust it for your use case
          // it needs to be an absolute path, neither $HOME nor ~ work here
          "PYTHONPATH": "/Users/mike/.virtualenvs/my-virtual-env/lib/python3.7/site-packages"
        }
      }
    }
  }
}
```

A basic configuration below can be used for bootstrapping your own:

```js
  //...
"pyls": {
  "enabled": true,
  "command": ["pyls"],
  "languageId": "python",
  "scopes": ["source.python"],
  "syntaxes": [
    "Packages/Python/Python.sublime-syntax",
    "Packages/MagicPython/grammars/MagicPython.tmLanguage",
    "Packages/Djaneiro/Syntaxes/Python Django.tmLanguage",
  ],
  "settings": {
    "pyls.env": {
      // Making Sublime's own libs available to the linters.
      // "PYTHONPATH": "/Applications/Sublime Text.app/Contents/MacOS/Lib/python33",
    },
    // Configuration is computed first from user configuration (in home directory),
    // overridden by configuration passed in by the language client,
    // and then overridden by configuration discovered in the workspace.
    "pyls.configurationSources": [
      "pycodestyle", // discovered in ~/.config/pycodestyle, setup.cfg, tox.ini and pycodestyle.cfg
      // "flake8",   // discovered in ~/.config/flake8, setup.cfg, tox.ini and flake8.cfg
    ],
    "pyls.plugins.jedi.extra_paths": [
      // The directory where the pip installation package is located
    ],
    // Enable fuzzy matches when requesting autocomplete
    "pyls.plugins.jedi.jedi_completion.fuzzy": true,
    "pyls.plugins.jedi.pycodestyle.enabled": true,
    "pyls.plugins.jedi.pycodestyle.exclude": [
      // Exclude files or directories which match these patterns
    ],
    "pyls.plugins.jedi.pycodestyle.ignore": [
      // Exclude files or directories which match these patterns
    ],
    // "pyls.plugins.jedi.pycodestyle.maxLineLength: 80" // set maximum allowed line length
    "pyls.plugins.pydocstyle.enabled" false,
    "pyls.plugins.pyflakes.enabled": true,
    "pyls.plugins.pylint.enabled": false,
    "pyls.plugins.yapf.enabled": true,
    // pyls' 3rd Party Plugins, Mypy type checking for Python 3, Must be installed via pip before enabling
    "pyls.plugins.pyls_mypy.enabled": false, // Install with: pip install pyls-mypy
    "pyls.plugins.pyls_mypy.live_mode": true
  }
},
```

See pylint documentation: [github:palantir/python-language-server](https://github.com/palantir/python-language-server)

Description of all built-in settings: https://github.com/palantir/python-language-server/blob/develop/vscode-client/package.json

### Microsoft's Python Language Server

Alternatively, use Microsoft Python Language Server (using .NET Core runtime).
Here is a basic configuration to be added to your User/LSP.sublime-settings file:

```js
  //...
"mspyls": {
  "enabled": true,
  "command": [ "dotnet", "exec", "PATH/TO/Microsoft.Python.LanguageServer.dll" ],
  "languageId": "python",
  "scopes": [ "source.python" ],
  "syntaxes": [
    "Packages/Python/Python.sublime-syntax",
    "Packages/MagicPython/grammars/MagicPython.tmLanguage",
    "Packages/Djaneiro/Syntaxes/Python Django.tmLanguage"
  ],
  "initializationOptions":
  {
    "interpreter":
    {
      "properties":
      {
        "UseDefaultDatabase": true,
        "Version": "3.7" // python version
      }
    }
  },
  "settings":
  {
    "python":
    {
      // At least an empty "python" object is (currently) required to initialise the language server.
      // Other options can be defined as explained below.
    }
  }
},
```

The language server has to be configured as per the Microsoft [documentation](https://github.com/microsoft/python-language-server/blob/master/README.md) and the Sublime Text [instructions](https://github.com/Microsoft/python-language-server/blob/master/Using_in_sublime_text.md).
An exhaustive list of the configuration options can be found in the VSCode [documentation](https://code.visualstudio.com/docs/python/settings-reference#_python-language-server-settings).

Here is an example of settings:

```js
  "settings":
  {
    "python":
    {
      // Solve the 'unresolved import' warning as documented in:
      // https://github.com/microsoft/python-language-server/blob/master/TROUBLESHOOTING.md#unresolved-import-warnings
      "autoComplete":
      {
          // add extra path for Sublime Text plugins
          "extraPaths": [ "/opt/sublime_text" ]
      }
      // Configure the linting options as documented in:
      // https://github.com/microsoft/python-language-server/#linting-options-diagnostics
      "analysis":
      {
        "errors": [ "undefined-variable" ],
        "warnings": [ "unknown-parameter-name" ],
        "information": [ "unresolved-import" ],
        "disabled": [ "too-many-function-arguments", "parameter-missing" ]
      },
      // "linting":
      // {
      //     "enabled": "false"
      // }
    }
  }
```

## R

1. Install the `languageserver` package from CRAN (see the [CRAN mirrored package on GitHub](https://github.com/cran/languageserver) for more information and up-to-date installation instructions):

        install.packages("languageserver")

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `rlang`.

## Ruby/Ruby on Rails

Different servers are available for Ruby:

Solargraph:

1. Install the solargraph gem (see [github:castwide/solargraph](https://github.com/castwide/solargraph) for up-to-date installation instructions):

        gem install solargraph

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `ruby`.

Sorbet:

1. Install the sorbet and sorbet-runtime gem (see [github:sorbet/sorbet](https://github.com/sorbet/sorbet)):

        gem install sorbet
        gem install sorbet-runtime

    If you have a Gemfile, using bundler, add sorbet and sorbet-runtime to your Gemfile and run:

        bundle install

2. Run "LSP:Enable Language Server Globally" from the Command Palette and choose `sorbet`.

## Rust

Goes well with the [Rust Enhanced package](https://github.com/rust-lang/rust-enhanced) which uses the RLS server: [github:rust-lang-nursery/rls](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.

Alternatively, a newer [rust-analyzer](https://github.com/rust-analyzer/rust-analyzer) server is under development, also supported by LSP.

## Scala

* **[Metals](https://scalameta.org/metals/)**: Most complete LSP server for Scala, see [LSP-metals](https://packagecontrol.io/packages/LSP-metals) for installation.
* **[SBT](https://www.scala-sbt.org/)**: Version 1.x supports limited and *unmaintained* language server functionalities, setup is described [here](http://eed3si9n.com/sbt-server-with-sublime-text3).
* **[Dotty](http://dotty.epfl.ch/)**: The future Scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html).
It is developed against VS Code, so ignore instructions related to VS Code.
Get the project compiling with dotty first (see [instructions](https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)).
At this point LSP should complain in the logs
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`
Then run `sbt configureIDE` to create the `.dotty-ide.json` file
Then the LSP plugin should launch as configured in `LSP.sublime-settings` using coursier.

## SonarLint

Follow installation instructions on [LSP-SonarLint](https://github.com/sublimelsp/LSP-SonarLint). (not available on Package Control)

## SourceKit

Follow installation instructions on [LSP-SourceKit](https://github.com/sublimelsp/LSP-SourceKit). (not available on Package Control)

## Stylelint

Follow installation instructions on [LSP-stylelint](https://github.com/sublimelsp/LSP-stylelint).

## Svelte

Follow installation instructions on [LSP-svelte](https://github.com/sublimelsp/LSP-svelte).

## Swift

1. Install the [Swift](https://packagecontrol.io/packages/Swift) package from Package Control for syntax highlighting.
2. Install Xcode 11.4 or later and ensure that `xcrun -find sourcekit-lsp` returns the path to sourcekit-lsp.

## TAGML

Follow installation instructions on [LSP-tagml](https://github.com/HuygensING/LSP-tagml).

## Terraform

1. Download [terraform-lsp](https://github.com/juliosueiras/terraform-lsp/releases) binary and make it available in your PATH.
2. Add to LSP settings' clients:

```js
"terraform": {
  "command": ["terraform-lsp"],
  "enabled": true,
  "languageId": "terraform" // will match source.terraform
}
```

## Vue

See: [LSP-vue](https://packagecontrol.io/packages/LSP-vue)

Be sure to install [Vue Syntax Highlight](https://packagecontrol.io/packages/Vue%20Syntax%20Highlight) from Package Control.

## XML

1. Download jar from [angelozerr/lsp4xml](https://github.com/angelozerr/lsp4xml/releases).
2. Add to LSP settings' clients:

```js
"lsp4xml": {
  "command": [
    "java",
    "-DwatchParentProcess=false",  // false on windows, true on other operating systems
    // JVM options (not necessary, but the vscode extension uses them by default)
    "-noverify",                   // bypass class verification
    "-Xmx64M",                     // set the maximum heap size
    "-XX:+UseG1GC",                // use the G1 garbage collector
    "-XX:+UseStringDeduplication", // enable string deduplication optimisation
    "-jar",
    "PATH/TO/org.eclipse.lsp4xml-uber.jar"
  ],
  "enabled": true,
  "languageId": "xml",
  "document_selector": "text.xml"
}
```

> **Note**: Discussed in [this issue](https://github.com/sublimelsp/LSP/issues/578).

## YAML

Follow installation instructions on [LSP-yaml](https://github.com/sublimelsp/LSP-yaml).
