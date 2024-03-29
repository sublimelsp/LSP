## Self-help instructions

Following are the primary places to look at when diagnosing issues:

1. Run `LSP: Toggle Log Panel` from the *Command Palette* to see communication logs between the server and the client. It allows to see what the server is doing exactly.
2. Open the *Sublime Text* console by going to `View` -> `Show Console` from the main menu. It provides information about installed packages, potential LSP crashes and additional LSP debugging logs when `log_debug` is enabled in `Preferences: LSP Settings`.
3. Focus the relevant file, then run `LSP: Troubleshoot server` from the *Command Palette* and select a server to see troubleshooting information. It can be a very efficient way to diagnose problems quickly when shared.

!!! note
    In case of reporting an issue, consider providing all before-mentioned logs. If you can reproduce the issue, then restarting Sublime Text before capturing the logs can help improve clarity of the logs.

## Updating the PATH used by LSP servers

Sublime Text might see a different `PATH` from what your shell environment uses and might not be able to find the server binary due to that. You can see what ST thinks your `PATH` is by opening the ST console by clicking on *View > Show Console*, and running `import os; os.environ["PATH"]` in that console.

The solution is to make ST use the same `PATH` that is read by your shell (or OS in general in the case of Windows).

Adjusting `PATH` can differ based on the operating system and the default shell used. Refer to the following table on where this should be adjusted:

<table>
<tr>
    <td>Windows</td>
    <td>Open Start Menu, type "environment" and select "Edit environment variables for your account". Modify the "Path" variable so that it includes the directory path to the program of your choice.</td>
</tr>
<tr>
    <td>macOS</td>
    <td>Depending on your default shell (macOS ships with zsh shell by default), edit: <code>~/.zprofile</code> (zsh), <code>~/.profile</code> (bash) or <code>~/.config/fish/config.fish</code> (fish).</td>
</tr>
<tr>
    <td>Linux</td>
    <td>Edit <code>~/.profile</code>.</td>
</tr>
</table>

For macOS and Linux you can extend the path like so:

```sh
export PATH="/usr/local/bin:$PATH"
```

For package managers like `nvm` (Node version manager), the recommended way is to insert its [initialization script](https://github.com/nvm-sh/nvm#install--update-script) in the respective location specified above.

!!! note
    On macOS, it's enough to restart ST for the changes to be picked up. On other platforms, you might have to re-login your user account.

Another solution could be (at least on Linux) to update the server `PATH` using the `env`parameter in your **LSP** configuration file. The following template can be used where:

  - `<your_language_server_name>` is the server name
  - `<added_path>` is the directory needed for the server to behave correctly

```jsonc
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

### Error dialog saying `Failed to start...`

If you are getting an error that the server binary can't be found (`No such file or directory...`) but it does start when Sublime Text is started from the terminal, then the issue is likely due to Sublime Text's internal environment not picking up the same `PATH` environment variable as you've configured in your shell. See ["Updating the PATH used by LSP servers"](troubleshooting.md#updating-the-path-used-by-lsp-servers) on how to fix that.

Otherwise refer to the ["Self-help instructions"](troubleshooting.md#self-help-instructions) section to try to understand the issue better.

### LSP doesn't start my language server

When language server is started, its name appears on the left side of the status bar. If you expect your server to start for a particular file but it doesn't then:

* Make sure that the root scope (eg. `source.php`) of the file matches the scope handled by the language server. You can check the root scope of the file by running `Show Scope Name` from the `Tools -> Developer` menu. Refer to the documentation of the language server or its own settings to know the expected scope.
* Make sure that the language server is not disabled globally either in its own settings, in `Preferences: LSP Settings` or in the project settings (`Project: Edit Project` from the *Command Palette*).

### Completions not shown after certain keywords

Sublime Text's built-in `Completion Rules.tmPreferences` for some languages suppresses completions after certain keywords.
The solution is to put an edited version of the `Completion Rules.tmPreferences` in the `Packages` folder.
More details on [workaround and a final fix for Lua](https://forum.sublimetext.com/t/bug-lua-autocomplete-not-working-between-if-then/36635).
