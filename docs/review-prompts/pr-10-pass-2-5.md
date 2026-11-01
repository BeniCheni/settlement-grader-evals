# PR #10 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text delivered Fri 30 Oct 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026; its handoff block is `pr-10-pass-3.md`. It was delivered in chat; this copy is recovered from the session's transcript.

---

## Executive Summary Brief: PR #10 · Pass 2.5 · Fri 30 Oct 2026, ET

**Decision: escalated to you.** [PR #10](https://github.com/BeniCheni/settlement-grader-evals/pull/10) passes every check the merge gate in `AGENTS.md` asks for at head `17e185a`. Merging is your call, and Cursor's Pass 3 does it once you give the word. It is not a release, so there is no tag.

### What ships
- **A run records its setup:** every grader run now saves the Ollama version and the model's digest in `run_meta.json` (your decision 5a). If either can't be read, the run stops before grading anything or creating a folder.
- **`python3 -m scorer.compare A B`:** it reports which tickets each run has, which final answers differ, each failure code's count in both runs, and the setup fields that differ, plus whether each run recorded its setup. It prints each run's in-sample sentence. It draws no conclusion from the differences.
- **Your two refusals (exit 2):** a run outside the working directory, including through a symlink, and a run whose trace file holds no records.
- **On the real data:** the three A/A runs show no differences at all, and v1 against aa-1 shows 21 different final answers. Neither pair recorded its setup, so neither difference can be traced to one, and `compare` says so.

### What the passes found
- **Pass 1 (Claude Code, fresh session): 11 findings, 7 fix commits.**
  - High: `compare` crashed on 18 of 22 malformed inputs, and two HTTP errors escaped `run_eval`'s setup read.
  - Medium: unwritable `--json` paths; tests writing real runs under `traces/`; a network guard that could be bypassed; and mutated code that the suite didn't catch.
- **Pass 2 (Codex): accepted all 11, and raised several to high** under the skill's rule that every test must be able to fail its claim. It added your two refusals and found 5 issues of its own:
  - a `--json` write that could truncate an existing file;
  - record ids of the wrong type crashing the duplicate check;
  - trace or metadata files symlinked out of a run folder;
  - a raw-socket bypass of the network guard;
  - an over-claiming docstring.

  It fixed all five in 5 commits.
- **Nothing is still disputed between the vendors**, and Codex has no questions for you.

### Verification as re-run (this pass only)
- **Tests:** 134 pass on Python 3.9.6 and 3.14.7, and `compileall` is clean on both. [`verify` run 41083233317](https://github.com/BeniCheni/settlement-grader-evals/actions/runs/41083233317) is green at `17e185a`.
- **Committed outputs:** all three committed `compare` outputs (aa-1/aa-2, aa-2/aa-3, v1/aa-1) regenerate byte-identical on both Pythons.
- **Refusals:**
  - a run outside the working directory, a symlink pointing outside, and an empty run each exit 2;
  - an absolute path inside the repo still works.

  When I removed the outside-directory refusal, the refusal test failed on every case.
- **Scope:** the existing files changed are `.gitignore`, `run_eval.py` and one docstring line in `scorer/score.py`. No committed run under `traces/` changed. There are 16 commits: 4 by Cursor, 7 by Claude, 5 by Codex.
- **Not re-run:** the live Ollama path, which no pass ran, and the two reviewers' other mutations.

### In sample, or held out
**Neither.** `compare` reports counts from code checks that were built against `traces/v1`, and it prints each run's in-sample sentence beside them. It reports no agreement figure.

### Risks and accepted costs
- **The live setup read is untested** against a real Ollama server. To verify it, read `/api/version` and `/api/tags` once, which needs no model call.
- **A known crash remains for a follow-up PR:** a case entry whose `expected` field isn't an object crashes `scorer/checks.py`, in both `compare` and `scorer.score`.
- **Not tested:** Windows path behaviour, and output to a terminal that isn't UTF-8.
- **One stale line:** the PR body still names the old head `dc68c2e`. It's cosmetic.

### Questions for the owner
1. Merge PR #10 through Cursor's Pass 3? (the button)
