"""Six commands, redirected UTF-8 streams and per-message commit receipts."""

from __future__ import annotations

import argparse
import math
import os
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from golded_ftn import ReaderIssue

from . import __version__, api
from .errors import ToolError
from .json_contract import dump


def _timeout(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("lock timeout must be a number") from error
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("lock timeout must be finite and non-negative")
    return number


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="ftnt",
        description="FTN message bases, JSONL pipes and text filters.",
        epilog=(
            "Keep bases offline: close GoldED and other users "
            "before reading or writing."
        ),
    )
    root.add_argument("--version", action="version", version=f"ftnt {__version__}")
    root.add_argument(
        "--debug", action="store_true", help="show error tracebacks on stderr"
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("create", "write", "read", "export", "decode", "repair"):
        epilog = ""
        if name == "write":
            epilog = (
                "JSONL is preflighted before writing. Each append commits separately. "
                "A broken pipe can hide a committed receipt; rerunning may "
                "create duplicates."
            )
        elif name == "export":
            epilog = (
                "Readers may buffer the base. Output can be partial: "
                "check exit status, "
                "including archive exit 7. Export is not a byte-identical backup."
            )
        elif name in {"decode", "repair"}:
            epilog = "This command reads the whole input into memory."
        sub = commands.add_parser(name, epilog=epilog)
        sub.add_argument("--debug", action="store_true", default=argparse.SUPPRESS)
        if name in {"create", "write", "read", "export"}:
            sub.add_argument("base", type=Path)
            sub.add_argument(
                "--format",
                required=True,
                choices=("msg", "opus", "jam", "squish", "hudson"),
            )
        if name in {"write", "read", "export"}:
            sub.add_argument("--board", type=int, help="Hudson board, 1..200")
        if name == "write":
            sub.add_argument("--jsonl", action="store_true")
            sub.add_argument("--encoding", default="CP850")
        if name in {"write", "read"}:
            sub.add_argument("--lock-timeout", type=_timeout, default=5.0)
        if name in {"read", "export"}:
            sub.add_argument("--fallback-charset", default="CP850")
        if name == "read":
            sub.add_argument("msgno", type=int)
            group = sub.add_mutually_exclusive_group()
            group.add_argument("--body", action="store_true")
            group.add_argument("--revision", action="store_true")
        if name == "export":
            sub.add_argument("--archive", action="store_true")
        if name == "decode":
            sub.add_argument("--charset", required=True)
        if name == "repair":
            sub.add_argument("--charset")
            sub.add_argument("--json", action="store_true")
            sub.add_argument("--no-prefer-quoted", action="store_true")
    return root


def _emit(value: object, stream: BinaryIO | None = None) -> None:
    target = sys.stdout.buffer if stream is None else stream
    target.write(dump(value).encode("utf-8"))
    target.flush()


def _text(value: str) -> None:
    sys.stdout.buffer.write(value.encode("utf-8"))
    sys.stdout.buffer.flush()


def _report(error: ToolError, debug: bool) -> int:
    if error.input_record is not None:
        print(
            f"ftnt: input record {error.input_record}; "
            f"committed {error.committed}: {error}",
            file=sys.stderr,
        )
    else:
        print(f"ftnt: {error}", file=sys.stderr)
    if debug:
        traceback.print_exc(file=sys.stderr)
    return error.exit_status


def _run(args: argparse.Namespace) -> int:
    if args.command == "decode":
        _text(api.decode(sys.stdin.buffer.read(), args.charset))
        return 0
    if args.command == "repair":
        result = api.repair(
            sys.stdin.buffer.read(),
            charset=args.charset,
            as_json=args.json,
            prefer_quoted=not args.no_prefer_quoted,
        )
        if isinstance(result, str):
            _text(result)
        else:
            _emit(result)
        return 0
    if args.command == "create":
        _emit(api.create(args.format, args.base))
        return 0
    if args.command == "write":
        records = sys.stdin.buffer if args.jsonl else [sys.stdin.buffer.read()]
        for receipt in api.write(
            args.format,
            args.base,
            records,
            board=args.board,
            encoding=args.encoding,
            lock_timeout=args.lock_timeout,
        ):
            _emit(receipt)
        return 0
    if args.command == "read":
        result = api.read(
            args.format,
            args.base,
            args.msgno,
            board=args.board,
            fallback_charset=args.fallback_charset,
            lock_timeout=args.lock_timeout,
            body=args.body,
            revision=args.revision,
        )
        if isinstance(result, str):
            _text(result)
        else:
            _emit(result)
        return 0

    def on_issue(issue: ReaderIssue) -> None:
        _emit(
            {"schema_version": 1, "type": "reader_issue", "issue": issue},
            sys.stderr.buffer,
        )

    exported = api.export(
        args.format,
        args.base,
        board=args.board,
        fallback_charset=args.fallback_charset,
        archive=args.archive,
        on_issue=on_issue if args.archive else None,
    )
    for envelope in exported:
        _emit(envelope)
    return exported.exit_status


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return _run(args)
    except BrokenPipeError:
        # Avoid a second failure when Python flushes stdout at shutdown.
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, sys.stdout.fileno())
        finally:
            os.close(null)
        return 141 if os.name == "posix" else 6
    except KeyboardInterrupt:
        print("ftnt: interrupted", file=sys.stderr)
        return 130
    except ToolError as error:
        return _report(error, args.debug)
    except Exception as error:
        from .errors import classify

        return _report(classify(error), args.debug)
