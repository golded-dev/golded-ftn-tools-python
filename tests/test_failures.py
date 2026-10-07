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
def session(*args):
    with original(*args) as actual:
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


def test_real_msg_lock_timeout(tmp_path: Path) -> None:
    base = str(tmp_path)
    assert cli("write", base, "--format", "msg", data=message()).returncode == 0
    with (tmp_path / ".golded-ftn-msg.lock").open("r+b") as lock:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.lockf(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB, 1)
        try:
            result = cli(
                "write", base, "--format", "msg", "--lock-timeout", "0", data=message()
            )
            assert result.returncode == 5, result.stderr
            assert not result.stdout
            assert b"committed 0" in result.stderr
        finally:
            lock.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.lockf(lock.fileno(), fcntl.LOCK_UN, 1)


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
adapters.reader = lambda _: Reader()
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
