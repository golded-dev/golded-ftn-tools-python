"""Strict write input and dataclass output for schema version 1."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import cast

from golded_ftn import ControlLine, FtnAddress, OutgoingMessage


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
    if format == "squish" and result.tzinfo is None:
        raise InputError(
            "squish requires a timezone-aware posted_at", code="input.date"
        )
    return result


def outgoing(data: dict[str, object], format: str) -> OutgoingMessage:
    required = {"from_name", "to_name", "subject", "body_text"}
    allowed = required | {
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
    return OutgoingMessage(
        from_name=_string(data["from_name"], "from_name"),
        to_name=_string(data["to_name"], "to_name"),
        subject=_string(data["subject"], "subject"),
        body_text=_string(data["body_text"], "body_text"),
        external_id=_optional_string(data, "external_id"),
        from_address=_address(data, "from_address"),
        to_address=_address(data, "to_address"),
        posted_at=_date(data, format),
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
