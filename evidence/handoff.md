# T1 golded-ftn-tools 1.1.0 handoff

Date: 2026-10-17. Isolated worktree from
`08278d673c32528f59cfa86a20ff8acf61f43bb5`. Distribution `golded-ftn-tools`
1.1.0, import `golded_ftn_tools`. No commit. No publish.

Original checkout `/Users/odinn/Projects/golded-dev/golded-ftn-tools` remains
`08278d673c32528f59cfa86a20ff8acf61f43bb5` with clean porcelain.

## Commands

```
uv sync --extra network
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy --strict src tests
```

| Command | Result |
| --- | --- |
| `pytest -q` | **80 passed** in ~28.8s (72 existing CLI/API/failure tests + 8 network) |
| `ruff check src tests` | All checks passed (`E501` ignored) |
| `ruff format --check src tests` | 13 files already formatted |
| `mypy --strict src tests` | Success: no issues found in 13 source files |

`[network]` extra: `golded-ftn-packet`, `golded-ftn-nodelist`, `golded-ftn-binkp`,
`golded-ftn-tosser`. Format deps bumped to k1 floors. `uv.sources` point at R1/F1
worktrees plus packet/nodelist/binkp/tosser packages.

## Files changed in this worktree

- `pyproject.toml`, `uv.lock`, `README.md`
- `src/golded_ftn_tools/__init__.py` (1.1.0)
- `src/golded_ftn_tools/cli.py` — `--log-level`; `packet`, `nodelist`, `node`
- `src/golded_ftn_tools/network.py` (new)
- `src/golded_ftn_tools/errors.py` — `classify_safe`
- `src/golded_ftn_tools/json_contract.py`, `catalog.py`, `examples/message-squish.json`,
  `tests/test_cli.py` — F1 Squish naive `posted_at` plus `TZUTC` (was aware JSON in 1.0.2)
- `tests/test_network_cli.py` (new)

Existing `create` / `write` / `read` / `export` / `decode` / `repair` / `heads` /
`catalog` still work. Network commands require the extra. Operational network
errors print a closed code only (no path/body/subject/password).

`--log-level` (CLI) overrides TOML `[logging].level` overrides INFO. A malformed
logging table still fails when a CLI override is supplied.

`ftnt node` subcommands: `check`, `toss`, `scan`, `poll`, `serve`, `status`,
`recover`. `poll`/`serve` refuse non-localhost. Default `serve` binds and closes;
`--wait` keeps the server.

## Remaining gaps

- Live binkp poll against a running peer is not in the suite (connection-refused
  on `127.0.0.1:1` is the poll error-path test).
- Default `serve` is bind-and-close; `--wait` is untested against a client.
- Reading-page HTML / `docs/` still describe 1.0.2 Squish as timezone-aware in
  places; JSON contract and catalog now match F1 naive+TZUTC.
- No wheel, no commit, no non-localhost bind.

## Conservative choices

- Packet `read` JSON omits names, subjects, bodies, and passwords.
- Missing packet/nodelist files report `packet_unreadable` / `nodelist_unreadable`
  without interpolating the path.
- Squish CLI write aligned to F1: naive wall time plus `TZUTC` (fail-closed vs
  keeping the 1.0.2 aware JSON that F1 rejects).
