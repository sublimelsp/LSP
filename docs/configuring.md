# Configuring

## Global Settings

* `show_status_messages` `true` *plugin shows messages in the status bar for a few seconds*
* `show_view_status` `true` *plugin shows permanent status in the status bar* 

## Language Specific Setup

For any of these components it is important that Sublime Text can find the package through the path, especially when using virtual environments.

* [Javascript/Typescript](#jsts)
* [Python](#python)

The default LSP.sublime-settings may not work for you. See [Client Config](#client-config) to 

### Javascript/Typescript<a name="jsts"></a>

`npm install -g javascript-typescript-langserver`

On windows you will need to override client config to launch `javascript-typescript-stdio.cmd` instead.

See: [github](https://github.com/sourcegraph/javascript-typescript-langserver)

### Python<a name="python"></a>

`pip install python-language-server`

See: [github](https://github.com/palantir/python-language-server)

### Other<a name="other"></a>

You are mostly on your own, please try to provide instructions and client configuration once you get something working!


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
