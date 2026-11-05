"""Tests for bin/ci-close-report-pr, driven against a scratch remote with `gh` stubbed."""

import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
CLOSE_PR = REPO_ROOT / "bin" / "ci-close-report-pr"
BRANCH = "reports/android"
BOT = "bot@example.invalid"
OWN_PR = json.dumps([{"number": 5}])
QUERY = "api repos/case/linkability/pulls?state=open&head=case:reports/android"

ISOLATED_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/nonexistent",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
}

# GH_STUB_PRS stands for the server's already owner-filtered answer; the script's --jq runs on it.
GH_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$GH_STUB_LOG"
if [ "$1" = api ]; then
  [ "${GH_STUB_LIST_FAILS:-}" = 1 ] && { echo "HTTP 401: Bad credentials" >&2; exit 1; }
  while [ $# -gt 0 ] && [ "$1" != --jq ]; do shift; done
  printf '%s' "${GH_STUB_PRS:-[]}" | JQ -r "$2"
  exit
fi
case "$1 $2" in
  "pr close") ;;
  *) exit 1 ;;
esac
"""


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=ISOLATED_GIT_ENV,
    )


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.invalid")
    (work / "seed.txt").write_text("seed\n")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "seed")
    bare = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    return bare


def push_branch(remote: Path, tmp_path: Path, committer: str, run: str | None = "7") -> None:
    """Push a report branch whose tip was committed by `committer`, from run `run`."""
    work = tmp_path / f"push-{committer}"
    git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.name", "Someone")
    git(work, "config", "user.email", committer)
    (work / "report.csv").write_text("com,true\n")
    git(work, "add", "-A")
    message = "Update Android platform reports"
    if run is not None:
        message += f"\n\nReport-Run: {run}"
    git(work, "commit", "-q", "-m", message)
    git(work, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}")


def run_close(remote: Path, tmp_path: Path, **env_overrides: str):
    jq = shutil.which("jq")
    if jq is None:
        pytest.skip("jq not available")
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "gh"
    stub.write_text(GH_STUB.replace("JQ", shlex.quote(jq)))
    stub.chmod(0o755)
    checkout = tmp_path / "checkout"
    if not checkout.exists():
        git(tmp_path, "clone", "-q", "--depth=1", f"file://{remote}", str(checkout))
    log = tmp_path / "gh.log"
    outputs = tmp_path / "outputs"
    env = {
        **ISOLATED_GIT_ENV,
        "PATH": f"{stub_dir}:{ISOLATED_GIT_ENV['PATH']}",
        "PUSH_REMOTE": f"file://{remote}",
        "CI_COMMITTER_EMAIL": BOT,
        "GITHUB_RUN_NUMBER": "7",
        "GITHUB_REPOSITORY": "case/linkability",
        "GITHUB_REPOSITORY_OWNER": "case",
        "GITHUB_OUTPUT": str(outputs),
        "GH_STUB_LOG": str(log),
        **env_overrides,
    }
    result = subprocess.run(
        [str(CLOSE_PR), BRANCH],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    calls = log.read_text() if log.exists() else ""
    emitted = outputs.read_text() if outputs.exists() else ""
    return result, calls, emitted


def test_closes_an_open_machine_owned_pr(remote, tmp_path):
    push_branch(remote, tmp_path, BOT)

    result, calls, emitted = run_close(remote, tmp_path, GH_STUB_PRS=OWN_PR)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr close 5 --comment" in calls
    assert "outcome=pr_closed" in emitted


def test_does_nothing_when_no_pr_is_open(remote, tmp_path):
    result, calls, emitted = run_close(remote, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr close" not in calls
    assert "outcome=no_open_pr" in emitted


def test_looks_up_only_this_repositorys_pr(remote, tmp_path):
    """The repo is public and the branch name is fixed, so a fork can reuse it."""
    result, calls, _ = run_close(remote, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert QUERY in calls


def test_leaves_a_pr_open_when_a_reviewer_committed_to_it(remote, tmp_path):
    push_branch(remote, tmp_path, "reviewer@example.invalid")

    result, calls, emitted = run_close(remote, tmp_path, GH_STUB_PRS=OWN_PR)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr close" not in calls
    assert "outcome=kept_reviewer_commit" in emitted
    assert "::warning::" in result.stdout


def test_an_older_run_does_not_close_a_newer_runs_pr(remote, tmp_path):
    """Re-running an old close job must not act on results a later run published."""
    push_branch(remote, tmp_path, BOT, run="9")

    result, calls, emitted = run_close(remote, tmp_path, GH_STUB_PRS=OWN_PR, GITHUB_RUN_NUMBER="8")

    assert result.returncode == 1
    assert "pr close" not in calls
    assert "outcome=stale_run" in emitted


def test_a_tip_without_a_run_number_counts_as_older(remote, tmp_path):
    push_branch(remote, tmp_path, BOT, run=None)

    result, calls, emitted = run_close(remote, tmp_path, GH_STUB_PRS=OWN_PR)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr close 5 --comment" in calls
    assert "outcome=pr_closed" in emitted


def test_a_failed_pr_lookup_fails_the_step(remote, tmp_path):
    """An outage must not read as 'no open PR', or a contradicted PR stays mergeable."""
    push_branch(remote, tmp_path, BOT)

    result, calls, emitted = run_close(remote, tmp_path, GH_STUB_LIST_FAILS="1")

    assert result.returncode != 0
    assert "pr close" not in calls
    assert "outcome=" not in emitted


def test_rejects_a_run_number_that_is_not_a_number(remote, tmp_path):
    result, calls, _ = run_close(remote, tmp_path, GH_STUB_PRS=OWN_PR, GITHUB_RUN_NUMBER="7a")

    assert result.returncode == 1
    assert "GITHUB_RUN_NUMBER is not a number" in result.stdout
    assert "pr close" not in calls


@pytest.mark.parametrize(
    "missing",
    [
        "PUSH_REMOTE",
        "CI_COMMITTER_EMAIL",
        "GITHUB_RUN_NUMBER",
        "GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY_OWNER",
    ],
)
def test_refuses_when_a_required_variable_is_unset(remote, tmp_path, missing):
    result, calls, _ = run_close(remote, tmp_path, GH_STUB_PRS=OWN_PR, **{missing: ""})

    assert result.returncode == 1
    assert f"{missing} is not configured" in result.stdout
    assert "pr close" not in calls
