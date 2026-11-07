# PR #51 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

Written Sat 7 Nov 2026 by the PM seat (Claude) and archived the same day. The chat carried its findings in short form, with the Pass 3 brief, which is `pr-51-pass-3.md`; this is the brief as saved in that session. The owner's one question was answered "Yes, Cursor", which is ruling 36.

---

## Executive Summary Brief: PR #51 · Pass 2.5 · Sat 7 Nov 2026, 15:51 EST

**Decision:** cleared for Pass 3 to merge at `b188b82`. The gate in AGENTS.md holds. The verdict is "mergeable after fixes", with every fix on the branch, including the one high finding. `verify` is green, nothing is contested and it is not a release. One condition stays open, under ruling 35: Cursor's cold read of Claude's last two commits. If that read finds anything, Cursor merges nothing and the PR comes back to the PM.

### What ships
- The A/B switch: `--rule-match exact|alias` and `--disable-tool lookup_rule`. With no flag, or with `exact`, a run sends and writes what main's does.
- The golden-set tooling: draft, key, check, pilot and freeze. Every key comes from code and none from a model.
- Rulings 30 to 34 in code. An own-goal first scorer is NEEDS_HUMAN, and cards count yellow plus red. A boosted ticket prints its boosted price. An owner's hand-crafted key holds. Freeze writes all three files or none.
- The LangSmith pin script, which has not been run.

### What the passes found
- Pass 1 (Claude Code): 16 findings, fixed in 5 commits.
- Pass 2 (Cursor, under ruling 35): reproduced and accepted all 16, and applied rulings 30 to 34 and decisions A to C in `31002f1`. It contested nothing.
- Cold read of `31002f1` (Claude Code):
  - Every ruling and decision holds.
  - 1 high finding: the test for ruling 32's unboosted leg prices compared a value with itself.
  - 2 medium: decision C's "with a line" and "only those two texts" had no test.
  - 2 low: the freeze refusal always named `v1.jsonl`, and a duplicate import.
  - Fixed in `d622154` and `b188b82`.
  - Push count settled at 15: Pass 1's 30 counted each leg without a side twice.
- This pass: corroborated, below.

### Verification as re-run
- 522 tests OK on Python 3.9.6 and 3.14.7, `compileall` exit 0 and `git diff --check` clean, at `b188b82`.
- `verify` run 42406979206 is green on both jobs at `b188b82`.
- 13 mutations of the ruling code all fail the tests at `b188b82`. Three of them (legs boosted before the ticket price, decision C's text without a line, a third exact text) pass at `31002f1`, which confirms the cold read's findings 1 to 3.
- The two fix commits remove two test lines: a duplicate import, and the self-comparison. Stronger assertions replace the self-comparison.
- Real rows: 25 of 30 agree with `data/gold.json` on every leg, the ticket result and the net, and 28 of 30 on the ticket result and net. 6 of the gold file's 32 keys are `verified_by_beni`.
- Privacy sweep of the two commits and the cold read's comment:
  - 0 e-mail addresses other than the agent identities;
  - 0 home paths and 0 person's names in the commits;
  - every hit in the comment is a pattern name, a SHA, a run id or a market name.
- Not re-run here: the push count of 15. Two reads agree on it; the PM did not re-derive it. Nobody has run the LangSmith script.

### In sample, or held out
Every number above is in sample. The 25 and 28 come from the 30 real rows the code was built and fixed against, scored against keys of which the owner has verified 6. They show that the code reproduces the gold file's keys, not that it is right on new tickets. The held-out evidence comes later: the owner's check of the drafted synthetic rows, and the pilot.

### Risks and accepted costs
- Decision A's "MOOT also passes once another leg is L" is also written on a lost parlay's only losing leg, where it can never apply. It is inert, not false. The PM will say so in the spec rather than change the code.
- Left for a later slice, each small:
  - tests for two branches no ruling covers;
  - "1st Goal Scorer" is read as anytime by both the old and the new code, and no market uses that spelling;
  - a boost text without a percentage would leave the price unboosted, and all three texts have one;
  - freeze can leave one file written if the disk fails between writes, though a failed check never does.
- The PR description still names a LangSmith call the script no longer makes. Pass 3 corrects it before the merge.

### Questions for the owner
1. While Codex has no credit, may Cursor give the cold read of the PM's docs PR, which records rulings 30 to 35, amends the spec and archives the briefs? AGENTS.md sends a Claude-written PR to Codex. Yes or no.
