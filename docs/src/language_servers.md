# Language Servers

Follow the setup steps for a language server to get it up and running.

If you encounter problems, consult the [common issues](troubleshooting.md#common-problems) page or search the [LSP issues](https://github.com/sublimelsp/LSP/issues) before opening new ones.

If there are no setup steps for a language server on this page, but a [language server implementation](https://microsoft.github.io/language-server-protocol/implementors/servers/) exist, follow the guide for [creating a client configuration](./client_configuration.md). Pull requests for adding a new client configuration are welcome.

!!! tip "We recommend installing [LSP-json](https://packagecontrol.io/packages/LSP-json)."
    [LSP-json](https://packagecontrol.io/packages/LSP-json) provides completions and diagnostics when editing JSON files that adhere to a JSON schema.

!!! info "For legacy ST3 docs, see [lsp.readthedocs.io](https://lsp.readthedocs.io)."


## Angular

Follow installation instructions on [LSP-angular](https://github.com/sublimelsp/LSP-angular).

## Assembly

1. Install `asm-lsp` via Cargo (see [github:bergercookie/asm-lsp](https://github.com/bergercookie/asm-lsp)):

    ```sh
    cargo install asm-lsp
    ```

2. Install the [x86 and x86_64 Assembly](https://packagecontrol.io/packages/x86%20and%20x86_64%20Assembly) package from Package Control.

3. Open `Preferences > Package Settings > LSP > Settings` and add the `"asm-lsp"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "asm-lsp": {
                "enabled": true,
                "command": ["asm-lsp"],
                "selector": "source.asm | source.assembly"
            }
        }
    }
    ```

## Bash

Follow installation instructions on [LSP-bash](https://github.com/sublimelsp/LSP-bash).

Also see [Shell](#shell).

## Bicep

Follow installation instructions on [LSP-Bicep](https://github.com/sublimelsp/LSP-Bicep).

## C/C++

Follow installation instructions on [LSP-clangd](https://github.com/sublimelsp/LSP-clangd).

## C\#

Follow installation instructions on [LSP-OmniSharp](https://github.com/sublimelsp/LSP-OmniSharp).

## Clojure

1. Download [clojure-lsp](https://clojure-lsp.io/installation/).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"clojure-lsp"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "clojure-lsp": {
                "enabled": true,
                "command": ["/PATH/TO/clojure-lsp"], // Update the PATH
                "selector": "source.clojure",
                "initializationOptions": {}
            }
        }
    }
    ```

!!! info "See available [initializationOptions](https://clojure-lsp.io/settings/#initializationoptions)."

## CSS

Follow installation instructions on [LSP-css](https://github.com/sublimelsp/LSP-css).

## D

1. Install the [D Language Server](https://github.com/Pure-D/serve-d#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"serve-d"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "serve-d": {
                "enabled": true,
                "command": ["C:/Users/MY_NAME_HERE/AppData/Roaming/code-d/bin/serve-d.exe"],
                "selector": "source.d",
                "settings": {
                    "d.dcdServerPath": "C:/Users/MY_NAME_HERE/AppData/Roaming/code-d/bin/dcd-server.exe",
                    "d.dcdClientPath": "C:/Users/MY_NAME_HERE/AppData/Roaming/code-d/bin/dcd-client.exe",
                }
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

    ```jsonc
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

## F\#

1. Install the [F#](https://packagecontrol.io/packages/F%23) package from Package Control for syntax highlighting.
2. Make sure you have installed the latest [.NET SDK](https://dotnet.microsoft.com/download).
3. Install the [FsAutoComplete](https://github.com/fsharp/FsAutoComplete) from command prompt using the following command:

    ```
    dotnet tool install --global fsautocomplete
    ```

4. Open `Preferences > Package Settings > LSP > Settings` and add the `"fsautocomplete"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "fsautocomplete": {
                "enabled": true,
                "command": ["fsautocomplete"],
                "selector": "source.fsharp",
                "initializationOptions": {
                    "AutomaticWorkspaceInit": true
                }
            }
        }
    }
    ```

!!! info "A note about .NET Tools and $PATH"
    If the `fsautocomplete` executable isn't on your $PATH after installing it globally, ensure the .NET global tools location (by default `$HOME/.dotnet/tools`) is on your $PATH.

## Fortran

1. Install the [ModernFortran](https://packagecontrol.io/packages/ModernFortran) or the [Fortran](https://packagecontrol.io/packages/Fortran) package from Package Control for syntax highlighting.
2. Install the [fortls](https://fortls.fortran-lang.org/quickstart.html#download) language server.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"fortls"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "fortls": {
                "enabled": true,
                "command": ["fortls", "--notify_init"],
                "selector": "source.fortran | source.modern-fortran | source.fixedform-fortran"
            }
        }
    }
    ```

!!! info "See available [configuration options](https://fortls.fortran-lang.org/options.html)."

## Go

Follow installation instructions on [LSP-gopls](https://github.com/sublimelsp/LSP-gopls).

!!! info "Visit [gopls repo](https://github.com/golang/tools/tree/master/gopls) for more info."
    Enable multi-module workspace support by setting the `experimentalWorkspaceModule` to `true`. Most features will work across modules, but some, such as `goimports`, will not work as expected. Please note that this setting is still very experimental.

## GDScript (Godot Engine)

1. Install the [GDScript (Godot Engine)](https://packagecontrol.io/packages/GDScript%20(Godot%20Engine)) package from Package Control for syntax highlighting.
2. Launch the Godot Editor on the project you are working on and leave it running.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"godot-lsp"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "godot-lsp": {
                "enabled": true,
                "command": ["/PATH/TO/godot-editor.exe"], // Update the PATH
                "tcp_port": 6005, // Older versions of Godot(3.x) use port 6008
                "selector": "source.gdscript",
            }
        }
    }
    ```

If you encounter high cpu load or any other issues you can try omitting the [command] line, and ensure the godot editor is running while you work in sublime.

## GraphQL

Follow installation instructions on [LSP-graphql](https://github.com/sublimelsp/LSP-graphql).

## Haskell

1. Install [haskell-language-server](https://github.com/haskell/haskell-language-server).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"haskell-language-server"` client configuration to the `"clients"`:

    ```jsonc
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

## Helm

1. Install [helm-ls](https://github.com/mrjosh/helm-ls).
2. (Optional & recommended) Install [yaml-language-server](https://github.com/mrjosh/helm-ls?tab=readme-ov-file#integration-with-yaml-language-server).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"helm-ls"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "helm-ls": {
                "enabled": true,
                "command": ["helm_ls", "serve"],
                "selector": "source.yaml.go", // Requires ST 4181+. Use `source.yaml` otherwise.
            },
        },
    }
    ```

Note that the YAML language server on its own does not function properly for Helm files,
which is why helm-ls interfaces with it directly.
The default configuration of [LSP-yaml](#yaml) disables itself for Go-templated files.

## HTML

Follow installation instructions on [LSP-html](https://github.com/sublimelsp/LSP-html).

## Java

Follow installation instructions on [LSP-jdtls](https://github.com/sublimelsp/LSP-jdtls).

## JavaScript/TypeScript

See also [Vue](#vue).

There are multiple options:

### Biome

Follow installation instructions on [LSP-biome](https://github.com/sublimelsp/LSP-biome).

### Deno

Follow installation instructions on [LSP-Deno](https://github.com/sublimelsp/LSP-Deno).

### ESLint

Follow installation instructions on [LSP-eslint](https://github.com/sublimelsp/LSP-eslint).

### Flow

Follow installation instructions on [LSP-flow](https://github.com/sublimelsp/LSP-flow).

### quick-lint-js

1. Install the [quick-lint-js LSP server](https://quick-lint-js.com/install/cli/) for JavaScript.
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"quick-lint-js"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "quick-lint-js": {
                "command": ["quick-lint-js", "--lsp-server"],
                "enabled": true,
                "selector": "source.js"
            }
        }
    }
    ```

### TypeScript Language Server

Follow installation instructions on [LSP-typescript](https://github.com/sublimelsp/LSP-typescript).

## JSON

Follow installation instructions on [LSP-json](https://github.com/sublimelsp/LSP-json).

## Julia

Follow installation instructions on [LSP-julia](https://github.com/sublimelsp/LSP-julia).

## Kotlin

1. Install the [Kotlin](https://packagecontrol.io/packages/Kotlin) package from Package Control for syntax highlighting.
2. Install the [Kotlin Language Server](https://github.com/fwcd/KotlinLanguageServer) (requires [building](https://github.com/fwcd/KotlinLanguageServer/blob/master/BUILDING.md) first).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"kotlinls"` client configuration to the `"clients"`:

    ```jsonc
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

### TexLab

Follow installation instructions on [LSP-TexLab](https://github.com/sublimelsp/LSP-TexLab).

### LTeX

Spell check can be provided by [LSP-ltex-ls](https://github.com/sublimelsp/LSP-ltex-ls).

### Digestif

1. Follow [installation instructions for Digestif](https://github.com/astoff/digestif#installation) to install the server, and make sure it is available in your PATH.
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"digestif"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "digestif": {
                "enabled": true,
                "command": ["digestif"],
                "selector": "text.tex.latex"
            }
        }
    }
    ```

3. To enable auto-completions for the relevant situations in LaTeX files, adjust Sublime's `"auto_complete_selector"` setting (`Preferences > Settings`); for example

    ```jsonc
    {
        "auto_complete_selector": "meta.tag, source - comment - string.quoted.double.block - string.quoted.single.block - string.unquoted.heredoc, text.tex constant.other.citation, text.tex constant.other.reference, text.tex support.function, text.tex variable.parameter.function",
    }
    ```

## Lisp

1. Install [cc-lsp](https://github.com/cxxxr/cl-lsp) using Roswell.
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"cc-lsp"` client configuration to the `"clients"`:

    ```jsonc
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

## Leo

Follow installation instructions on [LSP-leo](https://github.com/sublimelsp/LSP-leo).

## Lua

Follow installation instructions on [LSP-lua](https://github.com/sublimelsp/LSP-lua).

## Markdown

Spell check can be provided by [LSP-ltex-ls](https://github.com/LDAP/LSP-ltex-ls).

### markmark

[Markmark](https://github.com/nikku/markmark) is a language server for Markdown files, supporting go to definition / references [and more](https://github.com/nikku/markmark#features).

1. [Install Markmark](https://github.com/nikku/markmark#installation) (requires `Node >= 16`)
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"markmark"` client configuration to the `"clients"`:


    ```jsonc
    {
        "clients": {
            "markmark": {
                "enabled": true,
                "command": ["markmark-lsp", "--stdio"],
                "selector": "text.html.markdown"
            }
        }
    }
    ```

### Marksman

An LSP server for Markdown that provides completion, go to definition, find references, diagnostics, and more.

Follow installation instructions on [LSP-marksman](https://github.com/sublimelsp/LSP-marksman).

## Nim

Follow installation instructions on [LSP-nimlangserver](https://github.com/sublimelsp/LSP-nimlangserver).

## OCaml/Reason

1. Install the [Reason](https://packagecontrol.io/packages/Reason) package from Package Control for syntax highlighting.
2. Install the [Reason Language Server](https://github.com/jaredly/reason-language-server#sublime-text).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"reason"` client configuration to the `"clients"`:


    ```jsonc
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

## Odin

Follow installation instructions on [ols](https://github.com/DanielGavin/ols/).

## Perl

1. Install [Perl Navigator](https://github.com/bscan/PerlNavigator). The below example configuration assumes global NPM installation.
2. Install Perl::Critic, Perl::Tidy, etc. as required.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"perlnavigator"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "perlnavigator": {
                "enabled": true,
                "command": [
                    "/path/to/your/node", 
                    "/path/to/your/globally/installed/perlnavigator",
                    "--stdio"
                ],
                "selector": "source.perl",
                "settings": {
                    // "perlnavigator.perltidyProfile": "~/.perltidyrc",
                    // "perlnavigator.perlcriticProfile": "~/.perlcriticrc",
                    // "perlnavigator.perlEnvAdd": true,
                    // "perlnavigator.perlEnv": {
                    //     "KOHA_CONF": "/home/user/git/KohaCommunity/t/data/koha-conf.xml",
                    // },
                    // "perlnavigator.perlPath": "~/perl5/perlbrew/perls/perl-5.38.2/bin",
                    // "perlnavigator.perlcriticSeverity": 1,
                    // "perlnavigator.perlcriticEnabled": true,
                    // "perlnavigator.enableWarnings": true,
                    "perlnavigator.includePaths": [
                        // Used for syntax checking, typically local project roots.
                        // NOT used for finding installed modules such as perlcritic/perltidy/perlimports.
                        // Supports "$workspaceFolder", no need to include "$workspaceFolder/lib/".
                    ],
                    "perlnavigator.perlParams": [
                        // This is a list of arguments always passed to Perl.
                        // Does not support $workspaceFolder.
                        // Useful for finding perlcritic/perltidy/perlimports.
                        // "-I/path/to/local/perl5/bin"
                    ]
                }
            }
        },
    }
    ```

## PromQL

Follow installation instructions on [LSP-promql](https://github.com/prometheus-community/sublimelsp-promql).

## PHP

There are multiple options:

### Intelephense

Follow installation instructions on [LSP-intelephense](https://github.com/sublimelsp/LSP-intelephense).

### Phpactor

1. Install [Phpactor globally](https://phpactor.readthedocs.io/en/master/usage/standalone.html#installation-global).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"phpactor"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "phpactor": {
                "enabled": true,
                "command": ["PATH/TO/phpactor", "language-server"],
                "selector": "embedding.php",
                "priority_selector": "source.php",
            }
        }
    }
    ```

## PowerShell

Follow installation instructions on [LSP-PowerShellEditorServices](https://github.com/sublimelsp/LSP-PowerShellEditorServices).

## Python

There are multiple options:

### Pyright

> A full-featured, standards-based static type checker for Python. It is designed for high performance and can be used with large Python source bases.

Follow installation instructions on [LSP-pyright](https://github.com/sublimelsp/LSP-pyright).

### Python LSP Server (pylsp)

> A [Jedi](https://github.com/davidhalter/jedi)-powered language server that also supports running various linters through built-in plugins.

Follow installation instructions on [LSP-pylsp](https://github.com/sublimelsp/LSP-pylsp).

### LSP-ruff

> An extremely fast Python linter and code transformation tool, written in Rust.

Follow installation instructions on [LSP-ruff](https://github.com/sublimelsp/LSP-ruff).

## R

Follow installation instructions on [R-IDE](https://github.com/REditorSupport/sublime-ide-r#installation).

## Racket

1. Install the [Racket](https://packagecontrol.io/packages/Racket) package from Package Control for syntax highlighting.
2. Follow the instructions for installation at [racket-langserver](https://github.com/jeapostrophe/racket-langserver).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"racket-langserver"` client configuration to the `"clients"`:

```jsonc
{
    "clients": {
        "racket-langserver": {
            "enabled": true,
            "command": ["racket", "-l", "racket-langserver"],
            "selector": "source.racket"
        }
    }
}
```

## Ruby / Ruby on Rails

There are multiple options:

### Solargraph

1. Install [solargraph](https://github.com/castwide/solargraph#installation).

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"ruby"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "ruby": {
                "enabled": true,
                "command": ["solargraph", "stdio"],
                "selector": "source.ruby | text.html.ruby",
                "initializationOptions": {
                    "diagnostics": true
                }
            }
        }
    }
    ```

### Sorbet

1. Install the `sorbet` and `sorbet-runtime` gem (see [github:sorbet/sorbet](https://github.com/sorbet/sorbet)):

    ```sh
    gem install sorbet
    gem install sorbet-runtime
    ```

    If you have a Gemfile, using bundler, add sorbet and sorbet-runtime to your Gemfile and run:

    ```sh
    bundle install
    ```

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"sorbet"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "sorbet": {
                "enabled": true,
                "command": ["srb", "tc", "--typed", "true", "--enable-all-experimental-lsp-features", "--lsp", "--disable-watchman", "."],
                "selector": "source.ruby | text.html.ruby",
            }
        }
    }
    ```

### Stimulus LSP

1. Install the `stimulus-language-server` package (see [github:marcoroth/stimulus-lsp](https://github.com/marcoroth/stimulus-lsp)):

    ```sh
    npm install -g stimulus-language-server
    ```

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"stimulus"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "stimulus": {
                "enabled": true,
                "command": ["stimulus-language-server", "--stdio"],
                "selector": "text.html.rails"
            }
        }
    }
    ```

### Ruby LSP

1. Install the `ruby-lsp` gem (see [github:Shopify/ruby-lsp](https://github.com/Shopify/ruby-lsp)):

    ```sh
    gem install ruby-lsp
    ```

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"ruby-lsp"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "ruby-lsp": {
                "enabled": true,
                "command": ["ruby-lsp"],
                "selector": "source.ruby | text.html.ruby",
                "initializationOptions": {
                    "enabledFeatures": {
                        "diagnostics": true
                    },
                    "experimentalFeaturesEnabled": true
                }
            }
        }
    }
    ```

### Steep

1. Install the `steep` gem (see [github:soutaro/steep](https://github.com/soutaro/steep)):

    ```sh
    gem install steep
    ```

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"steep"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "steep": {
                "enabled": true,
                "command": ["steep", "langserver"],
                "selector": "source.ruby | text.html.ruby",
            }
        }
    }
    ```

## Rust

Follow installation instructions on [LSP-rust-analyzer](https://github.com/sublimelsp/LSP-rust-analyzer).

## Sass

Follow installation instructions on [LSP-some-sass](https://github.com/sublimelsp/LSP-some-sass).

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

    ```jsonc
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

## Solidity

1. Install the [Ethereum](https://packagecontrol.io/packages/Ethereum) package from Package Control for syntax highlighting.
2. Install the [github:NomicFoundation/hardhat-vscode](https://github.com/NomicFoundation/hardhat-vscode/tree/development/server) language server.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"solidity"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "solidity": {
                "enabled": true,
                "command": ["nomicfoundation-solidity-language-server", "--stdio"],
                "selector": "source.solidity"
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

## SystemVerilog

1. Install the [SystemVerilog](https://packagecontrol.io/packages/SystemVerilog) package from Package Control for syntax highlighting.
2. Make sure you install the latest version of [Verible](https://github.com/chipsalliance/verible).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"verible"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "verible": {
                "enabled": true,
                "command": [
                    "/PATH/TO/verible-verilog-ls"
                ],
                "selector": "source.systemverilog"
            }
        }
    }
    ```

## TAGML

Follow installation instructions on [LSP-tagml](https://github.com/HuygensING/LSP-tagml).

## Tailwind CSS

Follow installation instructions on [LSP-tailwindcss](https://github.com/sublimelsp/LSP-tailwindcss).

## Terraform

Follow installation instructions on [LSP-terraform](https://github.com/sublimelsp/LSP-terraform).

## Toit

1. Install the [Toit](https://packagecontrol.io/packages/Toit) package from Package Control for syntax highlighting.
2. Install the [Jaguar Language Server](https://github.com/toitlang/jaguar).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"jag"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "jag": {
                "enabled": true,
                "command": ["jag" "lsp"],
                "selector": "source.toit"
            }
        }
    }
    ```

## Twig

Follow installation instructions on [LSP-twiggy](https://github.com/sublimelsp/LSP-twiggy).

## TypeScript

See [Javascript/TypeScript](#javascripttypescript).

## Typst

1. Install the [Typst](https://packagecontrol.io/packages/Typst) package from Package Control for syntax highlighting.
2. Optional: to enable auto-completions for the relevant situations in Typst files, adjust Sublime's `"auto_complete_selector"` and/or `"auto_complete_triggers"` setting (`Preferences > Settings`); for example

    ```jsonc
    {
        "auto_complete_triggers":
        [
            {"selector": "text.html, text.xml", "characters": "<"},
            {"selector": "punctuation.accessor", "rhs_empty": true},
            {"selector": "text.typst", "characters": "#", "rhs_empty": true},
        ],
    }
    ```

There are 2 available languages servers.

### Tinymist

This server has more features, like go to definition, rename, etc.

1. Install [tinymist](https://github.com/Myriad-Dreamin/tinymist).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"tinymist"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "tinymist": {
                "enabled": true,
                "command": ["path/to/tinymist"],  // adjust this path according to your platform/setup
                "selector": "text.typst",
                // you can provide some initialization options:
                "initializationOptions": {
                    "exportPdf": "never",
                    "typstExtraArgs": [],
                },
            }
        }
    }
    ```

3. Optional: to enable some useful commands provided by language server, add the following to the `*.sublime-commands`:

    <!-- how to call: see https://github.com/Myriad-Dreamin/tinymist/blob/main/editors/vscode/src/extension.ts -->
    ```jsonc title="Packages/User/Default.sublime-commands"
    [
        // ...
        {
            "caption": "tinymist - Pin the main file to the currently opened document",
            "command": "lsp_execute",
            "args": {
                "session_name": "tinymist",
                "command_name": "tinymist.pinMain",
                "command_args": ["${file}"]
            }
        },
        {
            "caption": "tinymist - Unpin the main file",
            "command": "lsp_execute",
            "args": {
                "session_name": "tinymist",
                "command_name": "tinymist.pinMain",
                "command_args": [null]
            }
        },
    ]
    ```

### Typst-lsp

1. Install [typst-lsp](https://github.com/nvarner/typst-lsp/releases).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"typst-lsp"` client configuration to the `"clients"`:

    ```jsonc
    {
        "clients": {
            "typst-lsp": {
                "enabled": true,
                "command": ["path/to/typst-lsp"],  // adjust this path according to your platform/setup
                "selector": "text.typst"
            }
        }
    }
    ```

3. Optional: to enable some useful commands provided by language server, add the following to the `*.sublime-commands`:

    <!-- how to call: see https://github.com/nvarner/typst-lsp/blob/master/editors/vscode/src/extension.ts -->
    ```jsonc title="Packages/User/Default.sublime-commands"
    [
        // ...
        {
            "caption": "typst-lsp - Pin the main file to the currently opened document",
            "command": "lsp_execute",
            "args": {
                "session_name": "typst-lsp",
                "command_name": "typst-lsp.doPinMain",
                "command_args": ["${file_uri}"]
            }
        },
        {
            "caption": "typst-lsp - Unpin the main file",
            "command": "lsp_execute",
            "args": {
                "session_name": "typst-lsp",
                "command_name": "typst-lsp.doPinMain",
                "command_args": ["detached"]
            }
        },
    ]
    ```

## Vue

There are multiple options:

### Vue Language Server

Recommended, actively maintained package based on [vuejs/language-tools](https://github.com/vuejs/language-tools).

Follow installation instructions on [LSP-vue](https://github.com/sublimelsp/LSP-vue).

### Volar

Based on 1.x version of Volar (later renamed to Vue Language Server). Not recommended.

Follow installation instructions on [LSP-volar](https://github.com/sublimelsp/LSP-volar).

### Vetur

No longer maintained, not compatible with TypeScript 5+ or new Vue versions.

Follow installation instructions on [LSP-vetur](https://github.com/sublimelsp/LSP-vetur).

## Vala

1. Install the [Vala-TMBundle](https://packagecontrol.io/packages/Vala-TMBundle) package from Package Control to add Vala syntax highlighting and for Vala files to be reconginsed.
2. Install the [Vala Language Server](https://github.com/Prince781/vala-language-server)
3. Add Vala Langauge Server to LSP settings:

    ```jsonc
    {
        "clients": {
            "vala-language-server": {
                "enabled": true,
                "command": [
                    "/path/to/vala-language-server"
                ],
                "selector": "source.vala | source.genie"
            },
        },
    }
    ```

!!! warning "Only works for certain project types. Visit [vala-language-server repo](https://github.com/Prince781/vala-language-server) for more details."

## XML

Follow installation instructions on [LSP-lemminx](https://github.com/sublimelsp/LSP-lemminx).

## YAML

Follow installation instructions on [LSP-yaml](https://github.com/sublimelsp/LSP-yaml).
