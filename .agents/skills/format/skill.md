---
name: format
description: How to format your changes.
---

# Format

Use `ruff` to format your changes, and *only* your changes. "only your changes" is not a hard rule, as Ruff may widen the range a little bit in some cases. Use the `--range` option to specify the range of your changes. To understand the arguments to pass to the `--range` option, run:

```sh
ruff format --help | grep '\-\-range ' -A11
```

Then, format your changes:

```sh
ruff format --range <start_line>:<start_column>-<end_line>:<end_column> path/to/file.py
```

If `ruff` is not available, first check if there is a Python virtual environment already configured (in a .venv/ or venv/ directory, perhaps) and use that environment to either install it there or use the (already) installed `ruff` executable.

You may also consider looking in the .tox/py3/bin/ directory for a `ruff` executable.
