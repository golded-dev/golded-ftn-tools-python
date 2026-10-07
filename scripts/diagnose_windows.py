"""Compare published Windows failures with isolated, process-local probes."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MESSAGE = json.dumps(
    {
        "from_name": "Alice",
        "to_name": "Bob",
        "subject": "Fixture æøå",
        "body_text": "Text",
        "posted_at": "2024-10-05T13:24:56",
    }
).encode()

BINARY_PROBE = """
import os, sys
from golded_ftn_tools.cli import main
original = os.open
def binary_open(path, flags, *args, **kwargs):
    if str(path).upper().endswith(('.JDT', '.JDX')):
        flags |= getattr(os, 'O_BINARY', 0)
    return original(path, flags, *args, **kwargs)
os.open = binary_open
raise SystemExit(main(sys.argv[1:]))
"""

PIPE_PROBE = """
import sys
from golded_ftn_tools import cli
original = cli._json
def emit(*args, **kwargs):
    try:
        return original(*args, **kwargs)
    except OSError as error:
        if cli._pipe_closed(error):
            raise BrokenPipeError() from error
        raise
cli._json = emit
raise SystemExit(cli.main(sys.argv[1:]))
"""


def command(probe: str | None, *args: str) -> list[str]:
    entry = ["-c", probe] if probe else ["-m", "golded_ftn_tools"]
    return [sys.executable, *entry, *args]


def jam(base: Path, probe: str | None) -> tuple[int, bytes]:
    for args, data in (
        (("create", str(base), "--format", "jam"), b""),
        (("write", str(base), "--format", "jam"), MESSAGE),
        (("read", str(base), "1", "--format", "jam", "--revision", "--debug"), b""),
    ):
        result = subprocess.run(
            command(probe, *args), input=data, capture_output=True, timeout=20
        )
        print(args[0], "exit", result.returncode, "stderr", repr(result.stderr))
        if result.returncode:
            break
    index = base.with_suffix(".JDX").read_bytes()
    print("JDX length", len(index), "hex", index.hex())
    return result.returncode, index


def pipe(base: Path, probe: str | None) -> tuple[int, bytes]:
    base.mkdir()
    process = subprocess.Popen(
        command(probe, "write", str(base), "--format", "msg", "--debug"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin and process.stdout and process.stderr
    process.stdout.close()
    process.stdin.write(MESSAGE)
    process.stdin.close()
    code = process.wait(timeout=20)
    error = process.stderr.read()
    print("closed pipe exit", code, "stderr", repr(error))
    exported = subprocess.run(
        command(None, "export", str(base), "--format", "msg"),
        capture_output=True,
        timeout=20,
        check=True,
    )
    assert json.loads(exported.stdout)["message"]["msgno"] == 1
    print("Committed message remains readable")
    return code, error


def main() -> None:
    assert sys.platform == "win32", "Run this probe on native Windows"
    print(sys.version, sys.platform, "O_BINARY", os.O_BINARY)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        print("BASELINE JAM")
        baseline, index = jam(root / "baseline", None)
        assert baseline == 4 and index == bytes.fromhex("bf4e340d0a00040000")
        print("O_BINARY PROBE")
        fixed, index = jam(root / "binary", BINARY_PROBE)
        assert fixed == 0 and index == bytes.fromhex("bf4e340a00040000")
        print("BASELINE PIPE")
        baseline, _ = pipe(root / "baseline-msg", None)
        assert baseline == 120
        print("RECEIPT FLUSH HANDLER PROBE")
        fixed, error = pipe(root / "handled-msg", PIPE_PROBE)
        assert fixed == 6 and not error
    print("Both native Windows failures and isolated corrections confirmed")


if __name__ == "__main__":
    main()
