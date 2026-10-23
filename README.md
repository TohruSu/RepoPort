# RepoPort 0.1.0

A small, read-only CLI for finding potential cross-platform filename problems
in Git repositories. Requires Python 3.11+ and Git on `PATH`; no runtime dependencies.

```sh
python -m pip install .
repoport check
repoport check /path/to/repository
```

`python -m repoport check` also works. `PATH` must be a directory inside a Git
working tree; the entire repository is checked, even from a subdirectory.
RepoPort reads the index using `git ls-files --cached -z`, so staged additions
and tracked files missing locally are included. Untracked files and staged
deletions are excluded. No commits are needed. It never changes files or the index.

Checks apply to filenames and directory components:

| Code | Problem |
| --- | --- |
| `case-collision` | Paths collide after NFC normalization and Unicode case folding. |
| `nfc-collision` | Different spellings become identical after NFC normalization. |
| `windows-reserved-name` | Device names such as `CON`, `NUL.txt`, `COM1`, or `LPT¹`. |
| `invalid-character` | Windows-forbidden characters (`<>:"\|?*`) or ASCII controls 0–31. |
| `trailing-space-or-dot` | A component ends with a space or period. |

Example diagnostic:

```text
[windows-reserved-name] 'docs/NUL.txt': Windows reserves this device name, including with extensions; rename this file or directory.
```

Findings include affected repository-relative paths, an issue code, and a manual
remedy. Directory issues name the affected directory. Output is sorted by path
then code; duplicate index entries are checked once. Quoted names escape newlines,
non-ASCII characters, and control characters so each finding occupies one line.
Pure NFC collisions do not also produce a case-collision finding.

Exit codes: **0** clean, **1** portability findings, **2** execution or usage error.
Findings and the summary go to stdout; execution errors go to stderr.

Limits: Unicode case folding is a conservative portability check, not an exact
model of every filesystem. Non-UTF-8 index filenames produce exit 2. Submodule
paths are checked without recursing into their contents; symlink targets, file
contents, and path-length limits are not checked. There are no automatic fixes.

Run the focused standard-library tests after installing:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs the tests on Ubuntu and Windows with Python 3.11 and 3.14.
Windows checks follow [Microsoft's naming rules](https://learn.microsoft.com/windows/win32/fileio/naming-a-file).

MIT licensed.
