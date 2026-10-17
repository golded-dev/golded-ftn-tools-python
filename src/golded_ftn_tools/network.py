"""Packet, nodelist and node CLI operations. Requires the ``[network]`` extra."""

from __future__ import annotations

import ipaddress
import json
import logging
import sys
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any, BinaryIO, Literal, TextIO, cast

from golded_ftn import FtnAddress
from golded_ftn_binkp import BinkpError, BsoError
from golded_ftn_nodelist import (
    CrcPolicy,
    ExportFormat,
    ExportHeader,
    ListDialect,
    ListEntry,
    NodeIdentity,
    NodelistError,
    ParseOptions,
    export_list,
    find_by_address,
    find_by_name,
    normalize_identity,
    parse_list,
)
from golded_ftn_packet import (
    MessageDecodeOptions,
    PacketAddressFields,
    PacketError,
    PacketHeaderInput,
    PacketMessageInput,
    decode_message,
    encode_message,
    open_packet,
    write_packet,
)
from golded_ftn_tosser import (
    SafeStreamHandler,
    TosserError,
    TosserNode,
)
from golded_ftn_tosser.errors import TosserConfigError

from .errors import ToolError
from .json_contract import dump

_STATUS_2 = frozenset(
    {
        "config_unreadable",
        "invalid_logging",
        "invalid_config",
        "missing_product_id",
        "invalid_paths",
        "invalid_aka",
        "invalid_link",
        "invalid_area",
        "invalid_link_index",
        "invalid_port",
        "invalid_input",
        "invalid_address",
    }
)
_STATUS_3 = frozenset({"packet_unreadable", "nodelist_unreadable", "unreadable"})
_STATUS_5 = frozenset({"lock_timeout", "lock_order", "address_busy"})
_STATUS_6 = frozenset({"packet_unwritable", "nodelist_unwritable", "io_failed"})


def attach_cli_event_handler(stream: TextIO | None = None) -> None:
    """Attach a CLI-owned SafeStreamHandler. Never configure the root logger."""
    logger = logging.getLogger("golded_ftn_tosser.events")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    target = sys.stderr if stream is None else stream
    if any(isinstance(handler, SafeStreamHandler) for handler in logger.handlers):
        return
    logger.addHandler(SafeStreamHandler(stream=target))


def status_for_network_code(code: str) -> int:
    if code in _STATUS_2:
        return 2
    if code in _STATUS_3:
        return 3
    if code in _STATUS_5:
        return 5
    if code in _STATUS_6:
        return 6
    return 4


def _tool_error(code: str) -> ToolError:
    return ToolError(code, status_for_network_code(code), code)


def classify_network(error: Exception) -> ToolError:
    if isinstance(error, ToolError):
        return error
    if isinstance(error, TosserConfigError):
        return ToolError(error.code, 2, error.code)
    if isinstance(
        error, (TosserError, PacketError, NodelistError, BinkpError, BsoError)
    ):
        return _tool_error(error.code)
    if isinstance(error, FileNotFoundError):
        return _tool_error("unreadable")
    if isinstance(error, OSError):
        return _tool_error("io_failed")
    if isinstance(error, (IndexError, KeyError)):
        return _tool_error("invalid_link_index")
    if isinstance(error, OverflowError):
        return _tool_error("invalid_port")
    if isinstance(error, (UnicodeError, LookupError)):
        return _tool_error("invalid_charset")
    if isinstance(error, ValueError):
        return _tool_error("rejected")
    return ToolError("internal", 1, "internal")


def _reraise_closed_pipe(error: OSError) -> None:
    from .cli import _pipe_closed

    if _pipe_closed(error):
        raise BrokenPipeError() from error


def _emit_bytes(data: bytes) -> None:
    from .cli import _stdout

    _stdout(data)


def _emit(value: object) -> None:
    _emit_bytes(dump(value).encode("utf-8"))


def _read_bytes(path: Path, *, code: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        raise _tool_error(code) from None


def _parse_address(value: str) -> FtnAddress:
    address = FtnAddress.try_from_string(value.strip())
    if address is None:
        raise _tool_error("invalid_address")
    return address


def _fields(address: PacketAddressFields) -> dict[str, object]:
    return {
        "zone": address.zone,
        "net": address.net,
        "node": address.node,
        "point": address.point,
    }


def packet_read(path: Path, *, fallback_charset: str) -> int:
    try:
        options = MessageDecodeOptions(fallback_charset=fallback_charset)
    except PacketError:
        raise
    except (UnicodeError, LookupError, ValueError) as error:
        if isinstance(error, (IndexError, KeyError)):
            raise
        raise _tool_error("invalid_charset") from None
    try:
        with open_packet(path) as reader:
            header = reader.header
            _emit(
                {
                    "schema_version": 1,
                    "type": "packet_header",
                    "dialect": header.dialect,
                    "origin": _fields(header.origin),
                    "destination": _fields(header.destination),
                    "created_at": header.created_at.isoformat(),
                    "product_id": header.product_id,
                }
            )
            count = 0
            for record in reader:
                row: dict[str, object] = {
                    "schema_version": 1,
                    "type": "packet_record",
                    "ordinal": record.ordinal,
                    "offset": record.offset,
                }
                try:
                    decoded = decode_message(record, options=options)
                except PacketError as error:
                    row["error"] = error.code
                else:
                    row["posted_at"] = decoded.posted_at.isoformat()
                    row["attributes"] = decoded.attributes
                    row["packed_origin"] = _fields(decoded.packed_origin)
                    row["packed_destination"] = _fields(decoded.packed_destination)
                _emit(row)
                count += 1
            _emit(
                {
                    "schema_version": 1,
                    "type": "packet_summary",
                    "messages": count,
                    "complete": reader.is_complete,
                }
            )
    except PacketError:
        raise
    except OSError as error:
        _reraise_closed_pipe(error)
        raise _tool_error("packet_unreadable") from None
    return 0


def _naive_datetime(value: object) -> datetime:
    if type(value) is not str:
        raise _tool_error("invalid_input")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise _tool_error("invalid_input") from None
    if parsed.tzinfo is not None:
        raise _tool_error("invalid_input")
    return parsed


def _string(data: Mapping[str, object], name: str) -> str:
    value = data.get(name)
    if type(value) is not str:
        raise _tool_error("invalid_input")
    return value


def _optional_int(data: Mapping[str, object], name: str, default: int) -> int:
    if name not in data:
        return default
    value = data[name]
    if type(value) is not int:
        raise _tool_error("invalid_input")
    return value


def packet_write(raw: bytes, output: Path | None) -> int:
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise _tool_error("invalid_input") from None
    if not isinstance(payload, dict):
        raise _tool_error("invalid_input")
    data = cast(dict[str, object], payload)
    try:
        origin = _parse_address(_string(data, "origin"))
        destination = _parse_address(_string(data, "destination"))
        created_at = _naive_datetime(data.get("created_at"))
        product_id = data.get("product_id")
        if type(product_id) is not int:
            raise _tool_error("invalid_input")
        messages_raw = data.get("messages")
        if not isinstance(messages_raw, list):
            raise _tool_error("invalid_input")
        packed = []
        for item in messages_raw:
            if not isinstance(item, dict):
                raise _tool_error("invalid_input")
            row = cast(dict[str, object], item)
            message_class = row.get("message_class", "netmail")
            if message_class not in {"netmail", "echomail"}:
                raise _tool_error("invalid_input")
            area_raw = row.get("area_tag")
            area_tag: str | None
            if area_raw is None:
                area_tag = None
            elif type(area_raw) is str:
                area_tag = area_raw
            else:
                raise _tool_error("invalid_input")
            tz_raw = row.get("tzutc_minutes")
            tzutc: int | None
            if tz_raw is None:
                tzutc = None
            elif type(tz_raw) is int:
                tzutc = tz_raw
            else:
                raise _tool_error("invalid_input")
            charset = row.get("target_charset", "CP850")
            if type(charset) is not str:
                raise _tool_error("invalid_input")
            class_name: Literal["netmail", "echomail"] = (
                "netmail" if message_class == "netmail" else "echomail"
            )
            packed.append(
                encode_message(
                    PacketMessageInput(
                        from_name=_string(row, "from_name"),
                        to_name=_string(row, "to_name"),
                        subject=_string(row, "subject"),
                        body_text=_string(row, "body_text"),
                        from_address=_parse_address(_string(row, "from_address")),
                        to_address=_parse_address(_string(row, "to_address")),
                        posted_at=_naive_datetime(row.get("posted_at")),
                        tzutc_minutes=tzutc,
                        attributes=_optional_int(row, "attributes", 0),
                        cost=_optional_int(row, "cost", 0),
                        target_charset=charset,
                        message_class=class_name,
                        area_tag=area_tag,
                    )
                )
            )
        header = PacketHeaderInput(
            origin=origin,
            destination=destination,
            created_at=created_at,
            product_id=product_id,
        )
        if output is None:
            stream: BinaryIO = sys.stdout.buffer
            result = write_packet(stream, header=header, messages=packed)
            stream.flush()
        else:
            with output.open("wb") as handle:
                result = write_packet(handle, header=header, messages=packed)
    except PacketError:
        raise
    except ToolError:
        raise
    except OSError as error:
        _reraise_closed_pipe(error)
        raise _tool_error("packet_unwritable") from None
    if output is not None:
        _emit(
            {
                "schema_version": 1,
                "type": "packet_write_result",
                "bytes_written": result.bytes_written,
                "messages_written": result.messages_written,
            }
        )
    return 0


def _parse_options(args: Any) -> ParseOptions:
    try:
        dialect = ListDialect(args.dialect)
        crc_policy = CrcPolicy(args.crc_policy)
    except ValueError:
        raise _tool_error("invalid_input") from None
    encoding = args.encoding
    if encoding not in {"ascii", "cp850"}:
        raise _tool_error("invalid_input")
    return ParseOptions(
        dialect=dialect,
        domain=args.domain,
        default_zone=args.default_zone,
        encoding=cast(Literal["ascii", "cp850"], encoding),
        crc_policy=crc_policy,
    )


def _entry_row(entry: ListEntry) -> dict[str, object]:
    identity = entry.identity
    return {
        "schema_version": 1,
        "type": "nodelist_entry",
        "kind": entry.kind.value,
        "status": entry.status.value,
        "identity": {
            "domain": identity.domain,
            "zone": identity.zone,
            "net": identity.net,
            "node": identity.node,
            "point": identity.point,
        },
    }


def nodelist_parse(path: Path, args: Any) -> int:
    raw = _read_bytes(path, code="nodelist_unreadable")
    try:
        document = parse_list(raw, options=_parse_options(args))
    except NodelistError:
        raise
    _emit(
        {
            "schema_version": 1,
            "type": "nodelist_document",
            "dialect": document.dialect.value,
            "domain": document.domain,
            "entries": len(document.entries),
            "diagnostics": [item.code.value for item in document.diagnostics],
            "crc_status": document.crc.status.value,
            "day_of_year": document.day_of_year,
        }
    )
    for entry in document.entries:
        _emit(_entry_row(entry))
    return 0


def nodelist_lookup(path: Path, args: Any) -> int:
    raw = _read_bytes(path, code="nodelist_unreadable")
    try:
        document = parse_list(raw, options=_parse_options(args))
        if args.address is not None:
            ftn = _parse_address(args.address)
            identity = normalize_identity(ftn, domain=args.domain)
            matches = find_by_address(document, identity)
        else:
            matches = find_by_name(document, args.name)
    except NodelistError:
        raise
    except ValueError:
        raise _tool_error("invalid_input") from None
    _emit(
        {
            "schema_version": 1,
            "type": "nodelist_lookup",
            "matches": len(matches),
        }
    )
    for entry in matches:
        _emit(_entry_row(entry))
    return 0


def nodelist_export(path: Path, args: Any) -> int:
    raw = _read_bytes(path, code="nodelist_unreadable")
    try:
        document = parse_list(raw, options=_parse_options(args))
        edition = date.fromisoformat(args.edition_date)
        header = ExportHeader(
            edition_date=edition,
            day_of_year=edition.timetuple().tm_yday,
            network_label=args.network_label,
        )
        boss: NodeIdentity | None = None
        if args.boss is not None:
            boss = normalize_identity(_parse_address(args.boss), domain=args.domain)
        exported = export_list(
            document,
            format=ExportFormat(args.format),
            header=header,
            boss=boss,
        )
    except NodelistError:
        raise
    except ValueError:
        raise _tool_error("invalid_input") from None
    if args.output is None:
        try:
            _emit_bytes(exported)
        except OSError as error:
            _reraise_closed_pipe(error)
            raise _tool_error("nodelist_unwritable") from None
    else:
        try:
            args.output.write_bytes(exported)
        except OSError:
            raise _tool_error("nodelist_unwritable") from None
        _emit(
            {
                "schema_version": 1,
                "type": "nodelist_export",
                "bytes_written": len(exported),
            }
        )
    return 0


def _open_node(config: Path, cli_log_level: str | None) -> TosserNode:
    attach_cli_event_handler()
    return TosserNode.from_path(config, cli_log_level=cli_log_level)


def node_check(config: Path, cli_log_level: str | None) -> int:
    _emit(_open_node(config, cli_log_level).check())
    return 0


def node_toss(config: Path, cli_log_level: str | None) -> int:
    _emit(_open_node(config, cli_log_level).toss())
    return 0


def node_scan(config: Path, cli_log_level: str | None) -> int:
    _emit(_open_node(config, cli_log_level).scan())
    return 0


def node_status(config: Path, cli_log_level: str | None) -> int:
    _emit(_open_node(config, cli_log_level).status())
    return 0


def node_recover(config: Path, cli_log_level: str | None) -> int:
    _emit(_open_node(config, cli_log_level).recover())
    return 0


def _require_loopback_host(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise _tool_error("non_localhost_forbidden") from None
    if not address.is_loopback:
        raise _tool_error("non_localhost_forbidden")
    return host


def _require_tcp_port(port: int) -> int:
    if type(port) is not int or port < 0 or port > 65535:
        raise _tool_error("invalid_port")
    return port


def _require_link_index(index: int) -> int:
    if type(index) is not int or index < 0:
        raise _tool_error("invalid_link_index")
    return index


def node_poll(
    config: Path,
    cli_log_level: str | None,
    *,
    host: str,
    port: int,
    link_index: int,
) -> int:
    _require_loopback_host(host)
    _require_tcp_port(port)
    _require_link_index(link_index)
    try:
        _emit(
            _open_node(config, cli_log_level).poll(
                host=host, port=port, link_index=link_index
            )
        )
    except (IndexError, KeyError):
        raise _tool_error("invalid_link_index") from None
    return 0


def node_serve(
    config: Path,
    cli_log_level: str | None,
    *,
    host: str,
    port: int,
    wait: bool,
) -> int:
    _require_loopback_host(host)
    _require_tcp_port(port)
    _emit(_open_node(config, cli_log_level).serve(host=host, port=port, wait=wait))
    return 0
