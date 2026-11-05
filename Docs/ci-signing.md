# CI commit signing

The `Signed commits` ruleset on `main` (enabled 2026-09-03) requires verified signatures and
has no bypass actors, so the scheduled platform checks can no longer commit as
`github-actions[bot]`. The three check workflows split report generation from commit signing.

This mirrors the layer in [case/iana-data](https://github.com/case/iana-data), whose
`docs/memory/log/2026-09-07-ci-signing.md` and `docs/memory/log/2026-09-09-ci-signing-shared.md`
carry the longer rationale.

## A PR branch is not exempt

The ruleset targets the default branch, and these workflows push to `reports/<platform>`
rather than to `main`, which looks exempt. It is not. GitHub evaluates a pull request by building a
test merge commit and checking **the commits it introduces, including those on the head branch**, so
an unsigned commit on a report branch blocks the squash merge. iana-data learned this the expensive
way: PR #114 went `mergeStateStatus: BLOCKED` after the drift flow was scoped out on exactly that
reasoning. Source:
[`required-signed-commits.md`](https://github.com/github/docs/blob/main/data/reusables/repositories/required-signed-commits.md).

## The jobs

| Job                | Holds                                    | Does                                                                                |
| ------------------ | ---------------------------------------- | ----------------------------------------------------------------------------------- |
| `check`            | `contents: read`                         | Downloads zone data, runs the platform check.                                       |
| `publish`          | `contents: read`                         | Merges matrix snapshots, rebuilds, emits the patch. Apple and Windows only.         |
| `sign`             | `contents: write` + the key              | Rebases, validates, signs, pushes, opens the PR.                                    |
| `close-superseded` | `contents: read`, `pull-requests: write` | Android and Windows only. Runs when nothing changed; closes a superseded report PR. |

Android has no matrix, so its `check` job is also the producer.

The producer uploads a patch (`git diff --no-renames --binary --full-index HEAD -- Reports/`) as a
one-day artifact. The artifact name is a job output rather than being rebuilt downstream:
`run_attempt` increments per run, so a reconstructed name misses the producer's artifact after a
failed-jobs re-run.

## The scripts

| Script                      | Role                                                                         |
| --------------------------- | ---------------------------------------------------------------------------- |
| `bin/ci-make-report-patch`  | Producer. Emits `changed`, plus a patch and artifact name when there is one. |
| `bin/ci-apply-report-patch` | Validates an untrusted patch and stages it. Holds no credentials.            |
| `bin/ci-land-report-patch`  | Consumer, in two phases: `rebase` before the key exists, `commit` after.     |
| `bin/ci-open-report-pr`     | Lands the patch, then talks to `gh`.                                         |
| `bin/ci-close-report-pr`    | Closes a superseded report PR. Holds a token, never the key.                 |

## The credential boundary is a workflow step, not a process

`bin/ci-apply-report-patch` promises to hold no credentials, and that is structurally true only
because the pipeline is separate Actions steps. Consolidating it into one process would break it,
and calling the validator through `env -u` is cosmetic: the child reads the key straight out of the
parent's `/proc/<pid>/environ`, which records the environment the parent was _exec'd_ with.

So each workflow runs three steps:

1. `ci-land-report-patch rebase` — `GH_TOKEN` and `EXPECTED_HEAD`, no signing key.
2. `ci-apply-report-patch` — nothing at all.
3. `ci-open-report-pr` — signing key and token.

`TestCredentialBoundary` asserts it: the validator appears in each workflow as a `run:` line before
the first `CI_SSH_SIGNING_KEY`, only the `sign` job holds `contents: write` or the key, and `rebase`
runs with the signing variables absent.

## Patch validation

The patch is untrusted — it crosses a job boundary from a runner that built it out of zone data and
platform sources fetched from the internet. It is checked twice against different sources: the patch
headers, then the index. Keep both loops; either alone catches every shape constructible today, but
they read different truths.

- **Before applying**: `git apply --numstat -z` lists every path including creations. Each must match
  `^Reports/[A-Za-z0-9._/-]+$` with no `..` and no dot-prefixed segment. Any `rename from` header is
  rejected.
- **After `git apply --cached`**: `git diff --cached --no-renames --name-only -z HEAD`, unscoped,
  against the same rule, with destination modes limited to `100644` or `000000`.

- **Renames bypass any path check**, since every check sees only the destination. Producer and
  consumer both pass `--no-renames` and the mode check is unscoped, so a rename's source appears as
  its own deletion and fails the allowlist.
- **`--cached`, not `--index`**: it never writes the working tree a later `uses: ./...` would resolve
  against. It also makes creations visible — plain `git apply` leaves them untracked and `git diff`
  never lists them, so an additions-only patch reads as "no changes".
- The producer diffs against `HEAD`, not the index: `--intent-to-add` hides deletions from a
  worktree-versus-index diff.
- The signature check uses process substitution, not a pipe. `grep -q` exits early, SIGPIPEs
  `git cat-file`, and `pipefail` reads that as unsigned.

`Data-Zones/` is refreshed on every run and is deliberately outside the allowlist: the reports are
what these workflows commit, and the zone files are not theirs to change.

## The rebase guard

The patch is built minutes before it lands, and `main` moves in between. Refusing on any movement is
too strict — an unrelated commit is not a hazard — so `bin/ci-land-report-patch` compares paths.

- **`Reports/` is guarded**, measured from `EXPECTED_HEAD` (the producer's checkout), so a patch
  built against reports that have since changed on `main` is refused rather than reverting them.
- **`bin/` and `.github/` are guarded unconditionally**, measured from this job's own checkout: a
  checkout that rewrites them swaps the scripts of the running job, and bash reads a script
  incrementally rather than up front.
- A commit landing on `main` after this check is NOT caught by the push: the lease names the
  report branch, not `main`. The patch then lands on a base that
  moved, and the PR carries a stale or conflicting diff for review rather than overwriting `main`.

## The report branch is machine-owned

The checks run nightly, and each platform has one rolling branch, `reports/<platform>`. A change
found while its PR is still open force-pushes a fresh commit built against current `main` and
comments on the same PR, so there is at most one open report PR per platform. The repository deletes
head branches on merge, so the first change after a merge creates the branch again. Because the
branch is reused, the commit phase checks it before force-pushing:

- **Committer identity.** If the remote branch tip was not committed by `CI_COMMITTER_EMAIL`, the run
  exits 1 with `outcome=branch_diverged`, leaving a reviewer's commit on the PR branch intact. A
  lease alone cannot do this: the lease value is read from the same fetch that observes the human
  commit, so it would approve overwriting what it just saw.
- **`--force-with-lease=refs/heads/<branch>:<sha>`** covers the race between that fetch and the push.
  The `<refname>:<expect>` form names the ref explicitly rather than trusting a remote-tracking
  branch this job may never have fetched; an empty `<expect>` requires the ref not to exist, which is
  the fresh-branch case.

- **Run order.** Each commit carries a `Report-Run: <run_number>` trailer. A tip from a higher run
  exits 1 with `outcome=stale_run`, so re-running an old failed `sign` job cannot replace newer
  results. A same-number re-run still lands, and a tip with no trailer counts as older. The guard
  sees only published tips: to retry a failed `sign` job after a newer run has finished, dispatch a
  fresh run instead.
- **Same-repository PRs only.** The branch names are fixed and the repository is public, so a fork
  can open a PR from its own `reports/<platform>`. Both PR scripts look up open PRs with
  `isCrossRepository` false and act on that PR's number.
- **Branch and title are literals** in the steps that use them, not outputs of the producer job, so
  nothing the producer computes reaches the signing job except the validated patch.

Equality of the platform's own snapshot CSVs (`Reports/snapshots/<platform>/*.csv`) decides only
whether an existing PR is commented on. The check stamps a re-observed pending snapshot with that
night's `check_date`, and a rebuild picks up other platforms' merged reports, so comparing all of
`Reports/` would comment on unchanged results.

When a run finds results matching `main` again, there is no patch, and `close-superseded` closes the
open PR instead, so an observation the latest check contradicts cannot be merged. It leaves a PR open
when a reviewer committed to it. Apple has no such job: its snapshots are keyed by the runner's exact
macOS point release, so a night that lands on an older image during a rollout would close a valid PR.

Two limits remain:

- **Platforms can still conflict.** All three rebuild `Reports/manifest.json` and
  `Reports/summary.csv`, so merging one platform's PR can leave another's conflicted until its next
  nightly push rebuilds it against the new `main`. A merge landing mid-run trips the rebase guard,
  and the next night retries.
- **A reviewer commit left on the branch blocks it.** Merging deletes the branch, but closing a PR
  without merging, including `close-superseded`, keeps it. If its tip is a human commit, every run
  exits `branch_diverged`. Delete `reports/<platform>` once that work is on `main` or abandoned.

## Identity and credentials

Identity comes from the `CI_COMMITTER_NAME` / `CI_COMMITTER_EMAIL` repository variables; that email
must own the public signing key registered on the account, and the key must be registered as a
**signing** key rather than an authentication key. `CI_SSH_SIGNING_KEY` is the **private** key, with
no passphrase: `bin/ci-land-report-patch` runs no `ssh-agent` and writes one file, so a public key
there fails with `No private key found for public key`, and a passphrase-protected key fails with
`Enter passphrase` — both fatal, neither silent.

The push credential never reaches disk or argv: `PUSH_REMOTE` is credential-free and `GH_TOKEN` is
injected as an `http.<url>.extraheader` via `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_0` /
`GIT_CONFIG_VALUE_0`. The base64 is fed by `printf`, not a herestring, which would append a newline
and 401 the push.

## Linting

`mise.toml` pins `shellcheck` and `jactionlint`; `bin/lint` requires both on PATH and fails rather
than skipping, since a check that cannot fail is worse than no check. `uv` is deliberately not
pinned there: CI installs it with `astral-sh/setup-uv`, and two pins drift.

## Timeouts

Every long step carries its own cap. A job-level timeout is a cancellation, and `if: failure()` does
not fire on a cancelled job, so a job cap must exceed the sum of its step caps or the step guards can
never fire. `TestTimeoutBudgets` asserts that for every job in every workflow.

## Guards are proved by breaking them

A guard that has never been seen to fail is decoration. Each guard here was checked by breaking its
subject and confirming the matching test goes red: the ownership check, the lease, disabled
repository hooks, the second `--guard`, the rename and path and mode checks, the credential handling
in both phases, the job caps, the job permissions, `persist-credentials`, and the comment
deduplication. Do that for anything added here later.

## Accepted

- A PR opened with `GITHUB_TOKEN` has check runs awaiting manual approval. The PR body says so.
- There are no failure notifications. iana-data alerts by pushover and email; this repository has no
  such infrastructure, so a failed signing job is visible only in the Actions tab.
- Dated `reports/<platform>-<date>-<run>` branches from before the rolling branch remain on the
  remote; deleting them is optional housekeeping.
