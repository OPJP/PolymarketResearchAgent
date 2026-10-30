"""Command line access to the same tools the MCP server exposes.

    polyrea <tool> [--arg value ...]       e.g.  polyrea inspect_wallet_pnl --wallet 0xabc...
    polyrea --list
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import typing

from polyrea import tools


def _parser_for(name: str, fn) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"polyrea {name}", description=inspect.getdoc(fn))
    hints = typing.get_type_hints(fn)
    for pname, param in inspect.signature(fn).parameters.items():
        t = hints.get(pname, str)
        origin = typing.get_origin(t)
        args = [a for a in typing.get_args(t) if a is not type(None)]
        base = args[0] if origin is typing.Union and args else t
        kwargs: dict = {"required": param.default is inspect.Parameter.empty}
        if param.default is not inspect.Parameter.empty:
            kwargs["default"] = param.default
        if base is bool:
            kwargs["type"] = lambda s: s.lower() in ("1", "true", "yes")
        elif typing.get_origin(base) is list:
            kwargs["nargs"] = "*"
        elif base in (int, float):
            kwargs["type"] = base
        p.add_argument(f"--{pname.replace('_', '-')}", dest=pname, **kwargs)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "--list"):
        print("tools:\n  " + "\n  ".join(f"{n:26s} {(inspect.getdoc(f) or '').splitlines()[0]}" for n, f in tools.TOOLS.items()))
        return 0
    name, rest = argv[0], argv[1:]
    fn = tools.TOOLS.get(name)
    if fn is None:
        print(f"unknown tool {name}", file=sys.stderr)
        return 2
    ns = _parser_for(name, fn).parse_args(rest)
    print(json.dumps(fn(**vars(ns)), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
