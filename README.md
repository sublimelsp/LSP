# LSP

[![license](https://img.shields.io/github/license/mashape/apistatus.svg)]()

Universal Language Server support for Sublime Text 3 using the Language Server Protocol.

Features:

* Hover
* Completions
* Go to document symbol
* Go to symbol definition
* Find symbol references
* Diagnostics
* Code Actions

Tested against language servers for javascript/typescript, python, c/c++ (clangd), scala (dotty), rust. See [langserver.org](http://langserver.org) for available implementations

## Screenshots

Rich hover support from js/ts language server 

![hover screenshot](https://github.com/tomv564/LSP/blob/master/docs/images/screenshot-hover.png)

Cycle through diagnostics shown in output panel with `F4`. Code actions supplied by tslint language server plugin, applied by `super+.`

![diagnostics screenshot](https://github.com/tomv564/LSP/blob/master/docs/images/screenshot-diagnostics-action.png)


## Installing

Until this project is submitted to PackageControl's repository, only a manual clone into your Packages directory is supported:

```
# on a Mac
cd "$HOME/Library/Application Support/Sublime Text 3/Packages"
# on Linux
cd $HOME/.config/sublime-text-3/Packages
# on Windows (PowerShell)
cd "$env:appdata\Sublime Text 3\Packages\"

git clone git@github.com:tomv564/LSP.git

# Package Control need to be installed https://packagecontrol.io/installation
# install dependencies from command line
subl --command 'satisfy_dependencies'
# or open Command Palette and run 'Package Control: Satisfy Dependencies'
```

## Configuration

Documentation is available at [LSP.readthedocs.io](https://LSP.readthedocs.io) or [in the docs directory](https://github.com/tomv564/LSP/blob/master/docs/index.md)  
