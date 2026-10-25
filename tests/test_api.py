"""Library operations return values and do not touch stdout."""

import json
from pathlib import Path

import pytest
from test_cli import message

from golded_ftn_tools import catalog, create, export, heads, read, write
from golded_ftn_tools.errors import ToolError
from golded_ftn_tools.json_contract import InputError, dump, outgoing


def test_create_write_read_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    created = create("msg", tmp_path)
    assert created["format"] == "msg"
    assert created["base"] == str(tmp_path.resolve())
    receipts = list(write("msg", tmp_path, [message()]))
    assert len(receipts) == 1
    assert receipts[0]["input_record"] == 1
    envelope = read("msg", tmp_path, 1)
    assert isinstance(envelope, dict)
    assert envelope["message"].msgno == 1  # type: ignore[attr-defined]
    exported = export("msg", tmp_path)
    rows = list(exported)
    assert len(rows) == 1
    assert exported.exit_status == 0
    assert capsys.readouterr().out == ""
    assert json.loads(dump(envelope))["type"] == "message"


def test_write_reports_committed_count(tmp_path: Path) -> None:
    create("msg", tmp_path)
    bad = message(posted_at="2024-02-30T00:00:00")
    with pytest.raises(ToolError) as caught:
        list(write("msg", tmp_path, [bad]))
    assert caught.value.code == "input.date"
    assert caught.value.exit_status == 2
    assert caught.value.input_record == 1
    assert caught.value.committed == 0
    assert str(caught.value) == "input.date"


def test_heads_limit_omits_body(tmp_path: Path) -> None:
    create("msg", tmp_path)
    list(write("msg", tmp_path, [message(), message(subject="Second")]))
    indexed = heads("msg", tmp_path, limit=1)
    rows = list(indexed)
    assert len(rows) == 1
    assert "body_text" not in rows[0]
    body = read("msg", tmp_path, 1, body=True)
    assert isinstance(body, str)
    assert rows[0]["body_bytes"] == len(body.encode())
    assert indexed.exit_status == 0
    rest = list(heads("msg", tmp_path, after=1, limit=0))
    assert [row["subject"] for row in rest] == ["Second"]


def test_catalog_opus_date_matches_outgoing() -> None:
    document = catalog()
    rules = document["date_rules"]
    assert isinstance(rules, dict)
    assert rules["opus"] == "naive posted_at"
    assert rules["sqlite"] == "naive or timezone-aware posted_at"
    payload: dict[str, object] = {
        "from_name": "A",
        "to_name": "B",
        "subject": "S",
        "body_text": "T",
        "posted_at": "2024-01-01T00:00:00",
    }
    outgoing(payload, "opus")
    payload["posted_at"] = "2024-01-01T00:00:00Z"
    with pytest.raises(InputError) as caught:
        outgoing(payload, "opus")
    assert caught.value.code == "input.date"
    outgoing(
        {
            "from_name": "A",
            "to_name": "B",
            "subject": "S",
            "body_text": "T",
            "posted_at": "2024-01-01T00:00:00Z",
        },
        "sqlite",
    )


def test_two_d_addresses_are_preserved() -> None:
    written = outgoing(
        {
            "from_name": "Alice",
            "to_name": "Bob",
            "subject": "Zone",
            "body_text": "Body",
            "from_address": "230/9316",
            "to_address": "236/77",
        },
        "sqlite",
    )
    assert written.from_address is not None and written.from_address.zone is None
    assert written.to_address is not None and written.to_address.zone is None
    assert str(written.from_address) == "230/9316"
    assert str(written.to_address) == "236/77"


def test_export_envelope_unwraps_for_write() -> None:
    envelope: dict[str, object] = {
        "schema_version": 1,
        "type": "message",
        "source": {"format": "jam", "base": "/tmp/general", "board": None},
        "message": {
            "msgno": 9,
            "from_name": "Alice",
            "to_name": "Bob",
            "subject": "Pipe",
            "body_text": "Body",
            "attributes_raw": 0,
            "posted_at": "2024-10-05T13:24:56.123456",
            "external_id": "2:230/0 abc",
            "from_address": "2:230/0",
            "to_address": None,
            "area_code": "FIDO.GENERAL",
            "provenance": {"source_type": "jam", "source_path": "/tmp/general"},
            "control_lines": {
                "kludges": [
                    {"name": "PID", "value": "ftnt", "raw": "\x01PID: ftnt"},
                    {"name": "X-ODD", "value": "one", "raw": "\x01X-ODD: one"},
                ],
                "msgid": "2:230/0 abc",
                "seen_by": ["230/0"],
                "path": ["230/0"],
            },
        },
    }
    written = outgoing(envelope, "sqlite")
    assert written.from_name == "Alice"
    assert written.subject == "Pipe"
    assert written.posted_at is not None
    assert written.posted_at.microsecond == 0
    assert [line.name for line in written.control_lines] == ["PID", "X-ODD"]
    assert written.routing_seen_by == ("230/0",)
    assert written.routing_path == ("230/0",)
    assert written.external_id == "2:230/0 abc"


def test_export_envelope_drops_synthetic_id_and_adapts_squish_time() -> None:
    envelope: dict[str, object] = {
        "schema_version": 1,
        "type": "message",
        "source": {"format": "msg", "base": "/tmp/general", "board": None},
        "message": {
            "from_name": "Alice",
            "to_name": "Bob",
            "subject": "Pipe",
            "body_text": "Body",
            "posted_at": "2024-10-05T13:24:56+02:00",
            "external_id": "hash:sha256:" + "a" * 64,
            "attributes_raw": 0x20000,
        },
    }
    written = outgoing(envelope, "squish")
    assert written.external_id is None
    assert written.attributes_raw is None
    assert written.posted_at is not None
    assert written.posted_at.isoformat() == "2024-10-05T11:24:56"
    assert [(line.name, line.value) for line in written.control_lines] == [
        ("TZUTC", "+0000")
    ]


def test_flat_write_input_still_works() -> None:
    written = outgoing(
        {
            "from_name": "Alice",
            "to_name": "Bob",
            "subject": "Flat",
            "body_text": "Text",
            "control_lines": [{"name": "PID", "value": "x", "raw": "\x01PID: x"}],
            "routing_seen_by": ["230/1"],
        },
        "jam",
    )
    assert written.subject == "Flat"
    assert written.routing_seen_by == ("230/1",)


def test_sqlite_create_write_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "area.sqlite3"
    created = create("sqlite", path, area_code="FIDO.SQLITE")
    assert created["format"] == "sqlite"
    receipts = list(
        write(
            "sqlite",
            path,
            [message(posted_at="2024-10-05T13:24:56")],
        )
    )
    assert receipts[0]["identity"].format == "sqlite"  # type: ignore[attr-defined]
    envelope = read("sqlite", path, 1)
    assert isinstance(envelope, dict)
    assert envelope["message"].subject == "Fixture æøå"  # type: ignore[attr-defined]
