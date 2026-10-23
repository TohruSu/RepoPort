"""Read tracked names from Git's index; never inspect file contents."""

import os
import subprocess


class GitError(Exception):
    """Git cannot provide a usable list of tracked paths."""


def _git(path: str | os.PathLike[str], *arguments: str) -> bytes:
    command = [
        "git", "--no-optional-locks", "--no-literal-pathspecs",
        "-c", "core.fsmonitor=false",
        "-C", os.fspath(path), *arguments,
    ]
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except FileNotFoundError as error:
        raise GitError("Git was not found; install Git and put it on PATH.") from error
    except OSError as error:
        raise GitError(f"Could not run Git: {ascii(str(error))}.") from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(
            f"Git failed for {ascii(os.fspath(path))} "
            f"(exit {result.returncode}): {ascii(detail)}"
        )
    return result.stdout


def tracked_paths(path: str | os.PathLike[str]) -> list[str]:
    """Read the whole working tree's index, including from a subdirectory."""
    if _git(path, "rev-parse", "--is-inside-work-tree").strip() != b"true":
        raise GitError("PATH must be a directory inside a Git working tree.")
    data = _git(path, "ls-files", "--cached", "-z", "--full-name", "--", ":/")
    if not data:
        return []
    if not data.endswith(b"\0"):
        raise GitError("Git returned an incomplete NUL-delimited path list.")
    try:
        # Do not silently replace bytes: that can hide or invent collisions.
        paths = data[:-1].decode("utf-8").split("\0")
    except UnicodeDecodeError as error:
        raise GitError(
            "The Git index contains a filename that is not valid UTF-8; "
            "Unicode portability checks require UTF-8 filenames."
        ) from error
    return sorted(set(paths))
