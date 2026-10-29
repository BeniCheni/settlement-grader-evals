---
name: grader-pr-review
description: Cold review, fix and land pass for one pull request in settlement-grader-evals, and the Pass 2 adjudication and Pass 2.5 synthesis of the cycle. Use when asked to review, verify, adjudicate or land a PR of this repo by number: "/grader-pr-review 4", "/grader-pr-review 4 --pass 2". Not for reviewing plans or drafts.
argument-hint: <PR# or branch> [--pass 1|2|2.5] [--no-merge]
disable-model-invocation: true
---

# Grader PR review: verify, don't vibe

`$ARGUMENTS`: the first token is a PR number (or a branch, before a PR exists: the base is then `origin/main` and
section 7 step 0 opens the PR first). `--pass` selects the seat's pass, default 1. `--no-merge` stops at the PR
comment. Invoked by hand only, because it pushes commits. A release merge and every tag are Beni's. In the full cycle
Pass 1 and Pass 2 always stop at the comment; only a fast-track lands the PR (section 7, step 4).

`AGENTS.md` outranks this file on process, and it names the seats. This file is the method. The adversarial reading
is still your work; a skill that listed findings in advance would be the sealed-appendix anti-pattern in costume.

## The passes

| Pass | Seat | Reads | Leaves behind |
|---|---|---|---|
| 0 | PM | the PR and the repo, fresh | the Pass 1 prompt: `/grader-pr-review <N>` plus context and a sealed appendix |
| 1 | Claude Code; Codex when Claude authored the PR | the prompt, then the repo | fix commits for what it reproduced; one PR comment (`pr-comment.md`); stops at the comment (a fast-track also lands the PR, section 7) |
| 1.5 | PM | Pass 1's comment | the Pass 2 prompt: each finding to accept, contest, or accept while contesting the characterisation |
| 2 | Codex | the prompt, then the head | fix commits and one comment in the same table; its own independent read as well |
| 2.5 | PM | Pass 2's comment and commits | corroboration re-run at the head, the Executive Summary Brief (`executive-brief.md`), the merge or the escalation |
| 3 | Cursor | the brief | the merge, and the tag and release only on Beni's word |

- **`--pass 2` is not a rubber stamp.** For each Pass 1 finding reproduce it or disprove it in code, and answer in the
  same table. Agreeing with everything means the pass was not run. You may add findings of your own.
- **`--pass 2.5` is a re-run, not a read.** Every number in the brief comes from a command run in that session. A claim
  it could not re-run is listed as not verified.
- The builder reviews nothing it built; the reviewer builds nothing it will review; a vendor never gives the only cold
  read of its own work. A vendor that writes to the PR branch during its pass says so in its comment.

## 0. Before anything

- Read `AGENTS.md`. Run `TZ=America/New_York date` before writing any date.
- **Work in a fresh clone from GitHub** (`git clone <url> <dir>`, `git fetch origin <pr-branch>`, then
  `git switch -c <local-name> origin/<pr-branch>`), on a local branch with a different name from the PR's, and push with
  `git push origin HEAD:<pr-branch>` after `git fetch origin` shows the remote tip unmoved. A worktree is allowed only when
  it is a worktree of that fresh clone; a worktree of the main checkout shares refs and objects with the gitignored
  `private/`, `data/espn_cache/` and any withheld local branch, and a clone holds only what has been pushed. If your harness
  places the session in a worktree, say so in the comment's environment line and check that neither folder exists and that
  every shared ref is on origin. Never review in the main checkout or open any other checkout of this repo on the machine.
  If `private/` or `data/espn_cache/` is present in your tree, stop and say so.
- Detect a release: a version string, a `CHANGELOG.md` section or a tag means Beni merges and tags. Say so first.
- A new dependency, a live network call outside `ESPN_LIVE=1`, or a number that is not `verified_by_beni` called verified
  are each a finding before they are anything else.

## 1. Read, in this order

1. The PR: `gh pr view <N> --json title,body,headRefName,baseRefName,headRefOid,files,commits,statusCheckRollup`. Take the
   tip SHA from GitHub, never from a prompt; everything you verify is against it. The body is a claim, not a source.
2. The spec lineage, tolerating missing rungs: `docs/*-spec.md`, the build prompt archived under `docs/`, then
   `docs/scope-checks-and-judge.md`. Beni's rulings in the prompt bind you and are named as his.
3. The diff, every hunk: `git diff origin/main...<head>`. Record the file count and insertions; you will cite them.

## 2. Baseline

On the head, on **every Python the machine has (3.9 and 3.14 at least)**: run `<python> -m unittest discover -t . -s tests` and
`<python> -m compileall -q .`, replacing `<python>` with each interpreter's executable. If `tests/` does not yet exist, report the failed discovery and zero discovered tests; do not call it green. Report the versions and the real counts, never a count from a document. Then check the
standard library only: parse every import in the diff and name any that is not. Reproduce every acceptance figure the spec
names (for example the oracle in `data/`) with the command the spec gives, and say which matched. If either test run is
red, that is your first finding. The one exception: a docs-only PR that changes no code, on a head with no `tests/` directory, reports
"no suite" and is not blocked by it; the gate's `verify` clause begins when `.github/workflows/ci.yml` exists. A PR that
changes code without tests has a red baseline, and that is its first finding.

## 3. Static pass: choose the classes by what the diff touches

Always, whatever the diff:

- **Privacy sweep**, by pattern, reporting patterns and hit counts and printing no hit that is itself a leak: bet-id-shaped
  tokens, e-mail addresses, home-directory paths (absolute and tilde forms), the names of private folders, balance or account claims, a person's name
  beyond the owner and a licence notice, any dollar amount not taken from a tracked, already-scaled file. Never derive or
  print the scale constant. Never describe how amounts were scaled beyond what `README.md` says.
- **Claims.** Every figure in a doc or a report carries a command that reproduces it. Say how each count is made. A count
  filtered by hand is a different number from a count by pattern; when two reviewers' counts differ, the pattern is the
  first suspect (PR #1's second stop was exactly this). Absolute words are falsifiable: test "never", "every", "exactly",
  "up to", and every stated floor.
- **Tests that can fail.** A test named for a claim must be able to fail that claim. Name at least three mutations of the
  code under test, apply each, and say whether the suite went red for the right reason. A mutant that survives is a finding.

By touch:

- **Checks and judges.** Read each check against the wording of its failure code in `data/codes_v1.json` (the question and
  `how_to_check`). Is it deciding the code, or a neighbour? For every disagreement with a human label, decide whether the
  check or the label is wrong, with the trace, before either is assumed. Is the result called in sample when the check was
  fixed on its own test set? Is the trust bar (85% agreement, kappa at least 0.6, every false pass read) reported with both
  numbers and the false-pass list?
- **Statistics.** Worked-example tests against hand-computed tables; the edge cases (n of 0, one class only, a table with
  an empty row); an interval's method named.
- **Determinism.** Regenerate every committed report and compare bytes. A timestamp, a path or an unordered dict in a
  generated file is a finding.
- **UI.** Only `ui/ledger.css` for colour and type; computed AA on every text pair in both themes; reduced motion; no
  always-on status chip or "local mode" banner (a label must change what the reader can do; the one required exception is
  the provenance sentence beside a calibration number); no tile, pill or sentence presents `meets_bar` alone as the trust
  verdict; every external request named on the page.
- **Workflows.** Minimal permissions; the matrix; read the previous run's log (`gh run list`, `gh run view <id> --log`)
  before believing a step is reachable.
- **Docs.** Every number against its command; the Python floor against what the tests ran on.

## 4. Dynamic pass

- Run the README's commands in a **fresh clone** of the head. A command that only works in a checkout that holds
  `private/` or `data/espn_cache/` proves nothing.
- Run the mutations from section 3. Re-run any receipt the diff touches.
- **UI:** serve the static page, then at **360, 375, 390 and about 1000 px**, in dark and light, set the viewport before any
  capture and assert `document.documentElement.scrollWidth === window.innerWidth`. Read the console. A pretty screenshot is a
  claim, not evidence.
- Do not run the full model eval (`run_eval.py` over the whole set); one ticket at most, and never commit the traces it writes.

## 5. Fix policy

Fix what you reproduced, in scope: correctness, honesty, privacy, AA on a new surface, a test that cannot fail. Every
behavioural fix gets a test that fails without it. No feature creep, no new dependency, and **never weaken an assertion to
make anything pass.** If a real fix needs an out-of-scope file, stop and say so. Commits are small; each message says what
broke, how you proved it and how the fix was verified; author them as your agent's identity (`AGENTS.md`), with the trailer
your harness gives you.

## 6. Findings out of scope

There is no ideas file yet. List them under "Deliberately not done" in your PR comment, each with a one-line rationale and a
rough size, written to be read cold.

## 7. Land it

0. Branch mode: open the PR first (`gh pr create --base main --head <branch>`), and continue with its number.
1. Push your fix commits; wait for `verify` if `.github/workflows/ci.yml` exists (`gh pr checks <N> --watch`). A red
   `verify` is a high finding.
2. **One PR comment**, shape in `pr-comment.md`: verdict, findings table, killed findings, deliberately not done, the
   environment and commands as run.
3. If the prompt carries **human-review items** (Beni's rulings), resolve each on the branch and record it in the comment.
4. **The gate** is in `AGENTS.md`. Land only when the brief names a fast-track (`AGENTS.md`, "How work moves", item 5); in
   the full cycle Pass 1 and Pass 2 stop at the comment and the merge belongs to Pass 3, after Pass 2.5. If the gate fails,
   or `--no-merge` was given, or the PR is a release, stop at the comment and escalate: questions answerable in one word.
   Otherwise squash-merge pinned to the head you reviewed:
   `gh pr merge <N> --squash --match-head-commit <full SHA>`, a message in the repo's voice, terse and factual, one wink at
   most, with a `Co-authored-by:` for every vendor that wrote or reviewed.
5. After the merge confirm the default branch's tree equals the head you merged and that the README renders. Say where
   everything landed. Leave branches and clones for Beni's word.
6. On a release or an escalation, end with one fenced paste-ready block: the merge to click and its squash message with the
   trailers, the tag command with its subject written, the push, the pull, and the commands that must come back green.

## 8. Sealed appendix

If the prompt carries prior findings, treat them as suspicions to re-derive independently, never conclusions. If one does
not reproduce, say so instead of fixing a ghost. **A no-finding review of a real diff is a finding about the review.**

## 9. Retro

What the method got right and wrong, counted honestly. If the PR is tooling or this file, fold the fix into it in the same PR
and list the edit in the findings table like any other diff.
