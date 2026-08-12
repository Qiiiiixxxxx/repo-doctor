"""Command-line interface for repo-doctor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checks import run_checks

ICONS = {"ok": "PASS", "warn": "WARN", "fail": "FAIL"}


def render_text(report) -> str:
    lines = [f"repo-doctor report for {report.path}", ""]
    for f in report.findings:
        lines.append(f"[{ICONS[f.severity]}] {f.check}: {f.message}")
        if f.hint:
            lines.append(f"       hint: {f.hint}")
    lines += ["", f"Health score: {report.score}/100 (grade {report.grade})"]
    return "\n".join(lines)


def render_json(report) -> str:
    return json.dumps({
        "path": str(report.path),
        "score": report.score,
        "grade": report.grade,
        "findings": [
            {"check": f.check, "severity": f.severity, "message": f.message, "hint": f.hint}
            for f in report.findings
        ],
    }, indent=2, ensure_ascii=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo-doctor",
        description="Audit the health of a Git repository: docs, branches, commits, "
                    "large files, leaked secrets, and activity.",
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="Path to the repository (default: current directory).")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text).")
    parser.add_argument("--fail-under", type=int, default=None, metavar="SCORE",
                        help="Exit with code 1 if the health score is below SCORE. "
                             "Useful as a CI gate.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    repo = Path(args.path).resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2

    report = run_checks(repo)
    print(render_json(report) if args.format == "json" else render_text(report))

    if args.fail_under is not None and report.score < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
