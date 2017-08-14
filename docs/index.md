### Sublime LSP Plugin Documentation

# Configuration

## Global Settings

* `show_status_messages` `true` *plugin shows messages in the status bar for a few seconds*
* `show_view_status` `true` *plugin shows permanent status in the status bar* 

## Language Specific Setup

For any of these components it is important that Sublime Text can find the language server executable through the path, especially when using virtual environments.

The default LSP.sublime-settings contains some default LSP client configuration that may not work for you. See [Client Config](#client-config) for explanations for the available settings.

### Javascript/Typescript<a name="jsts"></a>

`npm install -g javascript-typescript-langserver`

On windows you will need to override client config to launch `javascript-typescript-stdio.cmd` instead.

See: [github](https://github.com/sourcegraph/javascript-typescript-langserver)

### Python<a name="python"></a>

`pip install python-language-server`

See: [github](https://github.com/palantir/python-language-server)


### Rust<a name="rust"></a>

Requires Rust Nightly.

See [github](https://github.com/rust-lang-nursery/rls) for up-to-date installation instructions.


### Scala<a name="scala"></a>

Dotty, the future scala compiler [contains LSP support](http://dotty.epfl.ch/docs/usage/ide-support.html). It is developed against VS Code, so ignore instructions related to VS Code.

Get the project compiling with dotty first (see https://github.com/lampepfl/dotty-example-project#using-dotty-in-an-existing-project)

At this point LSP should complain in the logs 
`java.util.concurrent.CompletionException: java.io.FileNotFoundException: /Users/tomv/Projects/tomv564/dottytest/finagle/doc/src/sphinx/code/quickstart/.dotty-ide.json`

Then run `sbt configureIDE` to create the .dotty-ide.json file
Then the LSP plugin should launch via coursier

### Other<a name="other"></a>

Please create issues / pull requests so we can get support for more languages.

### Client Configuration<a name="client-config"></a>

LSP ships with default client configuration for a few language servers. Here is an example for the Javascript/Typescript server:

```json
"jsts": {
    "command": ["javascript-typescript-stdio"],
    "scopes": ["source.ts", "source.tsx"],
    "syntaxes": ["Packages/TypeScript-TmLanguage/TypeScript.tmLanguage", "Packages/TypeScript-TmLanguage/TypeScriptReact.tmLanguage"],
    "languageId": "typescript"
}
```

These can be customized as follows by adding an override in the User LSP.sublime-settings

* `command` - specify a full paths, add arguments
* `scopes` - add language flavours, eg. `source.js`, `source.jsx`.
* `syntaxes` - syntaxes that enable LSP features on a document, eg. `Packages/Babel/JavaScript (Babel).tmLanguage`
* `languageId` - used both by the language servers and to select a syntax highlighter for sublime popups.

# Features

**Document actions**

* Show Code Actions: `cmd+.`
* Symbol References: `shift+f12`
* Go to definition: `f12` (falls back to built-in definition command)

**Workspace actions**

Show Diagnostics Panel: `super+shift+M`

**Mouse map configuration**

See below link, but bind to `symbol_definition` command
https://stackoverflow.com/questions/16235706/sublime-3-set-key-map-for-function-goto-definition


