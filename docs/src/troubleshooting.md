## Self-help instructions

Enable LSP logging: In LSP Settings enable the `log_debug` setting.
Enable server logging: set `log_server` to ["panel"] and `log_stderr` to `true`
Run "LSP: Toggle Log Panel" from the command palette. No restart is needed.
If you believe the issue is with this package, please include the output from the Sublime console in your issue report!

## Updating the PATH used by LSP servers

You can confirm that your issue is due to `PATH` being different by starting Sublime Text from the command line so that it inherits your shell's environment.

The solution is to make ST read the same `PATH` that is read by your shell (or OS in general, in case of Windows).

> **Note**: You can see what ST thinks your `PATH` is by opening the ST console by clicking on *View > Show Console*, and running `import os; os.environ["PATH"]` in that console.

Adjusting `PATH` can differ based on the operating system and the default shell used. Refer to the following table on where this can be adjusted:

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

> **Note**: It might be necessary to re-login your user account after changing the shell initialization script for the changes to be picked up.


Another solution could be (at least on Linux) to update the server `PATH` using the `env`parameter in your **LSP** configuration file. The following template can be used where:
  - `<your_language_server_name>` is the server name
  - `<added_path>` is the directory needed for the server to behave correctly

```json
"<your_language_server_name>":
{
    // ...

    "env":
    {
        "PATH": "<added_path>:/usr/local/bin"
    }
}
```

## Common problems

### 1. LSP doesn't start my language server

* Make sure you have a folder added in your Sublime workspace.
* Make sure the document you are opening lives under that folder.

Your client configuration requires two settings to match the document your are editing:

* Scope (eg. `source.php`): Verify this is correct by running "Show Scope Name" from the developer menu.
* Syntax (eg. `Packages\PHP\PHP.sublime-syntax`): Verify by running `view.settings().get("syntax")` in the console.

### 2. LSP cannot find my language server (`No such file or directory: 'xyz'`)
Assuming that the server is actually installed, and that you can start it from your shell, this issue is likely due to Sublime Text's internal environment not picking up the same `PATH` environment variable as you've configured in your shell.

The exact changes to make can differ depending on what program you want to expose to Sublime Text. The simplest way is to extend the path like so (replacing `/usr/local/bin` with the path of your choice):
```sh
export PATH="/usr/local/bin:$PATH"
```

If, for example, you want to expose a `Node` binary to ST and you have it installed through a version manager like `nvm`, you need to insert its [initialization script](https://github.com/nvm-sh/nvm#install--update-script) in the location specified in [this table](troubleshooting.md#updating-the-path-used-by-lsp-servers)

The complete procedure of updating the `PATH` used by Sublime Text depends on your platform and is explained [here](troubleshooting.md#updating-the-path-used-by-lsp-servers).

### 3. Error in build `streamingProcess: runInteractiveProcess: exec: does not exist (No such file or directory)`

This error could occurs when using `stack` or `cabal` (`Haskell` language building tools) with the `haskell-language-server` if a library or binary is missing in the language server `PATH`.

Depending on how you installed your `Haskell` tools, you will need to add one or more of the following to your Sublime Text `PATH`.
```bash
### Home specific and default Stack binaries location
export PATH=$PATH:~/.local/bin:~/bin

### Binaries and libraries installed using ghcup-hs
export PATH=$PATH:~/.ghcup/bin

### Binaries and librairies installed using Cabal
export PATH=$PATH:~/.cabal/bin
```

The complete procedure of updating the `PATH` used by Sublime Text depends on your platform and is explained [here](troubleshooting.md#updating-the-path-used-by-lsp-servers).

## Known Issues

### Completions not shown after certain keywords

Sublime Text's built-in `Completion Rules.tmPreferences` for some languages surpress completions after certain keywords.
Python's `import` keyword is an example - no completions are shown at `import a|` (See [this LSP issue](https://github.com/sublimelsp/LSP/issues/203)).
The solution is to put an edited version of the `Completion Rules.tmPreferences` in the `Packages` folder (you may need to clear the copy in the Cache folder afterwards).
More details on [workaround and a final fix for Lua](https://forum.sublimetext.com/t/bug-lua-autocomplete-not-working-between-if-then/36635)
