"""End-to-end tests for the CI report-update scripts, driven against scratch repos.

These are the only coverage the signing path has: it runs once a week on a
runner and never locally. Every case here builds a throwaway repo under tmp_path
and drives bin/ci-apply-report-patch and bin/ci-land-report-patch as CI does.
"""

import base64
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
APPLY = REPO_ROOT / "bin" / "ci-apply-report-patch"
LAND = REPO_ROOT / "bin" / "ci-land-report-patch"
MAKE = REPO_ROOT / "bin" / "ci-make-report-patch"

SIGNING_WORKFLOWS = ["android-check.yml", "apple-check.yml", "windows-check.yml"]

# The scripts write .git/config and sign commits, so the developer's own global
# config must not reach them. /dev/null reads as an empty config file.
ISOLATED_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/nonexistent",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
        env=ISOLATED_GIT_ENV,
    )


def run_script(
    script: Path, repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**ISOLATED_GIT_ENV, **(env or {})},
    )


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    return path


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message)


@pytest.fixture
def seeded(tmp_path: Path) -> Path:
    """A repo holding a small Reports/ tree plus a file the patch must never touch."""
    repo = init_repo(tmp_path / "consumer")
    (repo / "Reports" / "snapshots" / "android").mkdir(parents=True)
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "Reports" / "snapshots" / "android" / "keep.json").write_text("{}\n")
    (repo / "Reports" / "snapshots" / "android" / "gone.json").write_text("{}\n")
    (repo / ".github" / "workflows" / "android-check.yml").write_text("name: weekly\n")
    commit_all(repo, "seed")
    return repo


def make_patch(seeded: Path, tmp_path: Path, build: Callable[[Path], None]) -> Path:
    """Produce a patch the way a platform check job does, from a clone of `seeded`."""
    producer = tmp_path / "producer"
    git(tmp_path, "clone", "-q", str(seeded), str(producer))
    git(producer, "config", "user.name", "Test")
    git(producer, "config", "user.email", "test@example.invalid")
    build(producer)
    git(producer, "add", "--intent-to-add", "--", ".")
    patch = tmp_path / "report-update.patch"
    patch.write_text(
        git(producer, "diff", "--no-renames", "--binary", "--full-index", "HEAD").stdout
    )
    return patch


def rewrite_keep(text: str) -> Callable[[Path], None]:
    """A build step touching one file, for a second patch onto an already-landed branch."""

    def build(producer: Path) -> None:
        (producer / "Reports" / "snapshots" / "android" / "keep.json").write_text(text)

    return build


def legitimate_change(producer: Path) -> None:
    snapshots = producer / "Reports" / "snapshots" / "android"
    (snapshots / "keep.json").write_text('{"v": 2}\n')
    (snapshots / "added.json").write_text("{}\n")
    (snapshots / "gone.json").unlink()


class TestApplyReportPatch:
    def test_accepts_a_reports_only_patch_and_stages_every_change(self, seeded, tmp_path):
        patch = make_patch(seeded, tmp_path, legitimate_change)

        result = run_script(APPLY, seeded, str(patch))

        assert result.returncode == 0, result.stdout + result.stderr
        # --no-renames: gone.json and added.json have identical content, so
        # rename detection would otherwise fold the pair into a single R100.
        staged = git(seeded, "diff", "--cached", "--no-renames", "--name-status", "HEAD").stdout
        assert staged.split() == [
            "A",
            "Reports/snapshots/android/added.json",
            "D",
            "Reports/snapshots/android/gone.json",
            "M",
            "Reports/snapshots/android/keep.json",
        ]

    def test_leaves_the_working_tree_untouched(self, seeded, tmp_path):
        """--cached, so a later `uses: ./...` still resolves the checked-out action."""
        patch = make_patch(seeded, tmp_path, legitimate_change)

        assert run_script(APPLY, seeded, str(patch)).returncode == 0

        snapshots = seeded / "Reports" / "snapshots" / "android"
        assert (snapshots / "keep.json").read_text() == "{}\n"
        assert not (snapshots / "added.json").exists()
        assert (snapshots / "gone.json").exists()

    def test_rejects_a_rename_that_carries_a_file_out_of_the_repo_root(self, seeded, tmp_path):
        """Every other check sees only a rename's destination path."""
        producer = tmp_path / "producer"
        git(tmp_path, "clone", "-q", str(seeded), str(producer))
        git(
            producer,
            "mv",
            ".github/workflows/android-check.yml",
            "Reports/snapshots/android/pwned.yml",
        )
        patch = tmp_path / "evil.patch"
        patch.write_text(
            git(producer, "diff", "--cached", "--binary", "--full-index", "HEAD").stdout
        )
        assert "rename from " in patch.read_text()

        result = run_script(APPLY, seeded, str(patch))

        assert result.returncode == 1
        assert "contains a rename" in result.stdout
        assert (seeded / ".github" / "workflows" / "android-check.yml").exists()
        assert git(seeded, "diff", "--cached", "--name-only", "HEAD").stdout == ""

    @pytest.mark.parametrize(
        "path,reason",
        [
            (".gitattributes", "repo root"),
            ("src/linkability/evil.py", "outside Reports/"),
            ("Data-Zones/zones-full.txt", "a tracked data path the flow must not write"),
            ("Reports/.gitattributes", "dot segment directly under Reports/"),
            ("Reports/snapshots/.hidden/x.json", "nested dot segment"),
        ],
    )
    def test_rejects_a_path_outside_the_allowlist(self, seeded, tmp_path, path, reason):
        def add_path(producer: Path) -> None:
            target = producer / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n")

        patch = make_patch(seeded, tmp_path, add_path)

        result = run_script(APPLY, seeded, str(patch))

        assert result.returncode == 1, f"{reason}: {result.stdout}"
        assert "disallowed path" in result.stdout

    def test_rejects_a_symlink(self, seeded, tmp_path):
        def add_symlink(producer: Path) -> None:
            (producer / "Reports" / "snapshots" / "android" / "link.json").symlink_to("/etc/passwd")

        patch = make_patch(seeded, tmp_path, add_symlink)

        result = run_script(APPLY, seeded, str(patch))

        assert result.returncode == 1
        assert "non-regular file mode" in result.stdout

    def test_rejects_an_executable_bit(self, seeded, tmp_path):
        def add_executable(producer: Path) -> None:
            script = producer / "Reports" / "snapshots" / "android" / "run.json"
            script.write_text("{}\n")
            script.chmod(0o755)

        patch = make_patch(seeded, tmp_path, add_executable)

        result = run_script(APPLY, seeded, str(patch))

        assert result.returncode == 1
        assert "non-regular file mode" in result.stdout

    def test_rejects_a_missing_or_empty_patch(self, seeded, tmp_path):
        empty = tmp_path / "empty.patch"
        empty.write_text("")

        assert "missing or empty" in run_script(APPLY, seeded, str(empty)).stdout
        assert (
            "missing or empty" in run_script(APPLY, seeded, str(tmp_path / "absent.patch")).stdout
        )

    def test_prints_usage_without_applying_anything(self, seeded):
        result = run_script(APPLY, seeded)

        assert result.returncode == 0
        assert "Usage: bin/ci-apply-report-patch" in result.stdout
        assert git(seeded, "diff", "--cached", "--name-only", "HEAD").stdout == ""


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


@pytest.fixture
def pushable(tmp_path: Path, seeded: Path) -> tuple[Path, Path]:
    """A consumer repo whose origin is a local bare repo it can really push to."""
    bare = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(seeded), str(bare))
    return seeded, bare


GIT_STUB = """#!/usr/bin/env bash
# Records what the real git would have received, then stops the script.
{
  printf 'ARGV\\t%s\\n' "$*"
  printf 'COUNT\\t%s\\n' "${GIT_CONFIG_COUNT:-}"
  printf 'KEY\\t%s\\n' "${GIT_CONFIG_KEY_0:-}"
  printf 'VALUE\\t%s\\n' "${GIT_CONFIG_VALUE_0:-}"
} >> "$GIT_STUB_LOG"
exit 1
"""


def land_env(bare: Path, expected_head: str, key: str, **overrides: str) -> dict[str, str]:
    env = {
        "RUNNER_TEMP": str(bare.parent / "runner-temp"),
        "PUSH_REMOTE": str(bare),
        "EXPECTED_HEAD": expected_head,
        "CI_SSH_SIGNING_KEY": key,
        "CI_COMMITTER_NAME": "linkability bot",
        "CI_COMMITTER_EMAIL": "bot@example.invalid",
    }
    env.update(overrides)
    Path(env["RUNNER_TEMP"]).mkdir(parents=True, exist_ok=True)
    return env


def rebase(repo, bare, key, guards=("Reports/",), **env_overrides):
    args = [a for g in guards for a in ("--guard", g)]
    return run_script(
        LAND,
        repo,
        "rebase",
        *args,
        env=land_env(bare, git(repo, "rev-parse", "HEAD").stdout.strip(), key, **env_overrides),
    )


def land(
    repo,
    bare,
    patch,
    key,
    subject="Update Android platform reports 2026-09-10",
    branch="reports/x",
    guards=("Reports/",),
    before_commit=None,
    **env_overrides,
):
    """Drive the three CI steps in order: rebase, validate, sign and push."""
    env = land_env(bare, git(repo, "rev-parse", "HEAD").stdout.strip(), key, **env_overrides)
    guard_args = [a for g in guards for a in ("--guard", g)]
    staged = run_script(LAND, repo, "rebase", *guard_args, env=env)
    if staged.returncode != 0:
        return staged
    applied = run_script(APPLY, repo, str(patch), env=env)
    if applied.returncode != 0:
        return applied
    if before_commit is not None:
        before_commit()
    return run_script(LAND, repo, "commit", "--subject", subject, *guard_args, branch, env=env)


def git_stub(tmp_path: Path) -> tuple[Path, Path]:
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "git"
    stub.write_text(GIT_STUB)
    stub.chmod(0o755)
    return stub_dir, tmp_path / "git-stub.log"


# The exit-1 stub stops at the first git call, which carries no remote in the
# commit phase. This one records every call, so the push's argv is asserted too.
RECORDING_GIT_STUB = """#!/usr/bin/env bash
{
  printf 'ARGV\\t%s\\n' "$*"
  printf 'COUNT\\t%s\\n' "${GIT_CONFIG_COUNT:-}"
  printf 'KEY\\t%s\\n' "${GIT_CONFIG_KEY_0:-}"
  printf 'VALUE\\t%s\\n' "${GIT_CONFIG_VALUE_0:-}"
} >> "$GIT_STUB_LOG"
for a in "$@"; do
  if [ "$a" = "push" ]; then exit 0; fi
done
exec REAL_GIT "$@"
"""


def recording_git_stub(tmp_path: Path) -> tuple[Path, Path]:
    real_git = shutil.which("git")
    assert real_git is not None
    stub_dir = tmp_path / "recording-bin"
    stub_dir.mkdir()
    stub = stub_dir / "git"
    stub.write_text(RECORDING_GIT_STUB.replace("REAL_GIT", real_git))
    stub.chmod(0o755)
    return stub_dir, tmp_path / "recording.log"


def recorded_argv(log: Path) -> list[str]:
    return [
        line.split("\t", 1)[1] for line in log.read_text().splitlines() if line.startswith("ARGV\t")
    ]


def _stub_readback(log: Path) -> dict[str, str]:
    return dict(line.split("\t", 1) for line in log.read_text().splitlines() if "\t" in line)


def stubbed_rebase(repo, bare, key, stub_dir, log, **env_overrides) -> dict[str, str]:
    run_script(
        LAND,
        repo,
        "rebase",
        "--guard",
        "Reports/",
        env=land_env(
            bare,
            "0" * 40,
            key,
            GIT_STUB_LOG=str(log),
            PATH=f"{stub_dir}:{ISOLATED_GIT_ENV['PATH']}",
            **env_overrides,
        ),
    )
    return _stub_readback(log)


def stubbed_land(repo, bare, patch, key, stub_dir, log, **env_overrides) -> dict[str, str]:
    run_script(
        LAND,
        repo,
        "commit",
        "--guard",
        "Reports/",
        "--subject",
        "s",
        "main",
        env=land_env(
            bare,
            "0" * 40,
            key,
            GIT_STUB_LOG=str(log),
            PATH=f"{stub_dir}:{ISOLATED_GIT_ENV['PATH']}",
            **env_overrides,
        ),
    )
    return _stub_readback(log)


class TestLandReportPatch:
    def test_applies_signs_and_pushes(self, pushable, tmp_path, signing_key):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)

        result = land(repo, bare, patch, signing_key)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "gpgsig " in git(repo, "cat-file", "commit", "HEAD").stdout
        assert git(bare, "rev-parse", "reports/x").stdout == git(repo, "rev-parse", "HEAD").stdout

    def test_message_lists_changed_files_without_their_prefix(
        self, pushable, tmp_path, signing_key
    ):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)

        land(repo, bare, patch, signing_key)

        message = git(repo, "log", "-1", "--pretty=%B").stdout
        assert message.startswith("Update Android platform reports 2026-09-10\n\nChanged files:\n")
        assert "- snapshots/android/added.json\n" in message
        assert "Reports/" not in message

    def test_the_subject_comes_from_the_caller(self, pushable, tmp_path, signing_key):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)

        land(repo, bare, patch, signing_key, subject="Update Apple platform reports 2026-09-10")

        assert git(repo, "log", "-1", "--pretty=%s").stdout.strip() == (
            "Update Apple platform reports 2026-09-10"
        )

    def test_removes_the_signing_key_on_success(self, pushable, tmp_path, signing_key):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        runner_temp = Path(land_env(bare, "x", signing_key)["RUNNER_TEMP"])

        assert land(repo, bare, patch, signing_key).returncode == 0

        assert not (runner_temp / "linkability-ci-signing").exists()

    def test_removes_the_signing_key_when_signing_fails(self, pushable, tmp_path, signing_key):
        """The trap must fire on the failure path too, not only on success."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        runner_temp = Path(land_env(bare, "x", signing_key)["RUNNER_TEMP"])

        result = land(repo, bare, patch, "not-a-key\n")

        assert result.returncode != 0
        assert not (runner_temp / "linkability-ci-signing").exists()

    @pytest.mark.parametrize(
        "missing",
        [
            "PUSH_REMOTE",
            "RUNNER_TEMP",
            "CI_SSH_SIGNING_KEY",
            "CI_COMMITTER_NAME",
            "CI_COMMITTER_EMAIL",
        ],
    )
    def test_refuses_when_a_required_variable_is_unset(
        self, pushable, tmp_path, signing_key, missing
    ):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        before = git(bare, "rev-parse", "main").stdout.strip()

        result = land(repo, bare, patch, signing_key, **{missing: ""})

        assert result.returncode == 1
        assert f"{missing} is not configured" in result.stdout
        assert git(bare, "rev-parse", "main").stdout.strip() == before

    @pytest.mark.parametrize(
        "args,expected",
        [
            (("commit", "--guard", "Reports/", "reports/x"), "needs --subject and a branch"),
            (("commit", "--subject", "s", "reports/x"), "at least one --guard is required"),
            (("commit", "--guard", "Reports/", "--subject", "s"), "needs --subject and a branch"),
            (("rebase", "--guard", "Reports/", "reports/x"), "takes no branch argument"),
            (("rebase",), "at least one --guard is required"),
            (("sync", "--guard", "Reports/"), "unknown phase"),
            (("commit", "--force", "reports/x"), "unknown option"),
            ((), "a phase is required"),
        ],
        ids=[
            "no-subject",
            "no-guard",
            "no-branch",
            "rebase-with-branch",
            "rebase-no-guard",
            "phase-not-ported",
            "unknown-option",
            "missing-phase",
        ],
    )
    def test_rejects_a_bad_invocation(self, pushable, signing_key, args, expected):
        """An unexpanded variable in CI must not skip the step silently."""
        repo, bare = pushable

        result = run_script(LAND, repo, *args, env=land_env(bare, "x", signing_key))

        assert result.returncode == 2, result.stdout + result.stderr
        assert expected in result.stderr

    def test_help_still_exits_zero(self, pushable, signing_key):
        repo, bare = pushable

        result = run_script(LAND, repo, "--help", env=land_env(bare, "x", signing_key))

        assert result.returncode == 0
        assert "Usage: bin/ci-land-report-patch" in result.stdout

    def test_rebase_requires_expected_head(self, pushable, signing_key):
        repo, bare = pushable
        env = land_env(bare, "x", signing_key)
        env["EXPECTED_HEAD"] = ""

        result = run_script(LAND, repo, "rebase", "--guard", "Reports/", env=env)

        assert result.returncode == 1
        assert "EXPECTED_HEAD is not configured" in result.stdout

    def test_refuses_to_commit_when_nothing_is_staged(self, pushable, signing_key):
        repo, bare = pushable

        result = run_script(
            LAND,
            repo,
            "commit",
            "--guard",
            "Reports/",
            "--subject",
            "s",
            "reports/x",
            env=land_env(bare, "x", signing_key),
        )

        assert result.returncode == 1
        assert "refusing to create an empty commit" in result.stdout

    def test_repository_hooks_do_not_run(self, pushable, tmp_path, signing_key):
        """A hook in the checked-out tree is not the CI job's to obey, and a
        pre-commit hook would otherwise see the untrusted patch."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        for name in ("pre-commit", "pre-push"):
            (hooks / name).write_text("#!/usr/bin/env bash\nexit 1\n")
            (hooks / name).chmod(0o755)
        git(repo, "config", "core.hooksPath", str(hooks))

        assert land(repo, bare, patch, signing_key).returncode == 0

    def test_every_guarded_path_is_enforced_not_just_the_first(
        self, pushable, tmp_path, signing_key
    ):
        """--guard is repeatable; a guard that only reads the first is inert."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        clone = tmp_path / "mover"
        git(tmp_path, "clone", "-q", str(bare), str(clone))
        git(clone, "config", "user.name", "Other")
        git(clone, "config", "user.email", "other@example.invalid")
        (clone / "Reports" / "snapshots" / "apple").mkdir(parents=True, exist_ok=True)
        (clone / "Reports" / "snapshots" / "apple" / "14.json").write_text('{"moved": 1}\n')
        commit_all(clone, "move the second guarded path only")
        git(clone, "push", "-q", "origin", "main")

        result = land(
            repo,
            bare,
            patch,
            signing_key,
            guards=("Reports/snapshots/android", "Reports/snapshots/apple"),
        )

        assert result.returncode == 1
        assert "built against stale inputs" in result.stdout


class TestTimeoutBudgets:
    """A job cap below its step sum cancels, and a cancelled job fires no alert."""

    def test_every_job_cap_exceeds_the_sum_of_its_step_caps(self):
        checked = 0
        for workflow in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
            text = workflow.read_text()
            for chunk in re.split(r"\n  (?=[a-z][\w-]*:\n)", text):
                name = chunk.split(":", 1)[0].strip()
                job_cap = re.search(r"^    timeout-minutes: (\d+)", chunk, re.MULTILINE)
                if not job_cap:
                    continue
                cap = int(job_cap.group(1))
                steps = sum(
                    int(m)
                    for m in re.findall(r"^      +timeout-minutes: (\d+)", chunk, re.MULTILINE)
                )
                checked += 1
                assert steps < cap, f"{workflow.name}:{name} steps sum to {steps}, cap is {cap}"
        assert checked >= 8, f"only {checked} jobs inspected; the guard is vacuous"


class TestOwnership:
    def test_refuses_a_branch_last_committed_by_someone_else(self, pushable, tmp_path, signing_key):
        """A report branch is machine-owned; a reviewer's commit stops the re-run."""
        repo, bare = pushable
        (tmp_path / "own1").mkdir()
        first = make_patch(repo, tmp_path / "own1", legitimate_change)
        assert (land(repo, bare, first, signing_key, branch="reports/x")).returncode == 0

        human = tmp_path / "human"
        git(tmp_path, "clone", "-q", str(bare), str(human))
        git(human, "config", "user.name", "Reviewer")
        git(human, "config", "user.email", "reviewer@example.invalid")
        git(human, "checkout", "-q", "reports/x")
        (human / "Reports" / "snapshots" / "android" / "keep.json").write_text('{"human": 1}\n')
        commit_all(human, "reviewer edit")
        git(human, "push", "-q", "origin", "reports/x")
        theirs = git(human, "rev-parse", "HEAD").stdout.strip()

        remote_main = git(bare, "rev-parse", "main").stdout.strip()
        git(repo, "checkout", "-q", "--force", "--detach", remote_main)
        (tmp_path / "own2").mkdir()
        second = make_patch(
            repo,
            tmp_path / "own2",
            rewrite_keep('{"machine": 1}\n'),
        )
        outputs = tmp_path / "own-outputs"

        result = land(
            repo,
            bare,
            second,
            signing_key,
            branch="reports/x",
            GITHUB_OUTPUT=str(outputs),
        )

        assert result.returncode == 1
        assert "refusing to force-push over it" in result.stdout
        assert "outcome=branch_diverged" in outputs.read_text()
        assert git(bare, "rev-parse", "reports/x").stdout.strip() == theirs


class TestLease:
    def test_a_fresh_branch_is_created_under_an_empty_lease(self, pushable, tmp_path, signing_key):
        """Every scheduled run names a new branch, so this is the common path."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)

        result = land(repo, bare, patch, signing_key, branch="reports/android-2026-09-10-7")

        assert result.returncode == 0, result.stdout + result.stderr
        assert (
            git(bare, "rev-parse", "reports/android-2026-09-10-7").stdout
            == git(repo, "rev-parse", "HEAD").stdout
        )

    def test_the_push_carries_a_lease_naming_the_observed_sha(
        self, pushable, tmp_path, signing_key
    ):
        """A bare --force would satisfy every other assertion in this file."""
        repo, bare = pushable

        # First land creates the branch, so its tip is committed by the CI
        # identity and the ownership check passes on the second.
        (tmp_path / "first").mkdir()
        first = make_patch(repo, tmp_path / "first", legitimate_change)
        assert (land(repo, bare, first, signing_key, branch="reports/x")).returncode == 0
        observed = git(bare, "rev-parse", "reports/x").stdout.strip()

        remote_main = git(bare, "rev-parse", "main").stdout.strip()
        git(repo, "checkout", "-q", "--force", "--detach", remote_main)
        (tmp_path / "second").mkdir()
        # A fresh change: the first land already applied legitimate_change's
        # deletion, so replaying it against this clone would fail.
        second = make_patch(
            repo,
            tmp_path / "second",
            rewrite_keep('{"second": 1}\n'),
        )

        real_git = shutil.which("git")
        stub_dir = tmp_path / "push-stub"
        stub_dir.mkdir()
        log = tmp_path / "push.log"
        stub = stub_dir / "git"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            'for a in "$@"; do\n'
            '  if [ "$a" = "push" ]; then\n'
            '    printf \'PUSH\\t%s\\n\' "$*" >> "$GIT_STUB_LOG"\n'
            "    exit 0\n"
            "  fi\n"
            "done\n"
            f'exec {real_git} "$@"\n'
        )
        stub.chmod(0o755)

        result = land(
            repo,
            bare,
            second,
            signing_key,
            branch="reports/x",
            GIT_STUB_LOG=str(log),
            PATH=f"{stub_dir}:{ISOLATED_GIT_ENV['PATH']}",
        )

        assert log.exists(), result.stdout + result.stderr
        pushes = [ln for ln in log.read_text().splitlines() if ln.startswith("PUSH\t")]
        assert pushes, log.read_text()
        assert f"--force-with-lease=refs/heads/reports/x:{observed}" in pushes[-1], pushes[-1]


class TestCredentialBoundary:
    """The boundary is the workflow step, not the process. Why: Docs/ci-signing.md"""

    def _steps_before_signing(self, workflow: str) -> str:
        text = (REPO_ROOT / ".github" / "workflows" / workflow).read_text()
        marker = "CI_SSH_SIGNING_KEY"
        assert marker in text, workflow
        return text[: text.index(marker)]

    @pytest.mark.parametrize("workflow", SIGNING_WORKFLOWS)
    def test_the_validator_step_runs_before_any_signing_key(self, workflow):
        before = self._steps_before_signing(workflow)

        # A run: line, not a substring: a commented-out or merely mentioned
        # validator would satisfy `in` while validating nothing.
        assert re.search(r"^\s+run: bin/ci-apply-report-patch\b", before, re.MULTILINE), (
            f"{workflow} validates after the signing key is in scope"
        )
        assert re.search(r"^\s+bin/ci-land-report-patch rebase\b", before, re.MULTILINE), workflow

    @pytest.mark.parametrize("workflow", SIGNING_WORKFLOWS)
    def test_no_job_level_signing_key(self, workflow):
        """A job-level env would put the key in every step's process."""
        text = (REPO_ROOT / ".github" / "workflows" / workflow).read_text()

        for line in text.splitlines():
            if "CI_SSH_SIGNING_KEY" in line:
                assert line.startswith("          "), (
                    f"{workflow}: signing key is not scoped to a step: {line!r}"
                )

    @pytest.mark.parametrize("workflow", SIGNING_WORKFLOWS)
    def test_only_the_signing_job_can_write_contents(self, workflow):
        """The jobs that touch fetched content must not be able to push."""
        data = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / workflow).read_text())

        assert data.get("permissions") == {}, f"{workflow} grants a default token scope"
        writers = []
        holders = []
        jobs = data.get("jobs") or {}
        for name, job in jobs.items():
            if (job.get("permissions") or {}).get("contents") == "write":
                writers.append(name)
            # The key is step-scoped, so the whole job has to be searched for it.
            for step in job.get("steps") or []:
                if "CI_SSH_SIGNING_KEY" in (step.get("env") or {}):
                    holders.append(name)
                    break
        assert len(jobs) >= 2, f"{workflow}: only {len(jobs)} job(s) parsed; the guard is vacuous"
        assert writers == ["sign"], f"{workflow}: contents: write held by {writers}"
        assert holders == ["sign"], f"{workflow}: signing key held by {holders}"

    @pytest.mark.parametrize("workflow", SIGNING_WORKFLOWS)
    def test_no_job_persists_checkout_credentials(self, workflow):
        """actions/checkout leaves a push token in .git/config unless told not to."""
        text = (REPO_ROOT / ".github" / "workflows" / workflow).read_text()

        assert text.count("uses: actions/checkout@") == text.count("persist-credentials: false"), (
            f"{workflow} has a checkout that persists credentials"
        )

    def test_rebase_runs_without_any_signing_credentials(self, pushable, tmp_path, signing_key):
        repo, bare = pushable
        env = land_env(bare, git(repo, "rev-parse", "HEAD").stdout.strip(), signing_key)
        for name in ("CI_SSH_SIGNING_KEY", "CI_COMMITTER_NAME", "CI_COMMITTER_EMAIL"):
            env.pop(name)

        result = run_script(LAND, repo, "rebase", "--guard", "Reports/", env=env)

        assert result.returncode == 0, result.stdout + result.stderr


class TestWorkflowInvariants:
    """Workflow-level guards, asserted against parsed YAML. Why: Docs/ci-signing.md"""

    def workflows(self) -> list[Path]:
        found = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        assert len(found) >= 4, f"only {found} workflows found; the guard is vacuous"
        return found

    def load(self, path: Path) -> dict[Any, Any]:
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict), f"{path.name} did not parse to a mapping"
        return data

    def triggers(self, data: dict[Any, Any]) -> dict[str, Any]:
        """PyYAML is YAML 1.1, where an unquoted `on:` key parses as the boolean True."""
        on = data.get("on", data.get(True))
        assert isinstance(on, dict), "workflow has no parsed trigger mapping"
        return on

    def runner_labels(self, job: dict[str, Any]) -> list[str]:
        """Resolve `runs-on: ${{ matrix.os }}` through the job's own matrix."""
        runs_on = job.get("runs-on")
        labels = runs_on if isinstance(runs_on, list) else [runs_on]
        resolved: list[str] = []
        for label in labels:
            if not isinstance(label, str):
                continue
            m = re.fullmatch(r"\$\{\{\s*matrix\.(\w+)\s*\}\}", label.strip())
            if not m:
                resolved.append(label)
                continue
            axis = m.group(1)
            matrix = job.get("strategy", {}).get("matrix", {}) or {}
            resolved.extend(str(v) for v in matrix.get(axis, []))
            # include: entries schedule extra jobs with their own labels.
            for entry in matrix.get("include", []) or []:
                if isinstance(entry, dict) and axis in entry:
                    resolved.append(str(entry[axis]))
        return resolved

    def steps(self, data: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
        for job_name, job in (data.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                yield job_name, step

    def test_no_workflow_runs_on_a_floating_runner_image(self):
        """A -latest runner rolls to a new OS with no diff to review."""
        offenders = []
        checked = 0
        for w in self.workflows():
            for job_name, job in (self.load(w).get("jobs") or {}).items():
                labels = self.runner_labels(job)
                assert labels, f"{w.name}:{job_name} has no resolvable runs-on"
                checked += len(labels)
                offenders += [f"{w.name}:{job_name} {x}" for x in labels if x.endswith("-latest")]
        assert checked >= 8, f"only {checked} runner labels resolved; the guard is vacuous"
        assert offenders == [], f"floating runner images: {offenders}"

    def test_third_party_actions_are_pinned_to_a_sha(self):
        """First-party actions may float; everything else is a supply-chain decision."""
        first_party = ("actions/", "github/", "astral-sh/")
        floating = []
        checked = 0
        for w in self.workflows():
            for job_name, step in self.steps(self.load(w)):
                uses = step.get("uses")
                if not isinstance(uses, str):
                    continue
                checked += 1
                repo, _, ref = uses.partition("@")
                if repo.startswith(first_party):
                    continue
                if not re.fullmatch(r"[0-9a-f]{40}", ref):
                    floating.append(f"{w.name}:{job_name} {uses}")
        assert checked >= 8, f"only {checked} `uses:` steps parsed; the guard is vacuous"
        assert floating == [], f"third-party actions not SHA-pinned: {floating}"

    def test_every_workflow_declares_its_token_scope(self):
        """The default GITHUB_TOKEN scope depends on repo and org settings."""
        missing = [w.name for w in self.workflows() if "permissions" not in self.load(w)]
        assert missing == [], f"workflows with no permissions block: {missing}"

    def test_the_test_workflow_triggers_on_the_files_its_gate_now_covers(self):
        """bin/lint runs actionlint over every workflow, so every workflow must run it."""
        on = self.triggers(self.load(REPO_ROOT / ".github" / "workflows" / "test.yml"))

        for event in ("push", "pull_request"):
            paths = (on.get(event) or {}).get("paths") or []
            negations = [p for p in paths if str(p).startswith("!")]
            assert negations == [], (
                f"test.yml {event} has exclusion patterns {negations}; "
                "membership no longer proves the gate runs"
            )
            for needed in (".github/workflows/**", "mise.toml"):
                assert needed in paths, f"test.yml {event} does not trigger on {needed}"


class TestMakeReportPatch:
    def test_reports_no_change_and_writes_nothing(self, seeded, tmp_path):
        env = {"RUNNER_TEMP": str(tmp_path / "rt"), "GITHUB_OUTPUT": str(tmp_path / "out")}
        Path(env["RUNNER_TEMP"]).mkdir(parents=True, exist_ok=True)

        result = run_script(MAKE, seeded, "Reports/", env=env)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "changed=false" in Path(env["GITHUB_OUTPUT"]).read_text()
        assert not (Path(env["RUNNER_TEMP"]) / "report-update.patch").exists()

    def test_emits_a_patch_and_a_run_scoped_artifact_name(self, seeded, tmp_path):
        (seeded / "Reports" / "snapshots" / "android" / "new.json").write_text("{}\n")
        env = {
            "RUNNER_TEMP": str(tmp_path / "rt"),
            "GITHUB_OUTPUT": str(tmp_path / "out"),
            "GITHUB_RUN_ID": "77",
            "GITHUB_RUN_ATTEMPT": "2",
        }
        Path(env["RUNNER_TEMP"]).mkdir(parents=True, exist_ok=True)

        result = run_script(MAKE, seeded, "Reports/", env=env)

        assert result.returncode == 0, result.stdout + result.stderr
        out = Path(env["GITHUB_OUTPUT"]).read_text()
        assert "changed=true" in out
        assert "artifact=report-update-77-2" in out
        assert (Path(env["RUNNER_TEMP"]) / "report-update.patch").stat().st_size > 0

    def test_ignores_changes_outside_the_named_paths(self, seeded, tmp_path):
        """The zone files are refreshed every run and are not this flow's to commit."""
        (seeded / "Data-Zones").mkdir(parents=True, exist_ok=True)
        (seeded / "Data-Zones" / "zones-full.txt").write_text("com\n")
        env = {"RUNNER_TEMP": str(tmp_path / "rt"), "GITHUB_OUTPUT": str(tmp_path / "out")}
        Path(env["RUNNER_TEMP"]).mkdir(parents=True, exist_ok=True)

        result = run_script(MAKE, seeded, "Reports/", env=env)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "changed=false" in Path(env["GITHUB_OUTPUT"]).read_text()

    def test_requires_a_path(self, seeded, tmp_path):
        env = {"RUNNER_TEMP": str(tmp_path / "rt")}
        Path(env["RUNNER_TEMP"]).mkdir(parents=True, exist_ok=True)

        result = run_script(MAKE, seeded, env=env)

        assert result.returncode == 2
        assert "at least one path is required" in result.stderr


class TestRebaseGuard:
    """A patch is built minutes before it lands, and main moves in between."""

    def advance(self, pushable, tmp_path, path: str, text: str) -> str:
        _, bare = pushable
        clone = tmp_path / "other"
        git(tmp_path, "clone", "-q", str(bare), str(clone))
        git(clone, "config", "user.name", "Other")
        git(clone, "config", "user.email", "other@example.invalid")
        target = clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        commit_all(clone, "concurrent change")
        git(clone, "push", "-q", "origin", "main")
        return git(clone, "rev-parse", "HEAD").stdout.strip()

    def test_an_unrelated_commit_rebases_instead_of_failing(self, pushable, tmp_path, signing_key):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        tip = self.advance(pushable, tmp_path, "README.md", "docs\n")

        result = land(repo, bare, patch, signing_key)

        assert result.returncode == 0, result.stdout + result.stderr
        assert git(repo, "rev-parse", "HEAD^").stdout.strip() == tip
        assert (repo / "README.md").read_text() == "docs\n"

    def test_refuses_when_a_guarded_path_moved(self, pushable, tmp_path, signing_key):
        """The moved file is one the patch never touches: the guard covers the
        flow's generation inputs, not just the paths it writes."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        tip = self.advance(pushable, tmp_path, "Reports/summary.csv", "platform,linked\n")

        result = land(repo, bare, patch, signing_key)

        assert result.returncode == 1
        assert "built against stale inputs" in result.stdout
        assert git(bare, "rev-parse", "main").stdout.strip() == tip

    def test_refuses_when_ci_code_moved(self, pushable, tmp_path, signing_key):
        """Checking out over bin/ swaps the script bash is still reading."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        tip = self.advance(pushable, tmp_path, "bin/ci-land-report-patch", "#!/bin/sh\n")

        result = land(repo, bare, patch, signing_key)

        assert result.returncode == 1
        assert "changed CI code during the run" in result.stdout
        assert git(bare, "rev-parse", "main").stdout.strip() == tip

    def test_refuses_when_a_workflow_moved(self, pushable, tmp_path, signing_key):
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        self.advance(pushable, tmp_path, ".github/workflows/android-check.yml", "name: x\n")

        result = land(repo, bare, patch, signing_key)

        assert result.returncode == 1
        assert "changed CI code during the run" in result.stdout


class TestShallowClone:
    """actions/checkout defaults to fetch-depth: 1, and the guard diffs two shallow commits."""

    def shallow(self, bare: Path, tmp_path: Path) -> Path:
        clone = tmp_path / "shallow"
        git(tmp_path, "clone", "-q", "--depth", "1", f"file://{bare}", str(clone))
        git(clone, "config", "user.name", "Test")
        git(clone, "config", "user.email", "test@example.invalid")
        assert (clone / ".git" / "shallow").exists(), "clone is not shallow; the case is vacuous"
        return clone

    def test_rebase_succeeds_in_a_shallow_clone(self, pushable, tmp_path, signing_key):
        _, bare = pushable
        clone = self.shallow(bare, tmp_path)

        result = rebase(clone, bare, signing_key)

        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_guarded_path_moving_is_still_caught_when_shallow(
        self, pushable, tmp_path, signing_key
    ):
        """The refusal must survive the shallow fetch, or the guard is inert in CI."""
        _, bare = pushable
        clone = self.shallow(bare, tmp_path)
        expected_head = git(clone, "rev-parse", "HEAD").stdout.strip()

        mover = tmp_path / "mover"
        git(tmp_path, "clone", "-q", str(bare), str(mover))
        git(mover, "config", "user.name", "Other")
        git(mover, "config", "user.email", "other@example.invalid")
        (mover / "Reports" / "summary.csv").write_text("platform,linked\n")
        commit_all(mover, "concurrent report change")
        git(mover, "push", "-q", "origin", "main")

        result = run_script(
            LAND,
            clone,
            "rebase",
            "--guard",
            "Reports/",
            env=land_env(bare, expected_head, signing_key),
        )

        assert result.returncode == 1, result.stdout + result.stderr
        assert "built against stale inputs" in result.stdout

    def test_an_unrelated_commit_still_rebases_when_shallow(self, pushable, tmp_path, signing_key):
        _, bare = pushable
        clone = self.shallow(bare, tmp_path)
        expected_head = git(clone, "rev-parse", "HEAD").stdout.strip()

        mover = tmp_path / "unrelated"
        git(tmp_path, "clone", "-q", str(bare), str(mover))
        git(mover, "config", "user.name", "Other")
        git(mover, "config", "user.email", "other@example.invalid")
        (mover / "README.md").write_text("docs\n")
        commit_all(mover, "unrelated change")
        git(mover, "push", "-q", "origin", "main")
        tip = git(mover, "rev-parse", "HEAD").stdout.strip()

        result = run_script(
            LAND,
            clone,
            "rebase",
            "--guard",
            "Reports/",
            env=land_env(bare, expected_head, signing_key),
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert git(clone, "rev-parse", "HEAD").stdout.strip() == tip


class TestCredentialHandling:
    def test_token_never_reaches_git_argv(self, pushable, tmp_path, signing_key):
        """A credential in the remote URL would be world readable via /proc."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        stub_dir, log = recording_git_stub(tmp_path)
        token = "ghs_TOKEN_MUST_NOT_APPEAR_IN_ARGV"

        land(
            repo,
            bare,
            patch,
            signing_key,
            GH_TOKEN=token,
            GIT_STUB_LOG=str(log),
            PATH=f"{stub_dir}:{ISOLATED_GIT_ENV['PATH']}",
        )

        calls = recorded_argv(log)
        # Without this the assertions below pass on a run that never got near a
        # remote, which is how the first version of this test went inert.
        assert any(c.startswith("push ") or " push " in c for c in calls), calls
        assert any("fetch" in c for c in calls), calls
        for call in calls:
            assert token not in call, call
            assert "x-access-token" not in call, call

    def test_basic_credential_has_no_trailing_newline(self, pushable, tmp_path, signing_key):
        """`base64 <<< ...` appends a newline, which makes the push 401."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        stub_dir, log = git_stub(tmp_path)
        token = "ghs_EXACTLY_THIS"

        seen = stubbed_land(repo, bare, patch, signing_key, stub_dir, log, GH_TOKEN=token)

        assert seen["COUNT"] == "1"
        # An unscoped key authenticates nothing and the push 401s.
        assert seen["KEY"] == f"http.{bare}.extraheader"
        scheme, encoded = seen["VALUE"].rsplit(" ", 1)
        assert scheme == "Authorization: Basic"
        assert base64.b64decode(encoded) == f"x-access-token:{token}".encode()

    def test_the_rebase_phase_keeps_the_token_out_of_argv(self, pushable, tmp_path, signing_key):
        """rebase fetches too, so it configures credentials the same way."""
        repo, bare = pushable
        stub_dir, log = git_stub(tmp_path)
        token = "ghs_TOKEN_MUST_NOT_APPEAR_IN_ARGV"

        seen = stubbed_rebase(repo, bare, signing_key, stub_dir, log, GH_TOKEN=token)

        assert token not in seen["ARGV"], seen["ARGV"]
        assert "x-access-token" not in seen["ARGV"]
        assert seen["COUNT"] == "1"
        assert seen["KEY"] == f"http.{bare}.extraheader"
        scheme, encoded = seen["VALUE"].rsplit(" ", 1)
        assert scheme == "Authorization: Basic"
        assert base64.b64decode(encoded) == f"x-access-token:{token}".encode()

    def test_no_auth_config_when_the_token_is_absent(self, pushable, tmp_path, signing_key):
        """The bare-remote path must not inject an empty credential."""
        repo, bare = pushable
        patch = make_patch(repo, tmp_path, legitimate_change)
        stub_dir, log = git_stub(tmp_path)

        seen = stubbed_land(repo, bare, patch, signing_key, stub_dir, log)

        assert seen["COUNT"] == ""
        assert seen["VALUE"] == ""


def test_no_bin_script_needs_bash_4_or_gnu_coreutils():
    """test.yml runs bin/test on macOS, whose bash is 3.2 and whose base64 is BSD."""
    offenders = []
    for script in sorted((REPO_ROOT / "bin").rglob("*")):
        if not script.is_file():
            continue
        text = script.read_text(errors="replace")
        if not text.startswith("#!"):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for construct in ("mapfile ", "readarray ", "base64 -w", "stat -c"):
                if construct in line:
                    offenders.append(f"{script.relative_to(REPO_ROOT)}:{i} {construct.strip()}")
    assert offenders == [], f"not portable to the macOS runner: {offenders}"


def test_no_ci_script_is_excluded_from_a_fresh_clone():
    """A gitignored helper passes lint and tests locally, then breaks every run."""
    scripts = sorted(p for p in (REPO_ROOT / "bin").rglob("ci-*") if p.is_file())
    assert len(scripts) >= 4, f"expected the bin/ci-* family, found {scripts}"

    # --no-index, or a rule stops being reported the moment the file is tracked,
    # and this guard passes for the rest of the repository's life.
    result = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "check-ignore",
            "--no-index",
            "--verbose",
            "--non-matching",
            *(str(s) for s in scripts),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    ignored = [line for line in result.stdout.splitlines() if not line.startswith("::\t")]
    assert not ignored, f"gitignored CI scripts: {ignored}"
