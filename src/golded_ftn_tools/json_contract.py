"""Strict write input and dataclass output for schema version 1."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import cast

from golded_ftn import ControlLine, FtnAddress, OutgoingMessage

_WRITE_FIELDS = frozenset(
    {
        "from_name",
        "to_name",
        "subject",
        "body_text",
        "external_id",
        "from_address",
        "to_address",
        "posted_at",
        "attributes_raw",
        "control_lines",
        "reply_to_msgno",
        "reply1st_msgno",
        "reply_next_msgno",
        "reply_list",
        "routing_seen_by",
        "routing_path",
    }
)


class InputError(ValueError):
    """An input record does not satisfy the CLI contract."""

    def __init__(self, message: str, *, code: str = "input.structure") -> None:
        super().__init__(message)
        self.code = code


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise InputError(f"invalid JSON constant: {value}")


def load(text: str) -> dict[str, object]:
    try:
        value: object = json.loads(
            text, object_pairs_hook=_pairs, parse_constant=_constant
        )
    except (ValueError, RecursionError) as error:
        raise InputError(str(error)) from error
    if not isinstance(value, dict):
        raise InputError("expected one JSON object")
    return cast(dict[str, object], value)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InputError(f"{name} must be a string")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise InputError(f"{name} contains an unpaired Unicode surrogate")
    return value


def _optional_string(data: dict[str, object], name: str) -> str | None:
    value = data.get(name)
    return None if value is None else _string(value, name)


def _integer(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise InputError(f"{name} must be a non-negative integer")
    return value


def _optional_integer(data: dict[str, object], name: str) -> int | None:
    value = data.get(name)
    return None if value is None else _integer(value, name)


def _array(data: dict[str, object], name: str) -> list[object]:
    value = data.get(name, [])
    if not isinstance(value, list):
        raise InputError(f"{name} must be an array")
    return cast(list[object], value)


def _address(data: dict[str, object], name: str) -> FtnAddress | None:
    value = _optional_string(data, name)
    if value is None:
        return None
    try:
        return FtnAddress.from_string(value)
    except ValueError as error:
        raise InputError(str(error)) from error


def _date(data: dict[str, object], format: str) -> datetime | None:
    value = _optional_string(data, "posted_at")
    if value is None:
        return None
    if (
        re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?", value
        )
        is None
    ):
        raise InputError(
            "posted_at must use YYYY-MM-DDTHH:MM:SS with optional offset",
            code="input.date",
        )
    # datetime.fromisoformat accepts offset overflow such as +00:99.
    if len(value) == 25 and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise InputError("posted_at has an invalid UTC offset", code="input.date")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as error:
        raise InputError(str(error), code="input.date") from error
    if format in {"msg", "opus", "hudson"} and result.tzinfo is not None:
        raise InputError(f"{format} requires a naive posted_at", code="input.date")
    return result


def unwrap_write_record(data: dict[str, object]) -> dict[str, object]:
    """Map an export envelope or flat object into write-input fields."""
    if data.get("type") != "message":
        return data
    message = data.get("message")
    if not isinstance(message, dict):
        raise InputError("message envelope requires a message object")
    payload: dict[str, object] = {
        key: value for key, value in message.items() if key in _WRITE_FIELDS
    }
    controls = message.get("control_lines")
    if isinstance(controls, dict):
        if "control_lines" not in payload or isinstance(
            payload.get("control_lines"), dict
        ):
            kludges = controls.get("kludges", [])
            if not isinstance(kludges, list):
                raise InputError("control_lines.kludges must be an array")
            payload["control_lines"] = kludges
        if "routing_seen_by" not in payload:
            seen_by = controls.get("seen_by", [])
            if not isinstance(seen_by, list):
                raise InputError("control_lines.seen_by must be an array")
            payload["routing_seen_by"] = seen_by
        if "routing_path" not in payload:
            path = controls.get("path", [])
            if not isinstance(path, list):
                raise InputError("control_lines.path must be an array")
            payload["routing_path"] = path
    elif "control_lines" in payload and not isinstance(payload["control_lines"], list):
        raise InputError("control_lines must be an array or nested export object")
    posted_at = payload.get("posted_at")
    if isinstance(posted_at, str) and "." in posted_at:
        # Export may include microseconds; write input forbids them.
        head, _, rest = posted_at.partition(".")
        suffix = ""
        for index, char in enumerate(rest):
            if not char.isdigit():
                suffix = rest[index:]
                break
        payload["posted_at"] = head + suffix
    return payload


def outgoing(data: dict[str, object], format: str) -> OutgoingMessage:
    exported = data.get("type") == "message"
    source = data.get("source")
    source_format = source.get("format") if isinstance(source, dict) else None
    data = unwrap_write_record(data)
    if exported and isinstance(data.get("external_id"), str):
        if cast(str, data["external_id"]).startswith("hash:sha256:"):
            data.pop("external_id")
    if exported and source_format != format:
        data.pop("attributes_raw", None)
    required = {"from_name", "to_name", "subject", "body_text"}
    allowed = required | (_WRITE_FIELDS - required)
    if unknown := data.keys() - allowed:
        raise InputError(f"unknown fields: {', '.join(sorted(unknown))}")
    if missing := required - data.keys():
        raise InputError(f"missing fields: {', '.join(sorted(missing))}")
    controls: list[ControlLine] = []
    for item in _array(data, "control_lines"):
        if not isinstance(item, dict):
            raise InputError("control_lines entries must be objects")
        if (
            item.keys() - {"name", "value", "raw"}
            or not {"name", "value"} <= item.keys()
        ):
            raise InputError("controls require name/value and optional raw only")
        controls.append(
            ControlLine(
                name=_string(item["name"], "control.name"),
                value=_string(item["value"], "control.value"),
                raw=_string(item.get("raw", ""), "control.raw"),
            )
        )
    posted_at = _date(data, format if not exported else "export")
    if exported and posted_at is not None:
        if posted_at.tzinfo is not None:
            posted_at = posted_at.astimezone(UTC).replace(tzinfo=None)
        if format == "squish" and not any(
            control.name.upper() == "TZUTC" for control in controls
        ):
            controls.append(ControlLine(name="TZUTC", value="+0000", raw=""))
    return OutgoingMessage(
        from_name=_string(data["from_name"], "from_name"),
        to_name=_string(data["to_name"], "to_name"),
        subject=_string(data["subject"], "subject"),
        body_text=_string(data["body_text"], "body_text"),
        external_id=_optional_string(data, "external_id"),
        from_address=_address(data, "from_address"),
        to_address=_address(data, "to_address"),
        posted_at=posted_at,
        attributes_raw=_optional_integer(data, "attributes_raw"),
        control_lines=tuple(controls),
        reply_to_msgno=_optional_integer(data, "reply_to_msgno"),
        reply1st_msgno=_optional_integer(data, "reply1st_msgno"),
        reply_next_msgno=_optional_integer(data, "reply_next_msgno"),
        reply_list=tuple(_integer(v, "reply_list") for v in _array(data, "reply_list")),
        routing_seen_by=tuple(
            _string(v, "routing_seen_by") for v in _array(data, "routing_seen_by")
        ),
        routing_path=tuple(
            _string(v, "routing_path") for v in _array(data, "routing_path")
        ),
    )


def _default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def dump(value: object) -> str:
    return (
        json.dumps(
            value,
            default=_default,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    )
