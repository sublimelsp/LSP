## Self-help instructions

In LSP Settings enable the `log_debug` setting and `log_payloads` if needed. Restart Sublime and watch the logs as you reproduce the problem.
If you believe the issue is with this package, please include the output from the Sublime console in your issue report!

> **NOTE:** `log_stderr` can also be set to `true` to see the language server's own logging.

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

### 3. Multiple root folders?

Have you added multiple folders to your Sublime workspace? LSP may not handle your second folder as expected, see [this issue](https://github.com/tomv564/LSP/issues/81) for more details.

