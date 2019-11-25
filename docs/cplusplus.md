## C/C++ language servers

The below was written for clangd, but much applies to cquery and ccls as well.

### CCLS

A newer project emerged from cquery.
Build and install from source, see [ccls wiki](https://github.com/MaskRay/ccls/wiki/Build)

### Cquery

Build and install from source, see [cquery wiki](https://github.com/cquery-project/cquery/wiki/Building-cquery)
Note that work on cquery has stopped. Prefer using ccls or clangd.

### Clangd

To use clangd on Debian/Ubuntu, add the apt repositories [described here](https://apt.llvm.org).
After that, install with e.g. `apt install clang-tools-9`. The clangd executable
will have a version number suffix. For instance, clangd-9. You will thus have to
adjust your `"clients"` dictionary in your user preferences.

To use clangd on Mac, use Homebrew: `brew install llvm`. The clangd executable
will be present in /usr/local/Cellar/llvm/*version*/bin
You probably need to install the Xcode developer command-line tools. Run the following in a terminal:
```bash
xcode-select --install
```
And if you're on macOS 10.14, also run the following to install essential headers like `wchar_t.h`:
```bash
open /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg
```

To use clangd on Windows, install LLVM with the [LLVM installer](http://releases.llvm.org/download.html),
and then add C:\\Program Files\\LLVM\\bin to your %PATH%.

### Compilation database

For any project of non-trivial size, you probably have a build system in place
to compile your source files. The compilation command passed to your compiler
might include things like:

* Include directories,
* Define directives,
* Compiler-specific flags.

#### compile_commands.json

Like any language server, clangd works on a per-file (or per-buffer) basis. But
unlike most other language servers, it must also be aware of the exact compile
flags that you pass to your compiler. For this reason, people have come up with
the idea of a [*compilation database*](https://clang.llvm.org/docs/JSONCompilationDatabase.html).
At this time, this is just a simple JSON file that describes for each
*translation unit* (i.e. a `.cpp`, `.c`, `.m` or `.mm` file) the exact
compilation flags that you pass to your compiler.

It's pretty much standardized that this file should be called
`compile_commands.json`. **clangd searches for this file up in parent
directories from the currently active document**. If you don't have such a file
present, most likely clangd will spit out nonsense errors and diagnostics about
your code.

As it turns out, CMake can generate this file *for you* if you pass it the
cache variable `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` when invoking CMake. It will
be present in your build directory, and you can copy that file to the root of
your project. Make sure to ignore this file in your version control system.

If you are using a make-based build system, you could use [compiledb](https://github.com/nickdiego/compiledb)
to generate a `compile_commands.json`.

Since header files are (usually) not passed to a compiler, they don't have
compile commands. So even with a compilation database in place, clangd will
*still* spit out nonsense in header files. You can try to remedy this by
enhancing your compilation database with your header files using [this project called compdb](https://github.com/Sarcasm/compdb).

To generate headers with compdb, read [this closed issue](https://github.com/Sarcasm/compdb/issues/2).

You can also read about attempts to address this [on the CMake issue tracker](https://gitlab.kitware.com/cmake/cmake/issues/16285), along with the problem
of treating header files as translation units.

#### compile_flags.txt

Another way to let your language server know what the include dirs are is by hand-writing a compile_flags.txt file in
your source root. Each line is one flag. This can be useful for projects that e.g. only have a Visual Studio solution
file. For more information, see [these instructions](https://releases.llvm.org/8.0.0/tools/clang/tools/extra/docs/clangd/Installation.html#compile-flags-txt). Creating this file by hand is a reasonable place to start if your project is quite
simple.
