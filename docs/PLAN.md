# Implementation plan

Status: implementation started 2026-10-06. The phases below preserve the original
acceptance plan. Current implementation and verification are recorded here and
in [VERIFICATION.md](VERIFICATION.md).

## Implementation status

- Six commands and schema v1 are implemented locally using public APIs.
- Local MSG 1.3.0 adds explicit Opus sessions; dates use the shared DOS/text
  range 1980–2069 with even seconds. Arrived words default to zero and survive updates.
- Decode reads whole input in v1 and uses public `detect_charset(b"", charset)`
  for alias selection. It preserves trailing nulls and line endings.
- Hudson board mapping uses area_meta_key, protected by an independent two-board fixture.
- Subprocess tests cover workflows, preflight, partial commits, archive issues,
  locks, broken receipts, SIGINT and adapter error reporting.
- Linux/Windows remote CI, GoldED Opus runtime interoperability and public-index
  resolution remain release gates. Publication has not been authorized.
- Design files were inventoried. FTNT inherits documentation tokens from
  golded-ftn-python-docs/DESIGN.md, which uses golded-site's historical palette.
  This change updates status/copy only; layout and shared visual rules are unchanged.


## Chosen approach

A separate CLI repository, thin adapters and standard-library `argparse`.
`argparse` is sufficient for six commands and keeps the CLI's own runtime
dependencies small. Reconsider Click/Typer for a concrete need, not colored help.

Proposed dependencies: `golded-ftn>=1.2.1,<2` and the four format packages
`golded-ftn-msg>=1.3.0,<2` and `golded-ftn-jam`, `golded-ftn-squish`,
`golded-ftn-hudson` at `>=1.2.0,<2`. Install all formats in v1 so help matches actual capability.
No local `uv.sources` in public distributions. Core and format packages version
independently of the CLI. The MSG minimum version must be raised to the release
that implements and verifies Opus writing; the published MSG 1.2.0 writer rejects it; the local 1.3.0 extension implements it.

The CLI owns arguments, JSON types, text/binary streams and exit codes. Packages
own FTN rules. Use `json` with explicit field validation rather than another
runtime model framework. Choose small typed adapters over a plugin system.

## 0. Establish API boundaries — small/medium

Read [SPEC.md](SPEC.md) and [JSON.md](JSON.md), then inspect current installed
packages again. The original plan used core 1.2.1 and format packages 1.2.0, inspected
on 2026-10-05. Current local verification uses core 1.2.2 and MSG 1.3.0. Use public exports, not private writer helpers.

Discovery before implementation:

- Find a public codec/alias seam for incremental `decode`. If missing, propose a
  small core API separately; alternatively document whole-input decoding in v1.
  Do not duplicate alias tables or import private names.
- Establish Hudson board mapping on `ParsedMessage` with a literal fixture and
  verify read lookup across boards. Do not derive board from free text.
- Check create paths, source_type values, writer date defaults and supported
  reply fields per format. Document rejections in help.
- Confirm dependency ranges resolve from PyPI without checkout sources.

Exit: boundaries are settled. Revise the specification explicitly if a seam is missing.

## 0a. Add Opus writing to golded-ftn-msg — medium/large

Opus is a MSG header variant, not a fifth storage engine. Extend the public
`golded-ftn-msg` writer before wiring CLI writes. Existing `MsgReader("opus")`
can support reading/export while this work proceeds. No Opus serialization in
CLI code and no claim that the current writer supports it.

Use original GoldED source as the format reference. Document the public variant
selection for create/open and implement create, append, consistent read, update
and delete with the same identity, revision, offline and rollback contracts as
FTSC. Preserve FTSC behavior. Explicit selection is required; do not guess or
convert an existing area's header variant implicitly.

- Serialize written/arrived DOS timestamps at bytes 176–183 rather than FTSC
  zone/point words. Preserve both existing timestamps and unknown header bytes
  on updates unless explicitly changed.
- Represent zone/point through INTL/FMPT/TOPT. Specify how explicit addresses
  and supplied controls agree; reject contradictions before mutation. Address
  representation belongs to the format package, without adding automatic routing.
- Settle the date contract before implementation: DOS years 1980–2107,
  two-second precision, textual-date fallback, omitted written/arrived timestamps,
  and the limits of the existing core model. Prefer rejecting unrepresentable
  values over silent rounding. Document any required core API extension separately.
- Use TDD with independent literal headers: both timestamps, zero/invalid dates,
  year/precision limits, nonzero zones and points, reply links, unknown metadata,
  and conflicting controls. Cover every writer operation, revisions, rollback,
  and unchanged FTSC behavior; reader roundtrips alone are insufficient.
- Verify GoldED reads and edits Python-written Opus messages and Python reads
  and updates GoldED-written messages. Record the exact build/platform. This is
  offline compatibility testing, not authorization for concurrent use.

Exit: the public Opus writer contract is documented and tested, compatibility
results are recorded, and the CLI's MSG dependency floor names a release with
this capability. Publication remains a separately authorized step.

## 1. CLI and JSON foundation — medium

Add `pyproject.toml`, `src/golded_ftn_tools`, entry point, test/dependency groups
and CI. Proposed separation: argument parser, JSON contract, format adapters,
commands and shared diagnostic/exit-code mapping. Split responsibilities only
where a real consumer needs it.

Use TDD at the public CLI: one observable behavior at a time. Start with help,
version, stdout/stderr separation, UTF-8, unknown keys, duplicate keys and
addresses/dates. Avoid tests that merely mirror private functions.

Exit: schema v1 parses input and serializes results without base I/O.

## 2. Reading and text filters — medium

Implement `decode`, `repair`, `read` and `export`. Add ordinary strict reading
first, then archive issues and optional consistent revision reads. Use the actual
readers and helpers, not an alternative parser. Include explicit `--format opus`
using `MsgReader("opus")`; never interpret its timestamps as address words.
Opus `read --revision` depends on the writer added in phase 0a.

Tests: JSONL pipes, Unicode, CP850 and multibyte chunk boundaries, degree signs,
mojibake, unchanged text, LF/CRLF, body without an extra newline, sparse msgno/UID,
missing records, Hudson boards, corruption and partial exports. Cover archive
callbacks and exit code 7. Document reader buffering and offline requirements.

Exit: read/filter commands work without writes or automatic repair.

## 3. Create/write, starting with JAM — medium/large

Implement `create` and `write` for JAM, then MSG (FTSC and Opus), Squish and
Hudson. Opus writes depend on phase 0a. Use
context-managed sessions and `append`. Reject existing destination files.
Spool JSONL preflight to a temporary file; format validation stays with writers.

Tests: structural failure on record N causes zero writes; format/encoding failure
on N preserves previous commits; receipts match actual identity/revision. Cover
charset/control conflicts, numbers, dates, null input, attribute limits, reply
fields, auxiliary files and Hudson boards 1/200. No sidecar, overwrite or retry.

Exit: all four storage formats, including both MSG header variants, can create
bases and read CLI-written messages back.
Also compare some raw bytes to independent expectations, not only roundtrips.

## 4. Failures, pipes and platforms — medium/large

Add deterministic subprocess tests for lock timeout, broken pipe, SIGINT,
I/O failure and rollback failure. Use a controlled lock helper and focused
injection at the adapter boundary, not random timing. Reuse writer packages'
already-tested rollback and verify CLI reporting of the relevant exception.
Do not import private I/O layers to reproduce base algorithms.

Run redirected CLI subprocesses on Linux/macOS/Windows. Separate POSIX 141/SIGINT
from Windows behavior and record the observed contract. Cover failure after
append commits but before the stdout receipt. Do not describe it as rollback.

Exit: tests support SPEC's exit codes and partial-success semantics.

## 5. Documentation and distribution — medium

Replace planned status in README/HTML only once implementation exists. Keep
HTML copy, JSON examples, help and specification aligned. Run examples from a
wheel installed outside the checkout. Build wheel and sdist, inspect metadata
and entry point, rebuild the sdist, resolve dependencies without local sources
and run consumer tests.

Update the GoldED design documents together:

- `golded-ftn-tools/DESIGN.md`: FTNT identity, reading-copy generation, code
  panels, page/section navigation and sidebar scroll behavior.
- `golded-ftn-python-docs/DESIGN.md`: shared documentation rules and fixes that
  also apply to the Python library documentation.
- `golded-site/DESIGN.md`: shared GoldED identity and visual rules that also
  apply to the main site.

Inventory these files again when implementation begins. Compare shared palette,
typography, section labels, syntax colors, navigation, mobile and print rules.
Keep shared rules consistent and document intentional site-specific differences;
do not copy FTNT branding or CLI-specific rules into every site. Identify the
canonical source for each shared rule and cross-link it so later changes do not
drift. Check the affected HTML pages against their updated design documents,
including Safari sidebar scrolling and access to both ends of the TOC. Record
which pages and viewport states were actually checked.

Quality gate: pytest, Ruff lint/format, strict mypy, distribution checks,
README/spec examples and `git diff --check`. CI uses the same gate; local results
do not replace remote platform results. Run relevant API/format tests if a
discovery change required changes in a dependency.

Exit: SPEC acceptance criteria are met and documented; the relevant DESIGN.md
files agree on shared rules, and affected pages have been checked against them.
Tags, PyPI publication
and GitHub Pages require a later explicit task. Implementation is local. No publication is automatic.

## Review points

Odinn can focus on:

1. Six commands for the first release; `update/delete` can wait.
2. Explicit `--format` instead of detection.
3. Strict import and JSONL preflight with one commit per message.
4. Export envelopes and separate write input instead of a false lossless roundtrip.
5. Python packages are the engine; the CLI does not own format algorithms.

These are recommended decisions, not unanswered questions blocking review.

## Risks and accepted limits

| Risk | Response |
| --- | --- |
| Reader and writer share a bug | Independent binary expectations in integration tests |
| Late batch failure or closed pipe | Per-record receipts; no retry/whole-batch rollback |
| Export omits unknown raw metadata | Describe export as data, not backup |
| GoldED is using the base | Offline contract; no concurrent flag or new live promises |
| Helper lacks a public streaming seam | Resolve in phase 0; separate core change if needed |
| Fixture bytes vary with base time/platform | Fixed input date/MSGID; test content, not promised identical files |
| Dependencies change API | Version bounds, clean installs and CI integration |

## Source basis

Checked in local source repositories before writing this plan:

- Core `models.py`, `contracts.py` and exports: input model, sessions, revisions and issues.
- `MsgReader`/`JamReader`/`HudsonReader` and all four writer exports/signatures.
- Hudson `open(path, board, options, scan_path=...)` and its all-board reader behavior.
- Core strict encoding/repair and writer format validation.

Public references: [core API](https://golded-dev.github.io/golded-ftn-python-docs/core-api.html),
[writer guide](https://golded-dev.github.io/golded-ftn-python-docs/writers.html) and
[format references](https://golded-dev.github.io/golded-ftn-python-docs/).
These are entry points; inspected source takes precedence over later drift in web copy.

## Findings from example checks

MSG/Hudson require naive dates; Squish requires timezone; JAM accepts both.
Examples therefore use separate standard and Squish inputs. Preserve this
difference in JSON validation instead of hiding it with timezone conversion.
