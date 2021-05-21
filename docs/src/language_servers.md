# Language Servers

Follow the setup steps for a language server to get it up and running.

If you encounter problems, consult the [common issues](troubleshooting.md#common-problems) page or search the [LSP issues](https://github.com/sublimelsp/LSP/issues) before opening new ones.

If there are no setup steps for a language server on this page, but a [language server implementation](https://microsoft.github.io/language-server-protocol/implementors/servers/) exist, follow the guide for [creating a client configuration](./guides/client_configuration.md). Pull requests for adding a new client configuration are welcome.

!!! tip "We recommend installing [LSP-json](https://packagecontrol.io/packages/LSP-json)."
    [LSP-json](https://packagecontrol.io/packages/LSP-json) provides completions and diagnostics when editing JSON files that adhere to a JSON schema.


## Angular

Follow installation instructions on [LSP-angular](https://github.com/sublimelsp/LSP-angular).

## Bash

Follow installation instructions on [LSP-bash](https://github.com/sublimelsp/LSP-bash).

## C/C++

See the dedicated [C/C++ guide](guides/cplusplus.md) for using ccls or clangd.

## C\#

Follow installation instructions on [LSP-OmniSharp](https://github.com/sublimelsp/LSP-OmniSharp).

## Clojure

1. Download [clojure-lsp](https://github.com/snoe/clojure-lsp#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"clojure-lsp"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "clojure-lsp": {
                "enabled": true,
                "command": ["java", "-jar", "/PATH/TO/clojure-lsp"], // Update the PATH
                "selector": "source.clojure",
                "initializationOptions": {}
            }
        }
    }
    ```

!!! info "See available [initializationOptions](https://github.com/snoe/clojure-lsp#initializationoptions)."

## CSS

Follow installation instructions on [LSP-css](https://github.com/sublimelsp/LSP-css).

## D

1. Install the [D Language Server](https://github.com/d-language-server/dls#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"dls"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "dls": {
                "enabled": true,
                "command": ["/PATH/TO/DLS_EXECUTABLE"], // Update the PATH
                "selector": "source.d"
            }
        }
    }
    ```

## Dart

Follow installation instructions on [LSP-Dart](https://github.com/sublimelsp/LSP-Dart).

## Dockerfile

Follow installation instructions on [LSP-dockerfile](https://github.com/sublimelsp/LSP-dockerfile).

## Elixir

Follow installation instructions on [LSP-elixir](https://github.com/sublimelsp/LSP-elixir).

## Elm

Follow installation instructions on [LSP-elm](https://github.com/sublimelsp/LSP-elm).

## Erlang

1. Install the [Erlang Language Server](https://github.com/erlang-ls/erlang_ls).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"erlang-ls"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "erlang-ls": {
                "enabled": true,
                "command": [ "/PATH/TO/erlang_ls", "--transport", "stdio" ], // Update the PATH
                "selector": "source.erlang"
            }
        }
    }
    ```

## ESLint

Follow installation instructions on [LSP-eslint](https://github.com/sublimelsp/LSP-eslint).

## Flow

Follow installation instructions on [LSP-flow](https://github.com/sublimelsp/LSP-flow).

## Fortran

1. Install the [ Fortran](https://packagecontrol.io/packages/Fortran) package from Package Control for syntax highlighting.
2. Install the [Fortran Language Server](https://github.com/hansec/fortran-language-server#installation).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"fortls"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "fortls": {
                "enabled": true,
                "command": ["fortls"],
                "selector": "source.modern-fortran | source.fixedform-fortran"
            }
        }
    }
    ```

!!! info "See available [configuration options](https://github.com/hansec/fortran-language-server#language-server-settings)."
    For example set `"command": ["fortls", "--lowercase_intrinsics"]` to use lowercase for autocomplete suggestions.

## Go

1. Install [gopls](https://github.com/golang/tools/blob/master/gopls/README.md#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"gopls"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "gopls": {
                "enabled": true,
                "command": ["gopls"],
                "selector": "source.go",
                "initializationOptions": {
                    "experimentalWorkspaceModule": false
                }
            }
        }
    }
    ```

!!! info "Visit [gopls repo](https://github.com/golang/tools/tree/master/gopls) for more info."
    Enable multi-module workspace support by setting the `experimentalWorkspaceModule` to `true`. Most features will work across modules, but some, such as `goimports`, will not work as expected. Please note that this setting is still very experimental.


## GraphQL

Follow installation instructions on [LSP-graphql](https://github.com/sublimelsp/LSP-graphql).

## Haskell

1. Install [haskell-language-server](https://github.com/haskell/haskell-language-server).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"haskell-language-server"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "haskell-language-server": {
                "enabled": true,
                "command": ["haskell-language-server-wrapper", "--lsp"],
                "selector": "source.haskell"
            }
        }
    }
    ```

## HTML

Follow installation instructions on [LSP-html](https://github.com/sublimelsp/LSP-html).

## Java

Follow installation instructions on [LSP-jdtls](https://github.com/sublimelsp/LSP-jdtls).

## JSON

Follow installation instructions on [LSP-json](https://github.com/sublimelsp/LSP-json).

## Julia

1. Install the [Julia](https://packagecontrol.io/packages/Julia) package from Package Control for syntax highlighting.
2. Install the `LanguageServer` and `SymbolServer` packages from the Julia REPL:

        import Pkg;
        Pkg.add("LanguageServer")
        Pkg.add("SymbolServer")

3. Open `Preferences > Package Settings > LSP > Settings` and add the `"julials"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "julials": {
                "enabled": true,
                "command": ["bash", "PATH_TO_JULIA_SERVER/LanguageServer/contrib/languageserver.sh"], // on Linux/macOS
              // "command": ["julia", "--startup-file=no", "--history-file=no", "-e", "using Pkg; using LanguageServer; using LanguageServer.SymbolServer; env_path=dirname(Pkg.Types.Context().env.project_file); server=LanguageServer.LanguageServerInstance(stdin,stdout,false,env_path); run(server)"], // on Windows
                "selector": "source.julia",
                "settings": {
                    // Default values from VS Code:
                    "julia.format.calls": true,      // Format function calls
                    "julia.format.comments": true,   // Format comments
                    "julia.format.curly": true,      // Format braces
                    "julia.format.docs": true,       // Format inline documentation
                    "julia.format.indent": 4,        // Indent size for formatting
                    "julia.format.indents": true,    // Format file indents
                    "julia.format.iterOps": true,    // Format loop iterators
                    "julia.format.kw": true,         // Remove spaces around = in function keywords
                    "julia.format.lineends": false,  // [undocumented]
                    "julia.format.ops": true,        // Format whitespace around operators
                    "julia.format.tuples": true,     // Format tuples
                    "julia.lint.call": false,        // Check calls against existing methods (experimental)
                    "julia.lint.constif": true,      // Check for constant conditionals of if statements
                    "julia.lint.datadecl": false,    // [undocumented]
                    "julia.lint.iter": true,         // Check iterator syntax of loops
                    "julia.lint.lazy": true,         // Check for deterministic lazy boolean operators
                    "julia.lint.modname": true,      // Check for invalid submodule names
                    "julia.lint.nothingcomp": false, // [undocumented]
                    "julia.lint.pirates": true,      // Check for type piracy
                    "julia.lint.run": true,          // run the linter on active files
                    "julia.lint.typeparam": true     // Check for unused DataType parameters
                }
            }
        }
    }
    ```

## Kotlin

1. Install the [Kotlin](https://packagecontrol.io/packages/Kotlin) package from Package Control for syntax highlighting.
2. Install the [Kotlin Language Server](https://github.com/fwcd/KotlinLanguageServer) (requires [building](https://github.com/fwcd/KotlinLanguageServer/blob/master/BUILDING.md) first).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"kotlinls"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "kotlinls": {
                "enabled": true,
                "command": ["PATH/TO/KotlinLanguageServer/build/install/kotlin-language-server/bin/kotlin-language-server.bat"], // Update the PATH
                "selector": "source.Kotlin",
                "settings": {
                    "kotlin": {
                        // put your server settings here
                    }
                }
            }
        }
    }
    ```

## LaTeX

Follow installation instructions on [LSP-TexLab](https://github.com/sublimelsp/LSP-TexLab).

## Lisp

1. Install [cc-lsp](https://github.com/cxxxr/cl-lsp) using Roswell.
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"cc-lsp"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "cc-lsp": {
                "enabled": true,
                "command": ["cl-lsp", "stdio"],
                "selector": "source.lisp"
            }
        }
    }
    ```

## Lua

Follow installation instructions on [LSP-lua](https://github.com/sublimelsp/LSP-lua).

## OCaml/Reason

1. Install the [Reason](https://packagecontrol.io/packages/Reason) package from Package Control for syntax highlighting.
2. Install the [Reason Language Server](https://github.com/jaredly/reason-language-server#sublime-text).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"reason"` client configuration to the `"clients"`:


    ```json
    {
        "clients": {
            "reason": {
                "enabled": true,
                "command": ["PATH/TO/reason-language-server.exe"], // Update the PATH
                "selector": "source.ocaml | source.reason"
            }
        }
    }
    ```

## PromQL

Follow installation instructions on [LSP-promql](https://github.com/prometheus-community/sublimelsp-promql).

## PHP

There are multiple options:

### Intelephense

Follow installation instructions on [LSP-intelephense](https://github.com/sublimelsp/LSP-intelephense).

### Serenata

Follow installation instructions on [LSP-serenata](https://github.com/Cloudstek/LSP-serenata).

## PowerShell

Follow installation instructions on [LSP-PowerShellEditorServices](https://github.com/Cloudstek/LSP-PowerShellEditorServices).

## Python

There are multiple options:

### Pyright

Follow installation instructions on [LSP-pyright](https://github.com/sublimelsp/LSP-pyright).

### Python LSP Server

```sh
pip install 'python-lsp-server[all]'
```

Make sure you can run `pylsp` in your terminal. If you've installed it into a virtualenv, you might need to override the path to `pylsp` in global LSP settings (Package Settings -> LSP -> Settings):

    ```json
    {
        "clients": {
            "pylsp": {
                "enabled": true,
                "command": ["pylsp"],
                // "command": ["/Users/mike/.virtualenvs/pylsp-virtual-env/bin/pylsp"], // example path, adjust it for your use case
                "selector": "source.python"
            }
        }
    }
    ```

If you use a virtualenv for your current project, add a path to it in your [project configuration](https://www.sublimetext.com/docs/3/projects.html) (Project -> Edit Project):

```json
{
    "settings": {
        "LSP": {
            "pylsp": {
                "enabled": true, // if you want to enable Python Language Server for current project only
                "env": {
                    // example path, adjust it for your use case
                    // it needs to be an absolute path, neither $HOME nor ~ work here
                    "PYTHONPATH": "/Users/mike/.virtualenvs/my-virtual-env/lib/python3.7/site-packages"
                }
            }
        }
    }
}
```

A basic configuration below can be used for bootstrapping your own:

```json
"pylsp": {
    "enabled": true,
    "command": ["pylsp"],
    "settings": {
        "pylsp.env": {
          // Making Sublime's own libs available to the linters.
          // "PYTHONPATH": "/Applications/Sublime Text.app/Contents/MacOS/Lib/python33",
        },
        // Configuration is computed first from user configuration (in home directory),
        // overridden by configuration passed in by the language client,
        // and then overridden by configuration discovered in the workspace.
        "pylsp.configurationSources": [
          "pycodestyle", // discovered in ~/.config/pycodestyle, setup.cfg, tox.ini and pycodestyle.cfg
          // "flake8",   // discovered in ~/.config/flake8, setup.cfg, tox.ini and flake8.cfg
        ],
        "pylsp.plugins.jedi.extra_paths": [
          // The directory where the pip installation package is located
        ],
        // Enable fuzzy matches when requesting autocomplete
        "pylsp.plugins.jedi.jedi_completion.fuzzy": true,
        "pylsp.plugins.jedi.pycodestyle.enabled": true,
        "pylsp.plugins.jedi.pycodestyle.exclude": [
          // Exclude files or directories which match these patterns
        ],
        "pylsp.plugins.jedi.pycodestyle.ignore": [
          // Exclude files or directories which match these patterns
        ],
        // "pylsp.plugins.jedi.pycodestyle.maxLineLength: 80" // set maximum allowed line length
        "pylsp.plugins.pydocstyle.enabled": false,
        "pylsp.plugins.pyflakes.enabled": true,
        "pylsp.plugins.pylint.enabled": false,
        "pylsp.plugins.yapf.enabled": true,
        // pylsp' 3rd Party Plugins, Mypy type checking for Python 3, Must be installed via pip before enabling
        "pylsp.plugins.pyls_mypy.enabled": false, // Install with: pip install pyls-mypy
        "pylsp.plugins.pyls_mypy.live_mode": true
    }
}
```

Documentation: [github:python-lsp/python-lsp-server](https://github.com/python-lsp/python-lsp-server).

!!! info "List of all built-in [settings](https://github.com/palantir/python-language-server/blob/develop/vscode-client/package.json)."

## R

Follow installation instructions on [R-IDE](https://github.com/REditorSupport/sublime-ide-r#installation).

## Ruby / Ruby on Rails

There are multiple options:

### Solargraph

1. Install [solargraph](https://github.com/castwide/solargraph#installation).

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"ruby"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "ruby": {
                "enabled": true,
                "command": ["solargraph", "stdio"],
                "selector": "source.ruby | text.html.ruby",
                "initializationOptions": {
                    "diagnostics": false
                }
            }
        }
    }
    ```

### Sorbet

1. Install the sorbet and sorbet-runtime gem (see [github:sorbet/sorbet](https://github.com/sorbet/sorbet)):

        gem install sorbet
        gem install sorbet-runtime

    If you have a Gemfile, using bundler, add sorbet and sorbet-runtime to your Gemfile and run:

        bundle install

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"sorbet"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "sorbet": {
                "enabled": true,
                "command": ["srb", "tc", "--typed", "true", "--enable-all-experimental-lsp-features", "--lsp", "--disable-watchman"],
                "selector": "source.ruby | text.html.ruby",
            }
        }
    }
    ```

## Rust

There are multiple options:

### Rust Analyzer

1. Download a binary from the release page of [rust-analyzer](https://github.com/rust-analyzer/rust-analyzer).
2. Rename the binary to `rust-analyzer`.
3. Make sure the binary is in your `$PATH`.
4. Open `Preferences > Package Settings > LSP > Settings` and add the `"rust-analyzer"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "rust-analyzer": {
                "enabled": true,
                "command": ["rust-analyzer"],
                "selector": "source.rust"
            }
        }
    }
    ```

## Scala

Follow installation instructions on [LSP-metals](https://github.com/scalameta/metals-sublime).

## Stylelint

Follow installation instructions on [LSP-stylelint](https://github.com/sublimelsp/LSP-stylelint).

## Svelte

Follow installation instructions on [LSP-svelte](https://github.com/sublimelsp/LSP-svelte).

## Swift

Follow installation instructions on [LSP-SourceKit](https://github.com/sublimelsp/LSP-SourceKit).

## TAGML

Follow installation instructions on [LSP-tagml](https://github.com/HuygensING/LSP-tagml).

## Terraform

1. Install the [Terraform](https://packagecontrol.io/packages/Terraform) package from Package Control for syntax highlighting.
2. Download [terraform-lsp](https://github.com/juliosueiras/terraform-lsp/releases) binary and make it available in your PATH.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"terraform"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "terraform": {
                "enabled": true,
                "command": ["terraform-lsp"],
                "selector": "source.terraform"
            }
        }
    }
    ```

## TypeScript / JavaScript

Follow installation instructions on [LSP-typescript](https://github.com/sublimelsp/LSP-typescript).

## Vue

Follow installation instructions on [LSP-vue](https://github.com/sublimelsp/LSP-vue).

## XML

Follow installation instructions on [LSP-lemminx](https://github.com/sublimelsp/LSP-lemminx).

## YAML

Follow installation instructions on [LSP-yaml](https://github.com/sublimelsp/LSP-yaml).
