# LSP

[![GitHub release](https://img.shields.io/github/release/tomv564/LSP.svg)](https://github.com/tomv564/LSP/releases) 
[![Build Status](https://travis-ci.org/tomv564/LSP.svg?branch=master)](https://travis-ci.org/tomv564/LSP) 
[![Coverage Status](https://coveralls.io/repos/github/tomv564/LSP/badge.svg?branch=master)](https://coveralls.io/github/tomv564/LSP?branch=master) 
[![Join the chat at https://gitter.im/SublimeLSP/Lobby](https://badges.gitter.im/SublimeLSP/Lobby.svg)](https://gitter.im/SublimeLSP/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Language Server Protocol support for Sublime Text 3 that gives you IDE features.

![diagnostics screen-shot](docs/images/showcase.gif "TypeScript Server Example")

## Installation

### Stable Version

* Open the command palette and run `Package Control: Install Package` then select `LSP`.


### Development Version

* Clone this repository into your Packages directory.
* Open the command palette and run `Package Control: Satisfy Dependencies`.


## Getting started

Copy the configuration for a <a href="#available_languages">language</a>. 

Open `LSP.sublime-settings` and paste the configuration in the `clients` section.

Open a document supported by the language server. LSP should report the language server starting in the status bar. 

If the server doesn't start. Open the command palette and run `LSP: Enable Language Server` then select the server. If you still have any problems, see [troubleshooting](https://lsp.readthedocs.io/en/latest/#troubleshooting) problems or start a discussion in gitter [chat](https://gitter.im/SublimeLSP).

Documentation is available at [LSP.readthedocs.io](https://LSP.readthedocs.io).


## Available Languages <a name="available_languages"></a>
* [Bash](https://lsp.readthedocs.io/en/latest/#bash)
* [C/C++](https://lsp.readthedocs.io/en/latest/#clangd)
* [CSS/LESS/SASS (SCSS only)](https://lsp.readthedocs.io/en/latest/#css)
* [Dart](https://lsp.readthedocs.io/en/latest/#dart)
* [Flow (JavaScript)](https://lsp.readthedocs.io/en/latest/#flow)
* [Go](https://lsp.readthedocs.io/en/latest/#go)
* [HTML](https://lsp.readthedocs.io/en/latest/#html)
* [Java (Eclipse)](https://lsp.readthedocs.io/en/latest/#java)
* [Java (IntelliJ)](https://lsp.readthedocs.io/en/latest/#intellij)
* [JavaScript/TypeScript](https://lsp.readthedocs.io/en/latest/#typescript)
* [JSON](https://lsp.readthedocs.io/en/latest/#json)
* [Julia](https://lsp.readthedocs.io/en/latest/#julia)
* [Kotlin](https://lsp.readthedocs.io/en/latest/#kotlin)
* [PHP (Felix Becker)](https://lsp.readthedocs.io/en/latest/#php)
* [PHP (Intelephense)](https://lsp.readthedocs.io/en/latest/#intelephense)
* [Polymer](https://lsp.readthedocs.io/en/latest/#polymer)
* [Python](https://lsp.readthedocs.io/en/latest/#python)
* [Python (Microsoft)](https://lsp.readthedocs.io/en/latest/#python_microsoft)
* [R](https://lsp.readthedocs.io/en/latest/#r)
* [Reason](https://lsp.readthedocs.io/en/latest/#reason)
* [Ruby](https://lsp.readthedocs.io/en/latest/#ruby)
* [Rust](https://lsp.readthedocs.io/en/latest/#rust)
* [Scala](https://lsp.readthedocs.io/en/latest/#scala)
* [Vue (JavaScript)](https://lsp.readthedocs.io/en/latest/#vue)

See [Language Server Protocol](https://microsoft.github.io/language-server-protocol/implementors/servers/) for more available implementations. Please create issues/pull requests so we can get support for more languages.

## Troubleshooting Issues

Have any problems, see the [troubleshooting](https://lsp.readthedocs.io/en/latest/#troubleshooting) guide for tips and known limitations. If you still have any problems, discussions can be done in gitter [chat](https://gitter.im/SublimeLSP).
