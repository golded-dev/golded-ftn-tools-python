# Windows CI diagnosis — 2026-10-07

Both failures from Grok's CI run `37633160906` were reproduced against the
published `golded-ftn-tools==1.0.1` and public dependencies on native Windows.
The manual diagnostic workflow passed on CPython 3.12.10 and 3.14.7:
[run 37669214703](https://github.com/golded-dev/golded-ftn-tools-python/actions/runs/37669214703).

## Published production corrections

The corrections are published as `golded-ftn-jam` 1.2.1,
`golded-ftn-tools` 1.0.2 and `golded-ftn-mcp` 1.0.2. JAM opens both binary
files with `O_BINARY` on Windows. Tools handles recognized closed-pipe errors
at stdout writes/flushes and leaves stdout open after successful calls.
Ordinary I/O failures retain their error reporting.

Regular CI now includes Windows with Python 3.12 and 3.14. A separate fresh
installation exclusively from PyPI passed **74 tests, 1 skipped** on each
Windows version, including committed receipt persistence and actual MCP stdio:
[run 37673056768](https://github.com/golded-dev/golded-ftn-tools-python/actions/runs/37673056768).
The skipped test exercises POSIX SIGINT behavior. Imported package paths were
checked against the installed environment, excluding checkout source imports.

Existing bases corrupted by earlier text-mode writes are not automatically
repaired. The diagnosis below describes the original released versions and
process-local probes, before these production corrections.

## JAM: a binary index opened in text mode

`golded-ftn-jam`'s `JamSession._operation()` opens `.JDT` and `.JDX` using
`os.O_RDWR` without `os.O_BINARY`. On Windows these descriptors translate
newlines. The test's recipient `Bob` produces index bytes
`bf4e340a00040000`. Writing through the text descriptor expands `0a` to `0d0a`,
leaving `bf4e340d0a00040000`: nine bytes instead of eight.

`write` returns success, but subsequent `read --revision` rejects the index
because its size is not divisible by eight. This is actual file corruption,
not a reader newline or JSON issue. The header descriptor already uses
`O_BINARY` through the core lock manager.

The isolated probe adds `O_BINARY` to the `.JDT` and `.JDX` opens in that
process. The same write then produces the exact eight-byte index and
`read --revision` returns 0 on both Python versions. A production correction
belongs in `golded-ftn-jam`, with fixtures containing LF, CRLF and CTRL-Z in
binary index/body data. Existing bases written through text descriptors need
separate assessment; changing future opens does not repair prior corruption.

## Receipt pipe: the error occurs before the final handler

On Windows a closed receipt pipe raises `OSError` with `errno.EINVAL` inside
`_emit()`'s `target.flush()`. The append has already committed. `_run()` raises
before it can return, so the final flush/close block added by Grok is never
reached. The outer handler catches only `BrokenPipeError` specially; this
`OSError` falls through to the generic handler and reports exit status 6.

Pending stdout data is still buffered. CPython's shutdown flush fails again
and replaces the process exit status with 120. Native logs show both the
`io.failed` error and the final ignored `OSError: [Errno 22] Invalid argument`.

The isolated probe catches the recognized closed-pipe error at `_emit()` and
routes it through the existing `BrokenPipeError` cleanup. Both Python versions
then return 6 with empty stderr, and export confirms the committed message
remains readable. A production correction should handle recognized pipe
errors around the whole command, covering `_emit()` and `_text()`, while
retaining ordinary I/O errors. Grok's unconditional stdout buffer close is
also unnecessary for successful calls and warrants removal in that correction.

## Historical diagnostic scope and reproduction

At the diagnostic stage, no production Windows fix had been applied and Windows
was excluded from regular CI. The probes altered only their child processes.
The historical workflow is now pinned to tools 1.0.1 and JAM 1.2.0 to preserve
that baseline. Use `verify-windows-release.yml` to test the current public releases.

Run the focused diagnostic workflow:

```sh
gh workflow run diagnose-windows.yml
```

It asserts the original failures, the exact JAM index bytes, the corrected
exit statuses, and persistence of committed messages. It uses synthetic
temporary bases and installs public packages without checkout sources.

References: Python documents the need for
[`O_BINARY` with `os.open()` on Windows](https://docs.python.org/3/library/os.html#os.open)
and [exit 120 after failed shutdown cleanup](https://docs.python.org/3/library/sys.html#sys.exit).
