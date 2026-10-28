# PR #2 — Pass 1: the cold-review brief for slice 1 (archived Wed 28 Oct 2026, TZ=America/New_York)

Archive note: home-directory paths are redacted as placeholders; setup commands need local paths supplied before use.
Written by the PM seat (Claude Code, Sonnet 5.5) at about 15:30 EDT from a fresh read of PR #2 at head `402c423a11b352d677e81dd68fb0b32b4bb05476`
(Cursor, Grok 4.7; draft; `verify` green on 3.9 and 3.14). The brief is tip-agnostic: the reviewer takes the SHA from the latest
"Builder: HOLD at" comment and checks it against GitHub. This file is the archive; the delivery is the chat message.

Two things must be true before the session starts, and only the owner can do them.

1. The docs branch `docs/seat-the-repo` (AGENTS.md, the review skill, the spec, the PR template) is on `main`. It was never pushed when the
   builder started; the builder took the oracle and the readings from the PM's local commit `0f28bb2`. The copies are byte-identical to
   the docs branch (PM compared them), and `git merge-tree` of the docs branch against PR #2's head is clean, so the order of the two merges
   does not matter to the tree. The reviewer needs the skill in its checkout, so the docs land first.
2. The builder merges `origin/main` into its branch and re-posts "Builder: HOLD at <SHA>", so the reviewer's checkout holds AGENTS.md and the
   skill, and the SHA reviewed is the SHA the builder vouched for. The prompt for that is the next section.

Setup, once, after both are done:

    git clone https://github.com/BeniCheni/settlement-grader-evals.git [PR-2-review-checkout] && cd [PR-2-review-checkout] && git fetch origin cursor/slice-1-checks && git switch -c claude/pr2-review origin/cursor/slice-1-checks

A fresh clone, not a worktree: a worktree shares refs with the main checkout, and the main checkout holds the gitignored `private/`.

## The builder's sync prompt (Cursor, Grok 4.7 High, in [builder-checkout])

Sync PR #2 with main, then re-post the HOLD

You are the builder seat for PR #2, in your own clone at [builder-checkout] on cursor/slice-1-checks. The docs PR has landed on main (AGENTS.md, the review skill, the slice 1 spec, the PR template). Merge origin/main into your branch: a merge commit, no rebase, no force-push. data/oracle_slice1.json and data/calibration_readings_v1.json exist on both sides and are byte-identical, so the merge should be clean; if any file conflicts, stop and say which and why instead of resolving it. Then run the suite on Python 3.9 and 3.14 and compileall, regenerate the three reports and cmp them against the committed ones, push to cursor/slice-1-checks only, wait for verify on both Pythons, and post a new comment that begins "Builder: HOLD at <the full head SHA>" and says what you re-ran and what you did not. Author the merge commit as `Cursor` with the email your harness uses, never the owner's. Change no other file, do not mark the PR ready, do not request a review, do not merge.

## The Pass 1 prompt

---

/grader-pr-review 2 --pass 1 --no-merge

PR #2 — Pass 1 (cold review): slice 1, the eleven plain-code checks, their in-sample calibration and the first page, in github.com/BeniCheni/settlement-grader-evals

You are Pass 1 of the full cycle, running in Claude Code on Fable 5.1 at Extra effort, in a fresh session whose working directory is a fresh clone, [PR-2-review-checkout], on the local branch claude/pr2-review, which starts at the PR's head. Cursor on Grok 4.7 wrote the PR; you wrote none of it, and Codex adjudicates after you (Pass 2). The method is /grader-pr-review, which the line above invokes; it lives at .claude/skills/grader-pr-review/, and AGENTS.md outranks it on process. Read AGENTS.md first, then the skill, then this prompt again. You may fix what you reproduce, in scope, under the skill's fix policy, and you push with `git push origin HEAD:cursor/slice-1-checks` after `git fetch origin` shows the remote tip unmoved. `--no-merge` is on: stop at the PR comment. This is not a release (no tag, no version string, no CHANGELOG), and the merge itself waits for Pass 2 and Pass 3.

YOUR TREE IS A FRESH CLONE ON PURPOSE. The gitignored private/ and data/espn_cache/ are physically absent; if either is present, stop and say so. Do not open any other checkout of this repo on this machine, and never print or derive the scale constant. The reviewer reads the PR against the spec and the data, not against anything else.

WHAT THIS PR IS, AND WHAT IT IS NOT. The builder was told to produce the plain-code half of the scorer: scorer/traces.py (one record per ticket from an OTLP run), scorer/checks.py (eleven checks; SELF_CONTRADICTING_EVIDENCE needs a judge and is a later slice), scorer/stats.py (confusion, agreement, Cohen's kappa, Wilson, the trust bar), scorer/calibrate.py, scorer/score.py, scorer/report.py and ui/ledger.css (the first page, in the Haunted Ledger style), unittest tests, one CI job named verify on Python 3.9 and 3.14, the three regenerated reports under reports/, and one README sentence plus three commands. It is not the judge, the held-out labels, compare or the A/A floor, the A/B, or the labelling page; those are later slices. Calibration here is IN SAMPLE: the checks were fixed while reading the same 32 traces they are scored on, so a high agreement shows they reproduce the labels, not that they generalise.

STATE AT PASS 0, as the PM seat read it on Wed 28 Oct 2026 at about 15:20 EDT (re-check all of it, and expect the head to have moved by one merge commit from main).
- PR #2 is open and a draft, base main at 6c5ceb7 before the docs merge, head 402c423a11b352d677e81dd68fb0b32b4bb05476 on cursor/slice-1-checks. Seven commits by Cursor, 23 files, +2800 −0. Actions run 40750225976: verify (3.9) and verify (3.14) both passed at that SHA. Take the SHA to review from the latest "Builder: HOLD at" comment, and from GitHub, never from this prompt; if the head has moved since that comment, review the HOLD SHA and say what the delta is.
- The PR body is a claim, not a source. It says: the suite is 39 tests and OK on 3.9.6 and 3.14.7; the calibration matches data/oracle_slice1.json on every pinned field; every check has a test built to fail it, plus three named mutations; the committed reports regenerate byte-identical; the page has scrollWidth equal to innerWidth at 360, 375, 390 and 1000 in both themes; the lowest text contrast is 4.624; the privacy sweep of the added lines is clean. Re-run each one and say which matched.

THE CONTRACT YOU HOLD IT TO, in this order. docs/slice-1-spec.md is the spec of record: the names and behaviours it fixes are fixed. data/oracle_slice1.json is the acceptance data and was not the builder's to edit; confirm the PR left it and data/calibration_readings_v1.json byte-identical to main. docs/cursor-prompts/slice-1-build.md is the build prompt; its BOUNDARIES (standard library only, Python 3.9 and 3.14, no edits to check_gold.py, run_eval.py, grader/, gold.json, codes_v1.json, the oracle or the readings, no private/, no new dollar amount, no tag or version) are the standard the builder is judged against. Beni's rulings that bind you: the B01 and A02 labels are his and unchanged, so a flag the labels lack is a false fail to be read, never a label to be edited; the judge model is undecided and out of scope.

THE ORACLE PROVES LESS THAN IT LOOKS LIKE IT PROVES. Matching it shows the checks reproduce 32 traces they were fixed on. So, on top of the skill: (a) read each of the eleven checks against the wording of its code in data/codes_v1.json, the question and the how_to_check, and decide whether it is deciding that code or a neighbour; (b) run the scorer on the other tracked runs, traces/v1-2026-10-14 (30 tickets), traces/v1-adv (2) and traces/smoke-1 (3), which have no labels, and read the flags and the non-flags in the traces themselves: say how many tickets you read and which; (c) mutate inside the checks, not only around them.

SEALED APPENDIX: suspicions the PM seat measured on Wed 28 Oct 2026. Each is a question to re-derive independently, never a conclusion. If one does not reproduce, say so instead of fixing a ghost.
1. Whole-check mutants are the weakest kind. Mutate the inside of checks: the 0.5 team-name score threshold, the 0.01 net tolerance, the STATUS_FULL_TIME gate on find_match scores, None against 0.0 net, the exact-after-trim comparison in PLACEHOLDER_ECHO, the tie rule in _best_facts. Name at least six and say which survive.
2. The tie rule in _best_facts (the highest minimum team score wins, and a get_match_facts result beats a synthetic full-time score on a tie) is not in the spec, which says only that a fetched match is the leg's when both names score at least 0.5. The PR says the oracle matched with that rule. Is it load-bearing: remove it and does the oracle still hold, on every flag and on every pinned count? If the oracle holds without it, it is untested complexity. If it does not, the spec has a hole, which is a PM finding and not a builder bug. Say which, with the command.
3. _best_facts wraps espn.team_objects in `except Exception: continue`. The spec wants an event missing from the frozen set to skip the leg and nothing else. What does a broad except hide? Inject a different exception and see whether any test notices.
4. The PR admits that the hand-worked statistics tables pass counts straight in, and that swapping fp and fn inside confusion survived them; only the oracle caught it. Is there a direct test of confusion from two lists whose fp and fn differ? Is kappa or Wilson checked at an edge: n of 0, one class only, a table with an empty row, the second hand-worked table in the spec?
5. `python3 -m scorer.score traces/smoke-1` ends in an uncaught KeyError ('SMOKE1', a case that lives in data/smoke.json): score and calibrate take only data/gold.json on the command line, while calibrate() accepts cases_path. The spec names the function's arguments and no command-line flags. Classify it: a builder bug, a spec gap (the PM's), or fine. Check the traces/v1-adv run for the same.
6. The lowest contrast reported is 4.624, 0.124 above the 4.5 line. Does tests/test_contrast.py enumerate every text and background pair the page renders, including text over the cover gradient, the stat scrim, hover and focus states, and the light theme's equivalents, or a hand-picked list? Walk the rendered DOM with getComputedStyle, composite the real backgrounds, and compare your lowest ratio with the PR's.
7. The builder could not collect the console. You can: read it at each of the eight cells, and name every external request the page makes (the spec says there are none beyond fonts; check what the stylesheet and page actually fetch).
8. tests/test_readme.py asserts that a phrase and three command lines are present in the README. What would have to be true for that test to catch something that matters, and are those three commands the ones that work from a fresh clone, run exactly as written?
9. The CI job: read run 40750225976 and the latest run's log, not just the verdict. Are there Node deprecation annotations on actions/checkout@v4 or actions/setup-python@v5, and what is each action's current major? Is the permission minimal? On Python 3.14, does the job fail rather than pass if no tests are discovered (exit status 5)?
10. The known ResourceWarning from grader/espn.py (an unclosed frozen-facts file) is out of scope. Run the suite with warnings shown and attribute every distinct warning to a file; any warning that is the builder's own is a finding.
11. The PR body reports a privacy sweep by pattern with hit counts. Run your own, over the added lines and then over the committed reports and the page, and compare: two matches of the home-directory prefix are claimed to be negative assertions inside tests. Confirm that, and that nothing in the page names a machine, a model host or a person.

HOW YOU CLOSE. One PR comment in the shape of the skill's pr-comment.md: the verdict, the findings table (severity, file and line, what you reproduced, the fix commit or why none), what you killed, "Deliberately not done", and the environment and commands as run, with the interpreter versions and the real test counts. For every acceptance figure, say which command printed it. Whatever you would change in AGENTS.md or in the skill itself, list under "Deliberately not done" with a one-line rationale; those files belong to a different PR, so do not edit them here. End with the questions that only Beni can answer, each one answerable in one word. A no-finding review of a real diff is a finding about the review: if you found nothing, say what you tried that could have found something.

COMMITS. Author every commit as `Claude <noreply@anthropic.com>`, with the trailer your harness gives you, via per-commit `git -c user.name=Claude -c user.email=noreply@anthropic.com commit`, never `git config`, and never the owner's identity. Small commits; each message says what broke, how you proved it, and how the fix was verified. If you reach a usage limit, stop at a step boundary and say which step and which SHA.

THE STANDARD. A claim you could not re-run goes under "Not verified", never "verified". A test you did not watch fail is not yet a test. Prefer a failing command you can show over a sentence that says it works.
