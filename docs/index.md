

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

* `command` - specify a full paths, add arguments (if not specified then tcp_port must be specified)
* `tcp_port` - if not specified then stdin/out are used else sets the tcpport to connect to (if no command is specified then it is assumed that some process is listing on this port)
* `scopes` - add language flavours, eg. `source.js`, `source.jsx`.
* `syntaxes` - syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage`
* `languageId` - used both by the language servers and to select a syntax highlighter for sublime popups.
* `languages` - group scope, syntax and languageId together for servers that support more than one language
* `enabled` - enables a language server (default is disabled)
* `settings` - per-project settings (equivalent to VS Code's Workspace Settings)
* `env` - dict of environment variables to be injected into the language server's process (eg. PYTHONPATH)
* `initializationOptions` - options to send to the server at startup (rarely used)

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

