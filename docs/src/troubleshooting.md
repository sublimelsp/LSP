## Self-help instructions

To get more visibility into the inner-workings of the LSP client and the server and be able to diagnose problems, open `Preferences: LSP Settings` from the Command Palette and set the following options:

| Option                  | Description                                                          |
| ----------------------- | -------------------------------------------------------------------- |
| `log_debug: true`       | Show verbose debug messages in the Sublime Text console.             |
| `log_server: ["panel"]` | Log communication from and to language servers in the output panel.  |

Once enabled (no restart necessary), the communication log can be seen by running `LSP: Toggle Log Panel` from the Command Palette. It might be a good idea to restart Sublime Text and reproduce the issue again, so that the logs are clean.

If you believe the issue is with this package, please include the output from the Sublime console in your issue report!

If the server is crashing on startup, try running `LSP: Troubleshoot server` from the Command Palette and check the "Server output" for potential errors. Consider sharing the output of this command in the report.

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
    <td>Depending on your default shell, edit: <code>~/.profile</code> (bash), <code>~/.zprofile</code> (zsh) or <code>~/.config/fish/config.fish</code> (fish).</td>
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

When language server is started, its name appears on the left side of the status bar. If you expect your server to start for a particular file but it doesn't then:

* Make sure that the root scope (eg. `source.php`) of the file matches the scope handled by the language server. You can check the root scope of the file by running `Show Scope Name` from the `Tools -> Developer` menu. Refer to the documentation of the language server or its own settings to know the expected scope.
* Make sure that the language server is not disabled globally either in its own settings or in `Preferences: LSP Settings`, or in the project settings (`Project: Edit Project` from the Command Palette).

### 2. LSP cannot find my language server (`No such file or directory: 'xyz'`)

If you are getting an error that the server binary can't be found but it does start when running it from the terminal, then the issue is likely due to Sublime Text's internal environment not picking up the same `PATH` environment variable as you've configured in your shell.

See ["Updating the PATH used by LSP servers"](troubleshooting.md#updating-the-path-used-by-lsp-servers) on how to make Sublime Text aware of the location of your langugage server.

### 3. Popup error `Language server <your_server_language_name> has crashed`

The reason for this can be the same as in problem number 2. Additionally, the language servers may have dependencies that should also be in your `PATH` in addition to the server binary itself.

For instance if you have installed the `haskell-language-server` using [ghcup-hs](https://gitlab.haskell.org/haskell/ghcup-hs) you should expose its specific installation folder `~/.ghcup/bin`. If the build process uses `stack` then it should also be in your `PATH`.

If that doesn't solve the issue, try running `LSP: Troubleshoot server` and providing its output when asking for help.

## Known Issues

### Completions not shown after certain keywords

Sublime Text's built-in `Completion Rules.tmPreferences` for some languages suppresses completions after certain keywords.
The solution is to put an edited version of the `Completion Rules.tmPreferences` in the `Packages` folder (you may need to clear the copy in the Cache folder afterwards).
More details on [workaround and a final fix for Lua](https://forum.sublimetext.com/t/bug-lua-autocomplete-not-working-between-if-then/36635)
