# Getting started

To get up and running quickly:

1. Find a server for the language of your choice in the [list of language servers](language_servers.md) and follow its setup instructions.
2. Open a document in your chosen language - if the server starts successfully then its name will be shown on the left in the status bar.

If you are having issues with starting the server, check the [Troubleshooting](troubleshooting.md) section.

## About This Package

The package "LSP" is an acronym for **L**anguage **S**erver **P**rotocol. This is a specification for the communication protocol for use between text editors or IDEs and *language servers* - tools which provide language-specific features like autocomplete, go to definition, or documentation on hover.
This package acts as an interface between Sublime Text and your language server, which means that to obtain these features you need to install a server for your language first.
Language servers can be provided as standalone executables or might require a runtime environment like Node.js or Python.
Many new concepts not native to Sublime Text are in use. For an overview of these concepts, please see the [Features](features.md) page.
