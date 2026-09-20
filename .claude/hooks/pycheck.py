"""PostToolUse hook: syntax-check the .py file Claude just wrote/edited.

Reads the hook JSON from stdin, compiles the edited file with py_compile
(stdlib, zero install). On a syntax error, exits 2 so the error is fed
back to Claude for an immediate fix. Non-.py files and missing paths are
ignored (exit 0).
"""

import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input") or {}).get("file_path", "")
if not path.endswith(".py"):
    sys.exit(0)

import py_compile

try:
    py_compile.compile(path, doraise=True)
except py_compile.PyCompileError as err:
    print(f"py_compile failed for {path}:\n{err.msg}", file=sys.stderr)
    sys.exit(2)
except FileNotFoundError:
    sys.exit(0)
