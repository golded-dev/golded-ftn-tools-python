"""Check archives, rebuild the sdist and exercise installed wheels in isolation."""

import email
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    (wheel,) = (ROOT / "dist").glob("*.whl")
    (sdist,) = (ROOT / "dist").glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "golded_ftn_tools/py.typed" in names
        metadata = email.message_from_bytes(
            archive.read(next(name for name in names if name.endswith("/METADATA")))
        )
        assert metadata["Name"] == project["name"]
        assert metadata["Version"] == project["version"]
        assert metadata["Requires-Python"] == ">=3.12"
        assert metadata["License-Expression"] == "MIT"
        expected = {
            dependency.replace(">=", "<2,>=").replace(",<2", "")
            for dependency in project["dependencies"]
        }
        assert set(metadata.get_all("Requires-Dist", [])) == expected
        assert all("file:" not in dep for dep in metadata.get_all("Requires-Dist", []))
        entry = archive.read(next(n for n in names if n.endswith("/entry_points.txt")))
        assert b"ftnt = golded_ftn_tools.cli:main" in entry
    with tempfile.TemporaryDirectory(prefix="ftnt-distribution-") as temporary:
        work = Path(temporary)
        with tarfile.open(sdist) as archive:
            assert not any(
                "/.venv/" in name or "/.git/" in name for name in archive.getnames()
            )
            archive.extractall(work, filter="data")
        (source,) = (path for path in work.iterdir() if path.is_dir())
        config = tomllib.loads((source / "pyproject.toml").read_text())
        assert "sources" not in config.get("tool", {}).get("uv", {})
        assert not (source / "uv.lock").exists()
        run("uv", "build", "--wheel", cwd=source)
        (rebuilt,) = (source / "dist").glob("*.whl")
        with zipfile.ZipFile(wheel) as first, zipfile.ZipFile(rebuilt) as second:
            assert set(first.namelist()) == set(second.namelist())
            assert all(
                first.read(name) == second.read(name) for name in first.namelist()
            )
        dependencies = work / "dependency-wheels"
        for repository in (
            "golded-ftn-python",
            "golded-ftn-msg-python",
            "golded-ftn-jam-python",
            "golded-ftn-squish-python",
            "golded-ftn-hudson-python",
        ):
            run(
                "uv",
                "build",
                "--wheel",
                str(ROOT.parent / repository),
                "--out-dir",
                str(dependencies),
                cwd=work,
            )
        shutil.copytree(source / "tests", work / "tests")
        shutil.copytree(source / "examples", work / "examples")
        for index, candidate in enumerate((wheel, rebuilt)):
            env_path = work / f"installed-{index}"
            run("uv", "venv", "--python", sys.executable, str(env_path), cwd=work)
            python = env_path / (
                "Scripts/python.exe" if os.name == "nt" else "bin/python"
            )
            entrypoint = env_path / (
                "Scripts/ftnt.exe" if os.name == "nt" else "bin/ftnt"
            )
            run(
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                *map(str, dependencies.glob("*.whl")),
                str(candidate),
                cwd=work,
            )
            run(
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "pytest",
                "mypy",
                cwd=work,
            )
            run("uv", "pip", "check", "--python", str(python), cwd=work)
            run(str(entrypoint), "--help", cwd=work)
            run(str(python), "-m", "pytest", "tests", "-q", cwd=work)
            run(str(python), "-m", "mypy", "--strict", "tests", cwd=work)
            run(str(python), "-m", "mypy.stubtest", "golded_ftn_tools", cwd=work)
            for format in ("msg", "opus", "jam", "squish", "hudson"):
                base = work / f"example-{index}-{format}"
                args = ["--format", format]
                run(str(entrypoint), "create", str(base), *args, cwd=work)
                if format == "hudson":
                    args += ["--board", "1"]
                name = "message-squish.json" if format == "squish" else "message.json"
                with (work / "examples" / name).open("rb") as input_file:
                    receipt = subprocess.run(
                        [str(entrypoint), "write", str(base), *args],
                        stdin=input_file,
                        capture_output=True,
                        check=True,
                        cwd=work,
                    )
                identity = json.loads(receipt.stdout)["identity"]
                read = subprocess.run(
                    [str(entrypoint), "read", str(base), str(identity["msgno"]), *args],
                    capture_output=True,
                    check=True,
                    cwd=work,
                )
                assert (
                    json.loads(read.stdout)["message"]["subject"]
                    == "Encoding fixture: æøå"
                )
    print(
        "Archives, dependency metadata, sdist rebuild and "
        "both isolated wheel suites passed."
    )
    print(
        "Dependency wheels came from sibling checkouts; "
        "this is not a PyPI resolution check."
    )


if __name__ == "__main__":
    main()
