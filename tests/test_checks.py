import unittest

from repoport.checks import check_paths


class CheckPathsTests(unittest.TestCase):
    def test_portable_names_and_duplicate_paths_are_clean(self):
        self.assertEqual(check_paths([
            "src/main.py", "src/main.py", "docs/read me.md", ".github/ci.yml",
            "caf\u00e9.txt", "COM0", "COM10.txt", "LPT0", "LPT10", "console.txt",
        ]), [])

    def test_case_collisions_include_directories_and_file_directory_conflicts(self):
        cases = [
            (["readme", "README"], ("README", "readme")),
            (["src/a.py", "SRC/b.py"], ("SRC", "src")),
            (["Docs", "docs/file.txt"], ("Docs", "docs")),
            (["Stra\u00dfe", "STRASSE"], ("STRASSE", "Stra\u00dfe")),
            (["CAF\u00c9", "cafe\u0301"], ("CAF\u00c9", "cafe\u0301")),
        ]
        for paths, affected in cases:
            with self.subTest(paths=paths):
                findings = check_paths(paths)
                self.assertEqual([(f.code, f.paths) for f in findings], [
                    ("case-collision", affected),
                ])

    def test_nfc_collisions_include_directories_without_duplicate_case_findings(self):
        for paths, affected in [
            (["caf\u00e9.txt", "cafe\u0301.txt"], ("cafe\u0301.txt", "caf\u00e9.txt")),
            (["caf\u00e9/a", "cafe\u0301/b"], ("cafe\u0301", "caf\u00e9")),
        ]:
            with self.subTest(paths=paths):
                self.assertEqual([(f.code, f.paths) for f in check_paths(paths)], [
                    ("nfc-collision", affected),
                ])

    def test_reserved_devices_with_case_extensions_and_com_lpt_variants(self):
        names = ["con", "PrN.txt", "AuX.tar.gz", "NUL", "con .txt"]
        names += ["CONIN$", "conin$.txt", "CONOUT$", "conout$.tar.gz"]
        names += [f"{prefix}{digit}.log"
                  for prefix in ("COM", "lpt")
                  for digit in "123456789\u00b9\u00b2\u00b3"]
        for name in names:
            with self.subTest(name=name):
                findings = check_paths([f"docs/{name}/file.txt"])
                self.assertEqual([(f.code, f.paths) for f in findings], [
                    ("windows-reserved-name", (f"docs/{name}",)),
                ])

    def test_forbidden_characters_and_controls(self):
        for char in '<>:"\\|?*' + "".join(chr(n) for n in range(32)):
            with self.subTest(char=repr(char)):
                path = f"docs/bad{char}name/file"
                findings = check_paths([path])
                self.assertEqual([(f.code, f.paths) for f in findings], [
                    ("invalid-character", (f"docs/bad{char}name",)),
                ])
                self.assertIn(ascii(char), findings[0].message)

    def test_trailing_spaces_and_dots_at_each_level(self):
        findings = check_paths(["docs./name ", "docs./other", "NUL.txt."])
        self.assertEqual([(f.code, f.paths) for f in findings], [
            ("trailing-space-or-dot", ("NUL.txt.",)),
            ("windows-reserved-name", ("NUL.txt.",)),
            ("trailing-space-or-dot", ("docs.",)),
            ("trailing-space-or-dot", ("docs./name ",)),
        ])

    def test_findings_are_deterministic_and_group_all_colliding_names(self):
        paths = ["a", "A", "NUL", "bad?.", "caf\u00e9", "cafe\u0301", "a"]
        expected = check_paths(paths)
        self.assertEqual(check_paths(reversed(paths)), expected)
        self.assertEqual(check_paths(set(paths)), expected)
        findings = check_paths(["Readme", "README", "readme"])
        self.assertEqual(findings[0].paths, ("README", "Readme", "readme"))


if __name__ == "__main__":
    unittest.main()
