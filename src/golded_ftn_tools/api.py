"""Library operations behind the ftnt commands.

Functions return values and raise ToolError. They do not read argv or stdout.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from golded_ftn import (
    ConflictError,
    ParsedMessage,
    ReaderIssue,
    ReaderOptions,
    WriterOptions,
    detect_charset,
    repair_mojibake,
)

from . import adapters
from .errors import ToolError, classify
from .json_contract import InputError, dump, load, outgoing


class ExportResult:
    """Envelopes from one export. Exit status is valid after iteration."""

    def __init__(
        self, envelopes: Iterator[dict[str, object]], issues: list[int]
    ) -> None:
        self._envelopes = envelopes
        self._issues = issues

    def __iter__(self) -> Iterator[dict[str, object]]:
        yield from self._envelopes

    @property
    def exit_status(self) -> int:
        return 7 if self._issues[0] else 0


def _board(format: str, board: int | None, *, required: bool) -> None:
    if board is not None and (format != "hudson" or not 1 <= board <= 200):
        raise ToolError(
            "input.structure",
            2,
            "--board is only valid for Hudson and must be in 1..200",
        )
    if required and format == "hudson" and board is None:
        raise ToolError(
            "input.structure",
            2,
            "Hudson write/read requires --board 1..200",
        )


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


def create(format: str, base: Path) -> dict[str, object]:
    """Create an empty base and return the create_result object."""
    resolved = base.resolve()
    try:
        adapters.create(format, resolved)
    except (ToolError, BrokenPipeError, KeyboardInterrupt):
        raise
    except Exception as error:
        raise classify(error) from error
    return {
        "schema_version": 1,
        "type": "create_result",
        "format": format,
        "base": str(resolved),
    }


def write(
    format: str,
    base: Path,
    records: Iterable[bytes],
    *,
    board: int | None = None,
    encoding: str = "CP850",
    lock_timeout: float = 5.0,
) -> Iterator[dict[str, object]]:
    """Append preflighted records. Yield one write_result per commit."""
    _board(format, board, required=True)
    resolved = base.resolve()
    committed = 0
    record = 1
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", newline="\n") as spool:
        count = 0
        for record, raw in enumerate(records, 1):
            try:
                data = load(raw.decode("utf-8", errors="strict"))
                outgoing(data, format)
                spool.write(dump(data))
            except InputError as error:
                raise ToolError(
                    error.code,
                    2,
                    f"input record {record}: {error}; committed 0",
                ) from error
            except UnicodeError as error:
                raise ToolError(
                    "input.structure",
                    2,
                    f"input record {record}: {error}; committed 0",
                ) from error
            count = record
        if not count:
            raise ToolError(
                "input.structure",
                2,
                "input record 1: empty batch; committed 0",
            )
        spool.seek(0)
        record = 1
        try:
            with adapters.session(
                format,
                resolved,
                board,
                WriterOptions(
                    target_charset=encoding,
                    lock_timeout=lock_timeout,
                    concurrent=False,
                ),
            ) as session:
                for record, text in enumerate(spool, 1):
                    result = session.append(outgoing(load(text), format))
                    committed += 1
                    yield {
                        "schema_version": 1,
                        "type": "write_result",
                        "input_record": record,
                        "identity": result.identity,
                        "revision": result.revision,
                    }
        except BrokenPipeError:
            raise
        except Exception as error:
            raise classify(error, input_record=record, committed=committed) from error


def read(
    format: str,
    base: Path,
    msgno: int,
    *,
    board: int | None = None,
    fallback_charset: str = "CP850",
    lock_timeout: float = 5.0,
    body: bool = False,
    revision: bool = False,
) -> dict[str, object] | str:
    """Return one envelope, or the body text when body is set."""
    _board(format, board, required=True)
    if msgno < 1:
        raise ToolError("input.structure", 2, "msgno must be positive")
    resolved = base.resolve()
    try:
        return _read(
            format,
            resolved,
            msgno,
            board=board,
            fallback_charset=fallback_charset,
            lock_timeout=lock_timeout,
            body=body,
            revision=revision,
        )
    except ToolError:
        raise
    except (BrokenPipeError, KeyboardInterrupt):
        raise
    except Exception as error:
        raise classify(error) from error


def _read(
    format: str,
    base: Path,
    msgno: int,
    *,
    board: int | None,
    fallback_charset: str,
    lock_timeout: float,
    body: bool,
    revision: bool,
) -> dict[str, object] | str:
    if revision:
        with adapters.session(
            format,
            base,
            board,
            WriterOptions(
                target_charset=fallback_charset,
                lock_timeout=lock_timeout,
                concurrent=False,
            ),
        ) as session:
            try:
                result = session.read(msgno)
            except ConflictError as error:
                raise ToolError(
                    "message.missing", 3, f"message {msgno} not found"
                ) from error
            envelope = _envelope(result.message, format, base)
            envelope.update(identity=result.identity, revision=result.revision)
            return envelope
    options = ReaderOptions(fallback_charset=fallback_charset, archive_mode=False)
    for message in adapters.reader(format).read(base, options):
        if board is not None and adapters.board_of(message, format) != board:
            continue
        if message.msgno != msgno:
            continue
        if body:
            return message.body_text
        return _envelope(message, format, base)
    raise ToolError("message.missing", 3, f"message {msgno} not found")


def export(
    format: str,
    base: Path,
    *,
    board: int | None = None,
    fallback_charset: str = "CP850",
    archive: bool = False,
    on_issue: Callable[[ReaderIssue], None] | None = None,
) -> ExportResult:
    """Stream message envelopes. Exit status is 7 when archive issues occurred."""
    _board(format, board, required=False)
    resolved = base.resolve()
    issues = [0]

    def remember(issue: ReaderIssue) -> None:
        issues[0] += 1
        if callable(on_issue):
            on_issue(issue)

    options = ReaderOptions(
        fallback_charset=fallback_charset,
        archive_mode=archive,
        on_issue=remember if archive else None,
    )

    def envelopes() -> Iterator[dict[str, object]]:
        try:
            for message in adapters.reader(format).read(resolved, options):
                if board is not None and adapters.board_of(message, format) != board:
                    continue
                yield _envelope(message, format, resolved)
        except ToolError:
            raise
        except (BrokenPipeError, KeyboardInterrupt):
            raise
        except Exception as error:
            raise classify(error) from error

    return ExportResult(envelopes(), issues)


def heads(
    format: str,
    base: Path,
    *,
    board: int | None = None,
    fallback_charset: str = "CP850",
    archive: bool = False,
    limit: int = 100,
    after: int | None = None,
    on_issue: Callable[[ReaderIssue], None] | None = None,
) -> ExportResult:
    """Index messages without body text. limit 0 reads the whole base."""
    _board(format, board, required=False)
    if limit < 0:
        raise ToolError("input.structure", 2, "limit must be zero or positive")
    if after is not None and after < 0:
        raise ToolError("input.structure", 2, "after must be zero or positive")
    resolved = base.resolve()
    issues = [0]

    def remember(issue: ReaderIssue) -> None:
        issues[0] += 1
        if on_issue is not None:
            on_issue(issue)

    options = ReaderOptions(
        fallback_charset=fallback_charset,
        archive_mode=archive,
        on_issue=remember if archive else None,
    )

    def rows() -> Iterator[dict[str, object]]:
        produced = 0
        try:
            for message in adapters.reader(format).read(resolved, options):
                if board is not None and adapters.board_of(message, format) != board:
                    continue
                if after is not None and message.msgno <= after:
                    continue
                if limit and produced >= limit:
                    break
                row: dict[str, object] = {
                    "schema_version": 1,
                    "type": "head",
                    "msgno": message.msgno,
                    "from_name": message.from_name,
                    "to_name": message.to_name,
                    "subject": message.subject,
                    "posted_at": message.posted_at,
                    "board": adapters.board_of(message, format),
                    "body_bytes": len(message.body_text.encode("utf-8")),
                }
                controls = message.control_lines
                if controls is not None and controls.msgid is not None:
                    row["msgid"] = controls.msgid
                produced += 1
                yield row
        except ToolError:
            raise
        except (BrokenPipeError, KeyboardInterrupt):
            raise
        except Exception as error:
            raise classify(error) from error

    return ExportResult(rows(), issues)


def catalog() -> dict[str, object]:
    """Return the description of this binary."""
    from .catalog import catalog as build_catalog

    return build_catalog()


def decode(data: bytes, charset: str) -> str:
    """Decode a whole buffer with the core charset aliases."""
    try:
        chosen = detect_charset(b"", charset)
        return data.decode(chosen, errors="strict")
    except ToolError:
        raise
    except (BrokenPipeError, KeyboardInterrupt):
        raise
    except Exception as error:
        raise classify(error) from error


def repair(
    data: bytes,
    *,
    charset: str | None = None,
    as_json: bool = False,
    prefer_quoted: bool = True,
) -> dict[str, object] | str:
    """Repair UTF-8 text. as_json returns the repair_result object."""
    try:
        if charset is not None:
            detect_charset(b"", charset)
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise InputError(f"repair expects UTF-8: {error}") from error
        result = repair_mojibake(text, charset, prefer_quoted)
    except ToolError:
        raise
    except (BrokenPipeError, KeyboardInterrupt):
        raise
    except Exception as error:
        raise classify(error) from error
    if not as_json:
        return result.text
    return {
        "schema_version": 1,
        "type": "repair_result",
        "text": result.text,
        "changed": result.changed,
        "confidence": result.confidence,
    }
