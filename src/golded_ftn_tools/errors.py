"""Stable error codes for the library surface and the CLI."""

from __future__ import annotations

from golded_ftn import (
    ConflictError,
    LockTimeoutError,
    ParserException,
    RollbackError,
    WriterError,
)

from .json_contract import InputError


class ToolError(Exception):
    """A failed operation with the exit status the CLI already uses."""

    def __init__(
        self,
        code: str,
        exit_status: int,
        message: str,
        *,
        input_record: int | None = None,
        committed: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_status = exit_status
        self.input_record = input_record
        self.committed = committed


def classify(
    error: Exception,
    *,
    input_record: int | None = None,
    committed: int | None = None,
) -> ToolError:
    """Map an exception to today's CLI exit status."""
    if isinstance(error, ToolError):
        return error
    message = str(error)
    if isinstance(error, InputError):
        code = error.code
        status = 2
    elif isinstance(error, (FileNotFoundError, FileExistsError)):
        if isinstance(error, FileExistsError):
            code = "base.exists"
        elif message.startswith("message "):
            code = "message.missing"
        else:
            code = "base.missing"
        status = 3
    elif isinstance(error, LockTimeoutError):
        code, status = "lock.timeout", 5
    elif isinstance(error, ConflictError):
        code, status = "revision.conflict", 5
    elif isinstance(error, (OSError, RollbackError)):
        code, status = "io.failed", 6
    elif isinstance(error, (UnicodeError, LookupError)):
        code, status = "input.charset", 4
    elif isinstance(error, ParserException):
        code, status = "reader.failed", 4
    elif isinstance(error, (ValueError, WriterError)):
        code, status = "writer.rejected", 4
    else:
        code, status = "internal", 1
    return ToolError(
        code,
        status,
        message,
        input_record=input_record,
        committed=committed,
    )
