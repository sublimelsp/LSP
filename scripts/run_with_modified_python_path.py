"""
Wrapper script for setting the PYTHONPATH env var to Sublime's Lib/pythonXY directory.

This is used for tools like pyright and ruff that can then discover third-party libraries.
See the pyproject.toml file for usage of this script.

The first argument to this script should be the python directory name inside of Sublime's Lib/ directory.
For instance, it can be "python38" or "python314".

The rest of the arguments are passed unmodified to subprocess.call.
"""

from __future__ import annotations

from pathlib import Path
import os
import platform
import subprocess
import sys

if platform.system() == "Windows":
    config_root = Path.home() / "AppData" / "Roaming"
elif platform.system() == "Darwin":
    config_root = Path.home() / "Library" / "Application Support"
else:
    config_root = Path.home() / ".config"

for dirname in ("sublime-text-3", "sublime-text"):
    candidate = config_root / dirname
    if candidate.is_dir():
        sublime_dir = candidate
        break
else:
    raise RuntimeError(f"Could not find either 'sublime-text-3' or 'sublime-text' under {config_root}")

lib_dir = sublime_dir / "Lib" / sys.argv[1]
env = os.environ.copy()
env["PYTHONPATH"] = str(lib_dir)
print("modified PYTHONPATH:", env["PYTHONPATH"])
raise SystemExit(subprocess.call(sys.argv[2:], env=env))
