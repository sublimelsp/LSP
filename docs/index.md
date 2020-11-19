# Getting started

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

