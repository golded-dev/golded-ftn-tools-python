"""Six commands, redirected UTF-8 streams and per-message commit receipts."""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from golded_ftn import (
    ConflictError,
    LockTimeoutError,
    ParsedMessage,
    ParserException,
    ReaderIssue,
    ReaderOptions,
    RollbackError,
    WriterError,
    WriterOptions,
    detect_charset,
    repair_mojibake,
)

from . import __version__, adapters
from .json_contract import InputError, dump, load, outgoing


class MissingTargetError(FileNotFoundError):
    """No base or message matched the requested identity."""


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


def _error_code(error: Exception) -> int:
    if isinstance(error, InputError):
        return 2
    if isinstance(error, (FileNotFoundError, FileExistsError)):
        return 3
    if isinstance(error, (LockTimeoutError, ConflictError)):
        return 5
    if isinstance(error, (OSError, RollbackError)):
        return 6
    if isinstance(error, (ValueError, LookupError, ParserException, WriterError)):
        return 4
    return 1


def _write(args: argparse.Namespace, base: Path) -> int:
    committed = 0
    record = 1
    # Binary lines let invalid UTF-8 retain its input record number.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", newline="\n") as spool:
        inputs = sys.stdin.buffer if args.jsonl else [sys.stdin.buffer.read()]
        count = 0
        for record, raw in enumerate(inputs, 1):
            try:
                data = load(raw.decode("utf-8", errors="strict"))
                outgoing(data, args.format)
                spool.write(dump(data))
            except (InputError, UnicodeError) as error:
                raise InputError(
                    f"input record {record}: {error}; committed 0"
                ) from error
            count = record
        if not count:
            raise InputError("input record 1: empty batch; committed 0")
        spool.seek(0)
        record = 1
        try:
            with adapters.session(
                args.format,
                base,
                args.board,
                WriterOptions(
                    target_charset=args.encoding,
                    lock_timeout=args.lock_timeout,
                    concurrent=False,
                ),
            ) as session:
                for record, text in enumerate(spool, 1):
                    result = session.append(outgoing(load(text), args.format))
                    committed += 1
                    _emit(
                        {
                            "schema_version": 1,
                            "type": "write_result",
                            "input_record": record,
                            "identity": result.identity,
                            "revision": result.revision,
                        }
                    )
        except BrokenPipeError:
            raise
        except Exception as error:
            print(
                f"ftnt: input record {record}; committed {committed}: {error}",
                file=sys.stderr,
            )
            if args.debug:
                traceback.print_exc(file=sys.stderr)
            return _error_code(error)
    return 0


def _envelope(message: ParsedMessage, format: str, base: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "type": "message",
        "source": {
            "format": format,
            "base": str(base),
            "board": adapters.board_of(message, format),
        },
        "message": message,
    }


def _read(args: argparse.Namespace, base: Path) -> int:
    issues = 0

    def on_issue(issue: ReaderIssue) -> None:
        nonlocal issues
        issues += 1
        _emit(
            {"schema_version": 1, "type": "reader_issue", "issue": issue},
            sys.stderr.buffer,
        )

    if args.command == "read" and args.revision:
        with adapters.session(
            args.format,
            base,
            args.board,
            WriterOptions(
                target_charset=args.fallback_charset,
                lock_timeout=args.lock_timeout,
                concurrent=False,
            ),
        ) as session:
            try:
                result = session.read(args.msgno)
            except ConflictError as error:
                raise MissingTargetError(f"message {args.msgno} not found") from error
            envelope = _envelope(result.message, args.format, base)
            envelope.update(identity=result.identity, revision=result.revision)
            _emit(envelope)
            return 0
    archive = args.command == "export" and args.archive
    options = ReaderOptions(
        fallback_charset=args.fallback_charset,
        archive_mode=archive,
        on_issue=on_issue if archive else None,
    )
    for message in adapters.reader(args.format).read(base, options):
        if (
            args.board is not None
            and adapters.board_of(message, args.format) != args.board
        ):
            continue
        if args.command == "read":
            if message.msgno != args.msgno:
                continue
            if args.body:
                _text(message.body_text)
            else:
                _emit(_envelope(message, args.format, base))
            return 0
        _emit(_envelope(message, args.format, base))
    if args.command == "read":
        raise MissingTargetError(f"message {args.msgno} not found")
    return 7 if issues else 0


def _run(args: argparse.Namespace) -> int:
    if args.command == "decode":
        # Empty declaration input selects the explicit fallback through core aliases.
        charset = detect_charset(b"", args.charset)
        _text(sys.stdin.buffer.read().decode(charset, errors="strict"))
        return 0
    if args.command == "repair":
        if args.charset is not None:
            detect_charset(b"", args.charset)
        try:
            text = sys.stdin.buffer.read().decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise InputError(f"repair expects UTF-8: {error}") from error
        result = repair_mojibake(text, args.charset, not args.no_prefer_quoted)
        if args.json:
            _emit(
                {
                    "schema_version": 1,
                    "type": "repair_result",
                    "text": result.text,
                    "changed": result.changed,
                    "confidence": result.confidence,
                }
            )
        else:
            _text(result.text)
        return 0
    base = args.base.resolve()
    if args.command != "create":
        if args.board is not None and (
            args.format != "hudson" or not 1 <= args.board <= 200
        ):
            raise InputError("--board is only valid for Hudson and must be in 1..200")
        if (
            args.format == "hudson"
            and args.command in {"write", "read"}
            and args.board is None
        ):
            raise InputError("Hudson write/read requires --board 1..200")
    if args.command == "read" and args.msgno < 1:
        raise InputError("msgno must be positive")
    if args.command == "create":
        adapters.create(args.format, base)
        _emit(
            {
                "schema_version": 1,
                "type": "create_result",
                "format": args.format,
                "base": str(base),
            }
        )
        return 0
    if args.command == "write":
        return _write(args, base)
    return _read(args, base)


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
    except Exception as error:
        print(f"ftnt: {error}", file=sys.stderr)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return _error_code(error)
