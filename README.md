# FTNT💥

Eight command-line tools for FTN message bases, JSON fixtures and text pipes.
Python 3.12+. MIT licensed.

**Status: released on PyPI as 1.0.2.** Install with Python 3.12+:

```sh
python -m pip install golded-ftn-tools==1.0.2
ftnt --help
```

Development uses five sibling Python repositories.

```sh
uv sync --locked
uv run ftnt create ./fixtures/general --format jam
uv run ftnt write ./fixtures/general --format jam < examples/message.json
uv run ftnt export ./fixtures/general --format jam |
  jq -c 'select(.message.subject | contains("fixture"))'
```

`create`, `write`, `read` and `export` use an explicit `--format`:
`msg` (FTSC), `opus`, `jam`, `squish` or `hudson`. Hudson write/read requires
`--board 1..200`. Bases must be offline: close GoldED and other users first.
The format packages own validation, encoding, locks and rollback.

`write` accepts one JSON object or a JSONL batch with `--jsonl`. Structural
validation finishes before opening a writer. Each append commits separately;
a later failure keeps earlier appends. A broken pipe can hide the receipt of
an already committed message. Rerunning may create duplicates.

`read --body` emits the reader's `body_text` exactly, including any controls
present there, without adding a newline. `read --revision` adds the writer's
identity and revision. `export --archive` reports reader issues as JSONL on
stderr and exits 7 if any occur. Export is not a byte-identical backup.

```sh
uv run ftnt decode --charset IBMPC < old-text.txt
uv run ftnt repair --json < utf8-text.txt
```

Both filters read the whole input into memory. Decode uses the core charset
aliases, strict decoding and preserves line endings and trailing nulls.
Repair uses the core heuristic explicitly; import/export never repair text.

The public manual is the [front page](index.html) and one page per command:
[create](create.html), [write](write.html), [read](read.html),
[export](export.html), [decode](decode.html), [repair](repair.html),
[heads](heads.html) and [catalog](catalog.html).
Examples are in `examples/`. Maintainer notes stay in `docs/`.
The pages share [DESIGN.md](DESIGN.md).

Checks:

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
uv run twine check dist/*
uv run python scripts/verify_distribution.py
uv run scripts/build_reading_pages.py
```

Distribution checks build dependency wheels from sibling checkouts and run both
CLI wheels in fresh environments outside the checkout. A separate clean installation of 1.0.2
resolved all dependencies from PyPI and ran `ftnt --version`. The sdist strips checkout-only uv sources.
The CI matrix tests Linux, macOS and Windows with Python 3.12 and 3.14.
Windows is supported from 1.0.2 with `golded-ftn-jam>=1.2.1`. GoldED Opus runtime interoperability remains unverified.
Source and release archives are on [GitHub](https://github.com/golded-dev/golded-ftn-tools-python).
GitHub Pages deployment remains outside this release.
