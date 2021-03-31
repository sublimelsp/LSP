# LSP specification implementation status

## Text Document Capabilities

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

## Workspace Capabilities

- ✅ applyEdit
- ✅ workspaceEdit
    - ✅ documentChanges
    - ❌ resourceOperations
    - ❌ failureHandling
- ✅ didChangeConfiguration
- ❌ didChangeWatchedFiles [#892](https://github.com/sublimelsp/LSP/issues/892), [sublimehq/sublime_text#2669](https://github.com/sublimehq/sublime_text/issues/2669)
- ✅ symbol
- ✅ executeCommand

## Window Capabilities

- ✅ workDoneProgress
    - ✅ create
    - ❌ cancel
- ✅ showMessage request additionalPropertiesSupport

## Dynamic Registration

✅ Fully implemented
