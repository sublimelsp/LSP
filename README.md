# LSP

[![License](https://img.shields.io/github/license/sublimelsp/LSP)](https://github.com/sublimelsp/LSP/blob/master/LICENSE)
[![GitHub release](https://img.shields.io/github/release/sublimelsp/LSP.svg)](https://github.com/sublimelsp/LSP/releases)
[![Github Action](https://github.com/sublimelsp/LSP/workflows/main/badge.svg?branch=master)](https://github.com/sublimelsp/LSP/actions)
[![Coverage Status](https://codecov.io/github/sublimelsp/LSP/branch/master/graph/badge.svg)](https://codecov.io/gh/sublimelsp/LSP/tree/master/plugin)
[![Documentation](https://readthedocs.org/projects/lsp/badge/)](https://lsp.readthedocs.io/en/latest/)
[![SublimeHQ Discord](https://img.shields.io/discord/280102180189634562?label=SublimeHQ%20Discord&logo=discord)](#chat)

Language Server Protocol support for Sublime Text 3 that gives you IDE [features](https://lsp.readthedocs.io/en/latest/features/).

![diagnostics screen-shot](docs/images/showcase.gif "TypeScript Server Example")

## Installation

### Stable Version

Open the command palette and run `Package Control: Install Package`, then select `LSP`.

### Development Version

Clone this repository into your Packages directory. Open the command palette and run `Package Control: Satisfy Dependencies`.

## Getting started

Follow the installation steps for a <a href="#available_languages">language server</a>.

Enable the server by running `LSP: Enable Language Server` from the command palette.

Open a document supported by the language server. LSP should report the language server starting in the status bar.

Documentation is available at [LSP.readthedocs.io](https://LSP.readthedocs.io).

## Available Languages<a name="available_languages"></a>

* [Bash](https://lsp.readthedocs.io/en/latest/#bash)
* [C/C++](https://lsp.readthedocs.io/en/latest/cplusplus/)
* [C#](https://lsp.readthedocs.io/en/latest/#csharp)
* [CSS/LESS/SASS (SCSS only)](https://lsp.readthedocs.io/en/latest/#css)
* [D](https://lsp.readthedocs.io/en/latest/#d)
* [Dart](https://lsp.readthedocs.io/en/latest/#dart)
* [Dockerfile](https://lsp.readthedocs.io/en/latest/#dockerfile)
* [Elixir](https://lsp.readthedocs.io/en/latest/#elixir)
* [Elm](https://lsp.readthedocs.io/en/latest/#elm)
* [Erlang](https://lsp.readthedocs.io/en/latest/#erlang)
* [Flow (JavaScript)](https://lsp.readthedocs.io/en/latest/#flow)
* [Fortran](https://lsp.readthedocs.io/en/latest/#fortran)
* [Go](https://lsp.readthedocs.io/en/latest/#go)
* [HTML](https://lsp.readthedocs.io/en/latest/#html)
* [Java](https://lsp.readthedocs.io/en/latest/#java)
* [JavaScript/TypeScript](https://lsp.readthedocs.io/en/latest/#typescript)
* [JSON](https://lsp.readthedocs.io/en/latest/#json)
* [Julia](https://lsp.readthedocs.io/en/latest/#julia)
* [Kotlin](https://lsp.readthedocs.io/en/latest/#kotlin)
* [LaTeX](https://lsp.readthedocs.io/en/latest/#latex)
* [Lisp](https://lsp.readthedocs.io/en/latest/#lisp)
* [Lua](https://lsp.readthedocs.io/en/latest/#lua)
* [PHP](https://lsp.readthedocs.io/en/latest/#php)
* [Polymer](https://lsp.readthedocs.io/en/latest/#polymer)
* [PowerShell](https://lsp.readthedocs.io/en/latest/#powershell)
* [Python](https://lsp.readthedocs.io/en/latest/#python)
* [R](https://lsp.readthedocs.io/en/latest/#r)
* [Reason](https://lsp.readthedocs.io/en/latest/#reason)
* [Ruby](https://lsp.readthedocs.io/en/latest/#ruby)
* [Rust](https://lsp.readthedocs.io/en/latest/#rust)
* [Scala](https://lsp.readthedocs.io/en/latest/#scala)
* [Swift](https://lsp.readthedocs.io/en/latest/#swift)
* [Terraform](https://lsp.readthedocs.io/en/latest/#terraform)
* [Vue (JavaScript)](https://lsp.readthedocs.io/en/latest/#vue)
* [XML](https://lsp.readthedocs.io/en/latest/#xml)

See [Language Server Protocol](https://microsoft.github.io/language-server-protocol/implementors/servers/) for more available implementations. Please create issues/pull requests so we can get support for more languages.

## Customisation of the popups

LSP uses [mdpopups](https://github.com/facelessuser/sublime-markdown-popups) to display the popup. You can override its style by creating a `Packages/User/mdpopups.css` file. See the [mdpopups documentation](http://facelessuser.github.io/sublime-markdown-popups/) for more details.

## Getting help

If you have any problems, see the [troubleshooting](https://lsp.readthedocs.io/en/latest/troubleshooting/) guide for tips and known limitations. If the documentation cannot solve your problem, you can look for help in:
<a name="chat"></a>

* The [#lsp](https://discordapp.com/channels/280102180189634562/645268178397560865) channel (join the [SublimeHQ Discord](https://discord.gg/TZ5WN8t) first!)
* By [searching or creating a new issue](https://github.com/sublimelsp/LSP/issues)
* Search the [old Gitter chat](https://gitter.im/tomv564) (for live chat join Discord instead)

## Capabilities

### Text Document Capabilities

- ✅ synchronization
  - ✅ didOpen
  - ✅ didChange
    - ✅ Full text sync
    - ❌ Incremental text sync
  - ✅ willSave
  - ✅ willSaveWaitUntil
  - ✅ didSave
    - ✅ Include text
  - ✅ didClose
- ✅ completion
  - ❌ documentation field is ignored
  - ❌ completionItem/resolve is not perfect
  - ❌ various manual workarounds for textEdit
- ✅ hover
- ✅ signatureHelp
- ✅ declaration
  - ✅ link support
- ✅ definition
  - ✅ link support
- ✅ typeDefinition
  - ✅ link support
- ✅ implementation
  - ✅ link support
- ✅ references
- ✅ documentHighlight
- ✅ documentSymbol
- ✅ codeAction
- ❌ codeLens
- ❌ documentLink
- ✅ colorProvider
- ✅ formatting
- ✅ rangeFormatting
- ❌ onTypeFormatting
- ✅ rename
- ✅ publishDiagnostics
- ❌ foldingRange

### Workspace Capabilities

- ✅ applyEdit
- ✅ workspaceEdit
  - ✅ documentChanges
  - ❌ resourceOperations
  - ❌ failureHandling
- ✅ didChangeConfiguration
- ❌ didChangeWatchedFiles
- ✅ symbol
- ✅ executeCommand

### Window Capabilities

- ✅ workDoneProgress
  - ✅ create
  - ❌ cancel
