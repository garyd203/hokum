# hokum

> _Every CLI command already knows how to fail. `hokum` explains it to Claude Code properly._

`hokum` is a command-line tool that you can use to wrap any other CLI command as a Claude Code hook,
dealing with the quirky semantics around exit codes, stderr, and JSON.

## What Problem Does This Solve ?

Claude Code hooks look like ordinary shell commands, but Claude Code talks to them
through a surprise-laden protocol all of its own — and ordinary CLI tools don't speak it:

* **Input arrives as JSON on stdin.** The hook event (which tool ran, which file it
  touched, and so on) is delivered as a JSON document, not as command-line arguments.
  A tool like `ruff check` wants a file path in argv and has no use for a JSON blob.
* **Exit codes carry unusual meanings.** `0` is success. `2` means "block with an error
  if relevant for this hook, and feed stderr back to Claude". Anything else — including
  the exit code `1` that nearly every linter, formatter, and test runner uses to report
  findings — is a *non-blocking* error: the output is shown to the user, but Claude
  never sees it.
* **Output routing depends on the outcome.** Only stderr, and only with exit code `2`,
  reaches Claude as feedback. Ordinary tools print their findings to stdout or stderr
  as they please, and exit `1` when something's wrong.

Put together, the naive setup — "run my linter after every edit" — produces a hook
that fires, finds problems, exits `1`, and is silently ignored. Everything looks
configured, but nothing actually happens.

`hokum` sits between Claude Code and your command and translates in both directions:
it extracts what the command needs from the event JSON, runs the command as the
normal CLI tool it is, and maps the result onto the exit codes and streams that
Claude Code actually respects.

