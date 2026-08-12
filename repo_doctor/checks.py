"""Individual health checks for a Git repository.

Every check returns a Finding with a severity of "ok", "warn" or "fail".
Checks never raise on a missing tool or weird repo state; they degrade to a
"warn" finding so the report stays useful everywhere.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Finding:
    check: str
    severity: str  # "ok" | "warn" | "fail"
    message: str
    hint: Optional[str] = None


@dataclass
class Report:
    path: Path
    findings: List[Finding] = field(default_factory=list)

    @property
    def score(self) -> int:
        """100 minus penalties: fail=20, warn=7. Clamped to [0, 100]."""
        penalty = sum(20 if f.severity == "fail" else 7 if f.severity == "warn" else 0
                      for f in self.findings)
        return max(0, 100 - penalty)

    @property
    def grade(self) -> str:
        s = self.score
        if s >= 90:
            return "A"
        if s >= 75:
            return "B"
        if s >= 60:
            return "C"
        if s >= 40:
            return "D"
        return "F"


def _git(repo: Path, *args: str) -> Optional[str]:
    """Run a git command in repo; return stripped stdout or None on failure."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def check_is_git_repo(repo: Path) -> Finding:
    if (repo / ".git").exists():
        return Finding("git-repo", "ok", "Directory is a Git repository.")
    return Finding("git-repo", "fail", "Not a Git repository (no .git directory).",
                   hint="Run `git init` or point repo-doctor at a cloned repo.")


def check_required_files(repo: Path) -> List[Finding]:
    findings = []
    required = {
        "README": ["README.md", "README.rst", "README", "readme.md"],
        "LICENSE": ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"],
        "gitignore": [".gitignore"],
    }
    hints = {
        "README": "Add a README.md with what/why/install/usage.",
        "LICENSE": "Pick a license (MIT/Apache-2.0) — no license means 'all rights reserved'.",
        "gitignore": "Add a .gitignore to keep build artifacts and secrets out of history.",
    }
    for name, candidates in required.items():
        if any((repo / c).exists() for c in candidates):
            findings.append(Finding(f"file-{name.lower()}", "ok", f"{name} file present."))
        else:
            findings.append(Finding(f"file-{name.lower()}", "fail" if name != "gitignore" else "warn",
                                    f"Missing {name} file.", hint=hints[name]))
    return findings


def check_branch_hygiene(repo: Path) -> Finding:
    merged = _git(repo, "branch", "--merged")
    if merged is None:
        return Finding("branches", "warn", "Could not list branches (git unavailable?).")
    stale = [b.strip().lstrip("* ") for b in merged.splitlines()
             if b.strip() and not b.strip().startswith("*")
             and b.strip().lstrip("* ") not in {"main", "master", "develop", "dev"}]
    if stale:
        return Finding("branches", "warn",
                       f"{len(stale)} merged branch(es) still around: {', '.join(stale[:5])}"
                       + (" ..." if len(stale) > 5 else ""),
                       hint="Delete merged branches: git branch -d <name>.")
    return Finding("branches", "ok", "No stale merged branches.")


def check_commit_messages(repo: Path, limit: int = 20) -> Finding:
    log = _git(repo, "log", f"-{limit}", "--pretty=%s")
    if not log:
        return Finding("commits", "warn", "No commits found or git unavailable.")
    subjects = log.splitlines()
    sloppy = [s for s in subjects
              if len(s) < 8 or not re.search(r"[a-zA-Z\u4e00-\u9fff]", s)
              or s.lower() in {"fix", "update", "wip", "tmp", "test", "1", "."}
              or s.endswith(".") and len(s) < 15]
    ratio = len(sloppy) / max(len(subjects), 1)
    if ratio > 0.3:
        return Finding("commits", "warn",
                       f"{len(sloppy)}/{len(subjects)} recent commit messages look uninformative "
                       f"(e.g. \"{sloppy[0]}\").",
                       hint="Use imperative summaries, e.g. 'fix: handle empty config file'.")
    return Finding("commits", "ok", f"Recent {len(subjects)} commit messages look healthy.")


def check_large_files(repo: Path, threshold_kb: int = 1024) -> Finding:
    tracked = _git(repo, "ls-files")
    if tracked is None:
        return Finding("large-files", "warn", "Could not list tracked files.")
    big = []
    for rel in tracked.splitlines():
        p = repo / rel
        try:
            size_kb = p.stat().st_size / 1024
        except OSError:
            continue
        if size_kb > threshold_kb:
            big.append((rel, size_kb))
    if big:
        big.sort(key=lambda x: -x[1])
        shown = ", ".join(f"{r} ({s:.0f} KB)" for r, s in big[:3])
        return Finding("large-files", "fail", f"{len(big)} tracked file(s) over {threshold_kb} KB: {shown}",
                       hint="Use Git LFS or remove binaries from history (git filter-repo).")
    return Finding("large-files", "ok", f"No tracked files over {threshold_kb} KB.")


def check_secret_patterns(repo: Path) -> Finding:
    patterns = {
        "private key": re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"),
        "aws access key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "generic token assignment": re.compile(r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]{12,}"),
    }
    hits = []
    tracked = _git(repo, "ls-files")
    if tracked is None:
        return Finding("secrets", "warn", "Could not scan files.")
    for rel in tracked.splitlines():
        p = repo / rel
        try:
            if p.stat().st_size > 512 * 1024 or not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pat in patterns.items():
            if pat.search(text):
                hits.append(f"{rel} ({name})")
    if hits:
        return Finding("secrets", "fail",
                       f"Possible secrets committed: {', '.join(hits[:5])}",
                       hint="Rotate the credential, purge it from history, add it to .gitignore.")
    return Finding("secrets", "ok", "No obvious secrets in tracked files.")


def check_recent_activity(repo: Path) -> Finding:
    ts = _git(repo, "log", "-1", "--format=%ct")
    if not ts or not ts.isdigit():
        return Finding("activity", "warn", "No commit history found.")
    import time
    age_days = (time.time() - int(ts)) / 86400
    if age_days > 180:
        return Finding("activity", "warn",
                       f"Last commit is {int(age_days)} days old.",
                       hint="Dormant repos look unmaintained — even small upkeep commits help.")
    return Finding("activity", "ok", f"Last commit {int(age_days)} day(s) ago.")


ALL_CHECKS = (
    check_is_git_repo,
    check_required_files,
    check_branch_hygiene,
    check_commit_messages,
    check_large_files,
    check_secret_patterns,
    check_recent_activity,
)


def run_checks(repo: Path) -> Report:
    report = Report(path=repo)
    for check in ALL_CHECKS:
        result = check(repo)
        if isinstance(result, list):
            report.findings.extend(result)
        else:
            report.findings.append(result)
    return report
