# RepoPort

**Find Git filenames that may cause problems across operating systems.**

RepoPort is a small, read-only CLI for checking tracked repository paths for case collisions, Unicode normalization conflicts, and Windows-incompatible names. It works directly from Git's index, making it useful before sharing a repository across Windows, macOS, and Linux.

Requires Python 3.11+ and Git on PATH. No additional Python packages are needed at runtime.

[Quick start](#60-second-quick-start) · [Cross-platform example](#example-linux-to-windows-and-macos) · [GitHub Actions](#github-actions)

## 60-second quick start

Inside the Git working tree you want to check, create a virtual environment with `python -m venv .venv`. Activate it with `source .venv/bin/activate` on Linux/macOS or `.\.venv\Scripts\Activate.ps1` in Windows PowerShell. You can also use an existing activated environment.

Install [v0.1.0](https://github.com/TohruSu/RepoPort/releases/tag/v0.1.0) directly from GitHub, pinned to its release commit; you do not need to clone RepoPort first:

```sh
python -m pip install "git+https://github.com/TohruSu/RepoPort.git@f6e7d0cc72f284d65a889a005a991f84c8684c38"
python -m repoport --version
python -m repoport check .
```

The version command prints `repoport 0.1.0`. A clean check exits with `0` and prints a summary like this (the tracked-path count depends on your repository):

```text
repoport: 3 tracked path(s), 0 finding(s).
```

You can also use `repoport check`, or check another working tree with `python -m repoport check "/path/to/repository"`. If you have already cloned RepoPort for development, install it from that checkout with `python -m pip install .`.

The optional path may point to the repository root or a subdirectory within a Git working tree. RepoPort checks the entire repository either way.

### Example: Linux to Windows and macOS

A contributor on a case-sensitive Linux filesystem stages these three files:

```text
assets/Logo.svg
assets/logo.svg
docs/NUL.txt
```

The two logos have different names on Linux but collide on typical case-insensitive Windows and macOS filesystems. Windows also reserves `NUL`, including with a `.txt` extension. Run `python -m repoport check .` before merging or sharing the repository:

```text
[case-collision] 'assets/Logo.svg', 'assets/logo.svg': These paths collide after NFC normalization and Unicode case folding; choose names that remain distinct without case sensitivity.
[windows-reserved-name] 'docs/NUL.txt': Windows reserves this device name, including with extensions; rename this file or directory.
repoport: 3 tracked path(s), 2 finding(s).
```

This check exits with `1`. On Linux, rename `assets/logo.svg` to a distinct name such as `assets/logo-small.svg` and `docs/NUL.txt` to `docs/null-device.txt`, update references, and stage the renames. Rerun the check; these three paths now produce the clean summary above. Commit the corrected names so collaborators can check out the corrected tree. RepoPort only reports issues; it does not rename files or update references.

New files must be staged with `git add` to be checked. An unstaged rename does not update the names RepoPort sees in the index.

## What it checks

| Finding | Description |
| --- | --- |
| `case-collision` | Paths become identical after Unicode case folding and NFC normalization. |
| `nfc-collision` | Different paths become identical after NFC normalization. |
| `windows-reserved-name` | Reserved Windows device names such as `CON`, `NUL.txt`, `COM1`, and `LPT¹`. |
| `invalid-character` | Characters not allowed in Windows filenames, including `<>:"\|?*` and ASCII controls. |
| `trailing-space-or-dot` | A filename or directory component ends in a space or a period. |

Findings identify the affected repository-relative path, the issue code, and a suggested manual fix. Directory-name issues point to the relevant directory component. Results are sorted by path and issue code, with paths escaped to keep each diagnostic on one line.

## GitHub Actions

Add this to the repository you want to check as `.github/workflows/filename-portability.yml`:

```yaml
name: Filename portability

on: [push, pull_request]

permissions:
  contents: read

jobs:
  filenames:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'
      - name: Install RepoPort v0.1.0
        run: python -m pip install "git+https://github.com/TohruSu/RepoPort.git@f6e7d0cc72f284d65a889a005a991f84c8684c38"
      - name: Check Git-index tracked paths
        run: python -m repoport check .
```

Checkout populates the target repository's Git index; installing RepoPort does not change which repository is checked. The final step succeeds on exit `0`, fails on portability findings (`1`), and also fails on usage or execution errors (`2`). Ubuntu can check filenames that would prevent a Windows checkout. This scans only the checked-out index, so untracked build outputs are excluded and submodule contents need separate checks.

## How it works

RepoPort reads tracked paths using `git ls-files --cached -z`. This includes staged additions and files present in the index even when their working-tree copies are missing. Untracked files and staged deletions are outside the scan.

Checks apply to each path component. Duplicate index entries are processed once, and a pure NFC collision is reported without a redundant case-collision finding.

RepoPort never changes repository files or the Git index.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No portability findings |
| `1` | Portability issues found |
| `2` | Usage or execution error |

Findings and the summary go to standard output; execution errors go to standard error. These exit codes make RepoPort easy to use in local checks or CI.

## Limitations

Unicode case folding is a conservative portability check rather than a precise model of every filesystem. Non-UTF-8 filenames in the Git index produce exit code `2`.

Submodule paths are checked without scanning their contents. Symlink targets, file contents, and path-length limits are not analyzed. RepoPort reports potential issues but leaves renaming decisions to you.

Exit `0` means none of the implemented checks found a problem; it does not guarantee that a repository will work on every operating system or filesystem.

Windows-specific rules follow [Microsoft's file naming guidance](https://learn.microsoft.com/windows/win32/fileio/naming-a-file).

## Tests

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs the tests on Ubuntu and Windows with Python 3.11 and 3.14. Version 0.1.0 includes 19 automated tests.

## License

[MIT](LICENSE)
