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

1. Download a .NET SDK. The ".NET Core" SDK is known to *not* work on macOS.
2. If on macOS/Linux, download the Mono Runtime in order to be able to run .NET executables and DLLs.
3. Download [omnisharp](https://github.com/OmniSharp/omnisharp-roslyn/releases).
4. Open `Preferences > Package Settings > LSP > Settings` and add the `"omnisharp"` client configuration to the `"clients"`:

=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "omnisharp": {
                "enabled": true,
                "command": [
                    "mono", // mono is only necessary for macOS/Linux
                    "/home/tb/prebuilt/omnisharp/OmniSharp.exe",
                    "-lsp"
                ],
                "env": {
                    // This may or may not be necessary, please report your findings!
                    "FrameworkPathOverride": "/path/to/omnisharp/.msbuild/Current"
                },
                "selector": "source.cs"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "omnisharp": {
                "enabled": true,
                "command": [
                    "mono", // mono is only necessary for macOS/Linux
                    "/home/tb/prebuilt/omnisharp/OmniSharp.exe",
                    "-lsp"
                ],
                "env": {
                    // This may or may not be necessary, please report your findings!
                    "FrameworkPathOverride": "/path/to/omnisharp/.msbuild/Current"
                },
                "languageId": "csharp",
                "scopes": ["source.cs"],
                "syntaxes": ["Packages/C#/C#.sublime-syntax"]
            }
        }
    }
    ```

## Clojure

1. Download [clojure-lsp](https://github.com/snoe/clojure-lsp#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"clojure-lsp"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "clojure-lsp": {
                "enabled": true,
                "command": ["java", "-jar", "/PATH/TO/clojure-lsp"], // Update the PATH
                "languageId": "clojure",
                "scopes": ["source.clojure"],
                "syntaxes": ["Packages/Clojure/Clojure.sublime-syntax"],
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

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "dls": {
                "enabled": true,
                "command": ["/PATH/TO/DLS_EXECUTABLE"], // Update the PATH
                "languageId": "d",
                "scopes": ["source.d"],
                "syntaxes": ["Packages/D/D.sublime-syntax"]
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

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "erlang-ls": {
                "enabled": true,
                "command": [ "/path/to/my/erlang_ls", "--transport", "stdio" ],
                "languageId": "erlang",
                "scopes": [ "source.erlang" ],
                "syntaxes": ["Packages/Erlang/Erlang.sublime-syntax"]
            }
        }
    }
    ```

## ESLint

Follow installation instructions on [LSP-eslint](https://github.com/sublimelsp/LSP-eslint).

## Flow

1. Install [flow](https://github.com/facebook/flow#using-flow).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"flow"` client configuration to the `"clients"`:

=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "flow": {
                "enabled": true,
                "command": ["flow", "lsp"],
                "selector": "source.js | source.js.react"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "flow": {
                "enabled": true,
                "command": ["flow", "lsp"],
                "languageId": "javascript",
                "scopes": ["source.js"],
                "syntaxes": ["Packages/Babel/JavaScript (Babel).sublime-syntax", "Packages/JavaScript/JavaScript.sublime-syntax"]
            }
        }
    }
    ```

## Fortran

1. Install the [ Fortran](https://packagecontrol.io/packages/Fortran) package from Package Control for syntax highlighting.
2. Install the [Fortran Language Server](https://github.com/hansec/fortran-language-server#installation).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"fortls"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "fortls": {
                "enabled": true,
                "command": ["fortls"],
                "languageId": "fortran",
                "scopes": ["source.modern-fortran", "source.fixedform-fortran"],
                "syntaxes": [
                    "Packages/Fortran/grammars/FortranModern.sublime-syntax",
                    "Packages/Fortran/grammars/FortranFixedForm.sublime-syntax"
                ]
            }
        }
    }
    ```

!!! info "See available [configuration options](https://github.com/hansec/fortran-language-server#language-server-settings)."
    For example set `"command": ["fortls", "--lowercase_intrinsics"]` to use lowercase for autocomplete suggestions.

## Go

1. Install [gopls](https://github.com/golang/tools/blob/master/gopls/doc/user.md#installation).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"gopls"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "gopls": {
                "enabled": true,
                "command": ["gopls"],
                "languageId": "go",
                "scopes": ["source.go"],
                "syntaxes": [
                    "Packages/Go/Go.sublime-syntax",
                    "Packages/GoSublime/syntax/GoSublime-Go-Recommended.sublime-syntax"
                ],
                "initializationOptions": {
                    "experimentalWorkspaceModule": false
                }
            },
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

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "haskell-language-server": {
                "enabled": true,
                "command": ["haskell-language-server-wrapper", "--lsp"],
                "languageId": "haskell",
                "scopes": ["source.haskell"],
                "syntaxes": ["Packages/Haskell/Haskell.sublime-syntax"]
            }
        }
    }
    ```

## HTML

Follow installation instructions on [LSP-html](https://github.com/sublimelsp/LSP-html).

## Java

1. Download and extract Eclipse's [jdt-ls](https://download.eclipse.org/jdtls/snapshots/jdt-language-server-latest.tar.gz).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"jdtls"` client configuration to the `"clients"`:


=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "jdtls": {
                "enabled": true,
                "command": [
                    "java",
                    "--add-modules=ALL-SYSTEM",
                    "--add-opens",
                    "java.base/java.util=ALL-UNNAMED",
                    "--add-opens",
                    "java.base/java.lang=ALL-UNNAMED",
                    "-Declipse.application=org.eclipse.jdt.ls.core.id1",
                    "-Dosgi.bundles.defaultStartLevel=4",
                    "-Declipse.product=org.eclipse.jdt.ls.core.product",
                    "-Dfile.encoding=UTF-8",
                    "-DwatchParentProcess={true|false}",  // false on windows, true other OSs
                    "-noverify",
                    "-Xmx1G",
                    "-XX:+UseG1GC",
                    "-XX:+UseStringDeduplication",
                    "-jar",
                    "PATH/TO/jdt-language-server-latest/plugins/org.eclipse.equinox.launcher_*.jar" // 1. replace the PATH/TO with your own 2. replace * with the file version
                    "-configuration",
                    "PATH/TO/jdt-language-server-latest/config_{win|mac|linux}", // 1. replace the PATH/TO with your own 2. choose the config folder based on the OS
                    "-data",
                    "<TEMP_DIR>/${project_base_name}/jdt_ws" // replace <TEMP_DIR> with the temp folder in your system. macOS: echo $TMPDIR
                ],
                "selector": "source.java"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "jdtls": {
                "enabled": true,
                "command": [
                    "java",
                    "--add-modules=ALL-SYSTEM",
                    "--add-opens",
                    "java.base/java.util=ALL-UNNAMED",
                    "--add-opens",
                    "java.base/java.lang=ALL-UNNAMED",
                    "-Declipse.application=org.eclipse.jdt.ls.core.id1",
                    "-Dosgi.bundles.defaultStartLevel=4",
                    "-Declipse.product=org.eclipse.jdt.ls.core.product",
                    "-Dfile.encoding=UTF-8",
                    "-DwatchParentProcess={true|false}",  // false on windows, true other OSs
                    "-noverify",
                    "-Xmx1G",
                    "-XX:+UseG1GC",
                    "-XX:+UseStringDeduplication",
                    "-jar",
                    "PATH/TO/jdt-language-server-latest/plugins/org.eclipse.equinox.launcher_*.jar" // 1. replace the PATH/TO with your own 2. replace * with the file version
                    "-configuration",
                    "PATH/TO/jdt-language-server-latest/config_{win|mac|linux}", // 1. replace the PATH/TO with your own 2. choose the config folder based on the OS
                    "-data",
                    "<TEMP_DIR>/${project_base_name}/jdt_ws" // replace <TEMP_DIR> with the temp folder in your system. macOS: echo $TMPDIR
                ],
                "languageId": "java",
                "scopes": ["source.java"],
                "syntaxes": ["Packages/Java/Java.sublime-syntax"]
            }
        }
    }
    ```

## JSON

Follow installation instructions on [LSP-json](https://github.com/sublimelsp/LSP-json).

## Julia

1. Install the [Julia](https://packagecontrol.io/packages/Julia) package from Package Control for syntax highlighting.
2. Install the `LanguageServer` and `SymbolServer` packages from the Julia REPL:

        import Pkg;
        Pkg.add("LanguageServer")
        Pkg.add("SymbolServer")

3. Open `Preferences > Package Settings > LSP > Settings` and add the `"julials"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "julials": {
                "enabled": true,
                "command": ["bash", "PATH_TO_JULIA_SERVER/LanguageServer/contrib/languageserver.sh"], // on Linux/macOS
              // "command": ["julia", "--startup-file=no", "--history-file=no", "-e", "using Pkg; using LanguageServer; using LanguageServer.SymbolServer; env_path=dirname(Pkg.Types.Context().env.project_file); server=LanguageServer.LanguageServerInstance(stdin,stdout,false,env_path); run(server)"], // on Windows
                "languageId": "julia",
                "scopes": ["source.julia"],
                "syntaxes": ["Packages/Julia/Julia.sublime-syntax"],
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

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "kotlinls": {
                "enabled": true,
                "command": ["PATH/TO/KotlinLanguageServer/build/install/kotlin-language-server/bin/kotlin-language-server.bat"], // Update the PATH
                "languageId": "kotlin",
                "scopes": ["source.Kotlin"],
                "syntaxes": ["Packages/kotlin/Kotlin.tmLanguage"],
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

!!! Info "Instructions for Sublime Text 4."

Follow installation instructions on [LSP-TexLab](https://github.com/sublimelsp/LSP-TexLab).

---

!!! Info "Instructions for Sublime Text 3."

1. Download the [binary](https://github.com/latex-lsp/texlab/releases).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"texlab"` client configuration to the `"clients"`:

```json
{
    "clients": {
        "texlab": {
            "enabled": true,
            "command": ["PATH/TO/texlab"], // Update the PATH
            "languages": [{
                "languageId": "latex",
                "document_selector": "text.tex.latex"
            }, {
                "languageId": "bibtex",
                "document_selector": "text.bibtex"
            }]
        }
    }
}
```

!!! info "For further requirements see the [TexLab Docs](https://texlab.netlify.com/docs#requirements)."

## Lisp

1. Install [cc-lsp](https://github.com/cxxxr/cl-lsp) using Roswell.
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"cc-lsp"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "cc-lsp": {
                "enabled": true,
                "command": ["cl-lsp", "stdio"],
                "languageId": "lisp",
                "scopes": ["source.lisp"],
                "syntaxes": ["Packages/Lisp/Lisp.sublime-syntax"]
            }
        }
    }
    ```

## Lua

1. Download the [VS Code extension](https://marketplace.visualstudio.com/items?itemName=sumneko.lua).
2. Open `Preferences > Package Settings > LSP > Settings` and add the `"lua-ls"` client configuration to the `"clients"`:

=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "lua-ls": {
                "enabled": true,
                "command": [
                    "PATH/TO/sumneko.lua-#.#.#/extension/server/bin/lua-language-server", // Update the PATH
                    "-E", "PATH/TO/sumneko.lua-#.#.#/extension/server/main.lua"
                ],
                "selector": "source.lua"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "lua-ls": {
                "enabled": true,
                "command": [
                    "PATH/TO/sumneko.lua-#.#.#/extension/server/bin/lua-language-server", // Update the PATH
                    "-E", "PATH/TO/sumneko.lua-#.#.#/extension/server/main.lua"
                ],
                "languageId": "lua",
                "scopes": ["source.lua"],
                "syntaxes": ["Packages/Lua/Lua.sublime-syntax"]
            }
        }
    }
    ```

## OCaml/Reason

1. Install the [Reason](https://packagecontrol.io/packages/Reason) package from Package Control for syntax highlighting.
2. Install the [Reason Language Server](https://github.com/jaredly/reason-language-server#sublime-text).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"reason"` client configuration to the `"clients"`:


=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "reason": {
                "enabled": true,
                "command": ["PATH/TO/reason-language-server.exe"], // Update the PATH
                "languageId": "reason",
                "scopes": ["source.ocaml", "source.reason"],
                "syntaxes": [
                    "Packages/Ocaml/OCaml.sublime-syntax",
                    "Packages/Reason/Reason.tmLanguage",
                    "Packages/sublime-reason/Reason.tmLanguage"
                ]
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

1. Install the [PowerShell](https://packagecontrol.io/packages/PowerShell) package from Package Control for syntax highlighting.
2. Download and extract the [latest release](https://github.com/PowerShell/PowerShellEditorServices/releases) PowerShellEditorServices.
3. Make sure PowerShell help files are up to date by running `Update-Help` in the PowerShell console (the one you're using in the command below).
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"powershell-ls"` client configuration to the `"clients"`:

=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "powershell-ls": {
                "enabled": true,
                "command": [
                    "powershell", // or pwsh for PowerShell Core
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", // Windows only
                    "-Command", "PATH/TO/PowerShellEditorServices/PowerShellEditorServices/Start-EditorServices.ps1",
                    "-LogPath", "PATH/TO/pses.log", // specify a path where a logfile should be stored
                    "-LogLevel", "Normal",
                    "-SessionDetailsPath", "PATH/TO/session.json", // specify a path where a file for session details should be stored
                    "-FeatureFlags", "@()",
                    "-HostName", "'Sublime Text'",
                    "-HostProfileId", "subl",
                    "-HostVersion", "1.0.0",
                    "-AdditionalModules", "@()",
                    "-BundledModulesPath", "PATH/TO/PowerShellEditorServices",
                    "-Stdio"
                ],
                "selector": "source.powershell"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "powershell-ls": {
                "enabled": true,
                "command": [
                    "powershell", // or pwsh for PowerShell Core
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", // Windows only
                    "-Command", "PATH/TO/PowerShellEditorServices/PowerShellEditorServices/Start-EditorServices.ps1",
                    "-LogPath", "PATH/TO/pses.log", // specify a path where a logfile should be stored
                    "-LogLevel", "Normal",
                    "-SessionDetailsPath", "PATH/TO/session.json", // specify a path where a file for session details should be stored
                    "-FeatureFlags", "@()",
                    "-HostName", "'Sublime Text'",
                    "-HostProfileId", "subl",
                    "-HostVersion", "1.0.0",
                    "-AdditionalModules", "@()",
                    "-BundledModulesPath", "PATH/TO/PowerShellEditorServices",
                    "-Stdio"
                ],
                "languageId": "powershell",
                "scopes": ["source.powershell"],
                "syntaxes": ["Packages/PowerShell/Support/PowershellSyntax.tmLanguage"]
            }
        }
    }
    ```

!!! info "For more details see this [issue](https://github.com/PowerShell/PowerShellEditorServices/issues/1057)."

## Python

There are multiple options:

### Pyright

Follow installation instructions on [LSP-pyright](https://github.com/sublimelsp/LSP-pyright).

### Pyls

```sh
pip install 'python-language-server[all]'
```

Make sure you can run `pyls` in your terminal. If you've installed it into a virtualenv, you might need to override the path to `pyls` in global LSP settings (Package Settings -> LSP -> Settings):

=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "pyls": {
                "enabled": true,
                "command": ["pyls"],
                // "command": ["/Users/mike/.virtualenvs/pyls-virtual-env/bin/pyls"], // example path, adjust it for your use case
                "selector": "source.python"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "pyls": {
                "enabled": true,
                "command": ["pyls"],
                // "command": ["/Users/mike/.virtualenvs/pyls-virtual-env/bin/pyls"], // example path, adjust it for your use case
                "languageId": "python",
                "scopes": ["source.python"],
                "syntaxes": ["Packages/Python/Python.sublime-syntax", "Packages/MagicPython/grammars/MagicPython.tmLanguage", "Packages/Djaneiro/Syntaxes/Python Django.tmLanguage"]
            }
        }
    }
    ```

If you use a virtualenv for your current project, add a path to it in your [project configuration](https://www.sublimetext.com/docs/3/projects.html) (Project -> Edit Project):

```json
{
    "settings": {
        "LSP": {
            "pyls": {
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
"pyls": {
    "enabled": true,
    "command": ["pyls"],
    "settings": {
        "pyls.env": {
          // Making Sublime's own libs available to the linters.
          // "PYTHONPATH": "/Applications/Sublime Text.app/Contents/MacOS/Lib/python33",
        },
        // Configuration is computed first from user configuration (in home directory),
        // overridden by configuration passed in by the language client,
        // and then overridden by configuration discovered in the workspace.
        "pyls.configurationSources": [
          "pycodestyle", // discovered in ~/.config/pycodestyle, setup.cfg, tox.ini and pycodestyle.cfg
          // "flake8",   // discovered in ~/.config/flake8, setup.cfg, tox.ini and flake8.cfg
        ],
        "pyls.plugins.jedi.extra_paths": [
          // The directory where the pip installation package is located
        ],
        // Enable fuzzy matches when requesting autocomplete
        "pyls.plugins.jedi.jedi_completion.fuzzy": true,
        "pyls.plugins.jedi.pycodestyle.enabled": true,
        "pyls.plugins.jedi.pycodestyle.exclude": [
          // Exclude files or directories which match these patterns
        ],
        "pyls.plugins.jedi.pycodestyle.ignore": [
          // Exclude files or directories which match these patterns
        ],
        // "pyls.plugins.jedi.pycodestyle.maxLineLength: 80" // set maximum allowed line length
        "pyls.plugins.pydocstyle.enabled": false,
        "pyls.plugins.pyflakes.enabled": true,
        "pyls.plugins.pylint.enabled": false,
        "pyls.plugins.yapf.enabled": true,
        // pyls' 3rd Party Plugins, Mypy type checking for Python 3, Must be installed via pip before enabling
        "pyls.plugins.pyls_mypy.enabled": false, // Install with: pip install pyls-mypy
        "pyls.plugins.pyls_mypy.live_mode": true
    }
}
```

See pylint documentation: [github:palantir/python-language-server](https://github.com/palantir/python-language-server).

!!! info "List of all built-in [settings](https://github.com/palantir/python-language-server/blob/develop/vscode-client/package.json)."

## R

Follow installation instructions on [R-IDE](https://github.com/REditorSupport/sublime-ide-r#installation).

## Ruby / Ruby on Rails

There are multiple options:

### Solargraph

1. Install [solargraph](https://github.com/castwide/solargraph#installation).

2. Open `Preferences > Package Settings > LSP > Settings` and add the `"ruby"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "ruby": {
                "enabled": true,
                "command": ["solargraph", "stdio"],
                "languageId": "ruby",
                "scopes": ["source.ruby", "source.ruby.rails", "text.html.ruby"],
                "syntaxes": [
                    "Packages/Ruby/Ruby.sublime-syntax",
                    "Packages/Rails/Ruby on Rails.sublime-syntax",
                    "Packages/Rails/HTML (Rails).sublime-syntax"
                ],
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

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "sorbet": {
                "enabled": true,
                "command": ["srb", "tc", "--typed", "true", "--enable-all-experimental-lsp-features", "--lsp", "--disable-watchman"],
                "languageId": "ruby",
                "scopes": ["source.ruby", "source.ruby.rails", "text.html.ruby"],
                "syntaxes": [
                    "Packages/Ruby/Ruby.sublime-syntax",
                    "Packages/Rails/Ruby on Rails.sublime-syntax",
                    "Packages/Rails/HTML (Rails).sublime-syntax"
                ],
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

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "rust-analyzer": {
                "enabled": true,
                "command": ["rust-analyzer"],
                "languageId": "rust",
                "scopes": ["source.rust"],
                "syntaxes": ["Packages/Rust/Rust.sublime-syntax", "Packages/Rust Enhanced/RustEnhanced.sublime-syntax"]
            }
        }
    }
    ```

### Rust Enhanced

Follow installation instructions on [Rust Enhanced](https://github.com/rust-lang/rust-enhanced).

## Scala

Follow installation instructions on [LSP-metals](https://github.com/scalameta/metals-sublime).

## Stylelint

Follow installation instructions on [LSP-stylelint](https://github.com/sublimelsp/LSP-stylelint).

## Svelte

Follow installation instructions on [LSP-svelte](https://github.com/sublimelsp/LSP-svelte).

## Swift

1. Install the [Swift](https://packagecontrol.io/packages/Swift) package from Package Control for syntax highlighting.
2. Install Xcode 11.4 or later and ensure that `xcrun -find sourcekit-lsp` returns the path to sourcekit-lsp.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"sourcekit-lsp"` client configuration to the `"clients"`:

=== "Sublime Text 4"
    ```json
    {
        "clients": {
            "sourcekit-lsp": {
                "enabled": true,
                "command": ["xcrun", "sourcekit-lsp"],
                "selector": "source.swift"
            }
        }
    }
    ```

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "sourcekit-lsp": {
                "enabled": true,
                "command": ["xcrun", "sourcekit-lsp"],
                "languageId": "swift",
                "scopes": ["source.swift"],
                "syntaxes": ["Packages/Swift/Syntaxes/Swift.tmLanguage"]
            }
        }
    }
    ```

## TAGML

Follow installation instructions on [LSP-tagml](https://github.com/HuygensING/LSP-tagml).

## Terraform

1. Install the [Terraform](https://packagecontrol.io/packages/Terraform) package from Package Control for syntax highlighting.
2. Download [terraform-lsp](https://github.com/juliosueiras/terraform-lsp/releases) binary and make it available in your PATH.
3. Open `Preferences > Package Settings > LSP > Settings` and add the `"terraform"` client configuration to the `"clients"`:

=== "Sublime Text 4"
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

=== "Sublime Text 3"
    ```json
    {
        "clients": {
            "terraform": {
                "enabled": true,
                "command": ["terraform-lsp"],
                "languageId": "terraform",
                "scopes": ["source.terraform"],
                "syntaxes":  ["Packages/Terraform/Terraform.sublime-syntax"]
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
