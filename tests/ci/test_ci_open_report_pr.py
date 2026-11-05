"""End-to-end tests for bin/ci-open-report-pr, driven against scratch repos.

The flow runs on a schedule on a runner and never locally, so every case here
builds a throwaway repo plus a bare remote and stubs `gh` on PATH. Signing and
pushing belong to bin/ci-land-report-patch and are covered in
test_ci_report_patch.py; what this file pins is the PR the wrapper then opens.
"""

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
OPEN_PR = REPO_ROOT / "bin" / "ci-open-report-pr"
BRANCH = "reports/android"
TITLE = "Update Android platform reports"

ISOLATED_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/nonexistent",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
}

OWN_PR = json.dumps([{"number": 5}])
QUERY = "api repos/case/linkability/pulls?state=open&head=case:reports/android"

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
  "pr create")
    [ "${GH_STUB_CREATE_FAILS:-}" = 1 ] && {
      echo "pull request create failed: GraphQL: GitHub Actions is not permitted" >&2
      exit 1
    }
    echo "https://github.com/case/linkability/pull/1" ;;
  "pr comment") ;;
  *) exit 1 ;;
esac
"""

BODY = """## Android Platform Check

Automated scheduled check of TLD auto-linking across Android versions.
"""


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
        env=ISOLATED_GIT_ENV,
    )


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def signing_key(tmp_path: Path) -> str:
    if shutil.which("ssh-keygen") is None:
        pytest.skip("ssh-keygen not available")
    key = tmp_path / "ci-signing"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "ci", "-f", str(key)],
        check=True,
        capture_output=True,
    )
    return key.read_text()


@dataclass(frozen=True)
class Workspace:
    repo: Path
    bare: Path
    stub_dir: Path
    gh_log: Path
    outputs: Path
    runner_temp: Path
    body: Path


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "user.name", "Test")
    git(origin, "config", "user.email", "test@example.invalid")
    snapshots = origin / "Reports" / "snapshots" / "android"
    snapshots.mkdir(parents=True)
    (snapshots / "16.csv").write_text("zone,linked\n")
    (snapshots / "16.json").write_text("{}\n")
    commit_all(origin, "seed")

    bare = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(origin), str(bare))
    repo = tmp_path / "consumer"
    git(tmp_path, "clone", "-q", str(bare), str(repo))
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")

    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "gh"
    jq = shutil.which("jq")
    if jq is None:
        pytest.skip("jq not available")
    stub.write_text(GH_STUB.replace("JQ", shlex.quote(jq)))
    stub.chmod(0o755)

    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    body = runner_temp / "pr-body.md"
    body.write_text(BODY)

    return Workspace(
        repo=repo,
        bare=bare,
        stub_dir=stub_dir,
        gh_log=tmp_path / "gh.log",
        outputs=tmp_path / "outputs",
        runner_temp=runner_temp,
        body=body,
    )


def stage_change(
    workspace: Workspace, results: str = "com,true\n", check_date: str = "2026-09-10"
) -> None:
    """Stage a snapshot the way the check writes one: results CSV plus dated sidecar."""
    snapshots = workspace.repo / "Reports" / "snapshots" / "android"
    (snapshots / "16.csv").write_text(f"zone,linked\n{results}")
    (snapshots / "16.json").write_text(json.dumps({"check_date": check_date}) + "\n")
    git(workspace.repo, "add", "-A")


def run_open_pr(
    workspace: Workspace,
    signing_key: str,
    *args: str,
    **env_overrides: str,
) -> subprocess.CompletedProcess[str]:
    env = {
        **ISOLATED_GIT_ENV,
        "PATH": f"{workspace.stub_dir}:{ISOLATED_GIT_ENV['PATH']}",
        "PUSH_REMOTE": str(workspace.bare),
        "RUNNER_TEMP": str(workspace.runner_temp),
        "GITHUB_OUTPUT": str(workspace.outputs),
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "case/linkability",
        "GITHUB_REPOSITORY_OWNER": "case",
        "GH_STUB_LOG": str(workspace.gh_log),
        "CI_SSH_SIGNING_KEY": signing_key,
        "CI_COMMITTER_NAME": "linkability bot",
        "CI_COMMITTER_EMAIL": "bot@example.invalid",
        "GITHUB_RUN_NUMBER": "7",
    }
    env.update(env_overrides)
    if not args:
        args = (BRANCH, TITLE)
        args = (*args, str(workspace.body))
    return subprocess.run(
        [str(OPEN_PR), *args],
        cwd=workspace.repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def outputs_of(workspace: Workspace) -> dict[str, str]:
    if not workspace.outputs.exists():
        return {}
    return dict(
        line.split("=", 1) for line in workspace.outputs.read_text().splitlines() if "=" in line
    )


class TestPrCreation:
    def test_opens_a_pr_and_pushes_a_signed_branch(self, workspace, signing_key):
        stage_change(workspace)

        result = run_open_pr(workspace, signing_key)

        assert result.returncode == 0, result.stdout + result.stderr
        pushed = git(workspace.bare, "rev-parse", BRANCH).stdout.strip()
        assert pushed == git(workspace.repo, "rev-parse", "HEAD").stdout.strip()
        assert "gpgsig " in git(workspace.repo, "cat-file", "commit", "HEAD").stdout
        assert outputs_of(workspace)["outcome"] == "pr_opened"

    def test_the_pr_carries_the_callers_title_and_body(self, workspace, signing_key):
        stage_change(workspace)

        run_open_pr(workspace, signing_key)

        calls = workspace.gh_log.read_text()
        assert "pr create --base main --head reports/android" in calls
        assert f"--title {TITLE}" in calls
        composed = (workspace.runner_temp / "pr-comment.md").read_text()
        assert composed.startswith("## Android Platform Check")
        assert "Automated scheduled check" in composed
        assert "Checks on this PR need manual approval" in composed
        # The caller's file is under $RUNNER_TEMP too, so composing in place
        # truncated it before it was read.
        assert workspace.body.read_text() == BODY

    def test_the_commit_subject_matches_the_pr_title(self, workspace, signing_key):
        stage_change(workspace)

        run_open_pr(workspace, signing_key)

        subject = git(workspace.repo, "log", "-1", "--pretty=%s").stdout.strip()
        assert subject == TITLE

    def test_the_signing_key_does_not_outlive_the_run(self, workspace, signing_key):
        stage_change(workspace)

        run_open_pr(workspace, signing_key)

        assert not (workspace.runner_temp / "linkability-ci-signing").exists()

    def test_blocked_create_still_pushes_and_reports_a_compare_url(self, workspace, signing_key):
        """Failing the step here would lose the branch that was already pushed."""
        stage_change(workspace)

        result = run_open_pr(workspace, signing_key, GH_STUB_CREATE_FAILS="1")

        assert result.returncode == 0, result.stdout + result.stderr
        assert git(workspace.bare, "rev-parse", BRANCH).returncode == 0
        emitted = outputs_of(workspace)
        assert emitted["outcome"] == "pr_blocked"
        assert emitted["compare_url"] == (
            "https://github.com/case/linkability/compare/reports/android?expand=1"
        )

    def test_refuses_when_nothing_was_staged(self, workspace, signing_key):
        result = run_open_pr(workspace, signing_key)

        assert result.returncode == 1
        assert "refusing to create an empty commit" in result.stdout
        assert (
            "pr create" not in workspace.gh_log.read_text() if workspace.gh_log.exists() else True
        )


class TestReRun:
    """A re-run keeps the run number, so it lands on the branch it already made."""

    def _first_run(self, workspace, signing_key) -> None:
        stage_change(workspace)
        assert run_open_pr(workspace, signing_key).returncode == 0
        workspace.outputs.unlink()
        workspace.gh_log.unlink()
        git(workspace.repo, "checkout", "-q", "--force", "--detach", "origin/main")

    def test_an_open_pr_gets_a_comment_instead_of_a_second_pr(self, workspace, signing_key):
        self._first_run(workspace, signing_key)
        stage_change(workspace, "com,false\n")

        result = run_open_pr(workspace, signing_key, GH_STUB_PRS=OWN_PR)

        assert result.returncode == 0, result.stdout + result.stderr
        calls = workspace.gh_log.read_text()
        assert "pr comment 5 --body-file" in calls
        assert "pr create" not in calls
        assert outputs_of(workspace)["outcome"] == "pr_updated"

    def test_identical_reports_are_not_announced_again(self, workspace, signing_key):
        """A re-run that regenerates the same reports must not double-comment."""
        self._first_run(workspace, signing_key)
        stage_change(workspace)

        result = run_open_pr(workspace, signing_key, GH_STUB_PRS=OWN_PR)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "pr comment" not in workspace.gh_log.read_text()
        assert outputs_of(workspace)["outcome"] == "unchanged"

    def test_the_same_results_on_a_later_day_are_not_announced(self, workspace, signing_key):
        """The check re-dates a pending snapshot every night; only results count."""
        self._first_run(workspace, signing_key)
        stage_change(workspace, check_date="2026-09-11")

        result = run_open_pr(workspace, signing_key, GH_STUB_PRS=OWN_PR)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "pr comment" not in workspace.gh_log.read_text()
        assert outputs_of(workspace)["outcome"] == "unchanged"
        branch_json = git(workspace.bare, "show", f"{BRANCH}:Reports/snapshots/android/16.json")
        assert "2026-09-11" in branch_json.stdout

    def test_looks_up_only_this_repositorys_pr(self, workspace, signing_key):
        """The repo is public and the branch name is fixed, so a fork can reuse it."""
        stage_change(workspace)

        result = run_open_pr(workspace, signing_key)

        assert result.returncode == 0, result.stdout + result.stderr
        assert QUERY in workspace.gh_log.read_text()

    def test_another_platform_merging_is_not_announced(self, workspace, signing_key, tmp_path):
        """Rebuilding on a main that gained other platforms' snapshots is not a new result."""
        self._first_run(workspace, signing_key)
        other = tmp_path / "other"
        git(tmp_path, "clone", "-q", str(workspace.bare), str(other))
        git(other, "config", "user.name", "Owner")
        git(other, "config", "user.email", "owner@example.invalid")
        apple = other / "Reports" / "snapshots" / "apple"
        apple.mkdir(parents=True)
        (apple / "26.csv").write_text("zone,linked\ncom,true\n")
        commit_all(other, "Merge Apple report PR")
        git(other, "push", "-q", "origin", "main")
        git(workspace.repo, "fetch", "-q", "origin")
        git(workspace.repo, "checkout", "-q", "--detach", "origin/main")
        stage_change(workspace, check_date="2026-09-11")

        result = run_open_pr(workspace, signing_key, GH_STUB_PRS=OWN_PR)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "pr comment" not in workspace.gh_log.read_text()
        assert outputs_of(workspace)["outcome"] == "unchanged"

    def test_a_kept_branch_is_reused_after_its_pr_merges(self, workspace, signing_key, tmp_path):
        self._first_run(workspace, signing_key)
        merger = tmp_path / "merger"
        git(tmp_path, "clone", "-q", str(workspace.bare), str(merger))
        git(merger, "config", "user.name", "Owner")
        git(merger, "config", "user.email", "owner@example.invalid")
        git(merger, "merge", "-q", "--no-ff", "-m", "Merge report PR", f"origin/{BRANCH}")
        git(merger, "push", "-q", "origin", "main")
        merged_main = git(merger, "rev-parse", "HEAD").stdout.strip()
        git(workspace.repo, "fetch", "-q", "origin")
        git(workspace.repo, "checkout", "-q", "--detach", "origin/main")
        stage_change(workspace, "com,false\n", check_date="2026-09-11")

        result = run_open_pr(workspace, signing_key, GITHUB_RUN_NUMBER="8")

        assert result.returncode == 0, result.stdout + result.stderr
        assert "pr create" in workspace.gh_log.read_text()
        assert outputs_of(workspace)["outcome"] == "pr_opened"
        assert git(workspace.bare, "rev-parse", f"{BRANCH}^").stdout.strip() == merged_main
        changed = git(workspace.bare, "diff", "--name-only", "main", BRANCH).stdout.split()
        assert changed == ["Reports/snapshots/android/16.csv", "Reports/snapshots/android/16.json"]

    def test_a_reviewer_commit_on_the_branch_is_not_discarded(
        self, workspace, signing_key, tmp_path
    ):
        self._first_run(workspace, signing_key)
        human = tmp_path / "human"
        git(tmp_path, "clone", "-q", str(workspace.bare), str(human))
        git(human, "config", "user.name", "Reviewer")
        git(human, "config", "user.email", "reviewer@example.invalid")
        git(human, "checkout", "-q", BRANCH)
        (human / "Reports" / "snapshots" / "android" / "16.json").write_text('{"human": 1}\n')
        theirs = commit_all(human, "reviewer edit")
        git(human, "push", "-q", "origin", BRANCH)
        stage_change(workspace, "com,false\n")

        result = run_open_pr(workspace, signing_key, GH_STUB_PRS=OWN_PR)

        assert result.returncode == 1
        assert "refusing to force-push over it" in result.stdout
        assert outputs_of(workspace)["outcome"] == "branch_diverged"
        tip = git(workspace.bare, "rev-parse", BRANCH).stdout.strip()
        assert tip == theirs


class TestArguments:
    def test_rejects_a_missing_body_file(self, workspace, signing_key):
        stage_change(workspace)

        result = run_open_pr(workspace, signing_key, "reports/x", "Title", "/nonexistent/body.md")

        assert result.returncode == 2
        assert "no body file at" in result.stderr
        assert not workspace.gh_log.exists()

    @pytest.mark.parametrize(
        "args",
        [
            ("reports/x",),
            ("reports/x", "Title"),
            ("reports/x", "Title", "body.md", "extra"),
        ],
        ids=["branch-only", "no-body", "too-many"],
    )
    def test_rejects_a_wrong_argument_count(self, workspace, signing_key, args):
        result = run_open_pr(workspace, signing_key, *args)

        assert result.returncode == 2

    @pytest.mark.parametrize("blank", [0, 1], ids=["empty-branch", "empty-title"])
    def test_rejects_an_empty_branch_or_title(self, workspace, signing_key, blank):
        args = ["reports/x", "Title", str(workspace.body)]
        args[blank] = ""

        result = run_open_pr(workspace, signing_key, *args)

        assert result.returncode == 2

    def test_rejects_an_option_in_place_of_the_branch(self, workspace, signing_key):
        result = run_open_pr(workspace, signing_key, "--own", "Title", str(workspace.body))

        assert result.returncode == 2

    @pytest.mark.parametrize(
        "missing", ["RUNNER_TEMP", "GITHUB_OUTPUT", "GITHUB_REPOSITORY", "GITHUB_REPOSITORY_OWNER"]
    )
    def test_refuses_when_a_required_variable_is_unset(self, workspace, signing_key, missing):
        """The old mktemp fallback could not work: the helper requires RUNNER_TEMP."""
        stage_change(workspace)

        result = run_open_pr(workspace, signing_key, **{missing: ""})

        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{missing} is not set" in result.stderr
        assert not workspace.gh_log.exists()

    def test_help_still_exits_zero(self, workspace, signing_key):
        result = run_open_pr(workspace, signing_key, "--help")

        assert result.returncode == 0
        assert "Usage: bin/ci-open-report-pr" in result.stdout
