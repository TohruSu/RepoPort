# RepoPort

**Find Git filenames that may cause problems across operating systems.**

RepoPort is a small, read-only CLI for checking tracked repository paths for case collisions, Unicode normalization conflicts, and Windows-incompatible names. It works directly from Git's index, making it useful before sharing a repository across Windows, macOS, and Linux.

Requires Python 3.11+ and Git on PATH. No additional Python packages are needed at runtime.

## Install and run

```sh
python -m pip install .
repoport check
repoport check /path/to/repository
```

You can also run `python -m repoport check`.

The optional path may point to the repository root or a subdirectory within a Git working tree. RepoPort checks the entire repository either way.

## What it checks

| Finding | Description |
| --- | --- |
| `case-collision` | Paths become identical after Unicode case folding and NFC normalization. |
| `nfc-collision` | Different paths become identical after NFC normalization. |
| `windows-reserved-name` | Reserved Windows device names such as `CON`, `NUL.txt`, `COM1`, and `LPT¹`. |
| `invalid-character` | Characters not allowed in Windows filenames, including `<>:"\|?*` and ASCII controls. |
| `trailing-space-or-dot` | A filename or directory component ends in a space or a period. |

Example:

```text
[windows-reserved-name] 'docs/NUL.txt': Windows reserves this device name, including with extensions; rename this file or directory.
```

Findings identify the affected repository-relative path, the issue code, and a suggested manual fix. Directory-name issues point to the relevant directory component. Results are sorted by path and issue code, with paths escaped to keep each diagnostic on one line.

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

Windows-specific rules follow [Microsoft's file naming guidance](https://learn.microsoft.com/windows/win32/fileio/naming-a-file).

## Tests

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs the tests on Ubuntu and Windows with Python 3.11 and 3.14. Version 0.1.0 includes 19 automated tests.

## License

[MIT](LICENSE)
