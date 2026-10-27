"""Format selection through public package APIs."""

from contextlib import AbstractContextManager
from pathlib import Path

from golded_ftn import (
    FtnAddress,
    MessageBaseReader,
    MessageWriterSession,
    ParsedMessage,
    ParserException,
    WriterOptions,
)
from golded_ftn_hudson import HudsonReader, HudsonWriter
from golded_ftn_jam import JamReader, JamWriter
from golded_ftn_msg import MsgReader, MsgWriter
from golded_ftn_sqlite import (
    AreaDefinition,
    AreaKind,
    SqliteDatabase,
    SqliteReader,
    SqliteWriter,
)
from golded_ftn_squish import SquishReader, SquishWriter


def reader(format: str, *, area: str | None = None) -> MessageBaseReader:
    match format:
        case "msg":
            return MsgReader()
        case "opus":
            return MsgReader("opus")
        case "jam":
            return JamReader()
        case "squish":
            return SquishReader()
        case "hudson":
            return HudsonReader()
        case "sqlite":
            return SqliteReader(area)
        case _:
            raise ValueError(f"Unknown format: {format}")


def create(
    format: str,
    base: Path,
    *,
    area: str | None = None,
    area_name: str | None = None,
    kind: str = "echomail",
    origin: str | None = None,
) -> None:
    match format:
        case "msg" | "opus":
            MsgWriter().create(
                base, header_format="opus" if format == "opus" else "ftsc"
            )
        case "jam":
            JamWriter().create(base)
        case "squish":
            SquishWriter().create(base)
        case "hudson":
            HudsonWriter().create(base)
        case "sqlite":
            if area is None:
                raise ValueError("sqlite create requires area")
            default_origin = (
                FtnAddress.from_string(origin) if origin is not None else None
            )
            SqliteDatabase.create(
                base,
                area=AreaDefinition(
                    code=area,
                    name=area_name if area_name is not None else area,
                    kind=AreaKind(kind),
                    default_origin=default_origin,
                ),
            )
        case _:
            raise ValueError(f"Unknown format: {format}")


def session(
    format: str,
    base: Path,
    board: int | None,
    options: WriterOptions,
    *,
    area: str | None = None,
) -> AbstractContextManager[MessageWriterSession]:
    match format:
        case "msg" | "opus":
            return MsgWriter().open(
                base, options, header_format="opus" if format == "opus" else "ftsc"
            )
        case "jam":
            return JamWriter().open(base, options)
        case "squish":
            return SquishWriter().open(base, options)
        case "hudson":
            assert board is not None
            return HudsonWriter().open(base, board, options)
        case "sqlite":
            return SqliteWriter(area).open(base, options)
        case _:
            raise ValueError(f"Unknown format: {format}")


def board_of(message: ParsedMessage, format: str) -> int | None:
    if format != "hudson":
        return None
    # HudsonReader sets area_meta_key from the numeric header board byte.
    key = message.area_meta_key or ""
    prefix, separator, number = key.partition(":")
    if (
        prefix != "hudson"
        or not separator
        or not number.isascii()
        or not number.isdigit()
    ):
        raise ParserException("Hudson reader did not supply a numeric area_meta_key")
    board = int(number)
    if not 1 <= board <= 200:
        raise ParserException("Hudson reader supplied an invalid board")
    return board
