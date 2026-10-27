#!/usr/bin/env python3
"""Test suite for the dedupe CLI. Stdlib only.

Runner: `make test` (or `python3 tests/test_dedupe.py`).
CLI under test: DEDUPE_BIN env var, else ../dedupe relative to this file.
All temp files live in tempfile dirs; no absolute repo paths are baked in.
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DEDUPE = os.environ.get("DEDUPE_BIN", os.path.join(HERE, "..", "dedupe"))


def run(args, stdin_data=None):
    """Run dedupe with given argv; stdin_data is str or None. Returns CompletedProcess with text."""
    return subprocess.run(
        [sys.executable, DEDUPE] + args,
        input=stdin_data,
        capture_output=True,
        text=True,
    )


def run_bytes_stdin(args, raw_bytes):
    """Run dedupe feeding raw bytes on stdin (for no-trailing-newline tests)."""
    return subprocess.run(
        [sys.executable, DEDUPE] + args,
        input=raw_bytes,
        capture_output=True,
    )


class TestInputModes(unittest.TestCase):
    def test_stdin_no_args(self):
        p = run([], stdin_data="b\na\nb\na\nc\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "b\na\nc\n")

    def test_stdin_explicit_dash(self):
        p = run(["-"], stdin_data="b\na\nb\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "b\na\n")

    def test_file_arg(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("p\nq\np\n")
            path = f.name
        try:
            p = run([path])
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stdout, "p\nq\n")
        finally:
            os.unlink(path)

    def test_multiple_files_in_order(self):
        paths = []
        try:
            for content in ("a\nb\n", "b\nc\n"):
                f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
                f.write(content)
                f.close()
                paths.append(f.name)
            p = run(paths)
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stdout, "a\nb\nc\n")
        finally:
            for path in paths:
                os.unlink(path)

    def test_no_trailing_newline_preserved(self):
        p = run_bytes_stdin([], b"a\nb")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"a\nb\n")

    def test_empty_stdin(self):
        p = run([], stdin_data="")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "")


class TestKeepModes(unittest.TestCase):
    def test_keep_first_default(self):
        p = run([], stdin_data="x\ny\nx\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "x\ny\n")

    def test_keep_first_explicit(self):
        p = run(["--keep-first"], stdin_data="x\ny\nx\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "x\ny\n")

    def test_keep_last_ordering(self):
        # x's last occurrence is position 3, y's is 2 -> y first, then x.
        p = run(["--keep-last"], stdin_data="x\ny\nx\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "y\nx\n")

    def test_keep_last_longer(self):
        p = run(["--keep-last"], stdin_data="a\nb\nc\nb\na\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "c\nb\na\n")


class TestCount(unittest.TestCase):
    def test_count_tab_format_keep_first(self):
        p = run(["--count"], stdin_data="b\na\nb\na\nc\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "2\tb\n2\ta\n1\tc\n")

    def test_count_follows_keep_last_order(self):
        p = run(["--count", "--keep-last"], stdin_data="x\ny\nx\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "1\ty\n2\tx\n")

    def test_count_tab_separator_is_literal_tab(self):
        p = run(["--count"], stdin_data="z\nz\n")
        self.assertEqual(p.returncode, 0)
        lines = p.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        count, sep, rest = lines[0].partition("\t")
        self.assertEqual(sep, "\t")
        self.assertEqual(count, "2")
        self.assertEqual(rest, "z")


class TestBlanks(unittest.TestCase):
    def test_blanks_collapse_to_single(self):
        p = run([], stdin_data="a\n\n   \n\nb\na\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "a\n\nb\n")

    def test_blank_at_first_position(self):
        p = run([], stdin_data="\n\na\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "\na\n")

    def test_blank_count(self):
        p = run(["--count"], stdin_data="a\n\n \n\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "1\ta\n3\t\n")

    def test_blank_pinned_first_under_keep_last(self):
        # Blank collapses at first blank position even with --keep-last.
        p = run(["--keep-last"], stdin_data="a\n\nb\n\nc\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "a\n\nb\nc\n")


class TestIgnoreCase(unittest.TestCase):
    def test_ignore_case_first_spelling(self):
        p = run(["--ignore-case"], stdin_data="Hello\nhello\nWORLD\nworld\nhello\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "Hello\nWORLD\n")

    def test_ignore_case_keep_last_uses_last_spelling(self):
        p = run(["--ignore-case", "--keep-last"],
                stdin_data="Hello\nhello\nWORLD\nworld\nhello\n")
        self.assertEqual(p.returncode, 0)
        # Last-seen spellings: 'hello' (last at idx 4), 'world' (idx 3).
        # Ordered by last occurrence: world, then hello.
        self.assertEqual(p.stdout, "world\nhello\n")

    def test_case_sensitive_by_default(self):
        p = run([], stdin_data="A\na\nA\n")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "A\na\n")


class TestExitCodes(unittest.TestCase):
    def test_unknown_flag_exit_2_stderr(self):
        p = run(["--frobnicate"], stdin_data="")
        self.assertEqual(p.returncode, 2)
        self.assertNotEqual(p.stderr.strip(), "")
        self.assertEqual(p.stdout, "")

    def test_single_dash_flag_exit_2(self):
        p = run(["-x"], stdin_data="")
        self.assertEqual(p.returncode, 2)
        self.assertNotEqual(p.stderr.strip(), "")

    def test_missing_file_nonzero_stderr(self):
        p = run(["/nonexistent_dedupe_test_file_xyz"])
        self.assertNotEqual(p.returncode, 0)
        self.assertNotEqual(p.stderr.strip(), "")

    def test_missing_file_exit_1(self):
        p = run(["/nonexistent_dedupe_test_file_xyz"])
        self.assertEqual(p.returncode, 1)

    def test_help_exit_0_stdout(self):
        p = run(["--help"])
        self.assertEqual(p.returncode, 0)
        self.assertIn("Usage", p.stdout)

    def test_help_short_flag(self):
        p = run(["-h"])
        self.assertEqual(p.returncode, 0)
        self.assertIn("Usage", p.stdout)

    def test_other_inputs_processed_despite_missing_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("m\nm\nn\n")
            path = f.name
        try:
            p = run([path, "/nonexistent_dedupe_test_file_xyz"])
            self.assertEqual(p.returncode, 1)
            self.assertEqual(p.stdout, "m\nn\n")
            self.assertNotEqual(p.stderr.strip(), "")
        finally:
            os.unlink(path)


class TestStreamingDiscipline(unittest.TestCase):
    def test_no_bulk_read_calls_in_source(self):
        import ast
        with open(DEDUPE, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        bulk = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in ("read", "readlines"):
                    bulk.append("attribute call .%s()" % func.attr)
                elif isinstance(func, ast.Name) and func.id == "list":
                    bulk.append("list() call")
        self.assertEqual(bulk, [],
                         "source must not buffer whole input; found: %s" % bulk)

    def test_large_input_smoke(self):
        # 200k lines, few uniques; assert correct output.
        n = 200_000
        uniques = ["alpha", "beta", "gamma", "delta", "epsilon"]
        data = "".join(uniques[i % len(uniques)] + "\n" for i in range(n))
        p = run(["--count"], stdin_data=data)
        self.assertEqual(p.returncode, 0)
        expected = "".join("%d\t%s\n" % (n // len(uniques), u) for u in uniques)
        self.assertEqual(p.stdout, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
