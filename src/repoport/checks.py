"""Check Git's slash-separated paths without touching the filesystem."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
import unicodedata


RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{digit}"
    for prefix in ("COM", "LPT")
    for digit in "123456789\u00b9\u00b2\u00b3"
}
FORBIDDEN_CHARACTERS = frozenset('<>:"\\|?*')


@dataclass(frozen=True)
class Finding:
    code: str
    paths: tuple[str, ...]
    message: str


def check_paths(paths: Iterable[str]) -> list[Finding]:
    """Return findings sorted by affected path, code, and message.

    Include directory prefixes so directory/directory and file/directory
    collisions are found even when their descendant filenames differ.
    """
    prefixes: set[str] = set()
    for path in paths:
        parts = path.split("/")
        prefixes.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))

    findings: list[Finding] = []
    by_nfc: dict[str, list[str]] = defaultdict(list)
    by_case: dict[str, list[str]] = defaultdict(list)
    for path in sorted(prefixes):
        normalized = unicodedata.normalize("NFC", path)
        by_nfc[normalized].append(path)
        by_case[normalized.casefold()].append(path)
        name = path.rsplit("/", 1)[-1]

        # Device names remain reserved with extensions and trailing spaces/dots.
        stem = name.split(".", 1)[0].rstrip(" ").upper()
        if stem in RESERVED_NAMES:
            findings.append(Finding(
                "windows-reserved-name", (path,),
                "Windows reserves this device name, including with extensions; "
                "rename this file or directory.",
            ))

        invalid = sorted({
            char for char in name
            if char in FORBIDDEN_CHARACTERS or ord(char) < 32
        })
        if invalid:
            characters = ", ".join(ascii(char) for char in invalid)
            findings.append(Finding(
                "invalid-character", (path,),
                f"Windows forbids {characters}; remove or replace these characters.",
            ))

        if name.endswith((" ", ".")):
            findings.append(Finding(
                "trailing-space-or-dot", (path,),
                "Windows does not reliably support trailing spaces or periods; "
                "remove them from this file or directory name.",
            ))

    for group in by_nfc.values():
        if len(group) > 1:
            findings.append(Finding(
                "nfc-collision", tuple(group),
                "These paths are equivalent after Unicode NFC normalization; "
                "choose distinct names after normalization.",
            ))
    for group in by_case.values():
        # A pure NFC collision already has a more specific diagnostic.
        if len({unicodedata.normalize("NFC", path) for path in group}) > 1:
            findings.append(Finding(
                "case-collision", tuple(group),
                "These paths collide after NFC normalization and Unicode case folding; "
                "choose names that remain distinct without case sensitivity.",
            ))

    return sorted(findings, key=lambda finding: (
        finding.paths, finding.code, finding.message,
    ))
