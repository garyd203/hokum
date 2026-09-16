import io
import json
from typing import Literal

from hokum.main import main

#: An executable name that won't exist on PATH.
MISSING_CMD = "hokum-test-no-such-command"


def run_hook_with_missing_command(
    monkeypatch, on_missing: Literal["skip", "advise", "block"]
) -> int:
    """Invoke the hook against an executable that isn't installed."""
    event = {"hook_event_name": "PreToolUse"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    return main(MISSING_CMD, on_missing=on_missing)


def test_on_missing_skip_exits_zero_silently(monkeypatch, capsys):
    # Exercise
    code = run_hook_with_missing_command(monkeypatch, "skip")

    # Verify
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err == ""


def test_on_missing_advise_exits_zero_with_advisory(monkeypatch, capsys):
    # Exercise
    code = run_hook_with_missing_command(monkeypatch, "advise")

    # Verify
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"{MISSING_CMD} isn't installed in this environment",
        }
    }
    assert captured.err == ""


def test_on_missing_block_exits_two_with_message(monkeypatch, capsys):
    # Exercise
    code = run_hook_with_missing_command(monkeypatch, "block")

    # Verify
    captured = capsys.readouterr()
    assert code == 2
    assert f"{MISSING_CMD} isn't installed in this environment" in captured.err
    assert captured.out == ""
