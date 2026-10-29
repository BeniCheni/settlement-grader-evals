# AGENTS.md: who does what in this repo, and what nobody may do

Read by every agent that touches this repo: Claude Code through `CLAUDE.md`, Codex and Cursor directly.
It outranks any prompt on process. A prompt may narrow it and may never loosen it.

## What this repo is

A local model settles soccer bet tickets that are already decided, and this repo measures how often it is wrong:
a gold set of real tickets, a harness that records every step, a taxonomy of failures, plain-code checks for each
failure, and the proof that any check or judge agrees with a human before it is trusted. It predicts nothing.
`README.md` is the public face; `docs/scope-checks-and-judge.md` is the plan.

## The seats

| Seat | Who | Does | Never |
|---|---|---|---|
| Owner | Beni | Rules on every fork, clicks every release merge and tag | |
| PM | Claude (Cowork or Claude Code) | Scopes slices; writes the spec, the build prompt, the review briefs and the synthesis; keeps docs and data records | Writes code. Docs and data records only. |
| Builder | Cursor, Grok 4.7 High (Extra High only for a design-heavy slice) | Builds one slice per PR from the spec | Reviews anything it built |
| Pass 1 | Claude Code, Fable 5.1 or Opus 5.5 (Extra on code, High on docs and UI) | Cold review of the builder's PR | Reviews anything it wrote or helped write |
| Pass 2 | Codex, GPT-6.1 Sol High (Extra High on the judge and A/B slices) | Adjudicates Pass 1's findings against the code, fixes what it accepts, adds its own read | |
| Pass 3 | Cursor, Grok 4.7 Medium | Merge logistics, and the tag and release when Beni says so | Merges a release without Beni's word |

- **The builder reviews nothing it built, and the reviewer builds nothing it will review.** A reviewer who wrote any
  line of a PR is not its reviewer. One vendor never gives the only cold read of work that vendor authored: a PR the
  PM or a Claude session wrote (docs, a skill, a record) gets Codex as Pass 1.
- Who may write to a PR branch during a pass is stated in that pass's comment. A branch that moved under the next seat
  says so.
- No version, tag, `CHANGELOG.md` section or release exists yet. A release number is Beni's decision; a session that
  picks one has renumbered the roadmap.

## Hard rules: privacy and honesty

1. **Amounts are scaled.** Every dollar amount here was multiplied by one constant that is not published. Never print,
   derive, hint at or reconstruct it, and never compute a ratio between a published amount and anything. The constant
   and the real amounts live only in the gitignored `private/`. Never open `private/` or `data/espn_cache/`. Every build
   and review session works in a fresh `git clone` from GitHub. A worktree is allowed only when it is a worktree of that
   fresh clone, which shares only what was pushed. Never use a worktree of the main checkout or of any checkout that holds
   `private/`, `data/espn_cache/` or a withheld local branch: it shares refs and objects with them. A harness that places a
   session in a worktree says so in its comment and checks that neither folder exists and that every shared ref is on
   origin. If either folder is in your tree, stop and say so. (Beni's ruling, 28 Oct 2026.)
2. **`design/` is local only** and is never committed. A brief that names a file in it grants read access to that file.
3. **Facts are frozen.** The grader reads `data/espn_frozen.json`; a lookup that is not in it raises and never reaches
   the network. Extending it is its own PR, run with `ESPN_LIVE=1` and `build_frozen.py`.
4. **Nothing here predicts a result.** Do not add a feature that does.
5. **No answer key is "verified" unless `verified_by_beni` says so.** A claim about the answer keys carries that count.
6. **Nothing private enters a PR**: no bet ids, e-mail addresses, home-directory paths (absolute
   and tilde forms alike), account or balance claims, and no person's name beyond the repo owner and licence notices. Every PR is swept
   for these by pattern, with the counts reported, the patterns stated and no hit printed.

## Engineering rules

- **Standard library only.** A dependency needs a paragraph in the PR body saying why. Code is tested on Python 3.9 and
  3.14; the floor is stated in `README.md` and is what the tests ran on.
- **Tests are `unittest` under `tests/`**, run with `python3 -m unittest discover -t . -s tests`. Every check and every
  claim has a test built to fail it: mutate the code, and the test must go red for the right reason. Never weaken an
  assertion to make something pass.
- **In sample is not held out.** A check or judge fixed while reading its own test set says so wherever it reports a
  number. The bar to trust one is agreement of at least 85%, Cohen's kappa of at least 0.6, and every false pass read.
  `meets_bar` tests the two numbers only: whether every false pass was read is reported beside it and never folded into
  it, and no tile, pill or sentence presents the numbers alone as the trust verdict.
- **Report both numbers.** Agreement and kappa; catch rate and over-block rate. One alone hides the other's failure.
- **A figure carries the command that reproduces it.** Say how a count is made. A count filtered by hand is not a count.
  Absolute words ("never", "every", "exactly", "up to") are claims: test them.
- **Generated files are byte-stable.** No timestamps, no machine paths; a test fails when a committed report is stale.

## UI rules: the Haunted Ledger style

`ui/ledger.css` is the only source of colour and type. Ink speaks, slime confirms, lamp marks where data came from and
nothing else, blood alarms. A label earns its place only if it changes what the reader can do: no always-green status
chips, no "local mode" banners. The one required exception is provenance: wherever a calibration number is shown, a
sentence beside it says whether it is in sample or held out and what it does and does not show, because that decides how
far the reader may trust it. It is a sentence, never a chip, and it changes when the evidence changes. Both themes; AA contrast on every text pair, computed; reduced motion respected; at
360, 375, 390 and about 1000 px the page's `scrollWidth` equals its `innerWidth`, with the viewport set before any capture.

## How work moves

1. PM: spec, then the build prompt (delivered in chat in a fenced block, one line per paragraph, archived under `docs/`).
2. Builder: a draft PR, one slice, every commit green on its own, the PR body filled in from the template.
3. Review, by `/grader-pr-review` (`.claude/skills/grader-pr-review/`): Pass 0 the PM's brief; Pass 1 cold review;
   Pass 1.5 the PM's rebuttal brief; Pass 2 adjudication; Pass 2.5 the PM's synthesis and merge gate; Pass 3 the merge.
4. **The merge gate.** Squash-merge pinned to the reviewed head only when: the verdict is "mergeable" or "mergeable after
   fixes"; every high finding has a fix commit; `verify` is green at the tip (once `.github/workflows/ci.yml` exists);
   nothing is still contested between vendors; and it is not a release. Otherwise the pass escalates to Beni with
   questions answerable in one word.
5. **Fast-track.** A PR that is not a release may run as a fast-track when the PM's Pass 0 brief says so: one cold review
   by a vendor that did not write it (Codex for a Claude-authored PR) takes the place of Passes 1 to 3, fixes what it
   reproduces, and squash-merges if the gate in item 4 holds. The default is the full sequence above, and the PM picks the
   shape per PR. A tag and a release number stay Beni's. (Beni's ruling, 28 Oct 2026; the same shape he set for the
   Kickoff repo on 7 Oct, and PR #1 here merged this way.)

## Commits and PRs

- Author as the agent doing the work: `Claude <noreply@anthropic.com>`, `Codex <noreply@openai.com>`, and `Cursor`
  (never Beni's identity). Use per-commit `git -c user.name=... -c user.email=...`, never `git config`.
- Small, reviewable commits; each message says what broke, how it was proved and how the fix was verified. End with the
  trailer your harness gives you. A squash body carries a `Co-authored-by:` for every vendor that wrote or reviewed.
- Never force-push. Push a fix to another seat's branch only with `git push origin HEAD:<branch>` after re-fetching.

## When to stop and ask

Unknown facts are escalated to Beni, never assumed. Stop on: a numbering or release fork; anything that would touch a
privacy rule; a finding the vendors still contest; a needed dependency; a need to read `private/`; a claim you could not
re-run. A review that finds nothing because it read and did not execute has not been run.
