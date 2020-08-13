## Getting started

1. Install a language server from the list below, ensuring it can be started from the command line (is in your PATH).
2. Run "LSP: Enable Language Server Globally" or "LSP: Enable Lanuage Server in Project" from Sublime's Command Palette to allow the server to start.
3. Open a document in your language - if the server starts its name will be in the left side of the status bar.


## About LSP

The *Language Server Protocol* is a specification about the communication protocol for use between text editors or IDEs and *language servers* - tools which provide language-specific features like autocomplete, go to definition, or documentation on hover.
This LSP package acts as an interface between Sublime Text and the language servers, which means that to obtain these features you need to install a server for your language first.
Language servers can be provided as standalone executables or might require a runtime environment like Node.js or Python.
The [list below](index.md#language-servers) shows installation instructions and example configurations for several servers that have been tested and are known to work with the LSP package.
Visit [Langserver.org](https://langserver.org/) or the [list of language server implementations](https://microsoft.github.io/language-server-protocol/implementors/servers/) maintained by Microsoft for a complete overview of available servers for various programming languages.

For a few languages you can also find dedicated packages on Package Control, which can optionally be installed to simplify the configuration and installation process of a language server and might provide additional features such as automatic updates for the server:

* [LSP-bash](https://packagecontrol.io/packages/LSP-bash)
* [LSP-css](https://packagecontrol.io/packages/LSP-css)
* [LSP-dockerfile](https://packagecontrol.io/packages/LSP-dockerfile)
* [LSP-elm](https://packagecontrol.io/packages/LSP-elm)
* [LSP-eslint](https://packagecontrol.io/packages/LSP-eslint)
* [LSP-html](https://packagecontrol.io/packages/LSP-html)
* [LSP-intelephense](https://packagecontrol.io/packages/LSP-intelephense)
* [LSP-json](https://packagecontrol.io/packages/LSP-json)
* [LSP-metals](https://packagecontrol.io/packages/LSP-metals)
* [LSP-serenata](https://packagecontrol.io/packages/LSP-serenata)
* [LSP-typescript](https://packagecontrol.io/packages/LSP-typescript)
* [LSP-vue](https://packagecontrol.io/packages/LSP-vue)
* [LSP-yaml](https://packagecontrol.io/packages/LSP-yaml)

### Server Configuration<a name="client-config"></a>

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
  "log_stderr": true,
  "log_payloads": true,

  // Language server configurations
  "clients": {
    "lsp-tsserver": {
      "command": ["lsp-tsserver"],
      "enabled": true,
      "languageId": "typescript",
      "scopes": ["source.ts", "source.tsx"],
      "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"]
    }
  }
}
```

Some language servers support multiple languages, which can be specified in the following way:

```js
{
  // General settings
  "log_stderr": true,
  "log_payloads": true,

  // Language server configurations
  "clients": {
    "lsp-tsserver": {
      "command": ["lsp-tsserver"],
      "enabled": true,
      "languages": [{
        "languageId": "javascript",
        "scopes": ["source.js", "source.jsx"],
        "syntaxes": ["Packages/Babel/JavaScript (Babel).sublime-syntax", "Packages/JavaScript/JavaScript.sublime-syntax"]
      }, {
        "languageId": "typescript",
        "scopes": ["source.ts", "source.tsx"],
        "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"]
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
| scopes | add language flavours, eg. `source.js`, `source.jsx` |
| syntaxes | syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage` |
| languageId | identifies the language for a document - see [LSP specifications](https://microsoft.github.io/language-server-protocol/specifications/specification-3-15/#textDocumentItem) |
| languages | group `scope`, `syntax` and `languageId` together for servers that support more than one language |
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

Any global language server settings can be overridden per project by adding an LSP settings block to your `.sublime-project` file:

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


## Language servers<a name="language-servers"></a>

The following list can help you to install and configure language servers for use with LSP.
Please remember to put the configurations in a `"clients"` dictionary in your `LSP.sublime-settings` file, as shown in the example above.
If you use or would like to use language servers that are not in this list, please create issues or pull requests, so we can add support for more languages.

### Bash<a name="bash"></a>

1. Install the [Bash Language Server](https://github.com/mads-hartmann/bash-language-server):

        npm i -g bash-language-server

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `bashls`.

### C/C++

See the dedicated <a href="cplusplus"/>C/C++ guide</a> for using ccls, cquery or clangd.

### C&#35;<a name="csharp"></a>

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
  "scopes": ["source.cs"],
  "syntaxes": ["Packages/C#/C#.sublime-syntax"]
}
```

### Clojure<a name="clojure"></a>

1. Download [clojure-lsp](https://github.com/snoe/clojure-lsp).
2. Add to LSP settings' clients:

```js
"clojure-lsp": {
  "command": ["java", "-jar", "/PATH/TO/clojure-lsp"],
  "enabled": true,
  "initializationOptions": {},
  "languageId": "clojure",
  "scopes": ["source.clojure"],
  "syntaxes": ["Packages/Clojure/Clojure.sublime-syntax"]
}
```

clojure-lsp has a [rich set of initializationOptions](https://github.com/snoe/clojure-lsp#initializationoptions).

### CSS<a name="css"></a>

1. Install the CSS language server from VS Code:

        npm install -g vscode-css-languageserver-bin

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `vscode-css`.

### D<a name="d"></a>

1. Install the [D Language Server](https://github.com/d-language-server/dls):

        dub fetch dls
        dub run dls:bootstrap

2. Add to LSP settings' clients:

```json
"dls": {
  "command": ["<PATH TO DLS EXECUTABLE>"],
  "enabled": true,
  "languageId": "d",
  "scopes": ["source.d"],
  "syntaxes": ["Packages/D/D.sublime-syntax"]
}
```

### Dart<a name="dart"></a>

1. Install the [Dartlight](https://packagecontrol.io/packages/Dartlight) package from Package Control for syntax highlighting.
2. Install the [Dart SDK](https://dart.dev/get-dart) and locate path to `analysis_server.dart.snapshot` in the "snapshots/bin" directory.
3. Add to LSP settings' clients (adjust the path if necessary):

```json
"dart": {
  "command": ["dart", "/usr/local/opt/dart/libexec/bin/snapshots/analysis_server.dart.snapshot", "--lsp"],
  "enabled": true,
  "languageId": "dart",
  "scopes": ["source.dart"],
  "syntaxes": ["Packages/Dartlight/Dart.tmLanguage"]
}
```

> **Note**: The older [natebosch/dart_language_server](https://github.com/natebosch/dart_language_server) is now deprecated.

### Dockerfile<a name="dockerfile"></a>

1. Install the [Dockerfile Syntax Highlighting](https://packagecontrol.io/packages/Dockerfile%20Syntax%20Highlighting) package from Package Control for syntax highlighting.
2. Install the [Dockerfile Language Server](https://github.com/rcjsuen/dockerfile-language-server-nodejs):

        npm install -g dockerfile-language-server-nodejs

3. Add to LSP settings' clients:

```js
"docker-langserver": {
  "command": ["docker-langserver", "--stdio"],
  "enabled": true,
  "languageId": "dockerfile",
  "scopes": ["source.dockerfile"],
  "settings": {
    "docker": {
      "languageserver": {
        "diagnostics": {
          // string values must be equal to "ignore", "warning", or "error"
          "deprecatedMaintainer": "warning",
          "directiveCasing": "warning",
          "emptyContinuationLine": "warning",
          "instructionCasing": "warning",
          "instructionCmdMultiple": "warning",
          "instructionEntrypointMultiple": "warning",
          "instructionHealthcheckMultiple": "warning",
          "instructionJSONInSingleQuotes": "warning"
        }
      }
    }
  },
  "syntaxes": ["Packages/Dockerfile Syntax Highlighting/Syntaxes/Dockerfile.sublime-syntax"]
}
```

### Elixir<a name="elixir"></a>

1. Install the [Elixir](https://packagecontrol.io/packages/Elixir) package from Package Control for syntax highlighting.
2. Download the prebuilt binaries or compile [elixir-ls](https://github.com/elixir-lsp/elixir-ls).
   This will get you a folder containing `language_server.sh` among other things.
3. Add to LSP settings' clients (adjust the path if necessary):

```json
"elixir-ls": {
  "command": ["/home/someUser/somePlace/elixir-ls/release/language_server.sh"],
  "enabled": true,
  "languageId": "elixir",
  "scopes": ["source.elixir"],
  "syntaxes": ["Packages/Elixir/Syntaxes/Elixir.tmLanguage"]
}
```

### Elm<a name="elm"></a>

1. Install the [Elm Syntax Highlighting](https://packagecontrol.io/packages/Elm%20Syntax%20Highlighting) package from Package Control for syntax highlighting.
2. See instructions for installing the [elm-language-server](https://github.com/elm-tooling/elm-language-server).
3. Add to LSP settings' clients:

```json
"elm": {
  "command": ["elm-language-server", "--stdio"],
  "enabled": true,
  "initializationOptions": {
    "elmAnalyseTrigger": "change"
  },
  "languageId": "elm",
  "scopes": ["source.elm"],
  "syntaxes": ["Packages/Elm Syntax Highlighting/src/elm.sublime-syntax"]
}
```

### Erlang<a name="erlang"></a>

1. See instructions for installing the [Erlang Language Server](https://github.com/erlang-ls/erlang_ls).
2. Add to LSP settings' clients:

```json
"erlang-ls": {
  "command"   : [ "/path/to/my/erlang_ls", "--transport", "stdio" ],
  "enabled"   : true,
  "languageId": "erlang",
  "scopes"    : [ "source.erlang" ],
  "syntaxes"  : ["Packages/Erlang/Erlang.sublime-syntax"]
}
```

> **Note**: Sometimes Erlang LS might take a little time to initialize. The default is 3 seconds so it is a good idea to increase the value for `"initialize_timeout"` in the LSP settings' clients:

        "initialize_timeout": 30


### Flow (JavaScript)<a name="flow"></a>

Official part of [flow-bin](https://github.com/facebook/flow):

```sh
npm install -g flow-bin
```

Older [flow-language-server](https://github.com/flowtype/flow-language-server):

```sh
npm install -g flow-language-server
```

### Fortran<a name="fortran"></a>

1. Install the [Fortran](https://packagecontrol.io/packages/Fortran) package from Package Control for syntax highlighting.
2. Install the [Fortran Language Server](https://github.com/hansec/fortran-language-server) (requires Python):

        pip install fortran-language-server

3. Add to LSP settings' clients:

```json
"fortls": {
  "command": ["fortls"],
  "enabled": true,
  "languageId": "fortran",
  "scopes": [
    "source.modern-fortran",
    "source.fixedform-fortran"
  ],
  "syntaxes": [
    "Packages/Fortran/grammars/FortranModern.sublime-syntax",
    "Packages/Fortran/grammars/FortranFixedForm.sublime-syntax"
  ]
}
```

> **Note**: See the [Language server settings](https://github.com/hansec/fortran-language-server#language-server-settings)
  documentation for a detailed description of available configuration options, for example
  `"command": ["fortls", "--lowercase_intrinsics"]` to use lowercase for autocomplete suggestions.

### Go<a name="go"></a>

#### Gopls

1. Install [gopls](https://github.com/golang/tools/tree/master/gopls), the official language server for the Go language:

        go get golang.org/x/tools/gopls@latest

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `gopls`.

> **Note**: See the [User guide](https://github.com/golang/tools/blob/master/gopls/doc/user.md#user-guide) for detailed installation instructions and configurations.

#### Sourcegraph's go-langserver

1. Install Sourcegraph's [Go Language Server](https://github.com/sourcegraph/go-langserver):

        go get github.com/sourcegraph/go-langserver

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `golsp`.

> **Note**: Work on this language server has been deprioritized in favor of the gopls language server mentioned above.

### Haskell

1. Install [ghcide](https://github.com/digital-asset/ghcide).
2. Add to LSP settings' clients:

```js
"ghcide": {
  "enabled": true,
  "languageId": "haskell",
  "command": ["ghcide", "--lsp"],
  "scopes": ["source.haskell"],
  "syntaxes": ["Packages/Haskell/Haskell.sublime-syntax"]
}
```

### Java<a name="java"></a>

#### Eclipse JDT Language Server

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
  "languageId": "java",
  "scopes": ["source.java"],
  "syntaxes": ["Packages/Java/Java.sublime-syntax"]
}
```

#### IntelliJ

Requires IntelliJ to be running.

```js
"intellij": {
  "command": [],
  "languageId": "java",
  "scopes": ["source.java"],
  "syntaxes": ["Packages/Java/Java.sublime-syntax"],
  "tcp_port": 8080 // default port
}
```

### JavaScript/TypeScript<a name="typescript"></a>

Different servers wrapping Microsoft's TypeScript services, most support plain JavaScript:

Theia's [typescript-language-server](https://github.com/theia-ide/typescript-language-server):

```sh
npm install -g typescript-language-server
```

My own [tomv564/lsp-tsserver](https://github.com/tomv564/lsp-tsserver):

```sh
npm install -g lsp-tsserver
```

Sourcegraph's [javascript-typescript-langserver](https://github.com/sourcegraph/javascript-typescript-langserver):

```sh
npm install -g javascript-typescript-langserver
```

### Julia<a name="julia"></a>

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
  "scopes": ["source.julia"],
  "settings": {
    // Default values from VS Code:
    "julia": {
      "format": {
        "calls": true,        // Format function calls
        "comments": true,     // Format comments
        "curly": true,        // Format braces
        "docs": true,         // Format inline documentation
        "indent": 4,          // Indent size for formatting
        "indents": true,      // Format file indents
        "iterOps": true,      // Format loop iterators
        "kw": true,           // Remove spaces around = in function keywords
        "lineends": false,    // [undocumented]
        "ops": true,          // Format whitespace around operators
        "tuples": true        // Format tuples
      },
      "lint": {
        "call": false,        // Check calls against existing methods (experimental)
        "constif": true,      // Check for constant conditionals of if statements
        "datadecl": false,    // [undocumented]
        "iter": true,         // Check iterator syntax of loops
        "lazy": true,         // Check for deterministic lazy boolean operators
        "modname": true,      // Check for invalid submodule names
        "nothingcomp": false, // [undocumented]
        "pirates": true,      // Check for type piracy
        "run": true,          // run the linter on active files
        "typeparam": true     // Check for unused DataType parameters
      }
    }
  },
  "syntaxes": ["Packages/Julia/Julia.sublime-syntax"]
}
```

<!-- Alternatively, install the [LSP-julia](https://github.com/randy3k/LSP-julia) package for Sublime Text. -->
<!-- (Currently doesn't work with newest release of Julia's LanguageServer) -->

### Kotlin<a name="kotlin"></a>

1. Install the [Kotlin](https://packagecontrol.io/packages/Kotlin) package from Package Control for syntax highlighting.
2. Install the [Kotlin Language Server](https://github.com/fwcd/KotlinLanguageServer) (requires [building](https://github.com/fwcd/KotlinLanguageServer/blob/master/BUILDING.md) first).
3. Add to LSP settings' clients:

```js
"kotlinls": {
  "command": ["PATH/TO/KotlinLanguageServer/build/install/kotlin-language-server/bin/kotlin-language-server.bat"],
  "enabled": true,
  "languageId": "kotlin",
  "scopes": ["source.Kotlin"],
  "settings": {
    "kotlin": {
      // put your server settings here
    }
  },
  "syntaxes": ["Packages/kotlin/Kotlin.tmLanguage"]
}
```

### LaTeX<a name="latex"></a>

1. Download a [precompiled binary](https://github.com/latex-lsp/texlab/releases) (Windows/Linux/macOS) of the [TexLab](https://texlab.netlify.com/) language server.
2. Add to LSP settings' clients:

```json
"texlab": {
  "command": ["PATH/TO/texlab"],
  "enabled": true,
  "languages": [{
    "languageId": "latex",
    "scopes": ["text.tex.latex"],
    "syntaxes": ["Packages/LaTeX/LaTeX.sublime-syntax"]
  }, {
    "languageId": "bibtex",
    "scopes": ["text.bibtex"],
    "syntaxes": ["Packages/LaTeX/Bibtex.sublime-syntax"]
  }]
}
```

> **Note**: To enable code completions while typing, ensure to have `text.tex.latex` (for LaTeX files) and/or `text.bibtex`
  (for BibTeX files) included in the `auto_complete_selector` setting in your `Preferences.sublime-settings` file.
  For further requirements see the [TexLab Docs](https://texlab.netlify.com/docs#requirements).

### Lisp<a name="lisp"></a>

1. Install [cc-lsp](https://github.com/cxxxr/cl-lsp) using Roswell.
2. Add to LSP settings' clients:

```json
"cc-lsp": {
  "command": ["cl-lsp", "stdio"],
  "enabled": true,
  "languageId": "lisp",
  "scopes": ["source.lisp"],
  "syntaxes": ["Packages/Lisp/Lisp.sublime-syntax"]
}
```

### Lua<a name="lua"></a>

1. Download the [VS Code extension](https://marketplace.visualstudio.com/items?itemName=sumneko.lua).
2. Add to LSP settings' clients:

```json
"lua-ls": {
  "command": [
    "PATH/TO/sumneko.lua-#.#.#/extension/server/bin/lua-language-server",
    "-E", "PATH/TO/sumneko.lua-#.#.#/extension/server/main.lua"
  ],
  "enabled": true,
  "languageId": "lua",
  "scopes": ["source.lua"],
  "syntaxes": ["Packages/Lua/Lua.sublime-syntax"]
}
```

Alternatively you can use the less maintained [lua-lsp](https://github.com/Alloyed/lua-lsp).

### OCaml/Reason<a name="reason"></a>

1. Install the [Reason](https://packagecontrol.io/packages/Reason) package from Package Control for syntax highlighting.
2. Install the [Reason Language Server](https://github.com/jaredly/reason-language-server#sublime-text).
3. Add to LSP settings' clients:

```json
"reason": {
  "command": ["PATH/TO/reason-language-server.exe"],
  "enabled": true,
  "languageId": "reason",
  "scopes": ["source.ocaml", "source.reason"],
  "syntaxes": [
    "Packages/Ocaml/OCaml.sublime-syntax",
    "Packages/Reason/Reason.tmLanguage",
    "Packages/sublime-reason/Reason.tmLanguage"
  ]
}
```

### PHP<a name="php"></a>

#### Intelephense

```sh
npm i intelephense -g
```

See [bmewburn/intelephense-docs](https://github.com/bmewburn/intelephense-docs)


#### PHP Language server

See: [felixfbecker/php-language-server](https://github.com/felixfbecker/php-language-server)

Global installation:

1. modify `~/.composer/composer.json` to set `"minimum-stability": "dev"` and `"prefer-stable": true`
2. run `composer global require felixfbecker/language-server`
3. run `composer run-script --working-dir=~/.composer/vendor/felixfbecker/language-server parse-stubs`

### Polymer<a name="polymer"></a>

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

### PowerShell<a name="powershell"></a>

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
  "languageId": "powershell",
  "scopes": ["source.powershell"],
  "syntaxes": ["Packages/PowerShell/Support/PowershellSyntax.tmLanguage"]
}
```

> **Note**: For more details see this [issue](https://github.com/PowerShell/PowerShellEditorServices/issues/1057).

### Python<a name="python"></a>

There are at least two language servers, use either one.

#### Palantir's Python Language Server

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
    "pyls": {
      "env":
      {
        // Making Sublime's own libs available to the linters.
        // "PYTHONPATH": "/Applications/Sublime Text.app/Contents/MacOS/Lib/python33",
      },
      // Configuration is computed first from user configuration (in home directory),
      // overridden by configuration passed in by the language client,
      // and then overridden by configuration discovered in the workspace.
      "configurationSources": [
        "pycodestyle",  // discovered in ~/.config/pycodestyle, setup.cfg, tox.ini and pycodestyle.cfg
        // "flake8",  // discovered in ~/.config/flake8, setup.cfg, tox.ini and flake8.cfg
      ],
      "plugins": {
        "jedi": {
          "extra_paths": [
            // The directory where the pip installation package is located
          ],
        },
        "jedi_completion": {
          "fuzzy": true,  // Enable fuzzy when requesting autocomplete
        },
        "pycodestyle": {
          "enabled": true,
          "exclude": [  // Exclude files or directories which match these patterns
          ],
          "ignore": [  // Ignore errors and warnings
            // "E501",  // Line too long (82 &gt; 79 characters)
          ],
          // "maxLineLength": 80,  // Set maximum allowed line length
        },
        "pydocstyle": {"enabled": false},
        "pyflakes": {"enabled": true},
        "pylint": {"enabled": false},
        "yapf": {"enabled": true},
        // pyls' 3rd Party Plugins, Mypy type checking for Python 3, Must be installed via pip before enabling
        "pyls_mypy": {  // Install with: pip install pyls-mypy
          "enabled": false,
          "live_mode": true,
        },
      }
    }
  }
},
```

See pylint documentation: [github:palantir/python-language-server](https://github.com/palantir/python-language-server)

Description of all built-in settings: https://github.com/palantir/python-language-server/blob/develop/vscode-client/package.json

#### Microsoft's Python Language Server

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

### R<a name="r"></a>

1. Install the `languageserver` package from CRAN (see the [CRAN mirrored package on GitHub](https://github.com/cran/languageserver) for more information and up-to-date installation instructions):

        install.packages("languageserver")

2. Run "LSP: Enable Language Server Globally" from the Command Palette and choose `rlang`.

### Ruby/Ruby on Rails<a name="ruby"></a>

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

### Rust<a name="rust"></a>

Goes well with the [Rust Enhanced package](https://github.com/rust-lang/rust-enhanced) which uses the RLS server: [github:rust-lang-nursery/rls](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.

Alternatively, a newer [rust-analyzer](https://github.com/rust-analyzer/rust-analyzer) server is under development, also supported by LSP.

### Scala<a name="scala"></a>

* **[Metals](https://scalameta.org/metals/)**: Most complete LSP server for Scala, see [LSP-metals](https://packagecontrol.io/packages/LSP-metals) for installation.
* **[SBT](https://www.scala-sbt.org/)**: Version 1.x supports limited and *unmaintained* language server functionalities, setup is described [here](http://eed3si9n.com/sbt-server-with-sublime-text3).
* **[Dotty](http://dotty.epfl.ch/)**: The future Scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html).
It is developed against VS Code, so ignore instructions related to VS Code.
Get the project compiling with dotty first (see [instructions](https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)).
At this point LSP should complain in the logs
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`
Then run `sbt configureIDE` to create the `.dotty-ide.json` file
Then the LSP plugin should launch as configured in `LSP.sublime-settings` using coursier.

### Swift<a name="swift"></a>

1. Install the [Swift](https://packagecontrol.io/packages/Swift) package from Package Control for syntax highlighting.
2. Install Xcode 11.4 or later and ensure that `xcrun -find sourcekit-lsp` returns the path to sourcekit-lsp.

### Terraform<a name="terraform"></a>

1. Download [terraform-lsp](https://github.com/juliosueiras/terraform-lsp/releases) binary and make it available in your PATH.
2. Add to LSP settings' clients:

```json
"terraform": {
  "command": ["terraform-lsp"],
  "enabled": true,
  "languageId": "terraform",
  "scopes": ["source.terraform"],
  "syntaxes":  ["Packages/Terraform/Terraform.sublime-syntax"]
}
```

### Vue (Javascript)<a name="vue"></a>

See: [LSP-vue](https://packagecontrol.io/packages/LSP-vue)

Be sure to install [Vue Syntax Highlight](https://packagecontrol.io/packages/Vue%20Syntax%20Highlight) from Package Control.

### XML<a name="xml"></a>

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
  "scopes": ["text.xml"],
  "syntaxes": ["Packages/XML/XML.sublime-syntax"]
}
```

> **Note**: Discussed in [this issue](https://github.com/sublimelsp/LSP/issues/578).
