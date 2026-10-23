from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from repoport.cli import main
from repoport.git import GitError, tracked_paths


class GitErrorTests(unittest.TestCase):
    def test_missing_git_and_launch_failure_return_two(self):
        for error, message in [
            (FileNotFoundError(), "Git was not found"),
            (PermissionError("access denied"), "Could not run Git"),
        ]:
            with self.subTest(error=error), patch(
                "repoport.git.subprocess.run", side_effect=error,
            ), redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["check"]), 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn(message, stderr.getvalue())

    def test_invalid_path_encoding_and_incomplete_git_output_are_errors(self):
        for data, message in [
            (b"bad\xff.txt\0", "not valid UTF-8"),
            (b"truncated.txt", "incomplete NUL-delimited"),
        ]:
            with self.subTest(data=data), patch(
                "repoport.git._git", side_effect=[b"true\n", data],
            ):
                with self.assertRaisesRegex(GitError, message):
                    tracked_paths(".")

    def test_invalid_arguments_return_two(self):
        for arguments in ([], ["fix"], ["check", "--unknown"]):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(arguments)
                self.assertEqual(error.exception.code, 2)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repository with spaces"
        self.repo.mkdir()
        # Keep fixtures independent of the caller's Git configuration/index.
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith("GIT_")}
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "--quiet")
        self.blob = self.git("hash-object", "-w", "--stdin", input=b"fixture\n").stdout.strip()

    def git(self, *arguments, input=None):
        return subprocess.run([
            "git", "-c", "core.protectNTFS=false", "-c", "core.ignorecase=false",
            "-C", str(self.repo), *arguments,
        ], input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.environment, check=True)

    def add_index_paths(self, *paths):
        # Populate the index directly: these names need not exist on Windows.
        records = b"".join(b"100644 " + self.blob + b"\t" + path.encode("utf-8") + b"\0"
                           for path in paths)
        self.git("update-index", "-z", "--index-info", input=records)

    def cli(self, *arguments, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "repoport", *arguments],
            cwd=cwd or self.root, env=self.environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def test_empty_and_clean_repositories_and_default_path(self):
        empty = self.cli("check", cwd=self.repo)
        self.assertEqual((empty.returncode, empty.stdout, empty.stderr), (
            0, b"repoport: 0 tracked path(s), 0 finding(s).\n".replace(b"\n", os.linesep.encode()), b"",
        ))
        self.add_index_paths("src/main.py", "docs/read me.md", "caf\u00e9.txt")
        result = self.cli("check", str(self.repo))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"3 tracked path(s), 0 finding(s)", result.stdout)
        self.assertEqual(result.stderr, b"")

    def test_all_findings_from_real_index_with_safe_deterministic_output(self):
        self.add_index_paths(
            "README", "readme", "caf\u00e9", "cafe\u0301", "docs/NUL.txt",
            "bad\nline", "tab\tname", "bad?.txt", "trailing. ", "src/a", "SRC/b",
        )
        result = self.cli("check", str(self.repo))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, b"")
        text = result.stdout.decode("ascii")
        for code in ("case-collision", "nfc-collision", "windows-reserved-name",
                     "invalid-character", "trailing-space-or-dot"):
            self.assertIn(f"[{code}]", text)
        for path in ("bad\nline", "tab\tname", "caf\u00e9", "cafe\u0301"):
            self.assertIn(ascii(path), text)
        self.assertIn("'SRC', 'src'", text)
        self.assertEqual(len(text.splitlines()), 9)  # Eight findings plus summary.
        self.assertEqual(result.stdout, self.cli("check", str(self.repo)).stdout)

    def test_literal_pathspec_environment_cannot_suppress_tracked_paths(self):
        self.add_index_paths("NUL.txt", "README", "readme")
        baseline = self.cli("check", str(self.repo))
        self.environment["GIT_LITERAL_PATHSPECS"] = "1"
        result = self.cli("check", str(self.repo))
        self.assertEqual(baseline.returncode, 1, baseline.stderr)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, baseline.stdout)
        self.assertIn(b"3 tracked path(s), 2 finding(s)", result.stdout)
        self.assertIn(b"[windows-reserved-name] 'NUL.txt'", result.stdout)
        self.assertIn(b"[case-collision] 'README', 'readme'", result.stdout)

    def test_console_device_names_are_reported_from_the_index(self):
        self.add_index_paths("CONIN$", "nested/CONOUT$.txt")
        result = self.cli("check", str(self.repo))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertIn(b"2 tracked path(s), 2 finding(s)", result.stdout)
        self.assertIn(b"[windows-reserved-name] 'CONIN$'", result.stdout)
        self.assertIn(b"[windows-reserved-name] 'nested/CONOUT$.txt'", result.stdout)

    def test_subdirectory_checks_whole_index_and_scan_is_read_only(self):
        self.add_index_paths("NUL.txt", "nested/clean.txt", "missing.txt")
        nested = self.repo / "nested"
        nested.mkdir()
        (nested / "clean.txt").write_text("unstaged content", encoding="utf-8")
        (self.repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        (self.repo / "ignored").mkdir()
        (self.repo / "ignored" / "bad.").mkdir()
        (self.repo / "untracked.").mkdir()

        def snapshot():
            return {path.relative_to(self.repo).as_posix(): path.read_bytes()
                    for path in self.repo.rglob("*") if path.is_file()}

        before = snapshot()
        result = self.cli("check", cwd=nested)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"'NUL.txt'", result.stdout)
        self.assertIn(b"3 tracked path(s), 1 finding(s)", result.stdout)
        self.assertNotIn(b"untracked", result.stdout)
        self.assertNotIn(b"ignored", result.stdout)
        self.assertEqual(before, snapshot())
        self.assertFalse((self.repo / ".git" / "index.lock").exists())

    def test_staged_deletions_are_excluded(self):
        self.add_index_paths("NUL.txt", "clean.txt")
        self.git("update-index", "--force-remove", "--", "NUL.txt")
        result = self.cli("check", str(self.repo))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"1 tracked path(s)", result.stdout)

    def test_merge_stages_are_deduplicated(self):
        records = b"".join(b"100644 " + self.blob + b" " + str(stage).encode() + b"\tNUL.txt\0"
                           for stage in (1, 2, 3))
        self.git("update-index", "-z", "--index-info", input=records)
        result = self.cli("check", str(self.repo))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"1 tracked path(s), 1 finding(s)", result.stdout)

    def test_non_repository_missing_path_and_file_path_are_errors(self):
        file = self.root / "file.txt"
        file.write_text("content", encoding="utf-8")
        for path in (self.root, self.root / "missing", file):
            with self.subTest(path=path):
                result = self.cli("check", str(path))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"repoport: error:", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)

    def test_bare_repository_is_an_error(self):
        bare = self.root / "bare.git"
        self.git("init", "--bare", "--quiet", str(bare))
        result = self.cli("check", str(bare))
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"inside a Git working tree", result.stderr)


if __name__ == "__main__":
    unittest.main()
