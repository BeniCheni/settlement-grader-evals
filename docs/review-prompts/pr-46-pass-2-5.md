# PR #46 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text delivered Thu 5 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat; this copy is recovered from the session's transcript, without the handoff block, which is `pr-46-pass-3.md`. The owner's answer is the merge at `c2ecc6e`.

---

## Executive Summary Brief: PR #46 · Pass 2.5 · Thu 5 Nov 2026, 22:00 EST

**Decision: ready to merge at `490f05d`.** Every merge condition holds:
- Both reviews say "mergeable after fixes."
- Every high finding has a fix commit.
- CI (`verify`) passes at the head.
- Nothing is in dispute between the reviewers.
- It isn't a release.

Cursor does the merge (Pass 3) once you say go. There is no tag.

### What ships
- **`decide`** sends each row's free text to TypeSafe's `jev-1.14.0` with your key, records the two probabilities exactly as returned, and sorts each row:
  - block at 0.9 or more;
  - allow at 0.1 or less;
  - review in between.

  It stops before writing anything on a bad key, a broken or redirected reply, or a bad `--out`. No path prints the key.
- **`report`** prints, for dev, reserve and the two combined:
  - catch, over-block and review, each with a confidence range;
  - whether every attack Jev can see was blocked (ruling 60);
  - G2's results side by side;
  - each band's error rate;
  - three calibration bins on the winning probability, with a chart (ruling 63);
  - a cost search capped at 8 reviews (ruling 65).

  It refuses any decisions file `decide` couldn't have written.
- **Test runs can't pass for Jev.** A run with invented answers says `adapter: fake` (ruling 64).
- **Jev's catch bar is now 17 of 20.** Nothing about Jev is measured yet, and no decisions or report are committed.

### What the passes found
- **Pass 1 (Claude Code):** fixed three high findings in four commits:
  - the key printed when it ended in a newline;
  - tracebacks on broken replies;
  - a redirect sent the key to another server.

  It also moved the `--out` check before any request and added tests for eight rules no test could catch breaking. Two gaps it could not fix itself became rulings 64 and 65.
- **Pass 2 (Codex):** confirmed every Pass 1 fix, and coded rulings 64 and 65 and my spec changes. It found three more problems and fixed them:
  - report accepted rows `decide` would refuse (high);
  - very large numbers in a reply's JSON crashed with a traceback (high);
  - refusals printed a usage line on top of the error (medium; now one line).

  It also corrected me. My reason for leaving the float-rounding issue alone (F9) was wrong: a 17-digit rendering of 0.1 trips it too, not only 20-digit values. The outcome is unchanged, because report refuses such a file loudly. One code mutation went uncaught, but it removes a check that another check already does, so nothing is unguarded.
- **Pass 2.5 (me):** confirmed the results below. Nothing is disputed.

### Verification I re-ran this session
- **Tests:** 461, OK, 1 skipped, on Python 3.9.6 and 3.14.7, one at a time. Compile check clean, and no stray files afterwards. CI run 42152443449 passed on both at `490f05d`.
- **Scope:** since my docs commit, only `scorer/jev.py` and `tests/test_jev.py` changed.
- **The key:** I tried seven bad key shapes on both Pythons: a trailing newline, a trailing carriage return, a line break inside, a non-ASCII letter, only spaces, a space inside, and a valid key aimed at a closed port. Each stops with exactly one line and no traceback, never shows the key, and writes nothing.
- **A rehearsal of your run, offline:** I invented answers for all 49 rows, then ran `decide` and `report`.
  - Both ran through, with identical output bytes across two runs and both Pythons.
  - The meta file says `fake` with no endpoint, and the model line reads `model: jev-1.14.0; adapter: fake`.
  - In every section the bins add up to the rows.
  - G2's numbers match step 8's committed results.
  - The cost line respects the cap and says reviews were priced at nothing.
  - The chart has axis titles, a section title and the perfect-calibration diagonal.
  - The real stale test passes, fails after I changed one byte, and passes again once restored.
- **Six code mutations of my own,** all caught:
  - the review cap compared strictly;
  - the cap hard-coded to 8;
  - the review bar compared strictly;
  - a web address written for a fake run;
  - the adapter check between slices removed;
  - P2's block counted toward the attacks Jev can see.

  One of my first attempts was malformed and I redid it correctly.
- **Privacy:** a counts-only scan of Codex's code, commit messages and comment is clean.
- **Not re-run:** Codex's 30 mutations and its fake-server tests, and anything against TypeSafe itself.

### Can the numbers be trusted as a fresh test?
Nothing in this PR measures Jev; the rehearsal's numbers are invented. After your run:
- **Jev's results on the 40 rows** come from a model nobody tuned on them, using a question fixed before it ran. They still aren't a clean held-out test, because I wrote the reserve rows and they've been public since step 7.
- **The cost search** picks its band pair on those same 40 rows, so it measures nothing independent, and its line says so.

### Risks and accepted costs
- **Key format:** TypeSafe doesn't publish one. If your key holds a space or anything outside plain ASCII, `decide` stops before sending anything and shows nothing of the key.
- **Rounding at exactly 0.1 (F9):** if TypeSafe writes 17-digit numbers and a row lands at exactly 0.1, `decide` records it as review and `report` refuses the file. The fix and a re-run of the 49 rows would cost under a cent. Storing the returned text instead would be about 20 to 40 lines; not done.
- **Error format:** Jev's errors are now one line, while the guardrail and judge commands print a usage line too. A later slice can make them match.
- **Still open from before:**
  - the builder's one oversized commit (the next build prompt asks for smaller ones);
  - the colophon test race, which no pass saw (a later slice);
  - Braintrust's copy of your key, which you may delete.

### Questions for you
You made rulings 64 and 65 yourself in this conversation, so there's nothing second-hand to confirm. The only open question is the merge, in the box below.
