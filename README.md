# LSP

[![GitHub release](https://img.shields.io/github/release/tomv564/LSP.svg)](https://github.com/tomv564/LSP/releases)
[![Build Status](https://travis-ci.org/tomv564/LSP.svg?branch=master)](https://travis-ci.org/tomv564/LSP)
[![Coverage Status](https://coveralls.io/repos/github/tomv564/LSP/badge.svg?branch=master)](https://coveralls.io/github/tomv564/LSP?branch=master)
[![Join the chat at https://gitter.im/SublimeLSP/Lobby](https://badges.gitter.im/SublimeLSP/Lobby.svg)](https://gitter.im/SublimeLSP/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Language Server Protocol support for Sublime Text 3 that gives you IDE [features](https://lsp.readthedocs.io/en/latest/#features).

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

## Available Languages <a name="available_languages"></a>
* [Bash](https://lsp.readthedocs.io/en/latest/#bash)
* [C/C++](https://lsp.readthedocs.io/en/latest/#clangd)
* [CSS/LESS/SASS (SCSS only)](https://lsp.readthedocs.io/en/latest/#css)
* [D](https://lsp.readthedocs.io/en/latest/#d)
* [Dart](https://lsp.readthedocs.io/en/latest/#dart)
* [Elm](https://lsp.readthedocs.io/en/latest/#elm)
* [Flow (JavaScript)](https://lsp.readthedocs.io/en/latest/#flow)
* [Go](https://lsp.readthedocs.io/en/latest/#go)
* [HTML](https://lsp.readthedocs.io/en/latest/#html)
* [Java](https://lsp.readthedocs.io/en/latest/#java)
* [JavaScript/TypeScript](https://lsp.readthedocs.io/en/latest/#typescript)
* [JSON](https://lsp.readthedocs.io/en/latest/#json)
* [Julia](https://lsp.readthedocs.io/en/latest/#julia)
* [Kotlin](https://lsp.readthedocs.io/en/latest/#kotlin)
* [LaTeX](https://lsp.readthedocs.io/en/latest/#latex)
* [Lua](https://lsp.readthedocs.io/en/latest/#lua)
* [PHP](https://lsp.readthedocs.io/en/latest/#php)
* [Polymer](https://lsp.readthedocs.io/en/latest/#polymer)
* [Python](https://lsp.readthedocs.io/en/latest/#python)
* [R](https://lsp.readthedocs.io/en/latest/#r)
* [Reason](https://lsp.readthedocs.io/en/latest/#reason)
* [Ruby](https://lsp.readthedocs.io/en/latest/#ruby)
* [Rust](https://lsp.readthedocs.io/en/latest/#rust)
* [Scala](https://lsp.readthedocs.io/en/latest/#scala)
* [Vue (JavaScript)](https://lsp.readthedocs.io/en/latest/#vue)
* [XML](https://lsp.readthedocs.io/en/latest/#xml)

See [Language Server Protocol](https://microsoft.github.io/language-server-protocol/implementors/servers/) for more available implementations. Please create issues/pull requests so we can get support for more languages.

## Customisation of the popup

LSP uses [mdpopups](https://github.com/facelessuser/sublime-markdown-popups) to display the popup. If you want to customise it, check the [doc](http://facelessuser.github.io/sublime-markdown-popups/).

tl;dr?

Create/modify the file `Packages/User/mdpopups.css` and put your own style.

## Getting help

If you have any problems, see the [troubleshooting](https://lsp.readthedocs.io/en/latest/#troubleshooting) guide for tips and known limitations. If the documentation cannot solve your problem, help can be found in the [gitter chat](https://gitter.im/SublimeLSP) or by searching/creating [creating a new issue](https://github.com/tomv564/LSP/issues).

