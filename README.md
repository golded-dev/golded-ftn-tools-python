# FTNT💥

Small command-line tools for FTN message bases, text filters and fixtures.

**Status: proposal for review. The CLI is not implemented.** The commands below
show the proposed contract, not something you can install yet.

The package will use the existing Python libraries for MSG, JAM, Squish and
Hudson, including the planned Opus writer extension in `golded-ftn-msg`.
Those libraries own file formats, encoding, locks and rollback. This
repository owns arguments, JSON and pipes.

Start here:

- [HTML landing page](index.html): the idea in GoldED's documentation design, in one standalone file.
- [DESIGN.md](DESIGN.md): layout, palette, typography and status rules.
- [Specification](specification.html): scope, commands and acceptance criteria.
- [JSON contract](json-contract.html): import, export, identity and revision.
- [Implementation plan](plan.html): HTML reading copy with sequence, tests and decisions.
  [Markdown source](docs/PLAN.md) remains the editable plan.
- [Example message](examples/message.json), [JSONL batch](examples/messages.jsonl) and [Squish variant](examples/message-squish.json).

```sh
ftnt create ./fixtures/general --format jam
ftnt write ./fixtures/general --format jam < examples/message.json
ftnt export ./fixtures/general --format jam | jq -c 'select(.subject | contains("fixture"))'
```

The proposed first version includes `create`, `write`, `read`, `export`, `decode`
and `repair`. No tosser, packet handling or automatic repair of source data.

This repository contains planning material only. There is no release or CLI test
suite yet. Implementation and publication need a separate task. Git is local;
there is no remote configured.

Rebuild the embedded message and all HTML reading copies after editing their sources:

```sh
uv run --with markdown --with pygments scripts/build_reading_pages.py
```
