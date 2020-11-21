# Language Servers

The following list can help you to install and configure language servers for use with LSP.
Please remember to put the configurations in a `"clients"` dictionary in your `LSP.sublime-settings` file, as shown in the example above.
If you use or would like to use language servers that are not in this list, please create issues or pull requests, so we can add support for more languages.

!!! tip
    We recommend installing [LSP-json](https://packagecontrol.io/packages/LSP-json), as it can give settings completions and report errors when inside the `LSP.sublime-settings` file.

## Angular

Follow installation instructions on [LSP-angular](https://github.com/sublimelsp/LSP-angular).

## Bash

Follow installation instructions on [LSP-bash](https://github.com/sublimelsp/LSP-bash).

## C/C++

See the dedicated <a href="/guides/cplusplus"/>C/C++ guide</a> for using ccls or clangd.

## C\#

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-OmniSharp](https://github.com/sublimelsp/LSP-OmniSharp).

## CMake

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-cmake](https://github.com/sublimelsp/LSP-cmake).

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

Follow installation instructions on [LSP-css](https://github.com/sublimelsp/LSP-css).

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

Follow installation instructions on [LSP-Dart](https://github.com/sublimelsp/LSP-Dart).

## Dockerfile

Follow installation instructions on [LSP-dockerfile](https://github.com/sublimelsp/LSP-dockerfile).

## Elixir

Follow installation instructions on [LSP-elixir](https://github.com/sublimelsp/LSP-elixir).

## Elm

Follow installation instructions on [LSP-elm](https://github.com/sublimelsp/LSP-elm).

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

Follow installation instructions on [LSP-eslint](https://github.com/sublimelsp/LSP-eslint).

## Flow

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-flow](https://github.com/sublimelsp/LSP-flow).

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

## JSON

Follow installation instructions on [LSP-json](https://github.com/sublimelsp/LSP-json).

## Julia

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-julia](https://github.com/sublimelsp/LSP-julia).

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

Follow installation instructions on [LSP-TexLab](https://github.com/sublimelsp/LSP-TexLab).

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

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-lua](https://github.com/sublimelsp/LSP-lua).

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

Follow installation instructions on [LSP-intelephense](https://github.com/sublimelsp/LSP-intelephense).

### Serenata

Follow installation instructions on [LSP-serenata](https://github.com/Cloudstek/LSP-serenata).

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

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-PowerShellEditorServices](https://github.com/sublimelsp/LSP-PowerShellEditorServices).

## Python

### Pyls

Follow installation instructions on [LSP-pyls](https://github.com/sublimelsp/LSP-pyls).

### Pyright

Follow installation instructions on [LSP-pyright](https://github.com/sublimelsp/LSP-pyright).

### Anakin

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-anakin](https://github.com/sublimelsp/LSP-anakin).

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

Follow installation instructions on [LSP-metals](https://github.com/scalameta/metals-sublime).

## SonarLint

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-SonarLint](https://github.com/sublimelsp/LSP-SonarLint).

## SourceKit

!!! warning  "Not published on Package Control"
    Follow the steps for [installing not published `LSP-*` plugins]()

Follow installation instructions on [LSP-SourceKit](https://github.com/sublimelsp/LSP-SourceKit).

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

## TypeScript / JavaScript

Follow installation instructions on [LSP-typescript](https://github.com/HuygensING/LSP-typescript).

## Vue

Follow installation instructions on [LSP-vue](https://github.com/sublimelsp/LSP-vue).

## XML

Follow installation instructions on [LSP-lemminx](https://github.com/sublimelsp/LSP-lemminx).

## YAML

Follow installation instructions on [LSP-yaml](https://github.com/sublimelsp/LSP-yaml).
