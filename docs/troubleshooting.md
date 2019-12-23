## Self-help instructions

Enable LSP logging: In LSP Settings enable the `log_debug` setting and `log_payloads` if needed.
Enable server logging: set `log_server` and `log_stderr` to `true`
Restart Sublime and open the console (``ctrl+` ``) to see the additional logging.
If you believe the issue is with this package, please include the output from the Sublime console in your issue report!

## Common problems

### 1. LSP doesn't start my language server

* Make sure you have a folder added in your Sublime workspace.
* Make sure the document you are opening lives under that folder.

Your client configuration requires two settings to match the document your are editing:

* Scope (eg. `source.php`): Verify this is correct by running "Show Scope Name" from the developer menu.
* Syntax (eg. `Packages\PHP\PHP.sublime-syntax`): Verify by running `view.settings().get("syntax")` in the console.

### 2. LSP cannot find my language server

Often caused by Sublime Text's internal environment not picking up the same PATH as you've configured in your shell.

This issue can be solved in a few ways:

* Always launch sublime from the command line (so it inherits your shell's environment)
* On OS-X: Install the [SublimeFixMacPath](https://github.com/int3h/SublimeFixMacPath) package
* On OS-X: Use `launchctl setenv` to set PATH for OS-X UI applications.

## Known Issues

### Completions not shown after certain keywords

Sublime Text's built-in `Completion Rules.tmPreferences` for some languages surpress completions after certain keywords.
Python's `import` keyword is an example - no completions are shown at `import a|` (See [this LSP issue](https://github.com/sublimelsp/LSP/issues/203)).
The solution is to put an edited version of the `Completion Rules.tmPreferences` in the `Packages` folder (you may need to clear the copy in the Cache folder afterwards).
More details on [workaround and a final fix for Lua](https://forum.sublimetext.com/t/bug-lua-autocomplete-not-working-between-if-then/36635)
