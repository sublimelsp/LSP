:information_source: Note that the `st4000-exploration` branch corresponds to the ST4 version of LSP. If you are looking for information on ST3 version, switch to [master branch](/LSP/tree/master).

# LSP

[![License](https://img.shields.io/github/license/sublimelsp/LSP)](https://github.com/sublimelsp/LSP/blob/master/LICENSE)
[![GitHub release](https://img.shields.io/github/release/sublimelsp/LSP.svg)](https://github.com/sublimelsp/LSP/releases)
[![Github Action](https://github.com/sublimelsp/LSP/workflows/main/badge.svg?branch=master)](https://github.com/sublimelsp/LSP/actions)
[![Coverage Status](https://codecov.io/github/sublimelsp/LSP/branch/master/graph/badge.svg)](https://codecov.io/gh/sublimelsp/LSP/tree/master/plugin)
[![SublimeHQ Discord](https://img.shields.io/discord/280102180189634562?label=SublimeHQ%20Discord&logo=discord)](#chat)

Language Server Protocol support for Sublime Text that gives you IDE [features](https://sublimelsp.github.io/LSP/features/).

![diagnostics screen-shot](docs/src/images/showcase.gif "TypeScript Server Example")

## Installation

### Stable Version

Open the command palette and run `Package Control: Install Package`, then select `LSP`.

### Development Version

Clone this repository into your Packages directory. Open the command palette and run `Package Control: Satisfy Dependencies`.

## Getting started

Follow the installation steps for a [specific language server](https://sublimelsp.github.io/LSP/language_servers/).

Open a document supported by the language server. LSP should report the language server starting in the status bar.

See more information in the [documentation](https://sublimelsp.github.io/LSP/) :open_book:.

## Customisation of the popups

LSP uses [mdpopups](https://github.com/facelessuser/sublime-markdown-popups) to display the popup. You can override its style by creating a `Packages/User/mdpopups.css` file. See the [mdpopups documentation](http://facelessuser.github.io/sublime-markdown-popups/) for more details.

## Getting help

If you have any problems, see the [troubleshooting](https://sublimelsp.github.io/LSP/troubleshooting/) guide for tips and known limitations. If the documentation cannot solve your problem, you can look for help in:
<a name="chat"></a>

* The [#lsp](https://discordapp.com/channels/280102180189634562/645268178397560865) channel (join the [SublimeHQ Discord](https://discord.gg/TZ5WN8t) first!)
* By [searching or creating a new issue](https://github.com/sublimelsp/LSP/issues)

## LSP specification implementation status

### Text Document Capabilities

- ✅ synchronization
  - ✅ didOpen
  - ✅ didChange
    - ✅ Full text sync
    - ✅ Incremental text sync
  - ✅ willSave
  - ✅ willSaveWaitUntil
  - ✅ didSave
    - ✅ Include text
  - ✅ didClose
- ✅ completion
  - ✅ insertText
  - ✅ textEdit
  - ❌ prefix filter textEdit
  - ✅ documentation (both static and from completionItem/resolve)
  - ✅ Run command after inserting completion
  - ❌ insertReplaceEdit variant
- ✅ hover
- ✅ signatureHelp
  - ❌ context
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
  - ✅ resolve
- ✅ codeLens (*only when backed by a helper package*)
- ❌ documentLink
- ✅ colorProvider
  - ❌ color picker [#1291](https://github.com/sublimelsp/LSP/issues/1291)
- ✅ formatting
- ✅ rangeFormatting
- ❌ onTypeFormatting
- ✅ rename
- ✅ publishDiagnostics
- ❌ foldingRange [sublimehq/sublime_text#3389](https://github.com/sublimehq/sublime_text/issues/3389)
- ✅ selectionRange
- ❌ semanticHighlighting [#887](https://github.com/sublimelsp/LSP/issues/887), [sublimehq/sublime_text#817](https://github.com/sublimehq/sublime_text/issues/817)
- ❌ callHierarchy

### Workspace Capabilities

- ✅ applyEdit
- ✅ workspaceEdit
  - ✅ documentChanges
  - ❌ resourceOperations
  - ❌ failureHandling
- ✅ didChangeConfiguration
- ❌ didChangeWatchedFiles [#892](https://github.com/sublimelsp/LSP/issues/892), [sublimehq/sublime_text#2669](https://github.com/sublimehq/sublime_text/issues/2669)
- ✅ symbol
- ✅ executeCommand

### Window Capabilities

- ✅ workDoneProgress
  - ✅ create
  - ❌ cancel
- ✅ showMessage request additionalPropertiesSupport

### Dynamic Registration

✅ Fully implemented
