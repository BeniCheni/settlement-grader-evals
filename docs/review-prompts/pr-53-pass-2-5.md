# PR #53 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

Written Sun 8 Nov 2026 by the PM seat (Claude) and archived the same day. The chat carried it with the Pass 3 brief, which is `pr-53-pass-3.md`; this is the brief as saved in that session. The owner's two questions had been answered by then, as rulings 43 and 44.

---

## Executive Summary Brief: PR #53 · Pass 2.5 · Sun 8 Nov 2026, 10:41 EST

**Decision:** cleared for Pass 3 to merge at `5e055dd`. The gate in AGENTS.md holds: the verdict is "mergeable after fixes" with every fix on the branch, CI passed, nothing is contested after your rulings 43 and 44, and it is not a release. One condition stays open under ruling 42: Cursor's cold read of Claude's last two commits. If that read finds anything, Cursor merges nothing and the PR comes back to me.

### What ships
- Four RAG scorers read from recorded runs: context recall, context precision, faithfulness and answer relevancy.
- `python3 -m scorer.rag run` and `report`: a paired A/B with bootstrap intervals and three bars, and two tables per variant.
- A refusal: `report` won't compare two runs whose metadata differs anywhere but `run_id`, `rule_match` and `outcome_matches`.
- The Braintrust uploader, which has never been run and prints no experiment id for a pair with holes in it.
- No measurement yet. v1 isn't frozen, so no Week 4 run or report exists.

### What the passes found
- Pass 1 (Claude Code): 9 findings, 1 high, fixed in 5 commits. The high one was a suite the next three planned commits would have turned red.
- Pass 2 (Cursor, under ruling 42): reproduced and accepted all 9, and made rulings 39 and 40 and the decision on finding 7 in 3 commits.
- Cold read of those 3 commits (Claude Code): 1 medium and 1 low, both test gaps, fixed in `2e57070` and `5e055dd`. No wrong number was found.
- Correction: Cursor's Pass 2 comment put 399 lookups over 180 records. 399 is all 192 records of the six runs, and the count over the 180 real-row records is 377. Pass 3 corrects it on the PR.
- Contested: only finding 5's severity, closed as medium by ruling 44.

### Verification as re-run
- 578 tests OK on Python 3.9.6 and 3.14.7, `compileall` exit 0, `git diff --check` clean, at `5e055dd`.
- Each of Cursor's and Claude's last commits passes alone on 3.9.6: 575, 576, 577, 578, 578.
- CI run 42495011846 passed on both jobs at `5e055dd`.
- 15 deliberate breaks of the table rows and ruling 40's code all fail the tests at the head. Seven of them, on the rows, passed at `afc1b95`.
- `score_case` didn't change between `a7a5675` and `afc1b95` on 241 recorded real-row records. The last two commits touch only tests.
- With a two-row stand-in v1: the suite passes 578 after the hash, after the ids, and after the statement, both runs and the report. `run` and `report` exit 0 through the real `run_eval.main` on a scripted fake model, and no machine path reaches any output. The report's bytes match on 3.9.6 and 3.14.7.
- Lookup counts: 180 records, 377 calls, 48 errored, 0 non-string topics; 192 records, 399 calls, 48, 0.
- Ruling 43's case: precision reads 1 of 2 when the integer 3 and the string "3" collide, and 1 of 3 when they don't.
- Whole PR: 9 files, +3,003 / −0. No file outside the allowed paths changed, no test on main changed, and `scorer/stats.py` loses no line.
- Privacy sweep of all added lines and 13 commit messages: 0 e-mail addresses other than the agent identities, 0 home paths, 0 private folder names, 0 balance or account words, 0 dollar figures, 0 digit runs of six or more, 0 bet-id shapes. The 5 distinct capitalised spans are product, model and market words, and none is a person's name.
- Not re-run: the uploader, which the PR forbids running, and Claude Code's 18-cell mutation list as written. I ran my own 15 instead.

### In sample, or held out
Every number here comes from the recorded runs over the 30 real rows, which the alias table and spec were written from, or from fixtures. All of it is in sample, and none is a v1 result. A frozen v1 and the two Week 4 runs (step 9) are what would make the A/B a real measurement.

### Risks and accepted costs
- The uploader's first real run is yours, and it's the first time that code meets the SDK.
- The real model has never driven this path. Only a scripted fake has.
- `run --root` checks one tree while `run_eval` writes to another. The contract's commands never pass `--root`, and I'll note the limit in the spec.
- Ruling 43 accepts a rare id collision: one retrieved item fewer in a ticket that sends the same topic both ways.

### Questions for the owner
None left. Rulings 43 (yes, may share an id) and 44 (finding 5 is medium) are recorded.
