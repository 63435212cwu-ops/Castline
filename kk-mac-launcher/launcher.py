"""Core helpers for the KK Windows game launcher.

The module intentionally has no GUI and no network access.  It provides the
small, deterministic pieces used by a launcher UI: validating downloads,
checking local compatibility runtimes, and constructing a safe argv/env pair
for a child process.  Keeping these pieces pure makes them easy to test and
prevents accidentally passing a user supplied path through a shell.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Iterable, Mapping, Sequence


class RuntimeKind(str, Enum):
    """Supported host-side ways to run a Windows executable."""

    WINE = "wine"
    CROSSOVER = "crossover"
    WHISKY = "whisky"
    PARALLELS = "parallels"
    UTM = "utm"


class UnsupportedRuntimeError(RuntimeError):
    """Raised when a runtime cannot launch an individual Windows executable."""


@dataclass(frozen=True)
class RuntimeInfo:
    """A detected runtime and the command used to invoke it.

    ``command`` is an argv prefix, never a shell string.  For app based
    runtimes (Whisky) this is ``("open", "-a", "Whisky", "--args")``.
    """

    kind: RuntimeKind
    command: tuple[str, ...]
    version: str | None = None
    source: str | None = None
    supports_prefix: bool = False

    @property
    def available(self) -> bool:
        return bool(self.command)


# A version probe is deliberately short and non-interactive.  A runtime can
# still be used if it does not understand --version; the probe only enriches
# the status shown by the UI.
VersionRunner = Callable[..., subprocess.CompletedProcess[str]]
Which = Callable[[str], str | None]


def sha256_file(path: os.PathLike[str] | str, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase SHA-256 digest of *path*.

    Reading in chunks keeps this safe for multi-gigabyte game installers.
    ``chunk_size`` must be positive so a typo cannot cause an infinite loop.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_sha256(expected: str) -> str:
    value = expected.strip().lower()
    # Accepting a conventional sha256: prefix is useful when values come from
    # a checksum file, while still rejecting truncated or ambiguous digests.
    if value.startswith("sha256:"):
        value = value[7:].strip()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("expected SHA-256 must be exactly 64 hexadecimal characters")
    return value


def verify_sha256(
    path: os.PathLike[str] | str,
    expected: str,
    *,
    chunk_size: int = 1024 * 1024,
) -> bool:
    """Compare a file digest with *expected* using a constant-time comparison."""

    import hmac

    wanted = _normalise_sha256(expected)
    actual = sha256_file(path, chunk_size=chunk_size)
    return hmac.compare_digest(actual, wanted)


def _version(path: str, runner: VersionRunner = subprocess.run) -> str | None:
    """Best effort version probe for a runtime executable."""

    try:
        result = runner(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0][:200] if output else None


def _first_available(which: Which, names: Iterable[str]) -> str | None:
    for name in names:
        found = which(name)
        if found:
            return found
    return None


def detect_runtimes(
    *,
    which: Which = shutil.which,
    version_runner: VersionRunner = subprocess.run,
    app_paths: Mapping[RuntimeKind, os.PathLike[str] | str] | None = None,
) -> list[RuntimeInfo]:
    """Detect installed compatibility runtimes without modifying the system.

    ``which`` and ``version_runner`` are injectable for deterministic tests.
    App paths default to standard macOS locations but can be overridden (for
    example when an app is installed on an external volume).
    """

    paths: dict[RuntimeKind, Path] = {
        RuntimeKind.CROSSOVER: Path("/Applications/CrossOver.app"),
        RuntimeKind.WHISKY: Path("/Applications/Whisky.app"),
        RuntimeKind.PARALLELS: Path("/Applications/Parallels Desktop.app"),
        RuntimeKind.UTM: Path("/Applications/UTM.app"),
    }
    if app_paths:
        paths.update({kind: Path(value) for kind, value in app_paths.items()})

    found: list[RuntimeInfo] = []

    wine = _first_available(which, ("wine64", "wine"))
    if wine:
        found.append(
            RuntimeInfo(
                RuntimeKind.WINE,
                (wine,),
                _version(wine, version_runner),
                source=wine,
                supports_prefix=True,
            )
        )

    crossover = _first_available(which, ("crossover", "cxrun", "wine-crossover"))
    if crossover:
        found.append(
            RuntimeInfo(
                RuntimeKind.CROSSOVER,
                (crossover,),
                _version(crossover, version_runner),
                source=crossover,
                supports_prefix=True,
            )
        )
    elif paths[RuntimeKind.CROSSOVER].exists():
        # CrossOver bundles a Wine binary even when no command line shim is on
        # PATH.  This path works for launching an .exe directly.
        bundled = paths[RuntimeKind.CROSSOVER] / "Contents/SharedSupport/CrossOver/bin/wine"
        if bundled.exists():
            bundled_str = str(bundled)
            found.append(
                RuntimeInfo(
                    RuntimeKind.CROSSOVER,
                    (bundled_str,),
                    _version(bundled_str, version_runner),
                    source=str(paths[RuntimeKind.CROSSOVER]),
                    supports_prefix=True,
                )
            )

    whisky = _first_available(which, ("whisky",))
    if whisky:
        found.append(
            RuntimeInfo(
                RuntimeKind.WHISKY,
                (whisky,),
                _version(whisky, version_runner),
                source=whisky,
                supports_prefix=True,
            )
        )
    elif paths[RuntimeKind.WHISKY].exists():
        # ``open -a`` is available on macOS and avoids relying on private app
        # bundle internals.  The app receives the executable via --args.
        found.append(
            RuntimeInfo(
                RuntimeKind.WHISKY,
                ("open", "-a", "Whisky", "--args"),
                source=str(paths[RuntimeKind.WHISKY]),
                supports_prefix=True,
            )
        )

    parallels = _first_available(which, ("prlctl",))
    if parallels or paths[RuntimeKind.PARALLELS].exists():
        found.append(
            RuntimeInfo(
                RuntimeKind.PARALLELS,
                (parallels or "open",) if parallels else ("open", "-a", "Parallels Desktop"),
                source=parallels or str(paths[RuntimeKind.PARALLELS]),
            )
        )

    utm = _first_available(which, ("utmctl", "utm"))
    if utm or paths[RuntimeKind.UTM].exists():
        found.append(
            RuntimeInfo(
                RuntimeKind.UTM,
                (utm or "open",) if utm else ("open", "-a", "UTM"),
                source=utm or str(paths[RuntimeKind.UTM]),
            )
        )

    return found


def build_launch_command(
    runtime: RuntimeInfo,
    executable: os.PathLike[str] | str,
    args: Sequence[os.PathLike[str] | str] = (),
) -> list[str]:
    """Construct a process argv list, preserving arguments exactly.

    No shell parsing is performed.  The returned list can be passed directly
    to ``subprocess.Popen`` or ``subprocess.run``.
    """

    if runtime.kind in (RuntimeKind.PARALLELS, RuntimeKind.UTM):
        raise UnsupportedRuntimeError(
            f"{runtime.kind.value} starts a Windows VM; launch the game inside the VM"
        )
    if not runtime.command:
        raise ValueError("runtime command cannot be empty")
    raw_target = os.fspath(executable)
    if not raw_target:
        raise ValueError("executable cannot be empty")
    target = str(Path(raw_target).expanduser())
    return [*runtime.command, target, *(str(item) for item in args)]


def build_launch_env(
    runtime: RuntimeInfo,
    *,
    prefix: os.PathLike[str] | str | None = None,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment for a launch, adding ``WINEPREFIX`` if needed."""

    env = dict(base if base is not None else os.environ)
    if prefix is not None:
        if not runtime.supports_prefix:
            raise UnsupportedRuntimeError(f"{runtime.kind.value} does not support WINEPREFIX")
        env["WINEPREFIX"] = str(Path(prefix).expanduser())
    return env
