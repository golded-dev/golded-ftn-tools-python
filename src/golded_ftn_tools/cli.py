"""Six commands, redirected UTF-8 streams and per-message commit receipts."""

from __future__ import annotations

import argparse
import errno
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
    root.add_argument(
        "--json-errors",
        action="store_true",
        help="print errors as JSON objects on stderr",
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name in (
        "create",
        "write",
        "read",
        "export",
        "decode",
        "repair",
        "heads",
        "catalog",
    ):
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
        elif name == "heads":
            epilog = (
                "One JSON object per message, without the body. "
                "The default limit is 100. --limit 0 reads the whole base."
            )
        sub = commands.add_parser(name, epilog=epilog)
        sub.add_argument("--debug", action="store_true", default=argparse.SUPPRESS)
        sub.add_argument(
            "--json-errors", action="store_true", default=argparse.SUPPRESS
        )
        if name in {"create", "write", "read", "export", "heads"}:
            sub.add_argument("base", type=Path)
            sub.add_argument(
                "--format",
                required=True,
                choices=("msg", "opus", "jam", "squish", "hudson"),
            )
        if name in {"write", "read", "export", "heads"}:
            sub.add_argument("--board", type=int, help="Hudson board, 1..200")
        if name == "write":
            sub.add_argument("--jsonl", action="store_true")
            sub.add_argument("--encoding", default="CP850")
        if name in {"write", "read"}:
            sub.add_argument("--lock-timeout", type=_timeout, default=5.0)
        if name in {"read", "export", "heads"}:
            sub.add_argument("--fallback-charset", default="CP850")
        if name == "heads":
            sub.add_argument("--limit", type=int, default=100)
            sub.add_argument("--after", type=int)
            sub.add_argument("--archive", action="store_true")
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
    data = dump(value).encode("utf-8")
    if stream is None:
        _stdout(data)
    else:
        stream.write(data)
        stream.flush()


def _stdout(data: bytes) -> None:
    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except OSError as error:
        if _pipe_closed(error):
            raise BrokenPipeError() from error
        raise


def _text(value: str) -> None:
    _stdout(value.encode("utf-8"))


def _sentence(error: ToolError) -> str:
    if error.input_record is None:
        return str(error)
    return f"input record {error.input_record}; committed {error.committed}: {error}"


def _report(error: ToolError, debug: bool, json_errors: bool) -> int:
    sentence = _sentence(error)
    structured = json_errors or not sys.stderr.isatty()
    if structured:
        payload: dict[str, object] = {
            "schema_version": 1,
            "type": "error",
            "code": error.code,
            "exit_status": error.exit_status,
            "message": sentence,
        }
        if error.input_record is not None:
            payload["input_record"] = error.input_record
            payload["committed"] = error.committed
        _emit(payload, sys.stderr.buffer)
    else:
        print(f"ftnt: {sentence}", file=sys.stderr)
    if debug and not structured:
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
    if args.command == "catalog":
        _emit(api.catalog())
        return 0
    if args.command == "heads":
        return _heads(args)
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


def _heads(args: argparse.Namespace) -> int:
    def on_issue(issue: ReaderIssue) -> None:
        _emit(
            {"schema_version": 1, "type": "reader_issue", "issue": issue},
            sys.stderr.buffer,
        )

    indexed = api.heads(
        args.format,
        args.base,
        board=args.board,
        fallback_charset=args.fallback_charset,
        archive=args.archive,
        limit=args.limit,
        after=args.after,
        on_issue=on_issue if args.archive else None,
    )
    for row in indexed:
        _emit(row)
    return indexed.exit_status


def _pipe_closed(error: OSError) -> bool:
    if isinstance(error, BrokenPipeError):
        return True
    if error.errno in {errno.EPIPE, errno.EINVAL, errno.ECONNRESET, errno.EBADF}:
        return True
    return getattr(error, "winerror", None) in {109, 232}


def _discard_stdout() -> None:
    """Point stdout at null so the interpreter's shutdown flush stays quiet."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, sys.stdout.fileno())
        finally:
            os.close(null)
    except OSError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        code = _run(args)
        try:
            sys.stdout.buffer.flush()
        except OSError as error:
            if not _pipe_closed(error):
                raise
            _discard_stdout()
            return 141 if os.name == "posix" else 6
        return code
    except BrokenPipeError:
        # Avoid a second failure when Python flushes stdout at shutdown.
        _discard_stdout()
        return 141 if os.name == "posix" else 6
    except KeyboardInterrupt:
        print("ftnt: interrupted", file=sys.stderr)
        return 130
    except ToolError as error:
        return _report(error, args.debug, args.json_errors)
    except Exception as error:
        from .errors import classify

        return _report(classify(error), args.debug, args.json_errors)
