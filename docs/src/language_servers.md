# Language Servers

Follow the setup steps for a language server to get it up and running.

If you encounter problems, consult the [common issues](troubleshooting.md#common-problems) page or search the [LSP issues](https://github.com/sublimelsp/LSP/issues) before opening new ones.

If there are no setup steps for a language server on this page, but a [language server implementation](https://microsoft.github.io/language-server-protocol/implementors/servers/) exist, follow the guide for [creating a client configuration](./guides/client_configuration.md). Pull requests for adding a new client configuration are welcome.

!!! tip "We recommend installing [LSP-json](https://packagecontrol.io/packages/LSP-json)."
    [LSP-json](https://packagecontrol.io/packages/LSP-json) provides completions and diagnostics when editing JSON files that adhere to a JSON schema.

!!! info "For legacy ST3 docs, see [lsp.readthedocs.io](https://lsp.readthedocs.io)."


## Angular

Follow installation instructions on [LSP-angular](https://github.com/sublimelsp/LSP-angular).

## Bash

Follow installation instructions on [LSP-bash](https://github.com/sublimelsp/LSP-bash).

Also see [Shell](#shell).

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

Follow installation instructions on [LSP-pylsp](https://github.com/sublimelsp/LSP-pylsp).

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

## Shell

1. Install [shellcheck](https://github.com/koalaman/shellcheck) (follow instructions in the repo).
2. Install the [diagnostic-languageserver](https://github.com/iamcco/diagnostic-languageserver) server.

    ```sh
    # with NPM
    npm i -g diagnostic-languageserver
    # or with Yarn
    yarn global add diagnostic-languageserver
    ```
3.  Open `Preferences > Package Settings > LSP > Settings` and add the `"diagnostic-ls"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "diagnostic-ls": {
                "enabled": true,
                "command": ["diagnostic-languageserver", "--stdio"],
                "selector": "source.shell.bash",
                "initializationOptions": {
                    "linters": {
                        "shellcheck": {
                            "command": "shellcheck",
                            "args": ["--format=json", "-"],
                            "debounce": 100,
                            "formatLines": 1,
                            "offsetLine": 0,
                            "offsetColumn": 0,
                            "sourceName": "shellcheck",
                            "parseJson": {
                                "line": "line",
                                "column": "column",
                                "endLine": "endLine",
                                "endColumn": "endColumn",
                                "security": "level",
                                "message": "\\${message} [\\${code}]",
                            },
                            "securities": {
                                "error": "error",
                                "warning": "warning",
                                "note": "info",
                            },
                        }
                    },
                    "formatters": {},
                    "filetypes": {
                        "shellscript": "shellcheck",
                    }
                }
            }
        }
    }
    ```

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

## Vala

1. Install the [Vala-TMBundle](https://packagecontrol.io/packages/Vala-TMBundle) package from Package Control to add Vala syntax highlighting and for Vala files to be reconginsed.
2. Install the [Vala Language Server](https://github.com/Prince781/vala-language-server)
3. Add Vala Langauge Server to LSP settings:

    ```json
    {
        "clients": {
            "vala-language-server": {
                "command": [
                    "/path/to/vala-language-server"
                ],
                "selector": "source.vala | source.genie"
            },
        },
    }
    ```

4. Enable the Vala Langauge Server for the project by going to `Tools > LSP > Enable Language Server In Project...`
5. For the server to fully understand your code, you will need to generate a `compile_commands.json` file or build your project with [meson](https://mesonbuild.com/).

## XML

Follow installation instructions on [LSP-lemminx](https://github.com/sublimelsp/LSP-lemminx).

## YAML

Follow installation instructions on [LSP-yaml](https://github.com/sublimelsp/LSP-yaml).
