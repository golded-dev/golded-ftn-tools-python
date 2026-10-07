# Verification

## Windows production corrections — 2026-10-07

- Published `golded-ftn-jam` 1.2.1, `golded-ftn-tools` 1.0.2 and
  `golded-ftn-mcp` 1.0.2. PyPI version endpoint wheel/sdist SHA-256 values
  match the local release archives for all three packages. GitHub releases
  are immutable; earlier releases remain intact.
- Release CI passed for JAM (`37671291899`), tools (`37671379353`) and MCP
  (`37672320776`), including native Windows Python 3.12 and 3.14. MCP CI
  installs public dependencies and exercises a real SDK client/server stdio
  session, listing and calling all six read-only tools.
- A fresh public-package Windows workflow installed tools 1.0.2, MCP 1.0.2
  and JAM 1.2.1 exclusively from PyPI. Package imports were checked to reside
  inside the installed environment. Both Python 3.12 and 3.14 passed
  **74 tests, 1 skipped** (POSIX SIGINT), including CLI receipt persistence
  after pipe closure and actual MCP stdio:
  [run 37673056768](https://github.com/golded-dev/golded-ftn-tools-python/actions/runs/37673056768).
- A local macOS environment installed all three current packages from PyPI,
  passed dependency compatibility checks and all **75 tools/MCP tests**.
- Local lint/format, strict typing, builds and twine checks passed. JAM's
  suite passed 133 tests with one skip, including independent literal binary
  fixtures. Tools distribution checks passed both isolated wheel suites,
  sdist rebuild equivalence, consumer typing, stubtest and all five formats.
  Regression checks cover closed-pipe errors during stdout flush, successful
  calls leaving stdout open, and ordinary ENOSPC error reporting.
- README and generated manual release/support text were updated after tags.
  The nine-page HTML checker passed links, anchors, IDs, copy targets and
  embedded fixtures. No new browser visual check or Pages deployment occurred.
- See [Windows diagnosis](WINDOWS-DIAGNOSIS.md) for the original mechanisms.
  The fixes prevent future binary text-mode corruption; they do not repair
  already-corrupted bases. GoldED Opus runtime interoperability remains
  unverified, and concurrent base use remains unsupported.

## Initial public releases — 2026-10-07

- `golded-ftn-tools` 1.0.1 and `golded-ftn-mcp` 1.0.1 are published on PyPI.
  PyPI JSON version endpoints report wheel/sdist SHA-256 values identical to
  the local release archives for both packages. Both GitHub releases are
  immutable. The earlier tools `v1.0.0` release remains intact.
- Tools release commit `781627f`: all four Linux/macOS CI jobs passed with
  Python 3.12 and 3.14 (run `37667798564`). MCP release commit `b95bee0`: the
  same matrix passed using public dependencies (run `37668692706`).
- Local ruff lint/format, strict mypy, builds and twine checks passed for both
  packages. Tools distribution verification passed both isolated wheel suites,
  sdist rebuild equivalence, consumer typing, stubtest and all five formats.
- A fresh environment installed both 1.0.1 packages exclusively from PyPI,
  passed dependency compatibility checks and all 70 tools/MCP tests. A real
  stdio session initialized, listed exactly the six read-only MCP tools, and
  successfully called catalog, heads, read, export, decode and repair against
  a synthetic offline MSG base and text inputs.
- Release-status documentation was committed after the release tags. The
  nine-page HTML checker passed links, anchors, unique IDs, copy targets and
  the exact embedded JSON fixture. A browser attempt to open the local manual
  was rejected by the browser's URL policy; no fresh visual check was completed.
- Windows stays unsupported. Both prior failures and isolated corrections
  were confirmed on native Windows 3.12.10 and 3.14.7; see
  [Windows diagnosis](WINDOWS-DIAGNOSIS.md). No production Windows fix was applied.
- GoldED Opus runtime interoperability remains unverified. GitHub Pages
  deployment was outside this release task and was not performed.

## Local implementation — 2026-10-06

Working-tree checks on macOS 27.0 arm64, CPython 3.14.6 and 3.12.8.
No release tag, CLI publication, remote CI run or deployment was performed.

- `uv run pytest -q`: 62 passed on Python 3.14.6.
- `uv run --isolated --python 3.12 pytest -q`: 62 passed on Python 3.12.8.
  Subprocess tests cover all six commands, all five format selections, actual
  writer receipts/revisions, strict JSON/JSONL preflight, partial commits,
  unknown/duplicate keys, invalid Unicode, dates, flags, missing targets,
  strict/archive corruption, sparse MSG numbers and literal Hudson boards 1/200.
- Real MSG record-lock contention with zero timeout returns 5 without a receipt.
  A deliberately closed stdout pipe returns POSIX 141 after append commits;
  export confirms the committed message. A controlled SIGINT returns 130.
  Adapter-boundary injections check rollback/I/O, conflict, lock, unsupported
  and unexpected failure reporting after an earlier successful append.
  Injection checks CLI reporting; package tests protect actual rollback algorithms.
- Ruff lint/format and strict mypy passed for CLI source/tests. Ruff also checks
  the build and verification scripts. `git diff --check` passed (whitespace only).
- `uv build`, `twine check` and `scripts/verify_distribution.py` passed. Wheel
  metadata uses public version constraints, contains the console entry point and
  py.typed, and has no local-source dependencies. The sdist strips uv sources.
  A wheel rebuilt from sdist has identical file contents. Both wheels installed
  in fresh environments outside the checkouts; each passed 62 subprocess tests,
  strict consumer typing, stubtest, pip check and all five format examples.
  Examples use the actual receipt identity, including Squish UIDs.
- Dependency wheels were built from sibling checkouts: core 1.2.2, MSG 1.3.0,
  JAM/Squish/Hudson 1.2.0. Other repositories' existing changes were preserved.
- `uv pip compile pyproject.toml --no-sources` failed resolution: the index
  offered only MSG 1.2.0, while the CLI requires >=1.3.0. Public installation
  remains blocked on publishing the independently reviewed MSG dependency.
- Local MSG Opus extension: 127 tests passed on Python 3.14.6 and 3.12.8;
  Ruff, strict mypy, agent-compose check, distribution rebuild and both isolated
  installed-package suites passed. New tests use literal timestamp/reply bytes,
  external header metadata, address contradictions, date boundaries, stale
  revisions, CRUD operations and controlled append/update/delete rollback.
- `scripts/build_reading_pages.py` regenerated all reading copies.
  `scripts/check_reading_pages.py` passed unique IDs, local links/anchors,
  copy targets, one current-page marker per page and exact embedded example JSON.
  No new visual/browser check was performed; earlier visual observations below
  are historical. Shared design files were inventoried; no layout/token rule changed.

## Historical release gates — 2026-10-06

- Run offline GoldED read/edit interoperability in both directions for Opus,
  against a pinned build/platform. Source inspection and Python fixtures do not
  establish this. Keep all bases offline; concurrent use remains unsupported.
- Commit/review the MSG dependency separately and publish it only when authorized.
  The CLI's declared public dependency range cannot currently resolve.
- Establish a remote and run the configured Linux/macOS/Windows CI matrix.
  Local macOS Python-version checks do not establish Linux or Windows execution.
- Visually check updated HTML on desktop/mobile/no-JS/print before site publication.
  Shared rules remain sourced from the documentation design and historical site palette.

## Planning-material checks

2026-10-05. At this point no CLI was implemented or tested.

- Compared specification and JSON fields with core models and writer-session signatures.
- Parsed JSON examples and mapped them to public OutgoingMessage/ControlLine
  models. In temporary bases, three inputs were accepted and read back with
  MSG/JAM/Hudson; the timezone-aware Squish example was accepted and read back.
  This checks examples, not independent binary interoperability.
- Date checks exposed different timezone requirements; corrected JSON specification
  and examples. No changes to existing Python packages.
- Local link checks covered Markdown links, HTML IDs, anchors and copy targets.
  HTML has exactly one current-page marker. JSON and JSONL examples parse correctly.
- Safari desktop: visually checked shell, masthead, fonts, section jumps, code
  panels and syntax colors. Copy code changed to Copied on activation.
  Clipboard contents were not inspected separately.
- Embedded example JSON matches `examples/message.json` exactly. Both HTML pages
  have unique IDs and valid local links, section anchors and copy targets; all
  implementation-plan sections are present in `plan.html`.
- Safari desktop: clicking 03 Contract moves the yellow section marker to Contract
  at the bottom of the home page. The Implementation plan link opens `plan.html`
  with the shared design and its own section navigation.
- Ruff check and format checks passed for `scripts/build_reading_pages.py`.
- Specification and JSON contract now have HTML reading copies generated from
  their Markdown sources. Local-link, unique-ID, anchor, copy-target and current-page
  checks passed for all four HTML pages. Safari navigation opened both new HTML
  pages; the JSON contract layout and selected-page marker were visually checked.
- Mobile/no-JS/print have CSS and fallback code but have not been visually checked.
  No claim of full browser acceptance or Pages publication.
- English translation: checked visible HTML text and local document links.
  The previous Git history was removed and a fresh local repository initialized.
  No remote is configured; the GitHub repository was deleted by Odinn.

Implementation must test SPEC acceptance criteria separately.

Opus scope update: specification, JSON contract and plan include the planned MSG
writer prerequisite. Regenerated all HTML reading copies and checked local links,
unique IDs, anchors and copy targets. No Opus writer was implemented or tested.

TOC scroll fix: reproduced in Safari on the long plan page. Upward scrolling
over a sidebar already at its top left the document scroll value at 0.6481752.
Changed sidebar overscroll behavior from contain to auto and regenerated all
four pages. Repeating upward scrolling over the sidebar reached document scroll
value 0 and showed the masthead. Recorded the rule in DESIGN.md.
