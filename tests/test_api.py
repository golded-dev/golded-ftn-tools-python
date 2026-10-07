"""Library operations return values and do not touch stdout."""

import json
from pathlib import Path

import pytest
from test_cli import message

from golded_ftn_tools import create, export, read, write
from golded_ftn_tools.errors import ToolError
from golded_ftn_tools.json_contract import dump


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
    assert "committed 0" in str(caught.value)
