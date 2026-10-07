# Specification: golded-ftn-tools

Status: implemented locally, 2026-10-06. Release acceptance still has external gates;
see [VERIFICATION.md](VERIFICATION.md).

## Purpose

Make the existing FTN Python packages useful from a terminal: read and export
messages, create bases and write fixtures from JSON, and filter text through pipes.

Distribution: `golded-ftn-tools`. Import name: `golded_ftn_tools`. Entry point:
`ftnt`. Python 3.12+. Proposed first release: 0.1.0, once the contract has been
implemented and verified. This document does not authorize a release.

V1 has six subcommands. `list`, `controls`, `address`, `inspect`, `grep`, `update`
and `delete` are possible extensions, not hidden v1 deliverables. No BBS, tosser,
packets, duplicate detection, automatic MSGID/routing, packing, base repair or
direct binary record serialization in CLI code.

## Ground rules

- stdout contains result data. Diagnostics and issues go to stderr.
- No banner, progress bar or terminal colors in data. Output is identical in a
  TTY and a pipe. Help and version are ordinary text.
- JSON is UTF-8 without a BOM, with readable Unicode and a trailing LF.
- Message streams and write results are JSONL: one independent object per line.
- All base commands require `--format msg|opus|jam|squish|hudson` in v1. No heuristic
  format detection or metadata sidecar. Examples must include the flag.
- Format packages own validation, locking, encoding and commit boundaries. The
  CLI must not import their private modules or duplicate their serialization.
- Bases must be offline with respect to GoldED and other external users during
  both reading and writing. Writers receive `concurrent=False`. No `--live` flag.
  A lock does not establish safe concurrent use; ordinary readers are not snapshots.
- No automatic mojibake repair during import or export. `repair` is a separate,
  explicit filter.

`msg` selects FTSC headers; `opus` selects Opus headers in the same `.MSG`
storage layout. Both variants support create/write/read/export locally. Opus writing and
consistent revision reads use the local `golded-ftn-msg` 1.3.0 extension.
The CLI dependency floor requires that release before public installation. No automatic header detection or conversion.

## Commands

| Command | Input | stdout | Mutation |
| --- | --- | --- | --- |
| `create BASE --format FORMAT` | Arguments | One create result | Creates an empty base |
| `write BASE --format FORMAT [--jsonl]` | JSON on stdin | One write result per append | Appends messages |
| `read BASE MSGNO --format FORMAT` | Arguments | One message object | None |
| `export BASE --format FORMAT` | Arguments | Message objects as JSONL | None |
| `decode --charset CHARSET` | Bytes on stdin | UTF-8 text | None |
| `repair [--charset CHARSET] [--json]` | UTF-8 text on stdin | Text or one repair result | None |

`--version` prints the CLI version. `--help` explains the data contract and flags.
Use shell redirection for input files; another input-file option is unnecessary.

### create

MSG (FTSC or Opus) and Hudson use a directory. JAM and Squish use a basename without a suffix,
e.g. `./fixtures/general`, not `general.JHR` or `general.SQD`.

Existing base files are rejected through the writer's `create`. No `--force`,
`--overwrite` or implicit creation in `write`. Hudson creation applies to the
whole base and does not accept `--board`. Auxiliary files and lastread
initialization belong to the writer. Emit a create result only after success.

```sh
ftnt create ./fixtures/hudson --format hudson
ftnt write ./fixtures/hudson --format hudson --board 42 < examples/message.json
```

### write

Default input is exactly one JSON object. `--jsonl` accepts one object per line;
blank lines, duplicate JSON keys and trailing data are rejected. Reject an empty batch.

Shared flags: `--encoding` (default CP850) and `--lock-timeout` (default five
seconds, finite number >= 0). Hudson requires `--board 1..200`; reject that flag
for other formats. V1 does not expose Hudson's separate `scan_path`; use the
writer package's documented default. Investigate external scan directories before
adding an option.

Read, parse and structurally validate the entire input before opening a writer
session. Spool normalized, validated JSONL records to a temporary file instead
of retaining the whole batch in RAM. Close and remove it after use.

Preflight covers JSON types, known fields, addresses, dates and CLI flags. It does
not promise full format validation: encoding representability, header limits,
charset controls and format-specific reply/attribute rules remain with writers.
There is no common public validate-only API. Do not invent one in CLI code merely
to offer a dry-run flag.

Call `append` in input order. One message is one commit unit. Failure on message
N stops the batch; earlier completed appends remain committed. stdout contains
receipts only for committed messages. stderr gives the failed record number and
the committed count. No automatic retry or rollback of earlier successes. No
guarantee against process death, power loss or an interrupted pipe.

A broken pipe can occur after append commits but before its receipt reaches the
consumer. Help and docs must explain this: rerunning can create duplicates.

### read and export

Default output follows [JSON.md](JSON.md). `read` matches the actual
`ParsedMessage.msgno`, never a list position. Squish numbers are UIDs. A missing
number is a distinct error. Scanning through the reader is acceptable in v1;
no constant-time lookup promise. Hudson requires `--board` for `read`.
Hudson `export` may omit board to export all boards or select one explicitly.
Reject `--board` for other formats.

`read --body` emits only `body_text` as UTF-8, without repair or an added newline.
It cannot be combined with `--revision`. `read --revision` uses the writer
session's consistent `read` and includes identity and revision; it does not
mutate, but may require write access to lock/base files. Normal `read` and `export`
use readers and never fabricate revisions.

`--fallback-charset` controls reading, default CP850. Strict reading is the default.
`export --archive` uses `ReaderOptions(archive_mode=True, on_issue=...)` and sends
each issue to stderr as JSONL. Recovered messages may be emitted, but any issue
produces exit code 7; stdout alone is not evidence of a complete export.
`read --revision` does not use archive mode. V1 has no archive mode on `read`.

Emit messages as the reader supplies them. Some readers load and validate a whole
base first; JSONL does not promise constant total RAM or immediate first output.
A strict failure after output begins can leave a partial export. Consumers must
check exit status, e.g. with `set -o pipefail`.

Export is not a byte-identical backup or universal export/import roundtrip.
Readers omit some raw metadata. No preservation promise for unknown subfields,
full reply lists, original text bytes or physical record locations.

### decode and repair

`decode` requires an explicit charset; use core aliases and strict decoding. No
charset guessing, replacement characters or `--ignore-errors`. V1 reads the whole input into memory. Core
`detect_charset(b"", charset)` selects the explicit codec using core aliases;
the CLI decodes with that codec and preserves trailing nulls. There is no chunk
boundary or private charset API in this implementation. Decode preserves line endings.

`repair` accepts UTF-8 and calls `repair_mojibake`. `--charset` supplies declared
charset, not stdin encoding. `--no-prefer-quoted` disables the lower threshold
for quoted lines. Default output is `result.text`, without an extra newline.
`--json` emits `{text, changed, confidence}` with schema version and type.

V1 processes all repair input in memory to preserve core line normalization
and confidence aggregation. Help must state this. A later streaming mode must
not silently change those semantics. Repair inherits the core heuristic,
including protection of literal degree signs. No change is success, not an error.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Entire operation succeeded without reader issues |
| 1 | Unexpected internal failure |
| 2 | Invalid arguments, JSON or structural input |
| 3 | Missing base/message, or existing base on create |
| 4 | Decode, format, writer-validation or unsupported-operation failure |
| 5 | Lock timeout or revision conflict |
| 6 | I/O failure or failed rollback |
| 7 | Archive export had issues, even if some messages were emitted |
| 130 | Interrupted by SIGINT |
| 141 | Broken pipe on POSIX; Windows returns 6 for a broken pipe; remote execution remains unverified |

Errors go to stderr, never into stdout JSON. Known errors have no traceback;
`--debug` may show one on stderr. Multiple failures use the terminal failure,
e.g. I/O code 6 rather than earlier archive issues. Broken pipes have no traceback.

## Fixture use

Fixture examples specify date, encoding and external MSGID explicitly. The CLI
adds no random IDs, implicit dates or routing. Writers may still generate base
timestamps and other format fields. Repeatable content is not a promise of
identical files or SHA-256 across platforms/runs.

Writer-generated bases are useful for examples and integration tests. Binary
correctness tests must also use independent literal fixtures; reader and writer
can otherwise agree on the same bug.

## Acceptance criteria for 0.1.0

- All six commands work with stdin/stdout in subprocess tests without a TTY.
- Create/write/read/export cover all four formats, including Hudson boards 1
  and 200, and both MSG header variants (FTSC and Opus). GoldBase is excluded.
- Opus support uses the verified public MSG writer extension, with independent
  timestamp/address fixtures and recorded offline GoldED interoperability.
- The JSON contract is documented, validated and stable in the released version.
- Invalid JSONL record N causes zero writes. A writer failure on N preserves
  earlier commits and produces accurate receipts and nonzero exit status.
- Encoding/address/date errors, missing targets, corrupt bases, lock timeout,
  broken pipes and rollback failures have tested behavior.
- No source repair, overwrite, implicit create or concurrent=True.
- A wheel and a wheel rebuilt from sdist install without local sources;
  `ftnt --help` and documented workflows run outside the checkout.
- Pytest, Ruff, strict mypy and distribution checks pass; CI tests Linux,
  macOS and Windows. Local success alone does not establish platform support.
