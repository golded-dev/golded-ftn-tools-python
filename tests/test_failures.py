"""Deterministic stream/lock failures and public adapter exception reporting."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest
from test_cli import cli, message


def injected(
    code: str, *args: str, data: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-c", code, *args], input=data, capture_output=True, timeout=20
    )


@pytest.mark.parametrize(
    "exception,expected",
    [
        ("RollbackError('rollback failed')", 6),
        ("OSError('disk failed')", 6),
        ("LockTimeoutError('locked')", 5),
        ("ConflictError('changed')", 5),
        ("UnsupportedOperationError('unsupported')", 4),
        ("RuntimeError('internal')", 1),
    ],
)
def test_adapter_failure_preserves_receipts(
    tmp_path: Path, exception: str, expected: int
) -> None:
    base = str(tmp_path)
    assert cli("write", base, "--format", "msg", data=message()).returncode == 0
    code = f"""
from contextlib import contextmanager
import sys
from golded_ftn import (
    RollbackError, LockTimeoutError, ConflictError, UnsupportedOperationError,
)
from golded_ftn_tools import adapters
from golded_ftn_tools.cli import main
original = adapters.session
@contextmanager
def session(*args, **kwargs):
    with original(*args, **kwargs) as actual:
        class Wrapped:
            count = 0
            def append(self, message):
                self.count += 1
                if self.count == 2:
                    raise {exception}
                return actual.append(message)
        yield Wrapped()
adapters.session = session
raise SystemExit(main(sys.argv[1:]))
"""
    result = injected(
        code,
        "write",
        base,
        "--format",
        "msg",
        "--jsonl",
        data=message() + b"\n" + message(),
    )
    assert result.returncode == expected, result.stderr
    assert len(result.stdout.splitlines()) == 1
    assert b"record 2; committed 1" in result.stderr
    assert b"Traceback" not in result.stderr
    assert len(cli("export", base, "--format", "msg").stdout.splitlines()) == 2


def test_broken_receipt_pipe_after_commit(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "golded_ftn_tools",
            "write",
            str(tmp_path),
            "--format",
            "msg",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert (
        process.stdin is not None
        and process.stdout is not None
        and process.stderr is not None
    )
    process.stdout.close()
    process.stdin.write(message())
    process.stdin.close()
    assert process.wait(timeout=20) == (141 if os.name == "posix" else 6)
    assert process.stderr.read() == b""
    exported = cli("export", str(tmp_path), "--format", "msg")
    assert json.loads(exported.stdout)["message"]["msgno"] == 1


@pytest.mark.parametrize("command", ["catalog", "decode"])
def test_windows_invalid_argument_output_pipe(command: str) -> None:
    code = """
import errno, io, os, sys
from golded_ftn_tools.cli import main
class ClosedPipe(io.RawIOBase):
    failed = False
    def writable(self):
        return True
    def fileno(self):
        return 1
    def write(self, data):
        if not self.failed:
            self.failed = True
            error = OSError(errno.EINVAL, 'Invalid argument')
            error.winerror = 109
            raise error
        return os.write(1, data)
sys.stdout = io.TextIOWrapper(io.BufferedWriter(ClosedPipe()), encoding='utf-8')
args = [sys.argv[1]]
if args[0] == 'decode':
    args += ['--charset', 'UTF-8']
raise SystemExit(main(args))
"""
    result = injected(code, command, data=b"Text")
    assert result.returncode == (141 if os.name == "posix" else 6), result.stderr
    assert result.stderr == b""


def test_successful_main_keeps_stdout_open() -> None:
    result = injected(
        """
import sys
from golded_ftn_tools.cli import main
assert main(['decode', '--charset', 'UTF-8']) == 0
assert not sys.stdout.closed
sys.stdout.buffer.write(b'after')
""",
        data=b"Text",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"Textafter"


def test_output_disk_error_is_reported() -> None:
    result = injected(
        """
import errno, sys
from golded_ftn_tools.cli import main
class Buffer:
    def write(self, data):
        raise OSError(errno.ENOSPC, 'No space left on device')
    def flush(self):
        pass
class Output:
    buffer = Buffer()
    def flush(self):
        pass
sys.stdout = Output()
raise SystemExit(main(['catalog']))
"""
    )
    assert result.returncode == 6
    payload = json.loads(result.stderr)
    assert payload["code"] == "io.failed"
    assert payload["message"] == "io.failed"
    assert b"No space left on device" not in result.stderr
    assert b"ENOSPC" not in result.stderr


@pytest.mark.skipif(os.name != "posix", reason="POSIX SIGINT contract")
def test_sigint_inside_command() -> None:
    code = """
import sys, threading
from golded_ftn_tools import adapters
from golded_ftn_tools.cli import main
class Reader:
    def read(self, *args):
        print("ready", file=sys.stderr, flush=True)
        threading.Event().wait()
        return ()
adapters.reader = lambda *args, **kwargs: Reader()
raise SystemExit(main(["export", ".", "--format", "msg"]))
"""
    with subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as process:
        assert process.stderr is not None
        assert process.stderr.readline() == b"ready\n"
        process.send_signal(signal.SIGINT)
        output, error = process.communicate(timeout=20)
        assert process.returncode == 130
        assert not output
        assert error == b"ftnt: interrupted\n"


def test_missing_base_omits_path(tmp_path: Path) -> None:
    missing = tmp_path / "sentinel-missing-base"
    result = cli("read", str(missing), "1", "--format", "msg")
    assert result.returncode == 3, result.stderr
    assert str(missing).encode() not in result.stderr
    assert b"No such file" not in result.stderr
    assert b"base.missing" in result.stderr
    assert b"Traceback" not in result.stderr


def test_debug_does_not_print_traceback(tmp_path: Path) -> None:
    missing = tmp_path / "sentinel-debug-path"
    result = cli("--debug", "export", str(missing), "--format", "msg")
    assert result.returncode == 3, result.stderr
    assert str(missing).encode() not in result.stderr
    assert b"Traceback" not in result.stderr
    assert b"base.missing" in result.stderr


def test_classify_message_is_code_not_os_text() -> None:
    from golded_ftn_tools.errors import classify

    error = FileNotFoundError(2, "No such file or directory", "/secret/path.msg")
    classified = classify(error)
    assert classified.code == "base.missing"
    assert str(classified) == "base.missing"
    assert classified.code in repr(classified)
    assert "/secret/path.msg" not in str(classified)
    assert "/secret/path.msg" not in repr(classified)
