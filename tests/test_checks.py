"""Tests for repo-doctor. Uses real temp git repos; requires git on PATH.
Run with: python -m unittest discover tests -v
"""

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from repo_doctor.checks import (check_large_files, check_required_files,
                                check_secret_patterns, run_checks)
from repo_doctor.cli import main, render_text

GIT = shutil.which("git")


def git(repo: Path, *args: str) -> None:
    subprocess.run([GIT, "-C", str(repo), *args], check=True, capture_output=True)


@unittest.skipUnless(GIT, "git not available")
class RepoDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        git(self.tmp, "init", "-q")
        git(self.tmp, "config", "user.email", "test@example.com")
        git(self.tmp, "config", "user.name", "Test")
        (self.tmp / "README.md").write_text("# demo\n")
        (self.tmp / "LICENSE").write_text("MIT\n")
        (self.tmp / ".gitignore").write_text("__pycache__/\n")
        (self.tmp / "main.py").write_text("print('hello')\n")
        git(self.tmp, "add", "-A")
        git(self.tmp, "commit", "-qm", "chore: initial commit with docs")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_required_files_all_present(self):
        findings = check_required_files(self.tmp)
        self.assertEqual(len(findings), 3)
        self.assertTrue(all(f.severity == "ok" for f in findings))

    def test_secret_detection(self):
        (self.tmp / "config.py").write_text('api_key = "sk-1234567890abcdef"\n')
        git(self.tmp, "add", "-A")
        finding = check_secret_patterns(self.tmp)
        self.assertEqual(finding.severity, "fail")
        self.assertIn("config.py", finding.message)

    def test_large_file_detection(self):
        (self.tmp / "blob.bin").write_bytes(b"x" * (1024 * 1024 + 1))
        git(self.tmp, "add", "-A")
        self.assertEqual(check_large_files(self.tmp, threshold_kb=1024).severity, "fail")

    def test_report_score_and_grade(self):
        report = run_checks(self.tmp)
        self.assertGreaterEqual(report.score, 0)
        self.assertLessEqual(report.score, 100)
        self.assertIn(report.grade, "ABCDF")

    def test_cli_json_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(self.tmp), "--format", "json"])
        data = json.loads(buf.getvalue())
        self.assertIn(data["grade"], "ABCDF")
        self.assertEqual(code, 0)

    def test_cli_fail_under(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.tmp), "--fail-under", "101"]), 1)

    def test_release_tags(self):
        from repo_doctor.checks import check_release_tags
        self.assertEqual(check_release_tags(self.tmp).severity, "warn")
        git(self.tmp, "tag", "-a", "v0.1.0", "-m", "first release")
        finding = check_release_tags(self.tmp)
        self.assertEqual(finding.severity, "ok")
        self.assertIn("v0.1.0", finding.message)

    def test_render_text_contains_score(self):
        self.assertIn("Health score", render_text(run_checks(self.tmp)))


class StaticChecks(unittest.TestCase):
    def test_required_files_missing(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            self.assertTrue(any(f.severity == "fail" for f in check_required_files(tmp)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cli_bad_path(self):
        self.assertEqual(main(["/nonexistent/path/xyz"]), 2)


if __name__ == "__main__":
    unittest.main()
