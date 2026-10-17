"""Packet, nodelist, node CLI and --log-level precedence. Synthetic fixtures only."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from golded_ftn_nodelist import compute_nodelist_crc
from test_cli import cli

_PIPE_EXIT = 141 if os.name == "posix" else 6

BODY_SENTINEL = "BODY-LEAK-PLEASE-ABSENT"
PASSWORD_SENTINEL = "area-fix-pass-sentinel"
SESSION_SENTINEL = "session-pass-sentinel"
SUBJECT_SENTINEL = "SECRET-private-subject"


def _packet_json() -> bytes:
    return json.dumps(
        {
            "origin": "2:999/2@fidonet",
            "destination": "2:999/1@fidonet",
            "created_at": "2026-10-17T12:00:00",
            "product_id": 254,
            "messages": [
                {
                    "from_name": "Remote",
                    "to_name": "Sysop",
                    "subject": SUBJECT_SENTINEL,
                    "body_text": f"\x01MSGID: 2:999/2 00000001\r{BODY_SENTINEL}\r",
                    "from_address": "2:999/2@fidonet",
                    "to_address": "2:999/1@fidonet",
                    "posted_at": "2026-10-17T12:00:00",
                    "tzutc_minutes": 120,
                    "message_class": "netmail",
                }
            ],
        }
    ).encode()


def _nodelist_bytes() -> bytes:
    body = (
        b";A\r\n"
        b"Zone,2,Europe,Copenhagen,Zone_Coord,45-11112222,9600,CM\r\n"
        b",10,Node_Ten,Odense,Anders_And,45-22223333,9600,CM\r\n"
        b";\r\n"
    )
    crc = compute_nodelist_crc(body)
    header = (
        f";A FidoNet Nodelist for Friday, October 17, 2026 -- Day number 290 : {crc:05d}\r\n"
    ).encode("ascii")
    return header + body + b"\x1a"


def _write_config(
    root: Path,
    *,
    log_level: str | None = "INFO",
    extra_logging_key: bool = False,
) -> Path:
    inbound = root / "inbound"
    outbound = root / "outbound"
    state = root / "state"
    held = root / "held"
    receipts = root / "receipts"
    netmail = root / "netmail"
    echo = root / "echo"
    for path in (inbound, outbound, state, held, receipts, netmail, echo):
        path.mkdir(parents=True, exist_ok=True)
    logging_block = ""
    if log_level is not None:
        extra = '\nunexpected = "no"\n' if extra_logging_key else ""
        logging_block = f'\n[logging]\nlevel = "{log_level}"{extra}\n'
    text = f"""
product_id = 254
charset_fallback = "CP850"
lock_timeout = 2.0
{logging_block}
[paths]
state = "{state}"
inbound = "{inbound}"
secure_inbound = "{inbound}"
outbound = "{outbound}"
held = "{held}"
receipts = "{receipts}"

[[domains]]
name = "fidonet"
default_zone = 2

[[akas]]
address = "2:999/1@fidonet"

[[links]]
address = "2:999/2@fidonet"
session_password = "{SESSION_SENTINEL}"
areafix_password = "{PASSWORD_SENTINEL}"
host = "127.0.0.1"
port = 24554

[[areas]]
domain = "fidonet"
tag = "NETMAIL"
format = "jam"
path = "{netmail / "mail"}"
kind = "netmail"

[[areas]]
domain = "fidonet"
tag = "TEST"
format = "jam"
path = "{echo / "test"}"
kind = "echo"

[[area_rights]]
domain = "fidonet"
tag = "TEST"
link = "2:999/2@fidonet"
import = true
export = true

[[mailboxes]]
address = "2:999/1@fidonet"
domain = "fidonet"
area_tag = "NETMAIL"

[[routes]]
destination = "2:999/3@fidonet"
via = "2:999/2@fidonet"
"""
    config = root / "node.toml"
    config.write_text(text, encoding="utf-8")
    return config


def test_help_lists_network_commands() -> None:
    result = cli("--help")
    assert result.returncode == 0
    for name in (b"packet", b"nodelist", b"node"):
        assert name in result.stdout
    node = cli("node", "--help")
    assert node.returncode == 0
    for name in (b"check", b"toss", b"scan", b"poll", b"serve", b"status", b"recover"):
        assert name in node.stdout


def test_invalid_log_level_fails_closed() -> None:
    result = cli("--log-level", "VERBOSE", "catalog")
    assert result.returncode == 2
    assert b"VERBOSE" in result.stderr or b"invalid log level" in result.stderr
    assert b"Traceback" not in result.stderr
    dotted = cli("--log-level", "ınfo", "catalog")
    assert dotted.returncode == 2
    assert b"invalid log level" in dotted.stderr
    assert "ınfo".encode() not in dotted.stderr


def test_packet_write_read_roundtrip(tmp_path: Path) -> None:
    packet = tmp_path / "mail.pkt"
    written = cli("packet", "write", "--output", str(packet), data=_packet_json())
    assert written.returncode == 0, written.stderr
    summary = json.loads(written.stdout)
    assert summary["type"] == "packet_write_result"
    assert summary["messages_written"] == 1
    read = cli("packet", "read", str(packet))
    assert read.returncode == 0, read.stderr
    rows = [json.loads(line) for line in read.stdout.splitlines()]
    assert rows[0]["type"] == "packet_header"
    assert rows[0]["product_id"] == 254
    assert rows[1]["type"] == "packet_record"
    assert rows[-1]["messages"] == 1
    blob = read.stdout + read.stderr
    assert BODY_SENTINEL.encode() not in blob
    assert SUBJECT_SENTINEL.encode() not in blob
    assert b"password" not in blob.lower()


def test_packet_errors_are_codes_only(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pkt"
    result = cli("packet", "read", str(missing))
    assert result.returncode == 3
    assert str(missing).encode() not in result.stderr
    assert b"packet_unreadable" in result.stderr
    bad = cli("packet", "write", data=b"{")
    assert bad.returncode == 2
    assert b"invalid_input" in bad.stderr
    assert b"Traceback" not in bad.stderr


def test_nodelist_parse_lookup_export(tmp_path: Path) -> None:
    path = tmp_path / "nodelist.txt"
    path.write_bytes(_nodelist_bytes())
    parsed = cli(
        "nodelist",
        "parse",
        str(path),
        "--domain",
        "fidonet",
        "--default-zone",
        "2",
    )
    assert parsed.returncode == 0, parsed.stderr
    rows = [json.loads(line) for line in parsed.stdout.splitlines()]
    assert rows[0]["type"] == "nodelist_document"
    assert rows[0]["entries"] == 2
    lookup = cli(
        "nodelist",
        "lookup",
        str(path),
        "--domain",
        "fidonet",
        "--default-zone",
        "2",
        "--address",
        "2:2/10",
    )
    assert lookup.returncode == 0, lookup.stderr
    found = [json.loads(line) for line in lookup.stdout.splitlines()]
    assert found[0]["matches"] == 1
    named = cli(
        "nodelist",
        "lookup",
        str(path),
        "--domain",
        "fidonet",
        "--default-zone",
        "2",
        "--name",
        "Anders And",
    )
    assert named.returncode == 0, named.stderr
    assert json.loads(named.stdout.splitlines()[0])["matches"] == 1
    exported = cli(
        "nodelist",
        "export",
        str(path),
        "--domain",
        "fidonet",
        "--default-zone",
        "2",
        "--format",
        "nam",
        "--edition-date",
        "2026-10-17",
        "--network-label",
        "FidoNet",
        "--output",
        str(tmp_path / "out.nam"),
    )
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout)["type"] == "nodelist_export"


def test_log_level_cli_overrides_toml(tmp_path: Path) -> None:
    config = _write_config(tmp_path, log_level="DEBUG")
    defaulted = cli("node", "--config", str(config), "status")
    assert defaulted.returncode == 0, defaulted.stderr
    assert json.loads(defaulted.stdout)["logging_level"] == "DEBUG"
    overridden = cli("--log-level", "OFF", "node", "--config", str(config), "status")
    assert overridden.returncode == 0, overridden.stderr
    assert json.loads(overridden.stdout)["logging_level"] == "OFF"
    info = _write_config(tmp_path / "info", log_level=None)
    implicit = cli("node", "--config", str(info), "status")
    assert implicit.returncode == 0, implicit.stderr
    assert json.loads(implicit.stdout)["logging_level"] == "INFO"
    explicit = cli("--log-level", "WARNING", "node", "--config", str(info), "status")
    assert json.loads(explicit.stdout)["logging_level"] == "WARNING"


def test_malformed_logging_not_hidden_by_cli(tmp_path: Path) -> None:
    config = _write_config(tmp_path, log_level="INFO", extra_logging_key=True)
    result = cli("--log-level", "DEBUG", "node", "--config", str(config), "check")
    assert result.returncode == 2
    assert b"invalid_logging" in result.stderr
    assert PASSWORD_SENTINEL.encode() not in result.stderr
    assert str(config).encode() not in result.stderr


def test_node_check_toss_scan_recover_serve(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    packet = tmp_path / "inbound" / "mail.pkt"
    written = cli("packet", "write", "--output", str(packet), data=_packet_json())
    assert written.returncode == 0, written.stderr
    check = cli("node", "--config", str(config), "check")
    assert check.returncode == 0, check.stderr
    payload = json.loads(check.stdout)
    assert payload["ok"] is True
    tossed = cli("node", "--config", str(config), "toss")
    assert tossed.returncode == 0, tossed.stderr
    scanned = cli("node", "--config", str(config), "scan")
    assert scanned.returncode == 0, scanned.stderr
    recovered = cli("node", "--config", str(config), "recover")
    assert recovered.returncode == 0, recovered.stderr
    served = cli("node", "--config", str(config), "serve", "--port", "0")
    assert served.returncode == 0, served.stderr
    bind = json.loads(served.stdout)
    assert bind["host"] in {"127.0.0.1", "::1"}
    assert bind["port"] >= 0
    forbidden = cli(
        "node", "--config", str(config), "serve", "--host", "8.8.8.8", "--port", "0"
    )
    assert forbidden.returncode == 4
    assert b"non_localhost_forbidden" in forbidden.stderr
    anyaddr = cli(
        "node", "--config", str(config), "serve", "--host", "0.0.0.0", "--port", "0"
    )
    assert anyaddr.returncode == 4
    assert b"non_localhost_forbidden" in anyaddr.stderr
    named = cli(
        "node",
        "--config",
        str(config),
        "poll",
        "--host",
        "example.com",
        "--port",
        "1",
    )
    assert named.returncode == 4
    assert b"non_localhost_forbidden" in named.stderr
    combined = (
        check.stdout
        + check.stderr
        + tossed.stdout
        + tossed.stderr
        + scanned.stdout
        + scanned.stderr
        + recovered.stdout
        + recovered.stderr
        + served.stdout
        + served.stderr
        + forbidden.stderr
        + anyaddr.stderr
        + named.stderr
    )
    assert BODY_SENTINEL.encode() not in combined
    assert PASSWORD_SENTINEL.encode() not in combined
    assert SESSION_SENTINEL.encode() not in combined
    assert SUBJECT_SENTINEL.encode() not in combined


def test_poll_connection_error_is_safe(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    result = cli(
        "node",
        "--config",
        str(config),
        "poll",
        "--host",
        "127.0.0.1",
        "--port",
        "1",
    )
    assert result.returncode != 0
    text = result.stderr
    assert BODY_SENTINEL.encode() not in text
    assert PASSWORD_SENTINEL.encode() not in text
    assert str(config).encode() not in text
    assert b"Traceback" not in text


def _closed_stdout(*args: str, data: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    process = subprocess.Popen(
        [sys.executable, "-m", "golded_ftn_tools", *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert (
        process.stdin is not None
        and process.stdout is not None
        and process.stderr is not None
    )
    process.stdout.close()
    process.stdin.write(data)
    process.stdin.close()
    stderr = process.stderr.read()
    command = [sys.executable, "-m", "golded_ftn_tools", *args]
    return subprocess.CompletedProcess(command, process.wait(timeout=20), b"", stderr)


def test_packet_read_closed_stdout_is_broken_pipe(tmp_path: Path) -> None:
    packet = tmp_path / "mail.pkt"
    written = cli("packet", "write", "--output", str(packet), data=_packet_json())
    assert written.returncode == 0, written.stderr
    result = _closed_stdout("packet", "read", str(packet))
    assert result.returncode == _PIPE_EXIT
    assert b"packet_unreadable" not in result.stderr


def test_packet_write_closed_stdout_is_broken_pipe() -> None:
    result = _closed_stdout("packet", "write", data=_packet_json())
    assert result.returncode == _PIPE_EXIT
    assert b"packet_unreadable" not in result.stderr
    assert b"packet_unwritable" not in result.stderr


def test_nodelist_stdout_closed_pipe_is_broken_pipe(tmp_path: Path) -> None:
    path = tmp_path / "nodelist.txt"
    path.write_bytes(_nodelist_bytes())
    parsed = _closed_stdout(
        "nodelist", "parse", str(path), "--domain", "fidonet", "--default-zone", "2"
    )
    assert parsed.returncode == _PIPE_EXIT
    assert b"nodelist_unreadable" not in parsed.stderr
    exported = _closed_stdout(
        "nodelist",
        "export",
        str(path),
        "--domain",
        "fidonet",
        "--default-zone",
        "2",
        "--format",
        "nam",
        "--edition-date",
        "2026-10-17",
        "--network-label",
        "FidoNet",
    )
    assert exported.returncode == _PIPE_EXIT
    assert b"nodelist_unreadable" not in exported.stderr


def test_windows_style_closed_stdout_is_broken_pipe(tmp_path: Path) -> None:
    packet = tmp_path / "mail.pkt"
    assert (
        cli("packet", "write", "--output", str(packet), data=_packet_json()).returncode
        == 0
    )
    path = tmp_path / "nodelist.txt"
    path.write_bytes(_nodelist_bytes())
    script = r"""
import errno, io, os, sys
from golded_ftn_tools.cli import main
class ClosedPipe(io.RawIOBase):
    failed = False
    def writable(self):
        return True
    def fileno(self):
        return 1
    def write(self, data):
        if not self.failed:
            self.failed = True
            error = OSError(errno.EINVAL, 'Invalid argument')
            error.winerror = 109
            raise error
        return os.write(1, data)
sys.stdout = io.TextIOWrapper(io.BufferedWriter(ClosedPipe()), encoding='utf-8')
raise SystemExit(main(sys.argv[1:]))
"""
    for args in (
        ["packet", "read", str(packet)],
        ["nodelist", "parse", str(path), "--domain", "fidonet", "--default-zone", "2"],
    ):
        result = subprocess.run(
            [sys.executable, "-c", script, *args],
            capture_output=True,
            timeout=20,
        )
        assert result.returncode == _PIPE_EXIT, result.stderr
        assert b"packet_unreadable" not in result.stderr
        assert b"nodelist_unreadable" not in result.stderr
        assert b"io_failed" not in result.stderr


def test_output_write_failures_are_unwritable(tmp_path: Path) -> None:
    missing = tmp_path / "missing-dir" / "out.pkt"
    packet = cli("packet", "write", "--output", str(missing), data=_packet_json())
    assert packet.returncode == 6
    assert b"packet_unwritable" in packet.stderr
    assert b"packet_unreadable" not in packet.stderr
    assert str(missing).encode() not in packet.stderr
    path = tmp_path / "nodelist.txt"
    path.write_bytes(_nodelist_bytes())
    exported = cli(
        "nodelist",
        "export",
        str(path),
        "--domain",
        "fidonet",
        "--default-zone",
        "2",
        "--format",
        "nam",
        "--edition-date",
        "2026-10-17",
        "--network-label",
        "FidoNet",
        "--output",
        str(tmp_path / "missing-dir" / "out.nam"),
    )
    assert exported.returncode == 6
    assert b"nodelist_unwritable" in exported.stderr
    assert b"nodelist_unreadable" not in exported.stderr


def test_same_code_same_exit_from_classifier() -> None:
    from golded_ftn_nodelist import NodelistError
    from golded_ftn_packet import PacketError
    from golded_ftn_tosser import TosserConfigError, TosserError

    from golded_ftn_tools.network import classify_network, status_for_network_code

    cases: list[tuple[Exception, str, int]] = [
        (PacketError("packet_unreadable"), "packet_unreadable", 3),
        (PacketError("packet_unwritable"), "packet_unwritable", 6),
        (NodelistError("nodelist_unreadable"), "nodelist_unreadable", 3),
        (NodelistError("nodelist_unwritable"), "nodelist_unwritable", 6),
        (TosserError("lock_timeout"), "lock_timeout", 5),
        (TosserError("lock_order"), "lock_order", 5),
        (TosserError("address_busy"), "address_busy", 5),
        (TosserConfigError("invalid_logging"), "invalid_logging", 2),
        (TosserError("invalid_paths"), "invalid_paths", 2),
        (TosserError("invalid_aka"), "invalid_aka", 2),
        (TosserError("invalid_link"), "invalid_link", 2),
        (TosserError("invalid_area"), "invalid_area", 2),
    ]
    for error, code, status in cases:
        classified = classify_network(error)
        assert classified.code == code
        assert classified.exit_status == status
        assert str(classified) == code
        if not isinstance(error, TosserConfigError):
            assert status_for_network_code(code) == status


def test_lock_timeout_from_from_path_exits_5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from golded_ftn_tosser import TosserError, TosserNode

    from golded_ftn_tools.cli import main

    def boom(path: object, *, cli_log_level: str | None = None) -> object:
        raise TosserError("lock_timeout")

    monkeypatch.setattr(TosserNode, "from_path", staticmethod(boom))
    config = _write_config(tmp_path)
    assert main(["--json-errors", "node", "--config", str(config), "status"]) == 5


def test_nodelist_unreadable_from_parse_exits_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from golded_ftn_nodelist import NodelistError

    from golded_ftn_tools import network
    from golded_ftn_tools.cli import main

    def boom(*args: object, **kwargs: object) -> object:
        raise NodelistError("nodelist_unreadable")

    monkeypatch.setattr(network, "parse_list", boom)
    path = tmp_path / "nodelist.txt"
    path.write_bytes(_nodelist_bytes())
    assert (
        main(
            [
                "--json-errors",
                "nodelist",
                "parse",
                str(path),
                "--domain",
                "fidonet",
                "--default-zone",
                "2",
            ]
        )
        == 3
    )


def test_link_index_and_port_are_precise(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    missing = cli(
        "node",
        "--config",
        str(config),
        "poll",
        "--host",
        "127.0.0.1",
        "--port",
        "1",
        "--link-index",
        "99",
    )
    assert missing.returncode == 2
    assert b"invalid_link_index" in missing.stderr
    assert b"invalid_charset" not in missing.stderr
    negative = cli(
        "node",
        "--config",
        str(config),
        "poll",
        "--host",
        "127.0.0.1",
        "--port",
        "1",
        "--link-index",
        "-1",
    )
    assert negative.returncode == 2
    assert b"invalid_link_index" in negative.stderr
    for port in ("-1", "65536", "70000"):
        result = cli(
            "node",
            "--config",
            str(config),
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            port,
        )
        assert result.returncode == 2
        assert b"invalid_port" in result.stderr
        assert b"internal" not in result.stderr


def test_lookup_error_kinds_are_distinct() -> None:
    from golded_ftn_tools.network import classify_network

    charset = classify_network(LookupError("unknown encoding: not-a-codec"))
    assert charset.code == "invalid_charset"
    assert charset.exit_status == 4
    assert str(charset) == "invalid_charset"
    index = classify_network(IndexError("list index out of range"))
    assert index.code == "invalid_link_index"
    assert index.exit_status == 2
    key = classify_network(KeyError("missing"))
    assert key.code == "invalid_link_index"
    overflow = classify_network(OverflowError())
    assert overflow.code == "invalid_port"
    assert overflow.exit_status == 2


def test_unknown_fallback_charset_is_invalid_charset(tmp_path: Path) -> None:
    packet = tmp_path / "mail.pkt"
    written = cli("packet", "write", "--output", str(packet), data=_packet_json())
    assert written.returncode == 0, written.stderr
    result = cli("packet", "read", str(packet), "--fallback-charset", "not-a-codec")
    assert result.returncode == 4
    assert b"invalid_charset" in result.stderr
    assert b"not-a-codec" not in result.stderr


def test_network_missing_message_equals_code(monkeypatch: pytest.MonkeyPatch) -> None:
    import golded_ftn_tools.cli as cli_mod
    from golded_ftn_tools.errors import ToolError

    real = __import__

    def blocked(
        name: str,
        globs: Mapping[str, object] | None = None,
        locs: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if fromlist and "network" in fromlist:
            raise ImportError("missing extra")
        return real(name, globs, locs, fromlist, level)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(ToolError) as caught:
        cli_mod._run_network(
            argparse.Namespace(command="packet", packet_command="read")
        )
    error = caught.value
    assert error.code == "network_missing"
    assert str(error) == "network_missing"
    assert error.exit_status == 4
    assert "." not in error.code


def test_classify_safe_is_not_a_second_table() -> None:
    import golded_ftn_tools.errors as errors
    from golded_ftn_tools.network import classify_network

    assert not hasattr(errors, "classify_safe")
    assert classify_network is not getattr(errors, "classify", None)


def test_open_node_keeps_from_path_emitter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from golded_ftn_tosser import TosserNode
    from golded_ftn_tosser.diagnostics import LogLevel

    from golded_ftn_tools import network

    seen: dict[str, object] = {}
    original = TosserNode.from_path

    def wrapped(path: str | Path, *, cli_log_level: str | None = None) -> TosserNode:
        node = original(path, cli_log_level=cli_log_level)
        seen["emitter"] = node.emitter
        return node

    monkeypatch.setattr(TosserNode, "from_path", staticmethod(wrapped))
    config = _write_config(tmp_path, log_level="DEBUG")
    node = network._open_node(config, "OFF")
    assert node.emitter is seen["emitter"]
    assert node.config.logging_level is LogLevel.OFF
    assert node.emitter._level is LogLevel.OFF


def test_cli_log_level_controls_events_after_open(tmp_path: Path) -> None:
    config = _write_config(tmp_path, log_level="DEBUG")
    off = cli("--log-level", "OFF", "node", "--config", str(config), "check")
    assert off.returncode == 0, off.stderr
    assert b"job_completed" not in off.stderr
    assert b"event=" not in off.stderr
    debug = cli("--log-level", "DEBUG", "node", "--config", str(config), "check")
    assert debug.returncode == 0, debug.stderr
    assert b"job_completed" in debug.stderr or b"event=" in debug.stderr
