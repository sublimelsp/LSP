

## Getting started

1. Install a language server from the list below, ensuring it can be started from the command line (is in your PATH)

2. Run "LSP: Enable Language Server" from Sublime's Command Palette to allow the server to start.

3. Open a document in your language - if the server starts its name will be in the left side of the status bar.


### Javascript/Typescript<a name="jsts"></a>

Different servers wrapping microsoft's typescript services, most support plain javascript:

Theia's [typescript-language-server](https://github.com/theia-ide/typescript-language-server): `npm install -g typescript-language-server`

My own [tomv564/lsp-tsserver](https://github.com/tomv564/lsp-tsserver): `npm install -g lsp-tsserver`

Sourcegraph's [javascript-typescript-langserver](https://github.com/sourcegraph/javascript-typescript-langserver): `npm install -g javascript-typescript-langserver`


### Flow (Javascript)<a name="flow"></a>

Official part of [flow-bin](https://github.com/facebook/flow): `npm install -g flow-bin`

Older flow-language-server: [github](https://github.com/flowtype/flow-language-server): `npm install -g flow-bin`

### Vue (Javascript)<a name="vue"></a>

See: [LSP-vue](https://packagecontrol.io/packages/LSP-vue)

Be sure to install [Vue Syntax Highlight](https://packagecontrol.io/packages/Vue%20Syntax%20Highlight) from Package Control.

### Python<a name="python"></a>

There are at least two language servers, use either one.

#### Palantir Python Language Server

```sh
pip install python-language-server
```

Make sure you can run `pyls` in your terminal. If you've installed it into a virtualenv, you might need to override the path to `pyls` in global LSP settings (Package Settings -> LSP -> Settings):


```js
{
    "clients": {
        "pyls": {
            "enabled": true, // if you want to enable Python Language Server globally
            "command": [
                // example path, adjust it for your use case
                "/Users/mike/.virtualenvs/pyls-virtual-env/bin/pyls"
            ]
        }
    }
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

See: [github:palantir/python-language-server](https://github.com/palantir/python-language-server)

#### Microsoft Python Language Server

Alternatively, use Microsoft Python Language Server (using .NET Core runtime). [Instructions](https://github.com/Microsoft/python-language-server/blob/master/Using_in_sublime_text.md).

### PHP<a name="php"></a>

#### Intelephense

`npm i intelephense -g`

See [bmewburn/intelephense-docs](https://github.com/bmewburn/intelephense-docs)


#### PHP Language server

See: [github:felixfbecker/php-language-server](https://github.com/felixfbecker/php-language-server)

Global installation:

1. modify `~/.composer/composer.json` to set `"minimum-stability": "dev"` and `"prefer-stable": true`
2. run `composer global require felixfbecker/language-server`
3. run `composer run-script --working-dir=~/.composer/vendor/felixfbecker/language-server parse-stubs`


### Ruby / Ruby on Rails<a name="ruby"></a>

Requires the solargraph gem:

    gem install solargraph

See [github.com:castwide/solargraph](https://github.com/castwide/solargraph) for up-to-date installation instructions.


### Rust<a name="rust"></a>

Goes well with the [Rust Enhanced package](https://github.com/rust-lang/rust-enhanced) which uses the RLS server: [github:rust-lang-nursery/rls](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.

Alternatively, a newer [rust-analyzer](https://github.com/rust-analyzer/rust-analyzer) server is under development, also supported by LSP.


### R<a name="r"></a>

Requires installation of the `languageserver` package from CRAN:

`install.packages("languageserver")`

See the [CRAN mirrored package on GitHub](https://github.com/cran/languageserver) for more information and up-to-date installation instructions.

Once this has been done the language server need only be enabled to work, as it is included amongst the default clients.


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


### C#

Omnisharp [omnisharp-roslyn](https://github.com/OmniSharp/omnisharp-roslyn)

Download or build according to instructions above, then add this client config to your LSP settings under clients:

```jsonc
"omnisharp": {
  "command":
  [
    "/home/tb/prebuilt/omnisharp/OmniSharp.exe", // or eg. /usr/local/opt/omnisharp/run
    "-lsp"
  ],
  "enabled": true,
  "languageId": "csharp",
  "syntaxes": ["Packages/C#/C#.sublime-syntax"],
  "scopes":
  [
    "source.cs"
  ]
}
```

### D<a name="d"></a>

See instructions for [d-language-server](https://github.com/d-language-server/dls).

```
dub fetch dls
dub run dls:bootstrap
```

Add to LSP settings' clients:

```json

"dls": {
    "command": ["<PATH TO DLS EXECUTABLE>"],
    "enabled": true,
    "languageId": "d",
    "scopes": ["source.d"],
    "syntaxes": ["Packages/D/D.sublime-syntax"]
}
```

### Elm<a name="elm"></a>

See instructions for installing the [elm-language-server](https://github.com/elm-tooling/elm-language-server).
Install [Elm Syntax Higlighting](https://packagecontrol.io/packages/Elm%20Syntax%20Highlighting) from Package Control for syntax highlighting.

Add to LSP settings' clients:

```json
"elm": {
    "command": [
        "elm-language-server",
        "--stdio"
    ],
    "enabled": true,
    "languageId": "elm",
    "scopes":
    [
        "source.elm"
    ],
    "syntaxes":
    [
        "Packages/Elm Syntax Highlighting/src/elm.sublime-syntax"
    ],
    "initializationOptions": {
        "elmAnalyseTrigger": "change"
    }
}
```


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

Install the Dart Sublime package and the [Dart SDK](https://dart.dev/get-dart)

Then locate the "snapshots/bin" directory of the SDK, and specify the path to `analysis_server.dart.snapshot` in the LSP user settings under "clients", "dart", then "command".

The older [natebosch/dart_language_server](https://github.com/natebosch/dart_language_server) is now deprecated

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


### Julia<a name="julia">


Install the LanguageServer package from the Julia repl.

Install the [LSP-julia](https://github.com/randy3k/LSP-julia) sublime package from package control.

Or instead of LSP-julia, add the following client configuration:

```json
"julials":
{
  "command": ["bash", "PATH_TO_JULIA_SERVER/LanguageServer/contrib/languageserver.sh"],
  "languageId": "julia",
  "scopes": ["source.julia"],
  "syntaxes": ["Packages/Julia/Julia.sublime-syntax"],
  "settings": {"runlinter": true}
}
```

### Lua<a name="lua">

1. Download the [VSCode extension](https://marketplace.visualstudio.com/items?itemName=sumneko.lua)
2. add these configurations:
```json
"lua-ls":
{
    "command":
    [
        "PATH/TO/sumneko.lua-#.#.#/extension/server/bin/lua-language-server",
        "-E",
        "PATH/TO/sumneko.lua-#.#.#/extension/server/main.lua"
    ],
    "enabled": true,
    "languageId": "lua",
    "scopes":
    [
        "source.lua",
    ],
    "syntaxes":
    [
        "Packages/Lua/Lua.sublime-syntax"
    ]
},
```
alternatively you can use the less maintained [lua-lsp](https://github.com/Alloyed/lua-lsp)


### Lisp<a name="lisp">

1. Install [cc-lsp](https://github.com/cxxxr/cl-lsp) using Roswell
2. Add this configuration to your clients in the LSP settings:
```json
"cc-lsp":
{
    "command":
    [
        "cl-lsp",
        "stdio"
    ],
    "enabled": true,
    "languageId": "lisp",
    "scopes":
    [
        "source.lisp",
    ],
    "syntaxes":
    [
        "Packages/Lisp/Lisp.sublime-syntax"
    ]
}
```

### Bash<a name="bash">

Install the [bash language server](https://github.com/mads-hartmann/bash-language-server)

`npm i -g bash-language-server`

### PowerShell<a name="powershell">

1. Download and extract the [latest release](https://github.com/PowerShell/PowerShellEditorServices/releases) PowerShellEditorServices
2. Install the [powershell plugin](https://packagecontrol.io/packages/PowerShell) for syntax highlighting
3. add these configurations:
```jsonc
"powershell-ls":
{
  "command":
  [
    "PATH/TO/powershell or pwsh",
    "-NoLogo",
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass",  // windows only
    "-Command",
    "PATH/TO/PowerShellEditorServices/PowerShellEditorServices/Start-EditorServices.ps1",
    "-LogPath", "PATH/TO/pses.log",  // the path itself is not relevant
    "-LogLevel", "Normal",
    "-SessionDetailsPath", "PATH/TO/session.json",  // the path itself is not relevant
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
  "scopes":
  [
    "source.powershell"
  ],
  "syntaxes":
  [
    "Packages/PowerShell/Support/PowershellSyntax.tmLanguage"
  ]
}
```
4. make sure powershell help files are up to date by running `Update-Help` in the powershell console (the one you're using in the command)

For more details see this [issue](https://github.com/PowerShell/PowerShellEditorServices/issues/1057)


### Terraform<a name="terraform">

1. Download [terraform-lsp](https://github.com/juliosueiras/terraform-lsp/releases) binary and make it available in PATH
2. add these configurations:
```json
"terraform":
{
  "command":
  [
    "terraform-lsp"
  ],
  "enabled": true,
  "scopes": ["source.terraform"],
  "syntaxes":  ["Packages/Terraform/Terraform.sublime-syntax"],
  "languageId": "terraform"
}
```

### Elixir

1. Download the prebuilt binaries or compile [elixir-ls](https://github.com/elixir-lsp/elixir-ls). This will get you a folder containing `language_server.sh` among other things
2. Download the official [Elixir package](https://packagecontrol.io/packages/Elixir) for syntax definitions
3. Update the elixir-ls configuration to point to your `language_server.sh`

```
    "elixir-ls": {
      "command": ["/home/someUser/somePlace/elixir-ls/release/language_server.sh"],
      "enabled": true,
      "languageId": "elixir",
      "scopes": ["source.elixir"],
      "settings": {
      },
      "syntaxes": [
        "Packages/Elixir/Syntaxes/Elixir.tmLanguage",
      ]
    },
```

### XML

Discussed in [this issue](https://github.com/tomv564/LSP/issues/578)

Download jar from [angelozerr/lsp4xml](https://github.com/angelozerr/lsp4xml/releases)

Add config:

```json
"lsp4xml":
{
    "command":
    [
        "java",

        // false on windows, true on other operating systems
        "-DwatchParentProcess=false",
        // JVM options (not necessary) but the vscode extension uses them by default
        "-noverify",  // bypass class verification
        "-Xmx64M",  // set the maximum heap size
        "-XX:+UseG1GC",  // use the G1 garbage collector
        "-XX:+UseStringDeduplication",  // enable string deduplication optimisation
        "-jar",
        "PATH/TO/org.eclipse.lsp4xml-uber.jar"
    ],
    "enabled": true,
    "languageId": "xml",
    "scopes":
    [
        "text.xml"
    ],
    "syntaxes":
    [
        "Packages/XML/XML.sublime-syntax"
    ]
}

```


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


### Java<a name="java"></a>

1. download and extract eclipse's [jdt-ls](https://download.eclipse.org/jdtls/snapshots/jdt-language-server-latest.tar.gz).
2. add these configurations:
```jsonc
"jdtls":
{
    "command":
    [
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
        "PATH/TO/jdt-language-server-latest/plugins/org.eclipse.equinox.launcher_*.jar"
        "-configuration",
        "PATH/TO/jdt-language-server-latest/config_{win|mac|linux}", // depending on the OS
        "-data",
        "<TEMP_DIR>/${project_base_name}/jdt_ws"
    ],
    "enabled": true,
    "languageId": "java",
    "scopes":
    [
        "source.java"
    ],
    "syntaxes":
    [
        "Packages/Java/Java.sublime-syntax"
    ]
}
```

### LaTeX<a name="latex"></a>

Download a [precompiled binary](https://github.com/latex-lsp/texlab/releases) (Windows/Linux/macOS) of the [TexLab](https://texlab.netlify.com/) Language Server and place it in a directory that is in your `PATH`.

Add to LSP settings' clients:
```json
"texlab": {
  "command": ["texlab"],
  "languages": [{
    "scopes": ["text.tex.latex"],
    "syntaxes": ["Packages/LaTeX/LaTeX.sublime-syntax"],
    "languageId": "latex"
  }, {
    "scopes": ["text.bibtex"],
    "syntaxes": ["Packages/LaTeX/Bibtex.sublime-syntax"],
    "languageId": "bibtex"
  }],
  "enabled": true
}
```

To enable code completions while typing, ensure to have `text.tex.latex` (for LaTeX files) and/or `text.bibtex` (for BibTeX files) included in the `auto_complete_selector` setting in your `Preferences.sublime-settings` file.
For further requirements see the [TexLab Docs](https://texlab.netlify.com/docs#requirements).

### Other<a name="other"></a>

Please create issues / pull requests so we can get support for more languages.

## Server Configuration<a name="client-config"></a>

LSP ships with default configurations for a few language servers.
These configurations need to be enabled before they will start.

If your language server is missing or not configured correctly, you can add/override the below settings under the `"clients"` key in the LSP Settings.

Here is an example for the Javascript/Typescript server:

```json
"jsts": {
  "command": ["lsp-tsserver"],
  "scopes": ["source.ts", "source.tsx"],
  "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"],
  "languageId": "typescript"
}
```

or in multi-language form:

```json
"lsp-tsserver": {
  "command": ["lsp-tsserver"],
  "languages": [{
    "scopes": ["source.js", "source.jsx"],
    "syntaxes": ["Packages/Babel/JavaScript (Babel).sublime-syntax", "Packages/JavaScript/JavaScript.sublime-syntax"],
    "languageId": "javascript"
  }, {
    "scopes": ["source.ts", "source.tsx"],
    "syntaxes": ["Typescript"],
    "languageId": "typescript"
  }
  ]
}
```

Most important:

* `enabled` - enables a language server (default is disabled)

Values that determine if a server should be started and queried for a given document:

* `scopes` - add language flavours, eg. `source.js`, `source.jsx`.
* `syntaxes` - syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage`
* `languageId` - identifies the language for a document - see https://microsoft.github.io/language-server-protocol/specification#textdocumentitem
* `languages` - group scope, syntax and languageId together for servers that support more than one language

Settings used to start and configure a language server:

* `command` - must be on PATH or specify a full path, add arguments (can be empty if starting manually, then TCP transport must be configured)
* `env` - dict of environment variables to be injected into the language server's process (eg. PYTHONPATH)
* `settings` - per-project settings (equivalent to VS Code's Workspace Settings)
* `initializationOptions` - options to send to the server at startup (rarely used)

The default transport is stdio, but TCP is also supported.
The port number can be inserted into the server's arguments by adding a `{port}` placeholder in `command`.

**Server-owned port**

Set `tcp_port` and optionally `tcp_host` if server running on another host.

**Editor-owned port** (servers based on vscode-languageserver-node):

Set `tcp_mode` to "host", leave `tcp_port` unset for automatic port selection.
`tcp_port` can be set if eg. debugging a server. You may want to check out the LSP source and extend the `TCP_CONNECT_TIMEOUT`.

## Per-project overrides

Any global language server settings can be overridden per project by adding an LSP settings block to your `.sublime-project` file.

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
