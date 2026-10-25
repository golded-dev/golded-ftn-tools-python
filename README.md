# FTNT💥

Command-line tools for FTN message bases, JSON fixtures, packets, nodelists
and node operations. Python 3.12+. MIT licensed.

Version **1.1.1** fixes numeric reply links during conversion. SQLite and network
operations were added in 1.1.0. Packet, nodelist and node commands require the
optional `[network]` extra.

```sh
uv sync --extra network
uv run ftnt --help
```

Base commands still work without the extra. Release verification installs built wheels; there are no local source overrides.

```sh
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

Export envelopes remap numeric reply links within the input batch and drop
links to omitted messages. Their receipts follow link updates. Flat write
objects keep destination-local reply numbers unchanged.

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

1.1.0 adds `--log-level` (CLI overrides TOML `[logging].level`, default INFO)
and network commands that require `uv sync --extra network`:

```sh
uv run ftnt packet write --output mail.pkt < packet.json
uv run ftnt packet read mail.pkt
uv run ftnt nodelist parse NODELIST.XXX --domain fidonet --default-zone 2
uv run ftnt nodelist lookup NODELIST.XXX --domain fidonet --address 2:2/0
uv run ftnt node --config node.toml check
uv run ftnt node --config node.toml toss
uv run ftnt node --config node.toml scan
uv run ftnt --log-level DEBUG node --config node.toml status
```

`ftnt node poll` and `ftnt node serve` wrap the binkp client/server and refuse
non-localhost hosts. Operational errors print a closed code only: no paths,
bodies, subjects, AreaFix subjects, passwords or CRAM material.

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

Distribution checks rebuild the wheel from the sdist and run both CLI wheels in
fresh environments outside the checkout. A separate clean installation resolves
all dependencies from PyPI and runs `ftnt --version`. The sdist contains no
checkout-only uv sources. CI targets Linux/macOS with Python 3.12–3.14.
The historical 1.0.2 Windows release is separate from 1.1.0's platform promises.
GoldED interoperability is limited to the pinned 3.1.0 profile in the suite manifest.
Source and release archives are on [GitHub](https://github.com/golded-dev/golded-ftn-tools-python).
GitHub Pages deployment remains outside this release.

## Version 1.1.0

Add optional network extra: packet, nodelist and node commands. Operational failures use closed codes, including legacy commands; broken stdout exits 141. Base operations remain available without network dependencies.

Linux and macOS, Python 3.12–3.14, are the release targets. Windows is outside
this release's test and compatibility promises. See [release preparation](docs/release.md).
