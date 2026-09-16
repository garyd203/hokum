"""hokum - adapt an ordinary CLI command to the Claude Code hook protocol."""

import fnmatch
import json
import subprocess
import sys
from typing import Annotated
from typing import Any
from typing import Literal

from cyclopts import App
from cyclopts import Parameter
from cyclopts.exceptions import CycloptsError

from hokum import __version__

app = App(
    name="hokum", version=__version__, exit_on_error=False, help_format="markdown"
)


def dig(obj: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def advise(event: dict[str, Any], message: str) -> None:
    """Surface a message to Claude as context without ending the turn."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": event.get("hook_event_name", "PostToolUse"),
                "additionalContext": message,
            }
        },
        sys.stdout,
    )


@app.default
def main(
    *cmd: str,
    field: str | None = None,
    only: Annotated[list[str], Parameter(negative=())] = [],
    stdin_json: Annotated[bool, Parameter(negative=())] = False,
    on_error: Literal["allow", "block"] = "allow",
    on_missing: Literal["skip", "advise", "block"] = "advise",
    advisory: Annotated[bool, Parameter(negative=())] = False,
    verbose: Annotated[bool, Parameter(negative="--quiet")] = False,
) -> int:
    """Run CMD (given after `--`) as a Claude Code hook.

    The hook protocol has three footguns. This wraps all of them once:
    the wrapped command exiting 0 becomes a silent hook exit 0; exiting
    non-zero becomes hook exit 2 with the wrapped output on STDERR (which
    Claude reads); and the shim itself breaking exits 0 (default) or 2
    (``--on-error block``).

    It never exits 1. Claude Code treats exit 1 as a non-blocking error and
    ignores your message entirely, which is the single most common way hooks
    silently do nothing.

    Typical hook command in `.claude/settings.json`:

    ```
    hokum --field tool_input.file_path --only '*.py' -- ruff check --fix
    ```

    Parameters
    ----------
    cmd
        The command to run, given after `--`.
    field
        Dotted path into the event JSON; value is appended to the command.
    only
        Skip (exit 0) unless the `--field` value matches this glob. Repeatable.
    stdin_json
        Pipe the raw event JSON to the command's stdin instead of appending a field.
    on_error
        Behaviour when the shim itself fails.
    on_missing
        Behaviour when the wrapped executable isn't installed: `skip` exits 0
        silently, `advise` exits 0 and tells Claude, `block` exits 2.
    advisory
        Report failures to Claude without blocking (exit 0 + JSON on stdout).
    verbose
        On success, echo the command's output to stdout for the transcript.
    """
    if not cmd:
        app.help_print()
        return 0

    raw = sys.stdin.read()
    try:
        event: dict[str, Any] = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(f"hokum: could not parse event JSON: {e}", file=sys.stderr)
        return 2 if on_error == "block" else 0

    argv = list(cmd)
    if field:
        value = dig(event, field)
        # Field absent (e.g. Bash tool has no file_path) -> nothing to act on.
        if value is None:
            return 0
        value = str(value)
        if only and not any(fnmatch.fnmatch(value, g) for g in only):
            return 0
        argv.append(value)

    try:
        proc = subprocess.run(
            argv, input=raw if stdin_json else "", capture_output=True, text=True
        )
    except FileNotFoundError:
        message = f"{argv[0]} isn't installed in this environment"
        if on_missing == "block":
            print(f"hokum: {message}", file=sys.stderr)
            return 2
        if on_missing == "advise":
            advise(event, message)
        return 0
    except (OSError, ValueError) as e:
        print(f"hokum: could not run {argv[0]!r}: {e}", file=sys.stderr)
        return 2 if on_error == "block" else 0

    output = (proc.stdout + proc.stderr).strip()

    if proc.returncode == 0:
        if output and verbose:
            print(output)
        return 0

    message = output or f"{argv[0]} exited {proc.returncode} with no output"

    if advisory:
        advise(event, message)
        return 0

    print(message, file=sys.stderr)
    return 2


def run() -> int:
    try:
        return app()
    except CycloptsError:
        # Cyclopts has already printed the parse error to stderr. A parse
        # error means the hook is misconfigured; block loudly rather than
        # exit 0 and silently no-op on every event. Never exit 1.
        return 2


if __name__ == "__main__":
    sys.exit(run())
