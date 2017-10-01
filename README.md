# LSP

[![GitHub release](https://img.shields.io/github/release/tomv564/LSP.svg)](https://github.com/tomv564/LSP/releases) [![Build Status](https://travis-ci.org/tomv564/LSP.svg?branch=master)](https://travis-ci.org/tomv564/LSP) [![license](https://img.shields.io/github/license/mashape/apistatus.svg)]() [![Join the chat at https://gitter.im/SublimeLSP/Lobby](https://badges.gitter.im/SublimeLSP/Lobby.svg)](https://gitter.im/SublimeLSP/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) 

Gives Sublime Text 3 rich editing features for languages with Language Server Protocol support.

Tested against language servers for javascript, typescript, python, php, java, go, c/c++ (clangd), scala (dotty), julia, rust, reason. 

See [langserver.org](http://langserver.org) for available implementations.

## Features

Completions with snippet support.

Navigate code with `Go to Symbol Definition` and `Find Symbol References`

Inline documentation from Hover and Signature Help popups

![hover screenshot](https://raw.githubusercontent.com/tomv564/LSP/master/docs/images/screenshot-hover.png)

As-you-type diagnostics with support for code fixes (`F4` to select, `super+.` to trigger actions)

![diagnostics screenshot](https://raw.githubusercontent.com/tomv564/LSP/master/docs/images/screenshot-diagnostics-action.png)

## Installing

Releases are published as **LSP** in Package Control.

To run latest master:
1. Clone this repository into your Packages directory
2. Run `Package Control: Satisfy Dependencies`

## Configuration

Documentation is available at [LSP.readthedocs.io](https://LSP.readthedocs.io) or [in the docs directory](https://github.com/tomv564/LSP/blob/master/docs/index.md)

## Troubleshooting

Enable the `log_debug` setting, restart Sublime and open the console.
See the [Troubleshooting](https://lsp.readthedocs.io/en/latest/#troubleshooting) guide for tips and known limitations.
