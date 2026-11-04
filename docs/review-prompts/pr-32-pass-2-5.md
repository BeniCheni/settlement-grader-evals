# PR #32 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text delivered Tue 3 Nov 2026, as archived by the PM seat (Claude) on Wed 4 Nov 2026. It was delivered in chat; this copy is recovered from the session's transcript. Its handoff block is `pr-32-pass-3.md`. The owner's two answers are the merge at `9c33814` and ruling 32.

---

## Executive Summary Brief: PR #32 · Pass 2.5 · Tue 3 Nov 2026, 22:59 EST

**Decision: escalated to you, and I recommend merging.** The gate holds at `baf7df3`: the verdict is "mergeable after fixes", both high findings have fix commits, `verify` is green, nothing is contested between vendors, and it isn't a release.

### What ships
- A poison overlay that changes a matching tool result and marks it on the trace and in `render_case`, so a poisoned fact can't pass as real.
- Follow-up turns under the grader's shared budgets, including the wall clock.
- `grade_ticket_guarded`: a blocked run returns a held final that names nothing, and the grader's answers are kept under `*_withheld` keys.
- `run_eval.py --drop-field`, plus refusals of bad cases before anything is written.
- The Promptfoo exec target and both configs, with `timeoutMs` at 720000.

With none of these in use, the grader's requests are unchanged, so Week 3 can still be compared with earlier runs.

### What the passes found
- **Pass 1 (Claude Code):** 13 findings, with fixes for the untested target wiring and for silent overwrites in a run directory.
- **Pass 2 (Codex):** accepted all 13, disputing two characterisations, and added its own. Two were high and are now fixed: follow-ups could run past the wall-clock budget, and the atomic write still had no test that could fail it.
- **Pass 2.5 (me):** I reproduced both of those and found nothing new in the code. The remaining differences are about what a test or number proves, and no code choice is contested.

### Verification as re-run
| Check | Result |
|---|---|
| Codex's four commits, one by one, on Python 3.9.6 and 3.14.7 | 245, 247, 248 and 248 tests, all OK, `compileall` clean |
| Merge result with `main` (tree `6d5da84`) | 248 tests OK on both, differs from the head only under `docs/` |
| `verify` at the head | Run 41767764787, green on both |
| Idle requests against the fork point, 32 gold tickets × 5 endings | Same hash on all four runs |
| Worst-case time on a fake clock | Was about 3,950 s, now at most 659 s |
| Mutants at the head | 12 of 12 now fail a test, including the atomic write |
| Scope | No test on `main` changed, the golden is only in `c2618ff`, no file outside the agreed set |
| Privacy sweep | No home paths in the code or commit messages (the only matches, in the PR body and comments, are pattern literals); only agent e-mail addresses; no dollar figures in the diff |

**Not re-run by me:**
- Codex's telemetry capture.
- Its comparison of the files `run_eval.py` writes; I compared requests, returned values and spans.
- A real five-minute ticket, which isn't allowed until step 3.

### In sample, or held out
Neither applies: this PR reports no result on real data, and every number comes from a fixture.

### Risks and accepted costs
- **720 s isn't a hard limit:** it covers the worst case only if each request stops within its timeout, and a very slow response could run longer. Promptfoo also doesn't kill a ticket that times out.
- **A crash between the two file writes:** this can leave `n_cases` one behind with no warning. The spec excludes crashes mid-write, so this stays as it is.
- **Promptfoo's error cells can contain a machine path:** step 3's notes and step 6's report must never paste one unscrubbed.
- **Step 3's assertions must check `status`:** a follow-up that ends unparseable still returns the last good final.

### Questions for you
**1. Merge #32? I recommend yes.**

**2. Accept or block Promptfoo's telemetry event? I recommend Block.** This doesn't affect the merge; it only decides how step 3 runs.

- **What Codex's capture claims:** one POST per run despite the disable flag, carrying a persistent ID and runtime details, with no matches for ticket data, paths, usernames or e-mail addresses.
- **Why block:** the plan promises telemetry off and no traffic beyond `127.0.0.1`, and real tickets go through this process at step 3.
- **What I tested:** a per-run sandbox edits no system file. External connections were denied, loopback stayed open, and the real Promptfoo proof passed with empty stderr.
- **The cost:** it's macOS-only, and it hasn't yet run with a real Ollama. If it fails at step 3, I'll stop and ask rather than run without it.
