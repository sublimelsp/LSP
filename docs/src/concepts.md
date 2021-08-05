# Concepts

This package enhances existing concepts from Sublime Text and introduces new concepts not native to Sublime Text. This page provides an overview of the most important capabilities. The capabilities/concepts are accessible in different ways. Some are accessible via the Context Menu by right-clicking with your mouse, or via the top Menu Bar. Others are part of an existing workflow. Almost all capabilities can also be bound to a key with a key binding.

## Auto Complete

The auto-complete functionality of Sublime Text is well-known to any user. It provides word completions from the current buffer, and, since ST4, completions from other files. It presents the auto-complete widget in a synchronous fashion.

The LSP package enhances the auto-complete functionality.

## Goto Definition

Sublime Text provides a "Goto Definition" feature by indexing the files in your project, and building a database out of the parsed files. The feature is accessible by clicking on Goto > Goto Definition. Sublime will attempt to jump to the definition of the word enclosing the caret. The files are parsed according to the `.sublime-syntax` associated to them. Entities which are assigned the `entity.name.*` scope are considered to be a "definition". Because a single `.sublime-syntax` file has no knowledge of the project structure, there may be multiple such "definitions".

This package provides a replacement for Sublime's Goto Definition if your language server has this capability. The feature is accessible by right-clicking with your mouse on the word (or any character) and clicking on LSP > Goto Definition. Similarly, an entry in the Goto menu in the top Menu Bar is also available.

## Goto Type Definition

Some languages have the notion of a "type definition". The functionality is similar to Goto Definition.

## Goto Declaration

Some languages have the notion of a "declaration". The functionality is similar to Goto Definition.

## Goto Implementation

Some languages have the notion of an "implementation". The functionality is similar to Goto Definition.

## Find References

By parsing and indexing a project with `.sublime-syntax` files, Sublime Text is able to provide an approximation of where a type or function is used.

This package provides a replacement of that functionality if your language server has this capability.

## Goto Symbol

Goto Symbol can be accessed by clicking on Goto > Goto Symbol. A common key binding for this is <kbd>ctrl</kbd><kbd>R</kbd>. Sublime Text will show a Quick Panel where you can select a symbol from the current buffer. This package provides a replacement if your language server has this capability. Each symbol's type is accurately described, and the start and end positions of each symbol are clearly visible.

## Goto Symbol In Project

Goto Symbol In Project is a great feature of Sublime Text. It is like Goto Symbol, except you can search for a symbol through your entire project. It is a two-step UX process where you first select an identifier, and you are then presented with the possible locations of your selected identifier. This package provides a replacement if your language server has this capability. The "LSP" Goto Symbol In Project works slightly different because it is a one-step process instead of a two-step process. You select the appropriate symbol immediately.

## Expand Selection

Expand Selection can be accessed by clicking on Selection > Expand Selection. A common key binding for this is <kbd>ctrl</kbd><kbd>shift</kbd><kbd>A</kbd>. A language server may also have this capability and is in a better position to decide what a "smart" Expand Selection should do.

## Hover

"Hover" is a general term for an informational popup that appears when you bring your mouse to a word in the file. Sublime Text shows the definition(s) and references of the word that is under your caret.

The LSP package replaces this built-in hover popup with your language server's hover info, if it has the capability. For instance, it may display type information, documentation, and example usage.

## Diagnostics

Diagnostics is a general term for "things that are of interest in the file". It may be syntax errors, warnings from your compiler, or hints about unused variables in a function.

It is incorrect to call this "lint results", because diagnostics encompass more than just lint results.

It is also incorrect to call these "problems", as hints are not really problems.

Sublime Text has no concept of diagnostics (nor lint results or problems), and hence does not provide an API endpoint to push diagnostics to the end-user. This package invented its own diagnostics presentation system.

The SublimeLinter package provides similar functionality.

## Formatting

Formatting is the art of computing a minimal set of white space text replacements. Formatting may be applied manually through a command invocation, or automatically when saving the file. Sublime Text has no concept of Formatting.

## Signature Help

Signature Help is similar to Auto Complete, but focuses on presenting the different overloads of a function invocation. This package provides Signature Help by means of showing a popup. If multiple overloads exist, you can browse through them just like Auto Complete. Sublime Text has no concept of Signature Help.

## Rename

When you want to rename an identifier in Sublime Text, you probably use <kbd>ctrl</kbd><kbd>D</kbd> to select a few next occurences and do the rename with multiple cursors.

Because a language server (usually) has an abstract syntax tree view of the file, it may be able to rename an identifier semantically. This package exposes that functionality through the hover popup, the context menu, and the top menu bar.

Some language servers provide _global_ rename functionality as well. This package will present a modal dialog to ask you to confirm to apply the changes if they span more than one file.

## Code Actions

Code Actions are an umbrella term for "Quick Fixes" and "Refactorings". They are actions that change the file (or more than one file) to resolve a diagnostic or apply a standard refactor technique. For instance, extracting a block of code into a separate method is usually called "Extract Method" and is a "Refactoring". Whereas "add a missing semicolon" would resolve a diagnostic that warns about a missing semicolon.

Formatting is different from Code Actions, because Formatting is supposed to _not_ mutate the abstract syntax tree of the file, only move around white space. Any Code Action will mutate the abstract syntax tree.

This package presents Code Actions as a bluish clickable annotation positioned to the right of the viewport. Alternatively, they can be presented as a light bulb in the Gutter Area.

Sublime Text has no concept of Code Actions.

## Code Lenses

Code Lenses are "actionable contextual information interspersed" in your source code.

- Actionable: You can click on the link and something happens.
- Contextual: The links are close to the code they are representing.
- Interspersed: The links are located throughout your source code.

This package presents Code Lenses as a greenish clickable annotation positioned to the right of the viewport. Alternatively, they can be presented as phantoms.

Sublime Text has no concept of Code Lenses.

## Server Commands

In Sublime Text you can bind any runnable command to a key or add it to various UI elements. Commands in Sublime Text are normally supplied by plugins or packages written in Python. A language server may provide a runnable command as well. These kinds of commands are wrapped in an `lsp_execute` Sublime command that you can bind to a key.

## Server Settings

Regular Sublime Text packages provide settings to adjust their behavior either via a `.sublime-settings` file that you can override in `Packages/User/package-name.sublime-settings`. A package may also allow customization through the `Packages/User/Preferences.sublime-settings` file and/or syntax-specific or project-specific settings.

A language server may itself also expose settings that you can use to customize its behavior. For instance certain linter settings. This package allows customizing language server settings.

## Server Initialization Options

Initialization Options are like [Server Settings](concepts.md#server-settings), except they are static in the sense that they cannot be changed once the language server subprocess has started.

## Subprocesses

A language server usually runs as a long-lived subprocess of Sublime Text. Once you start Sublime Text and open a view, the syntax of that view is matched against any possible client configurations registered. If a [client configuration](guides/client_configuration.md) matches, a subprocess is started that will then serve you language smartness.
