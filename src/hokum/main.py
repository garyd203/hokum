#!/usr/bin/env python3
"""
hookwrap - adapt an ordinary CLI command to the Claude Code hook protocol.

The protocol has three footguns. This wraps all of them once:

  wrapped exit 0         -> hook exits 0, silent
  wrapped exit non-zero  -> hook exits 2, wrapped output on STDERR (Claude reads it)
  shim itself breaks     -> hook exits 0 (default) or 2 (--on-error block)

It never exits 1. Claude Code treats exit 1 as a non-blocking error and ignores
your message entirely, which is the single most common way hooks silently do nothing.

Usage in .claude/settings.json:

  {
    "hooks": {
      "PostToolUse": [{
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "args": [],
          "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/hookwrap.py --field tool_input.file_path --only '*.py' -- ruff check --fix"
        }]
      }]
    }
  }

Flags:
  --field PATH     dotted path into the event JSON; value is appended to the command
  --only GLOB      skip (exit 0) unless the --field value matches this glob; repeatable
  --stdin-json     pipe the raw event JSON to the command's stdin instead of appending a field
  --on-error MODE  allow (default) or block, for when the shim itself fails
  --advisory       report failures to Claude without blocking (exit 0 + JSON on stdout)
  --quiet          discard output on success (default; kept for symmetry with --verbose)
  --verbose        on success, echo the command's output to stdout for the transcript
"""

import argparse
import fnmatch
import json
import subprocess
import sys


def dig(obj, dotted):
    for part in dotted.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--field")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--stdin-json", action="store_true")
    ap.add_argument("--on-error", choices=["allow", "block"], default="allow")
    ap.add_argument("--advisory", action="store_true")
    ap.add_argument("--quiet", action="store_true", default=True)
    ap.add_argument("--verbose", dest="quiet", action="store_false")
    ap.add_argument("-h", "--help", action="store_true")
    args, cmd = ap.parse_known_args()

    if args.help or not cmd:
        print(__doc__)
        return 0

    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("hookwrap: no command given after --", file=sys.stderr)
        return 2 if args.on_error == "block" else 0

    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(f"hookwrap: could not parse event JSON: {e}", file=sys.stderr)
        return 2 if args.on_error == "block" else 0

    argv = list(cmd)
    if args.field:
        value = dig(event, args.field)
        # Field absent (e.g. Bash tool has no file_path) -> nothing to act on.
        if value is None:
            return 0
        value = str(value)
        if args.only and not any(fnmatch.fnmatch(value, g) for g in args.only):
            return 0
        argv.append(value)

    try:
        proc = subprocess.run(
            argv,
            input=raw if args.stdin_json else "",
            capture_output=True,
            text=True,
        )
    except (OSError, ValueError) as e:
        print(f"hookwrap: could not run {argv[0]!r}: {e}", file=sys.stderr)
        return 2 if args.on_error == "block" else 0

    output = (proc.stdout + proc.stderr).strip()

    if proc.returncode == 0:
        if output and not args.quiet:
            print(output)
        return 0

    message = output or f"{argv[0]} exited {proc.returncode} with no output"

    if args.advisory:
        # Surface it to Claude as context without ending the turn.
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": event.get("hook_event_name", "PostToolUse"),
                    "additionalContext": message,
                }
            },
            sys.stdout,
        )
        return 0

    print(message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())