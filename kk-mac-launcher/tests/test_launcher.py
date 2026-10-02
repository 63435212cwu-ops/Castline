import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from launcher import (
    RuntimeInfo,
    RuntimeKind,
    UnsupportedRuntimeError,
    build_launch_command,
    build_launch_env,
    detect_runtimes,
    sha256_file,
    verify_sha256,
)


class HashVerificationTests(unittest.TestCase):
    def test_hash_is_streamed_and_matches_known_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "installer.exe"
            payload = b"KK installer\0" * 1024
            path.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            self.assertEqual(sha256_file(path, chunk_size=7), expected)
            self.assertTrue(verify_sha256(path, "sha256:" + expected.upper(), chunk_size=7))

    def test_wrong_hash_returns_false(self):
        with tempfile.NamedTemporaryFile() as stream:
            stream.write(b"not the installer")
            stream.flush()
            self.assertFalse(verify_sha256(stream.name, "0" * 64))

    def test_invalid_expected_hash_is_rejected_before_reading_file(self):
        with tempfile.NamedTemporaryFile() as stream:
            stream.write(b"content")
            stream.flush()
            with self.assertRaises(ValueError):
                verify_sha256(stream.name, "too-short")

    def test_non_positive_chunk_size_is_rejected(self):
        with tempfile.NamedTemporaryFile() as stream:
            with self.assertRaises(ValueError):
                sha256_file(stream.name, chunk_size=0)


class RuntimeDetectionTests(unittest.TestCase):
    @staticmethod
    def absent_app_paths():
        return {kind: f"/definitely/missing/{kind.value}.app" for kind in RuntimeKind}

    def test_detection_prefers_wine64_and_captures_version(self):
        paths = {"wine64": "/opt/wine64", "wine": "/opt/wine"}

        def fake_which(name):
            return paths.get(name)

        calls = []

        def fake_runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return Mock(stdout="wine-9.0\n", stderr="", returncode=0)

        runtimes = detect_runtimes(which=fake_which, version_runner=fake_runner, app_paths=self.absent_app_paths())
        self.assertEqual([runtime.kind for runtime in runtimes], [RuntimeKind.WINE])
        self.assertEqual(runtimes[0].command, ("/opt/wine64",))
        self.assertEqual(runtimes[0].version, "wine-9.0")
        self.assertEqual(calls[0][0], ["/opt/wine64", "--version"])

    def test_pathless_machine_has_no_false_positive_apps(self):
        runtimes = detect_runtimes(which=lambda _: None, app_paths={
            RuntimeKind.CROSSOVER: "/definitely/missing/CrossOver.app",
            RuntimeKind.WHISKY: "/definitely/missing/Whisky.app",
            RuntimeKind.PARALLELS: "/definitely/missing/Parallels.app",
            RuntimeKind.UTM: "/definitely/missing/UTM.app",
        })
        self.assertEqual(runtimes, [])


class CommandConstructionTests(unittest.TestCase):
    def test_wine_command_preserves_spaces_and_does_not_use_shell(self):
        runtime = RuntimeInfo(RuntimeKind.WINE, ("/opt/wine",), supports_prefix=True)
        command = build_launch_command(
            runtime,
            "/Users/carmen/Games/KK Duel/game.exe",
            ("--profile", "Player One", "--flag=some value"),
        )
        self.assertEqual(command, [
            "/opt/wine",
            "/Users/carmen/Games/KK Duel/game.exe",
            "--profile",
            "Player One",
            "--flag=some value",
        ])

    def test_empty_executable_is_rejected(self):
        runtime = RuntimeInfo(RuntimeKind.WINE, ("wine",), supports_prefix=True)
        with self.assertRaises(ValueError):
            build_launch_command(runtime, "")

    def test_prefix_is_added_to_copy_of_base_environment(self):
        runtime = RuntimeInfo(RuntimeKind.WINE, ("wine",), supports_prefix=True)
        base = {"PATH": "/bin"}
        env = build_launch_env(runtime, prefix="~/Library/Application Support/KK/prefix", base=base)
        self.assertEqual(base, {"PATH": "/bin"})
        self.assertEqual(env, {
            "PATH": "/bin",
            "WINEPREFIX": str(Path("~/Library/Application Support/KK/prefix").expanduser()),
        })

    def test_vm_runtime_is_not_treated_as_a_wine_command(self):
        runtime = RuntimeInfo(RuntimeKind.PARALLELS, ("prlctl",))
        with self.assertRaises(UnsupportedRuntimeError):
            build_launch_command(runtime, "/tmp/game.exe")

    def test_prefix_for_runtime_without_prefix_support_is_rejected(self):
        runtime = RuntimeInfo(RuntimeKind.PARALLELS, ("prlctl",))
        with self.assertRaises(UnsupportedRuntimeError):
            build_launch_env(runtime, prefix="/tmp/prefix", base={})


if __name__ == "__main__":
    unittest.main()
