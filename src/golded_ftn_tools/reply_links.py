"""Translate area-local reply numbers in exported messages."""

from dataclasses import dataclass, replace

from golded_ftn import UNSET, MessagePatch, OutgoingMessage

from .json_contract import InputError


@dataclass(frozen=True)
class SourceMessage:
    format: str
    base: str
    board: int | None
    area: str | None
    area_meta_key: str | None
    msgno: int


def source_message(data: dict[str, object]) -> SourceMessage | None:
    if data.get("type") != "message":
        return None
    source, message = data.get("source"), data.get("message")
    if not isinstance(source, dict) or not isinstance(message, dict):
        raise InputError("export requires source and message objects")
    format, base, board = source.get("format"), source.get("base"), source.get("board")
    msgno = message.get("msgno")
    area, area_meta_key = message.get("area"), message.get("area_meta_key")
    if (
        not isinstance(format, str)
        or not format
        or not isinstance(base, str)
        or not base
        or (board is not None and type(board) is not int)
        or type(msgno) is not int
        or msgno < 1
        or (area is not None and not isinstance(area, str))
        or (area_meta_key is not None and not isinstance(area_meta_key, str))
    ):
        raise InputError("export requires an unambiguous source message identity")
    return SourceMessage(format, base, board, area, area_meta_key, msgno)


def without_links(message: OutgoingMessage) -> OutgoingMessage:
    return replace(
        message,
        reply_to_msgno=None,
        reply1st_msgno=None,
        reply_next_msgno=None,
        reply_list=(),
    )


def link_patch(
    message: OutgoingMessage,
    source: SourceMessage,
    numbers: dict[SourceMessage, int],
) -> MessagePatch:
    def target(number: int | None) -> int | None:
        return numbers.get(replace(source, msgno=number)) if number else None

    return MessagePatch(
        reply_to_msgno=target(message.reply_to_msgno)
        if message.reply_to_msgno
        else UNSET,
        reply1st_msgno=target(message.reply1st_msgno)
        if message.reply1st_msgno
        else UNSET,
        reply_next_msgno=target(message.reply_next_msgno)
        if message.reply_next_msgno
        else UNSET,
        reply_list=tuple(
            mapped
            for number in message.reply_list
            if (mapped := target(number)) is not None
        )
        if message.reply_list
        else UNSET,
    )
