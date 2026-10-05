# JSON contract

Status: proposed schema version 1. CLI version and schema version are distinct.
Examples describe input/data, not an implemented parser.

## Import

`write` accepts a flat object matching `OutgoingMessage`. Required fields:
`from_name`, `to_name`, `subject`, `body_text`, all strings. Empty strings are
structurally valid, but format validation may reject them.

| Optional field | JSON type | Default |
| --- | --- | --- |
| `external_id` | string / null | null |
| `from_address`, `to_address` | FTN address string / null | null |
| `posted_at` | ISO 8601 datetime string / null | null |
| `attributes_raw` | integer >= 0 / null | null |
| `control_lines` | array of control objects | [] |
| `reply_to_msgno`, `reply1st_msgno`, `reply_next_msgno` | integer >= 0 / null | null |
| `reply_list` | array of integers >= 0 | [] |
| `routing_seen_by`, `routing_path` | array of strings | [] |

`posted_at` accepts `YYYY-MM-DDTHH:MM:SS` with optional `Z` or numeric UTC offset,
without microseconds. Reject invalid calendar dates. Timezone requirements are
format-specific and checked structurally before writing:

| Format | Date input |
| --- | --- |
| MSG / FTSC | Naive datetime; no timezone |
| MSG / Opus (planned writer extension) | Naive datetime; DOS precision and textual-date policy settled in plan phase 0a |
| JAM | Naive (interpreted as UTC) or timezone-aware datetime |
| Squish | Timezone-aware datetime; writer converts to UTC |
| Hudson | Naive datetime; no timezone |

Opus date limits and omitted/arrived timestamp behavior must be documented
with the planned MSG writer extension before CLI implementation. The current
FTSC date rules must not be applied to Opus by assumption.

Pass datetime through without converting or removing timezone. Use
`examples/message.json` for MSG/JAM/Hudson and `examples/message-squish.json`
for Squish. Date precision and year limits belong to the writer. Omitted/null
dates become None; this does not guarantee the current time. There is no common
lossless date contract across formats.

Parse addresses with `FtnAddress.from_string`, e.g. `2:236/77.1@fidonet`. Preserve
domain and point in the model; formats may impose narrower limits. Do not expand
abbreviated addresses. Booleans are not integers. Writers validate numeric widths;
a large JSON integer does not establish a valid header value.

Control objects require string `name` and `value`. Optional string `raw` defaults
to an empty string and maps directly to `ControlLine.raw`. Preserve unknown
controls in the input model. Writers decide raw/structured serialization and
conflicts. Do not invent another raw meaning or CLI-specific kludge escaping.
Arrays preserve order and duplicates. `external_id` is external MSGID, never a
base number. Do not conceal contradictory controls, MSGID or charset declarations.

Reject unknown top-level/control keys, duplicate keys, NaN/Infinity, incorrect
nested types, BOM and invalid UTF-8 with a record number. `provenance`, `msgno`,
`identity`, `revision` and export envelopes are not write input. Provenance comes
from the source/read operation, not an imported claim about the new record.

No arbitrary binary header import or requested message number. Append assigns
the format's number. Fixture authors manage forward reply links; there is no
automatic link resolver.

## Export and read

Messages use this envelope:

```json
{
  "schema_version": 1,
  "type": "message",
  "source": {"format": "jam", "base": "/resolved/path/general", "board": null},
  "message": {
    "msgno": 1,
    "from_name": "Alice",
    "to_name": "Bob",
    "subject": "Encoding fixture: æøå",
    "body_text": "First line.\nSecond line.",
    "attributes_raw": 0
  }
}
```

`message` includes all `ParsedMessage` fields, including nulls. The example shows
only required fields. Serialize dates with `datetime.isoformat()`; addresses stay
reader strings. Serialize control metadata and provenance recursively from
dataclass fields. Tuples become arrays. Do not normalize IDs, routing or text
beyond existing reader behavior.

`source.base` is the resolved absolute base path. Hudson `source.board` comes
from reader area/provenance through a documented adapter, not title heuristics.
Protect the precise mapping with a fixture test before shipping Hudson export.
Do not invent unavailable fields. Paths can expose local structure; users decide
whether to share output.

Only `read --revision` adds envelope-level `identity` and `revision`. Normal
read/export omit them. Treat digest and location as opaque data. They belong to
a physical base, not a portable export ID.

## Create and write results

```json
{"schema_version":1,"type":"create_result","format":"jam","base":"/resolved/path/general"}
```

```json
{
  "schema_version": 1,
  "type": "write_result",
  "input_record": 1,
  "identity": {"format": "jam", "base": "/resolved/path/general", "msgno": 1, "board": null},
  "revision": {
    "identity": {"format": "jam", "base": "/resolved/path/general", "msgno": 1, "board": null},
    "location": [1024, 0],
    "digest": "opaque-sha256-digest"
  }
}
```

Location is illustrative; emit the writer's actual tuple unchanged. Map identity
and revision from `WriteResult`, never reconstruct them. `input_record` is
one-based. Do not emit an extra summary line on stdout.

Export can produce new write input with an explicit mapping:

```sh
ftnt export ./old --format jam |
  jq -c '.message | {from_name, to_name, subject, body_text, posted_at, external_id}' |
  ftnt write ./new --format jam --jsonl
```

This intentionally selects only some fields. It is not a complete clone.

## Repair and issues

`repair --json` emits `schema_version: 1`, `type: "repair_result"`, and the core
fields `text`, `changed`, `confidence`. Confidence is a heuristic score, not a probability.

Archive issues on stderr contain `schema_version: 1`, `type: "reader_issue"` and
an `issue` object with every `ReaderIssue` field. Known command errors on stderr
are human-readable and include record number/commit count for batch failures.
A stable machine-readable error schema is outside v1.

Schema version 1 may gain documented optional output fields, but existing names,
types and meanings must not change. Consumers must ignore unknown output fields.
Write input stays strict. Breaking JSON changes require a new schema version
and an explicit migration.
