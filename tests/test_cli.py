"""Exercise the command through redirected binary streams and literal fixtures."""

import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def cli(*args: str, data: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "golded_ftn_tools", *args],
        input=data,
        capture_output=True,
        timeout=20,
    )


def message(**changes: Any) -> bytes:
    return json.dumps(
        {
            "from_name": "Alice",
            "to_name": "Bob",
            "subject": "Fixture æøå",
            "body_text": "Text",
            **changes,
        },
        ensure_ascii=False,
    ).encode()


def test_json_errors_are_objects(tmp_path: Path) -> None:
    base = str(tmp_path / "base")
    assert cli("create", base, "--format", "msg").returncode == 0
    result = cli("write", base, "--format", "msg", "--json-errors", data=b"{}")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["type"] == "error"
    assert payload["code"] == "input.structure"
    assert payload["exit_status"] == 2


def test_help_and_version() -> None:
    result = cli("--help")
    assert result.returncode == 0
    assert all(
        command.encode() in result.stdout
        for command in (
            "create",
            "write",
            "read",
            "export",
            "decode",
            "repair",
            "heads",
            "catalog",
        )
    )
    assert not result.stderr
    assert cli("--version").stdout.replace(b"\r\n", b"\n") == b"ftnt 1.0.2\n"


@pytest.mark.parametrize("format", ["msg", "opus", "jam", "squish", "hudson"])
def test_base_workflow(tmp_path: Path, format: str) -> None:
    base = str(tmp_path / "base")
    board = ["--board", "200"] if format == "hudson" else []
    result = cli("create", base, "--format", format)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["type"] == "create_result"
    date = "2024-10-05T13:24:56Z" if format == "squish" else "2024-10-05T13:24:56"
    result = cli(
        "write", base, "--format", format, *board, data=message(posted_at=date)
    )
    assert result.returncode == 0, result.stderr
    assert cli("create", base, "--format", format).returncode == 3
    receipt = json.loads(result.stdout)
    assert receipt["identity"]["format"] == format
    number = str(receipt["identity"]["msgno"])
    result = cli("read", base, number, "--format", format, *board, "--revision")
    assert result.returncode == 0, result.stderr
    read = json.loads(result.stdout)
    assert read["revision"] == receipt["revision"]
    assert read["message"]["subject"] == "Fixture æøå"
    assert (
        cli("read", base, number, "--format", format, *board, "--body").stdout
        == read["message"]["body_text"].encode()
    )
    export = cli("export", base, "--format", format)
    assert export.returncode == 0, export.stderr
    envelope = json.loads(export.stdout)
    assert "revision" not in envelope
    assert envelope["source"]["board"] == (200 if format == "hudson" else None)
    for revision in ([], ["--revision"]):
        assert (
            cli("read", base, "999", "--format", format, *board, *revision).returncode
            == 3
        )


@pytest.mark.parametrize(
    "invalid",
    [
        b"{}",
        b'{"from_name":"A","from_name":"B"}',
        b"[]",
        b"null",
        message(attributes_raw=True),
        message(reply_list=[True]),
        message(from_address="1/2"),
        message(posted_at="2024-02-30T00:00:00"),
        message(posted_at="2024-01-01T00:00:00.000"),
        message(posted_at="2024-01-01T00:00:00+00:99"),
        message().replace("Fixture æøå".encode(), rb"\ud800"),
        message(unknown="x"),
        message(control_lines=[{"name": "X", "value": "v", "extra": "x"}]),
        b"\xef\xbb\xbf" + message(),
        b"\xff",
        message() + b"\n\n",
        message(attributes_raw=float("nan")),
        message(attributes_raw=float("inf")),
    ],
)
def test_jsonl_preflight_zero_writes(tmp_path: Path, invalid: bytes) -> None:
    base = str(tmp_path / "base")
    assert cli("create", base, "--format", "jam").returncode == 0
    result = cli(
        "write", base, "--format", "jam", "--jsonl", data=message() + b"\n" + invalid
    )
    assert result.returncode == 2, result.stderr
    assert not result.stdout
    assert b"record 2" in result.stderr or b"record 3" in result.stderr
    assert cli("export", base, "--format", "jam").stdout == b""


def test_partial_writer_failure(tmp_path: Path) -> None:
    base = str(tmp_path / "base")
    assert cli("create", base, "--format", "msg").returncode == 0
    result = cli(
        "write",
        base,
        "--format",
        "msg",
        "--jsonl",
        data=message() + b"\n" + message(subject="x" * 72) + b"\n",
    )
    assert result.returncode == 4
    assert len(result.stdout.splitlines()) == 1
    assert b"record 2" in result.stderr and b"committed 1" in result.stderr
    assert len(cli("export", base, "--format", "msg").stdout.splitlines()) == 1


@pytest.mark.parametrize(
    "charset,data,expected",
    [
        ("IBMPC", bytes.fromhex("91 9b 86 0d 0a"), "æøå\r\n".encode()),
        ("UTF8", "🦄\r\n".encode(), "🦄\r\n".encode()),
        ("UTF-8", b"A\x00", b"A\x00"),
    ],
)
def test_decode(charset: str, data: bytes, expected: bytes) -> None:
    result = cli("decode", "--charset", charset, data=data)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    assert not result.stderr


def test_decode_errors_and_repair() -> None:
    assert cli("decode", "--charset", "UTF-8", data=b"\xff").returncode == 4
    assert cli("decode", "--charset", "unknown", data=b"x").returncode == 4
    result = cli("repair", "--json", data="Temperature 20°".encode())
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["changed"] is False
    assert (
        cli("repair", data="Temperature 20°".encode()).stdout
        == "Temperature 20°".encode()
    )


@pytest.mark.parametrize("format", ["msg", "opus", "jam", "squish", "hudson"])
@pytest.mark.parametrize("command", ["read", "export", "write"])
def test_missing_base(tmp_path: Path, format: str, command: str) -> None:
    args = [command, str(tmp_path / "missing")]
    if command == "read":
        args.append("1")
    args.extend(["--format", format])
    if format == "hudson":
        args.extend(["--board", "1"])
    result = cli(*args, data=message())
    assert result.returncode == 3, result.stderr
    assert not result.stdout


@pytest.mark.parametrize(
    "flags",
    [
        ["write", "x", "--format", "jam", "--board", "1"],
        ["write", "x", "--format", "hudson"],
        ["export", "x", "--format", "hudson", "--board", "201"],
        ["read", "x", "0", "--format", "jam"],
        ["write", "x", "--format", "jam", "--lock-timeout", "nan"],
        ["read", "x", "1", "--format", "msg", "--revision", "--body"],
    ],
)
def test_invalid_flags(flags: list[str]) -> None:
    result = cli(*flags, data=message())
    assert result.returncode == 2
    assert not result.stdout


def test_archive_issues_and_strict_corruption(tmp_path: Path) -> None:
    base = str(tmp_path)
    assert cli("write", base, "--format", "msg", data=message()).returncode == 0
    (tmp_path / "9.MSG").write_bytes(b"short")
    assert cli("export", base, "--format", "msg").returncode == 4
    archived = cli("export", base, "--format", "msg", "--archive")
    assert archived.returncode == 7
    assert len(archived.stdout.splitlines()) == 1
    issue = json.loads(archived.stderr)
    assert issue["type"] == "reader_issue"
    assert issue["issue"]["source_id"] == "9"


def test_sparse_msg_number(tmp_path: Path) -> None:
    assert (
        cli("write", str(tmp_path), "--format", "msg", data=message()).returncode == 0
    )
    (tmp_path / "1.MSG").rename(tmp_path / "17.MSG")
    assert cli("read", str(tmp_path), "1", "--format", "msg").returncode == 3
    result = cli("read", str(tmp_path), "17", "--format", "msg")
    assert json.loads(result.stdout)["message"]["msgno"] == 17


def test_hudson_literal_board_mapping(tmp_path: Path) -> None:
    def pascal(value: bytes, width: int) -> bytes:
        return bytes([len(value)]) + value + bytes(width - len(value) - 1)

    headers = []
    for offset, (number, board) in enumerate(((17, 1), (42, 200))):
        headers.append(
            struct.pack(
                "<10H2BH3B",
                number,
                0,
                0,
                0,
                offset,
                1,
                230,
                1,
                230,
                150,
                2,
                2,
                0,
                0,
                0,
                board,
            )
            + pascal(b"12:34", 6)
            + pascal(b"01-02-24", 9)
            + pascal(b"Bob", 36)
            + pascal(b"Alice", 36)
            + pascal(b"Test", 73)
        )
    (tmp_path / "MSGHDR.BBS").write_bytes(b"".join(headers))
    (tmp_path / "MSGIDX.BBS").write_bytes(bytes.fromhex("11 00 01 2a 00 c8"))
    (tmp_path / "MSGTXT.BBS").write_bytes(
        pascal(b"First\0", 256) + pascal(b"Second\0", 256)
    )
    result = cli("export", str(tmp_path), "--format", "hudson")
    assert result.returncode == 0, result.stderr
    envelopes = [json.loads(line) for line in result.stdout.splitlines()]
    assert [item["source"]["board"] for item in envelopes] == [1, 200]
    assert (
        cli(
            "read", str(tmp_path), "42", "--format", "hudson", "--board", "1"
        ).returncode
        == 3
    )
    assert (
        cli(
            "read",
            str(tmp_path),
            "42",
            "--format",
            "hudson",
            "--board",
            "200",
            "--body",
        ).stdout
        == b"Second"
    )
