# repo-doctor

**A zero-dependency CLI that audits the health of a Git repository** — documentation, branch hygiene, commit quality, oversized files, accidentally committed secrets, and maintenance activity. It prints a human-readable report with a 0–100 health score, or JSON for CI pipelines.

```
$ repo-doctor .
[PASS] git-repo: Directory is a Git repository.
[PASS] file-readme: README file present.
[PASS] file-license: LICENSE file present.
[PASS] file-gitignore: gitignore file present.
[WARN] branches: 2 merged branch(es) still around: feature-x, hotfix-y
       hint: Delete merged branches: git branch -d <name>.
[PASS] commits: Recent 20 commit messages look healthy.
[FAIL] large-files: 1 tracked file(s) over 1024 KB: assets/demo.mp4 (8421 KB)
       hint: Use Git LFS or remove binaries from history (git filter-repo).
[PASS] secrets: No obvious secrets in tracked files.
[PASS] activity: Last commit 3 day(s) ago.

Health score: 73/100 (grade C)
```

## Why

Small and mid-size repos quietly rot: no license, merged branches piling up, a private key committed six months ago. `repo-doctor` is the five-second checkup you run before open-sourcing a project, handing off a repo, or in CI to stop regressions. It has **no dependencies beyond Python ≥ 3.9 and git**, so it runs anywhere.

## Install

```bash
pip install git+https://github.com/<you>/repo-doctor.git
# or from a clone:
pip install .
```

## Usage

```bash
repo-doctor                 # audit current directory
repo-doctor /path/to/repo   # audit another repo
repo-doctor --format json   # machine-readable output
repo-doctor --fail-under 80 # exit 1 below score 80 — use as a CI gate
```

### GitHub Actions gate

```yaml
- uses: actions/setup-python@v5
- run: pip install .
- run: repo-doctor --fail-under 70
```

## What it checks

| Check | What fails it |
|---|---|
| `git-repo` | Directory is not a Git repository |
| `file-readme` / `file-license` / `file-gitignore` | Missing standard files |
| `branches` | Merged branches never deleted |
| `commits` | >30% of recent commit messages are uninformative |
| `large-files` | Tracked files over 1 MB (should be in LFS) |
| `secrets` | Private keys, AWS keys, or token assignments in tracked files |
| `activity` | No commits in 180+ days |
| `release-tags` | No semantic-version tags (e.g. `v1.2.0`) for users to pin |
| `default-branch` | Default branch is neither `main` nor `master` |

Score starts at 100; each FAIL costs 20, each WARN costs 7. Grades: A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 40, F below.

## Development

```bash
python -m unittest discover tests -v   # run the test suite (stdlib only)
```

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
