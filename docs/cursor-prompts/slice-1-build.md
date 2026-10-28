# Slice 1: the Cursor build prompt (archived Wed 28 Oct 2026, TZ=America/New_York)

Written by the PM seat (Claude, Sonnet 5.5) from a fresh read of the repo, the trace files and the failure-code data, for the
builder seat (Cursor, Grok 4.7 High) under the owner's flow of 28 Oct 2026: Cursor builds, Claude Code is Pass 1, Codex is
Pass 2, Cursor merges in Pass 3. Delivered in chat in a four-backtick fence, one line per paragraph; this copy is the archive.

Why it exists. The PM seat first wrote this slice itself, as about 930 lines of Python, which broke the rule that a reviewer
builds nothing it will review. Its output survives as an oracle (`data/oracle_slice1.json`) and the code is withheld from the
builder, so the build is independent and Pass 1 can compare it with something written by other hands.

Setup that only a human can run, once, after the docs PR that carries this file, `AGENTS.md`, the spec and the oracle has
merged: a fresh clone (not a worktree, which would share this repo's refs and expose the withheld prototype), with the one
design file copied in and kept out of git:
`git clone https://github.com/BeniCheni/settlement-grader-evals.git ~/settlement-grader-cursor && cd ~/settlement-grader-cursor && git switch -c cursor/slice-1-checks && mkdir -p design && cp ~/settlement-grader-evals/design/haunted-ledger-draft.html design/ && printf 'design/\n' >> .git/info/exclude`
then open `~/settlement-grader-cursor` in Cursor, model Grok 4.7 High, and paste the prompt below.

---

Slice 1 build: the eleven plain-code checks, their calibration against the human labels, and the first page, in github.com/BeniCheni/settlement-grader-evals

You are the builder seat for slice 1, running in Cursor on Grok 4.7 High, in a fresh clone at ~/settlement-grader-cursor on the branch cursor/slice-1-checks. You build one draft pull request from the spec and review nothing. Claude Code reviews your PR cold, Codex adjudicates, and you merge it only after both and only on the owner's word. Your deliverables: a draft PR from cursor/slice-1-checks into main, every commit green on its own, the PR body filled in from .github/pull_request_template.md, and a final PR comment that begins "Builder: HOLD at <the full head SHA>" and says what you could not verify. Then stop. Do not merge, do not request a review, do not tag.

READ FIRST, in this order, before any code. AGENTS.md (it outranks this prompt on process; a prompt may narrow it and never loosen it). docs/slice-1-spec.md (the spec of record and the contract: names and behaviours it fixes are fixed). data/oracle_slice1.json (the acceptance data). docs/scope-checks-and-judge.md (why this slice exists and what comes after it). Then README.md, data/codes_v1.json, data/gold.json, data/calibration_readings_v1.json, check_gold.py, run_eval.py and grader/, which you reuse and do not change.

WHAT YOU BUILD. Everything in the spec's contract sections: scorer/traces.py, scorer/checks.py, scorer/stats.py, scorer/calibrate.py, scorer/score.py, scorer/report.py, ui/ledger.css, tests/ under unittest, .github/workflows/ci.yml with one job named verify, the regenerated reports/calibration-v1.html, .json and .md, and one sentence under "Where we are" plus the scorer commands under "Try it" in README.md. The reports must be the output of your own code run on traces/v1.

THE ORACLE IS THE ACCEPTANCE TEST AND IS NOT YOURS TO EDIT. data/oracle_slice1.json holds the expected output of the eleven checks on traces/v1, per code: the flagged case ids, tp, fp, fn, tn, agreement and kappa to four decimals, whether the bar is met, and the false passes and false fails. Write a test that loads it and asserts every field against your calibration. If your output differs from the oracle, do not change the oracle and do not tune a check until it matches: read the trace, decide whether your check or the oracle is wrong, and put the evidence in the PR body. A mismatch you cannot settle is a HOLD, not a guess. The two disagreements in the oracle (B01 under SKIPPED_SETTLE_TICKET and A02 under INCOMPLETE_LEG_LIST) are expected: they are flags the human labels lack, read in data/calibration_readings_v1.json, and the labels are the owner's to change, not yours.

THE REFERENCE IS WITHHELD ON PURPOSE. The PM seat wrote a prototype that produced the oracle. You do not have it, and you must not look for it: do not search this machine for another copy of a scorer/ directory, and do not read anything under ~/settlement-grader-evals (the one design file you need is already copied into design/ in your clone). The spec and the oracle are the whole contract.

BOUNDARIES.
- Python standard library only, and no dependency of any kind. Your code must run on Python 3.9 and 3.14 (3.9 has no `X | Y` annotations, no `match`, and no nested same-quote f-strings; run both and say which interpreters you used). Do not edit check_gold.py, run_eval.py, anything under grader/, data/gold.json, data/codes_v1.json, data/oracle_slice1.json or data/calibration_readings_v1.json. Do not touch viewer/ or share/.
- Never open private/ or data/espn_cache/ (they are not in your clone, and that is deliberate), never print or derive the scale constant, never add a dollar amount that is not already in a tracked file, and never run run_eval.py over the whole set or call Ollama. design/ is local only: the draft in it is your template for ledger.css, you never commit it, and it is already excluded from git.
- Author every commit as `Cursor` with the email your own harness uses for Cursor commits, never the owner's identity, via per-commit `git -c user.name=Cursor -c user.email=<that email> commit`, never `git config`. End each message with the trailer your harness gives you. Small commits; each message says what the commit does and how you proved it. Push only to cursor/slice-1-checks, never force, never to main.
- No tag, no version string, no CHANGELOG.md. A release number is the owner's.
- If you reach a usage limit, stop at a step boundary and say which step and which SHA.

HAZARDS THE PM SEAT KNOWS ABOUT, to check and not to trust.
- check_gold.py is a script at the repo root. Your tests import it, so they must run with `python3 -m unittest discover -t . -s tests` (the -t . puts the repo root on sys.path); check that this works from a fresh clone.
- espn.team_objects reads data/espn_frozen.json and raises for an event that is not in it. A leg whose match is not there is skipped, never an error. grader/espn.py opens the frozen file without closing it, which prints a ResourceWarning under unittest: that is out of scope, so do not fix it, and do not let it hide a real warning of yours.
- OTLP attribute values are typed, and an intValue arrives as a string. The `final` answer can be absent, invalid, or not a dict. A tool span's error is its status code 2, not a key in its result.
- A committed report must be byte-stable: ordered keys, no timestamps, no absolute paths, and a test that fails when it is stale.
- Python 3.14 may exit with status 5 when unittest discovers no tests, so the CI job and every commit must have at least one test from the first commit that adds the workflow.

WHAT YOUR PR MUST SHOW, each with the command you ran and the number it printed, at the SHA it ran on.
1. The oracle test, green, and a diff of your calibration against data/oracle_slice1.json showing zero differences.
2. Every check has a test built to fail it, and three mutations of your own code, named in the PR body, each of which turned the suite red for the right reason (show the failing test name for each).
3. The full suite and `python3 -m compileall -q .` on 3.9 and 3.14, with the real counts and the interpreter versions.
4. The committed reports regenerate byte-identical (show the cmp), and the report test fails on a stale file.
5. The page at 360, 375, 390 and about 1000 px, dark and light: set the viewport before any capture, assert that scrollWidth equals innerWidth in all eight, read the console, and report the lowest text contrast ratio and which pair it is, computed from the stylesheet's own tokens (a test that computes it is welcome). Say what browser and method you used. A stat tile must not wrap or clip at 360.
6. A privacy sweep by pattern with hit counts (bet-id-shaped tokens, e-mail addresses, home-directory paths, balances), printing no hit that is itself a leak.
7. The honest framing: wherever your PR or the page reports the calibration, it says the result is in sample.

OPEN CHOICES THAT ARE YOURS, each to be justified in a sentence in the PR body: the exact module internals, the action versions in ci.yml and why, how you compute contrast in a test, and the token values you extract from the draft. If anything in the spec is ambiguous, contradicts the oracle, or cannot be built without breaking a boundary, say so in the PR body and stop at a HOLD instead of choosing silently.

THE STANDARD. A claim you could not re-run goes under "Not verified", never "verified". Prefer a failing test you can show over a sentence that says it works.
