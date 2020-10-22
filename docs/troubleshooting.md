## Self-help instructions

Enable LSP logging: In LSP Settings enable the `log_debug` setting.
Enable server logging: set `log_server` to ["panel"] and `log_stderr` to `true`
Run "LSP: Toggle Log Panel" from the command palette. No restart is needed.
If you believe the issue is with this package, please include the output from the Sublime console in your issue report!

## Common problems

### 1. LSP doesn't start my language server

* Make sure you have a folder added in your Sublime workspace.
* Make sure the document you are opening lives under that folder.

Your client configuration requires two settings to match the document your are editing:

* Scope (eg. `source.php`): Verify this is correct by running "Show Scope Name" from the developer menu.
* Syntax (eg. `Packages\PHP\PHP.sublime-syntax`): Verify by running `view.settings().get("syntax")` in the console.

### 2. LSP cannot find my language server (`No such file or directory: 'xyz'`)

Assuming that the server is actually installed, and that you can start it from your shell, this issue is likely due to Sublime Text's internal environment not picking up the same `PATH` environment variable as you've configured in your shell.

You can confirm that the issue is due to `PATH` being different by starting Sublime Text from the command line so it inherits your shell's environment.

The solution is to make Sublime Text read the same `PATH` that is read by your shell (or OS in general, in case of Windows).

Adjusting `PATH` can differ based on the operating system and the default shell used. Refer to following table:

<table>
<tr>
    <td>Windows</td>
    <td>Open Start Menu, type "environment" and select "Edit environment variables for your account". Modify the "Path" variable so that it includes the directory path to the program of your choice.</td>
</tr>
<tr>
    <td>macOS</td>
    <td>Depending on your default shell, edit: <code>~/.profile</code> (bash), <code>~/.zprofile</code> (zsh) or <code>~/.config/fish/config.fish</code> (fish).</td>
</tr>
<tr>
    <td>Linux</td>
    <td>Edit <code>~/.profile</code>.</td>
</tr>
</table>

The exact changes to make can differ depending on what program you want to expose to Sublime Text. The simplest way is to extend the path like so (replacing `/usr/local/bin` with the path of your choice):

```sh
export PATH="/usr/local/bin:$PATH"
```

If, for example, you want to expose a `Node` binary to ST and you have it installed through a version manager like `nvm`, you need to insert its [initialization script](https://github.com/nvm-sh/nvm#install--update-script) in the location specified in the table above.

> **Note**: It might be necessary to re-login your user account after changing the shell initialization script for the changes to be picked up.

## Known Issues

### Completions not shown after certain keywords

Sublime Text's built-in `Completion Rules.tmPreferences` for some languages surpress completions after certain keywords.
Python's `import` keyword is an example - no completions are shown at `import a|` (See [this LSP issue](https://github.com/sublimelsp/LSP/issues/203)).
The solution is to put an edited version of the `Completion Rules.tmPreferences` in the `Packages` folder (you may need to clear the copy in the Cache folder afterwards).
More details on [workaround and a final fix for Lua](https://forum.sublimetext.com/t/bug-lua-autocomplete-not-working-between-if-then/36635)
