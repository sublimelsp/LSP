# Getting started

1. Find a server for the language of your choice in the [list of language servers](language_servers.md) and follow its setup instructions.
2. Open a document in your chosen language - if the server starts successfully then its name will be shown on the left in the status bar.

If you are having issues with starting the server, check the [Troubleshooting](troubleshooting.md) section.


## About LSP

The *Language Server Protocol* is a specification about the communication protocol for use between text editors or IDEs and *language servers* - tools which provide language-specific features like autocomplete, go to definition, or documentation on hover.
This LSP package acts as an interface between Sublime Text and the language servers, which means that to obtain these features you need to install a server for your language first.
Language servers can be provided as standalone executables or might require a runtime environment like Node.js or Python.
The [list of language servers](language_servers.md) shows installation instructions and example configurations for several servers that have been tested and are known to work with the LSP package.
Visit [Langserver.org](https://langserver.org/) or the [list of language server implementations](https://microsoft.github.io/language-server-protocol/implementors/servers/) maintained by Microsoft for a complete overview of available servers for various programming languages.
