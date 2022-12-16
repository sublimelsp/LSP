# Language Servers

Follow the setup steps for a language server to get it up and running.

If you encounter problems, consult the [common issues](troubleshooting.md#common-problems) page or search the [LSP issues](https://github.com/sublimelsp/LSP/issues) before opening new ones.

If there are no setup steps for a language server on this page, but a [language server implementation](https://microsoft.github.io/language-server-protocol/implementors/servers/) exist, follow the guide for [creating a client configuration](./client_configuration.md). Pull requests for adding a new client configuration are welcome.

!!! tip "We recommend installing [LSP-json](https://packagecontrol.io/packages/LSP-json)."
    [LSP-json](https://packagecontrol.io/packages/LSP-json) provides completions and diagnostics when editing JSON files that adhere to a JSON schema.

!!! info "For legacy ST3 docs, see [lsp.readthedocs.io](https://lsp.readthedocs.io)."


## Angular

Follow installation instructions on [LSP-angular](https://github.com/sublimelsp/LSP-angular).

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

1. Install the [D Language Server](https://github.com/Pure-D/serve-d#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"serve-d"` client configuration to the `"clients"`:

    ```json
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

## F\#

1. Install the [F#](https://packagecontrol.io/packages/F%23) package from Package Control for syntax highlighting.
2. Make sure you have installed the latest [.NET SDK](https://dotnet.microsoft.com/download).
3. Install the [FsAutoComplete](https://github.com/fsharp/FsAutoComplete) from command prompt using the following command:

    ```
    dotnet tool install --global fsautocomplete
    ```

4. Open `Preferences > Package Settings > LSP > Settings` and add the `"fsautocomplete"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "fsautocomplete": {
                "enabled": true,
                "command": ["fsautocomplete", "--background-service-enabled"],
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

Follow installation instructions on [LSP-gopls](https://github.com/sublimelsp/LSP-gopls).

!!! info "Visit [gopls repo](https://github.com/golang/tools/tree/master/gopls) for more info."
    Enable multi-module workspace support by setting the `experimentalWorkspaceModule` to `true`. Most features will work across modules, but some, such as `goimports`, will not work as expected. Please note that this setting is still very experimental.

## GDScript (Godot Engine)

1. Install the [GDScript (Godot Engine)](https://packagecontrol.io/packages/GDScript%20(Godot%20Engine)) package from Package Control for syntax highlighting.
2. Launch the Godot Editor on the project you are working on and leave it running.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"godot-lsp"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "godot-lsp": {
                "enabled": true,
                "command": ["/PATH/TO/godot-editor.exe"], // Update the PATH
                "tcp_port": 6008,
                "selector": "source.gdscript",
            }
        }
    }
    ```

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

## JavaScript/TypeScript

See also [Vue](#vue).

There are multiple options:

### Deno

Follow installation instructions on [LSP-Deno](https://github.com/sublimelsp/LSP-Deno).

### ESLint

Follow installation instructions on [LSP-eslint](https://github.com/sublimelsp/LSP-eslint).

### Flow

Follow installation instructions on [LSP-flow](https://github.com/sublimelsp/LSP-flow).

### quick-lint-js

1. Install the [quick-lint-js LSP server](https://quick-lint-js.com/install/cli/) for JavaScript.
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"quick-lint-js"` client configuration to the `"clients"`:

    ```json
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

### TypeScript

Follow installation instructions on [LSP-typescript](https://github.com/sublimelsp/LSP-typescript).

## JSON

Follow installation instructions on [LSP-json](https://github.com/sublimelsp/LSP-json).

## Julia

Follow installation instructions on [LSP-julia](https://github.com/sublimelsp/LSP-julia).

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

Spell check can be provided by [LSP-ltex-ls](https://github.com/LDAP/LSP-ltex-ls).

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


    ```json
    {
        "clients": {
            "markmark": {
                "enabled": true,
		"command": [
			"markmark-lsp",
			"--stdio"
		],
		"selector": "text.html.markdown"
            }
        }
    }
    ```


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

### Phpactor

1. Install [Phpactor globally](https://phpactor.readthedocs.io/en/master/usage/standalone.html#installation-global).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"phpactor"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "phpactor": {
                "enabled": true,
                "command": ["PATH/TO/phpactor", "language-server"],
                "selector": "source.php"
            }
        }
    }
    ```

## PowerShell

Follow installation instructions on [LSP-PowerShellEditorServices](https://github.com/sublimelsp/LSP-PowerShellEditorServices).

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

Follow installation instructions on [LSP-rust-analyzer](https://github.com/sublimelsp/LSP-rust-analyzer).

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

## Steep

1. Add the steep gem into your Gemfile and install it

    ```bash
    bundle install
    ```

2. Binstub steep executable

    ```bash
    steep binstub
    ```

3. Open `Preferences > Package Settings > LSP > Settings` and add the `"steep"` client configuration to the `"clients"`:

    ```json
    {
        "clients": {
            "steep": {
                "command": ["bin/steep", "langserver"],
                "selector": "source.ruby | text.html.ruby",
            }
        }
    }
    ```

4. Activate server for the currect project - open Command Palette `LSP: Enable Language Server in Project > steep`

## Stylelint

Follow installation instructions on [LSP-stylelint](https://github.com/sublimelsp/LSP-stylelint).

## Svelte

Follow installation instructions on [LSP-svelte](https://github.com/sublimelsp/LSP-svelte).

## Swift

Follow installation instructions on [LSP-SourceKit](https://github.com/sublimelsp/LSP-SourceKit).

## TAGML

Follow installation instructions on [LSP-tagml](https://github.com/HuygensING/LSP-tagml).

## Tailwind CSS

Follow installation instructions on [LSP-tailwindcss](https://github.com/sublimelsp/LSP-tailwindcss).

## Terraform

Follow installation instructions on [LSP-terraform](https://github.com/sublimelsp/LSP-terraform).

## Vue

There are multiple options:

### Vetur

Follow installation instructions on [LSP-vue](https://github.com/sublimelsp/LSP-vue).

### Volar

Follow installation instructions on [LSP-volar](https://github.com/sublimelsp/LSP-volar).

## Vala

1. Install the [Vala-TMBundle](https://packagecontrol.io/packages/Vala-TMBundle) package from Package Control to add Vala syntax highlighting and for Vala files to be reconginsed.
2. Install the [Vala Language Server](https://github.com/Prince781/vala-language-server)
3. Add Vala Langauge Server to LSP settings:

    ```json
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
