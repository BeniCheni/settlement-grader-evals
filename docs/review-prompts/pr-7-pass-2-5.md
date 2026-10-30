# PR #7 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text written Thu 29 Oct 2026, against head `26671e4`; its handoff block is `pr-7-pass-3.md`, as archived by the PM seat (Claude). It was delivered in chat, one line per paragraph; this copy is the archive, and the comment it led to is on the PR.

---

## Executive Summary Brief: PR #7 · Pass 2.5 · Thu 29 Oct 2026, ET

**Decision: escalated to you.** [PR #7](https://github.com/BeniCheni/settlement-grader-evals/pull/7) passes every check the merge gate in `AGENTS.md` asks for, at head `26671e4`. Merging is your call, and Cursor's Pass 3 does it once you give the word. It is not a release, so there is no tag.

### What ships
- A new command, `python3 -m scorer.judge`, with eight subcommands. They cover choosing the label set, making the owner's label sheet and importing it, running a local Ollama judge and reading its reply strictly, checking adjudicated labels, reporting each judge against the labels, and exporting the course's files.
- **It refuses to overclaim.** Nothing the code computes says "held out"; that statement must come from a provenance file written by hand. A rubric edited after the judge ran is refused at export. A run made from canned replies is labelled `http-fixture`, not Ollama. No machine path reaches a committed report.
- **Kappa exactly at the bar now counts as meeting it.** `cohen_kappa` keeps whole-number counts until one final division, so 3/5 equals 0.6.
- **The worst judge is chosen on the exact kappa.** Two judges whose kappas print the same at four decimals are still told apart.
- **No model is called and nothing is downloaded.** The tests use fixtures only.

### What the passes found
- **Pass 1 (Claude Code, fresh session): 20 findings, 12 fix commits.** The two high ones were a "no network" test that could not fail and an export that could ship the wrong rubric.
- **Pass 2 (Codex): adjudicated all 20, and added 7 of its own with 8 fix commits.** It corrected Pass 1's kappa count: 220 tables sit at exactly 3/5, and 32 of those were the ones that failed. It showed that the worst-judge ranking could pick the *wrong* judge. It also found the build-prompt archive missing.
- **Your rulings:** the five Pass 1 answers, then exact-kappa ranking, then the archive.
- **After the rulings:**
  - I added the archive (`83ab5cb`), and Codex read it cold.
  - Codex then fixed the ranking (`26671e4`).
- **Nothing is still disputed between the vendors.** Codex marks one thing not verified: that the archived text is the prompt exactly as I delivered it. The archive matches my saved copy byte for byte, but only you can confirm the chat history.

### Verification as re-run (this pass only)
- **Tests:** 105 pass on Python 3.9.6 and 3.14.7, and `compileall` is clean on both.
- **CI:** [`verify` run 40996742228](https://github.com/BeniCheni/settlement-grader-evals/actions/runs/40996742228) is green on both jobs at `26671e4`.
- **Regenerated files:** the three calibration reports and the two judge fixture reports come out byte-identical on both Pythons.
- **Existing files touched:** only `.gitignore`, `scorer/stats.py` (+6 / −4) and `tests/test_stats.py` (+35 / −0, no line removed). Nothing in `README.md`, `CHANGELOG.md` or any version string.
- **Kappa:** an exact enumeration of every table up to 60 rows finds 220 at kappa 3/5, and none now fails the kappa comparison. At 40 rows, no two different kappas collide.
- **Mutation:** when I made the ranking use the rounded kappa, the two new ranking tests failed, as they should.
- **Whole PR:** 28 files, +4,591 / −4. 23 commits: 1 by Cursor, 13 by Claude (12 review fixes plus the archive), 9 by Codex. The remote has no tags.
- **Not re-run by me:** the live Ollama call (Pass 1 ran it once with `qwen3:8b`), and Pass 1's 35 and Codex's 18 mutations beyond the one I ran.

### In sample, or held out
**Neither.** This PR reports no agreement on real labels: every number in its tests is made up. The first real result comes at step 6, after your rubrics (step 4) and your labels (step 5) are merged in that order.

### Risks and accepted costs
- **Writes are not crash-proof.** If a write fails, earlier files are restored, but a killed process could leave a partial output.
- **"No network" is checked, not enforced.** The tests watch the network calls they know about; there is no operating-system sandbox. Codex sized that at 30–80 lines and deferred it.
- **Fallback judge models are checked lazily.** A same-family candidate is refused only when the command reaches it, per your ruling 4.
- **Step 4 must change one test.** A test asserts that `rubrics/` doesn't exist yet, so the step 4 rubrics PR has to edit it (one line).

### Questions for the owner
1. Merge PR #7 through Cursor's Pass 3? (the button)
