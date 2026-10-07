"""Machine-readable description of the running ftnt binary."""

from __future__ import annotations

import argparse
from typing import cast

from . import __version__
from .errors import ERROR_CODES

DATE_RULES: dict[str, str] = {
    "msg": "naive posted_at",
    "opus": "naive posted_at",
    "jam": "naive or timezone-aware posted_at",
    "squish": "timezone-aware posted_at",
    "hudson": "naive posted_at",
}

WRITE_FIELDS: dict[str, str] = {
    "from_name": "string, required",
    "to_name": "string, required",
    "subject": "string, required",
    "body_text": "string, required",
    "external_id": "string or null",
    "from_address": "FTN address string or null",
    "to_address": "FTN address string or null",
    "posted_at": "datetime string or null",
    "attributes_raw": "integer >= 0 or null",
    "control_lines": "array of {name, value, raw?}",
    "reply_to_msgno": "integer >= 0 or null",
    "reply1st_msgno": "integer >= 0 or null",
    "reply_next_msgno": "integer >= 0 or null",
    "reply_list": "array of integers >= 0",
    "routing_seen_by": "array of strings",
    "routing_path": "array of strings",
}


def _flag(action: argparse.Action) -> dict[str, object] | None:
    if action.dest == "help":
        return None
    default: object = action.default
    if default is argparse.SUPPRESS:
        default = None
    choices = list(action.choices) if action.choices is not None else None
    return {
        "name": action.dest,
        "options": list(action.option_strings),
        "required": bool(getattr(action, "required", False)),
        "default": default,
        "choices": choices,
    }


def catalog() -> dict[str, object]:
    """Return the command catalog. Built from the live parser."""
    from .cli import parser

    root = parser()
    commands: list[dict[str, object]] = []
    for action in root._actions:  # noqa: SLF001
        if not isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            continue
        choices = cast(dict[str, argparse.ArgumentParser], action.choices)
        for name, sub in choices.items():
            flags = [flag for item in sub._actions if (flag := _flag(item))]  # noqa: SLF001
            commands.append({"name": name, "flags": flags})
    return {
        "schema_version": 1,
        "type": "catalog",
        "program": "ftnt",
        "version": __version__,
        "commands": commands,
        "write_fields": WRITE_FIELDS,
        "date_rules": DATE_RULES,
        "exit_codes": {
            "ok": 0,
            **{code: status for code, status in ERROR_CODES.items()},
            "archive_issues": 7,
            "interrupted": 130,
            "broken_pipe": 141,
        },
        "error_codes": ERROR_CODES,
    }
