# PR #38 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text delivered Thu 5 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat; this copy is recovered from the session's transcript, without the note to the owner that followed it. Its handoff block is `pr-38-pass-3.md`. The owner's answer is the merge at `ff673a0`.

---

## Executive Summary Brief: PR #38 · Pass 2.5 · Thu 5 Nov 2026, 09:45 EST

**Decision: escalated to you, and I recommend merging.** The gate holds at `86edeee`: the verdict is "mergeable after fixes", every high finding has a fix commit, `verify` is green, no vendor contests a code choice, and it isn't a release.

### What ships
- **Four guardrails:** G1 is regex over every string the model reads from a ticket. G2 is an LLM judge over the ten free-text fields. G3 is G1, then G2 when a code test finds the text suspicious. G4 is three existing checks plus a payout check on the output.
- **An honest catch:** a G4 block counts only when it fires a check that neither the attack's twin nor its base's control fired.
- **`scorer.guardrails`:** `expand`, `decide-input`, `decide-output`, `report`, `scan`, `transcript` and `test-set`. The report is byte-stable, and its stale test runs once step 8 commits its arguments.
- **`report --guarded`:** it lists rows where only G4 differs, and stops on an input difference, a missed G4 block or a guardrail error.
- **No change when idle:** with no new flag, the grader's requests are what they were.

### What the passes found
- **Pass 1 (Claude Code):** 22 findings, 15 fixed on the branch, including my two corrections. The three high ones were the stale test and those two corrections, each of which would have stopped step 8.
- **Pass 2 (Codex):** accepted all 22, disputing some characterisations, and built your four answers. It added two high findings, both fixed: the stale test compared text, so changed line endings passed, and a malformed trace gave a traceback.
- **Pass 2.5 (me):** three more, fixed in Codex's continuation: `--guarded` listed rows G4 never saw, because of my wording; a test that step 7 would have turned red; and nine of my 30 mutants survived.
- **Still contested:** nothing in the code. Codex's objections are to how some findings were worded.

### Verification as re-run
| Check | Result |
|---|---|
| Every commit from a clean copy, Python 3.9.6 and 3.14.7 | All OK with `compileall` clean: 303 to 353 (Cursor), 354 to 372 (Pass 1), 374 to 392 (Codex), one expected skip from `aedab1e` on |
| `verify` at the head | Run 42046490976, green on both |
| Squash result | Tree `ac886e8`, the same as the head's, because main hasn't moved |
| My mutants at the head | 37 of 37 killed on both Pythons, including the nine that survived before |
| Grader with no flags, against the fork point (32 tickets, 5 endings) | Same hash on both Pythons |
| Decisions regenerated | G1's rows identical on two runs; G4's differ only in latency; both metadata files identical |
| G4 at run time against G4 from disk (12 dev rows, fake model, at `4f1d715`) | Same on all 12, so no false stop there |
| Four commands | No traceback, and a run with no flag doesn't import the guardrails |
| Scope | No test on main changed, and nothing moved under `docs/`, `labels/`, `traces/`, `reports/` or `packages/` |
| Privacy sweep | Only agent e-mail addresses, and no home paths. Seven dollar figures, one brand token and one event id are all copied from data already on main |

**Not re-run by me:** Codex's own mutants, rehearsal script and 61-case refusal matrix, and the oracle by hand, which Pass 1 and Codex each worked out. I also ran my private check of the withheld files at this head, and nothing about them is stated here.

### In sample, or held out
No rate is reported. G1 and `suspicious` were written while reading dev, so the committed G1 decisions on dev and G4 decisions on the recorded attacks are in sample. Step 8 on the reserve is the first held-out test. I wrote those rows, so the hand-written statement has to say the PM wasn't blind to them.

### Risks and accepted costs
- **G1 still misses:** dots or underscores between words, combining marks and variation selectors, lookalikes outside its map, short encoded blobs, paraphrases, and, by reading the code, text inside a value that isn't a string. The ship report has to state these.
- **G2 doesn't read the six extra fields,** so G1 alone covers them.
- **`report` doesn't compare `guard_meta.json`,** so decisions made from another cases file pass if their ids fit.
- **How many rows `--guarded` will list is unknown** until a real session.
- **No model has met any of this.** Real G2 timing, and memory with two models alternating, are first tested at step 8, on a machine that has frozen once.
- **The spec on main lags the code** until my docs PR records your answers and the corrections.

### Questions for you
**Merge #38? I recommend yes.** To say yes, paste the Pass 3 brief into Cursor on Grok 4.7 Medium.
