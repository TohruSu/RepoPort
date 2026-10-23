"""The repoport check command."""

import argparse
from collections.abc import Sequence
import sys

from . import __version__
from .checks import check_paths
from .git import GitError, tracked_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repoport", description="Check Git-tracked filenames for portability.",
    )
    parser.add_argument("--version", action="version", version=f"repoport {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a Git working tree's index")
    check.add_argument(
        "path", nargs="?", default=".", metavar="PATH",
        help="directory inside the repository (default: current directory)",
    )
    args = parser.parse_args(argv)
    try:
        paths = tracked_paths(args.path)
        findings = check_paths(paths)
    except GitError as error:
        print(f"repoport: error: {error}", file=sys.stderr)
        return 2

    for finding in findings:
        affected = ", ".join(ascii(path) for path in finding.paths)
        print(f"[{finding.code}] {affected}: {finding.message}")
    print(f"repoport: {len(paths)} tracked path(s), {len(findings)} finding(s).")
    return 1 if findings else 0
