# Getting started

To get up and running quickly:

1. Find a server for the language of your choice in the [list of language servers](language_servers.md) and follow its setup instructions.
2. Open a document in your chosen language - if the server starts successfully then its name will be shown on the left in the status bar.

If you are having issues with starting the server, check the [Troubleshooting](troubleshooting.md) section.


## Introduction

"LSP" is an acronym for **L**anguage **S**erver **P**rotocol.
This is a specification for the communication protocol for use between text editors or IDEs and *language servers* - tools which provide language-specific features like autocomplete, go to definition, or documentation on hover.
As the so called *LSP client* this package acts as an interface between Sublime Text and your language server, which means that to obtain these features you need to install a server for your language first.
Language servers can be provided as standalone executables or require a runtime environment like Node.js or Python.
For various languages you can find a community maintained helper package with an `LSP-` name prefix on Package Control. These packages allow to install and update a particular language server automatically, to setup a default configuration with server specific settings, and they may also provide additional features for servers which use a custom extension of the language server protocol.
Alternatively, a language server can be installed manually and the necessary configuration can be added directly into the `LSP.sublime-settings` file; see the [Client Configuration](client_configuration.md) page for details.

Many new concepts not native to Sublime Text are in use.
For an overview of these concepts, please see the [Features](features.md) page.


## Projects & Workspace Folders

This LSP client supports to run multiple active servers at the same time for a single file type.
For example in a Python project you could use LSP-pyright for general features (autocomplete, go to definition, etc.) and simultaneously LSP-ruff for additional linter warnings.
In case you want to run multiple servers with a similar set of features at the same time, it is possible to prioritize one of the servers by disabling some of the features for the other server(s) using the `"disabled_capabilities"` setting in the [Client Configuration](client_configuration.md).

An instance of a language server is always bound to a single window in Sublime Text.
Note that this means if you move a file tab handled by a language server out of a window, a new instance of that server will be started, or if it was moved into another window where the corresponding server was already running, then it will be managed by that other server instance.
In other words you can have multiple projects open at the same time in different windows and each of them gets managed by its own language server instance.

"Workspace" and "workspace folders" are terms from VS Code and they are also used in the LSP specification.
Basically a workspace corresponds to a window in Sublime Text and the workspace folders are just the folders which are opened in the sidebar.
The window does not necessarily need to be associated with a [Sublime project](https://www.sublimetext.com/docs/projects.html), but sometimes this can be useful for project-specific configurations, see [Per-project overrides](client_configuration.md#per-project-overrides).
There can be multiple workspace folders, or even none if you just open individual files in the active window.
When a language server starts, it is notified about the workspace folders and many servers use them to look for configuration files, for instance `Cargo.toml` in Rust or `pyproject.toml` in a Python project.
So for project-based programming languages you typically want to have the root folder of your project opened as a folder in the sidebar.

If a file from outside the workspace folders is opened in the same window (for example manually, or when using "Goto Definition"), most LSP features should still work in that file.
However, note that diagnostic messages are filtered out for such files unless explicitly configured differently in the client configuration for that server.


## Server Settings & Initialization Options

A language server may expose settings that you can use to customize its behavior.
For instance certain linter settings or formatting options.
If you use an LSP-* helper package for your language server, its settings can be customized in the corresponding `.sublime-settings` file that you can open from the command palette or from the main menu under `Preferences > Package Settings > LSP > Servers`.

Initialization Options are like server settings, except they are static in the sense that they cannot be changed once the language server subprocess has started.


## Subprocesses

A language server usually runs as a long-lived subprocess of Sublime Text.
Once you start Sublime Text and open a view, the syntax of that view is matched against any possible client configurations registered.
If a [Client Configuration](client_configuration.md) matches, a subprocess is started that will then serve you language smartness.
