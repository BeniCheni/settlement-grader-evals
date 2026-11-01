# PR #15 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text delivered Sun 1 Nov 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026; its handoff block is `pr-15-pass-3.md`. It was delivered in chat; this copy is recovered from the session's transcript. One closing aside to the owner, about how the session ended its turns, is left out. The text ends with a question; its answer is not in this file.

---

## Executive Summary Brief: PR #15 · Pass 2.5 · Sun 1 Nov 2026, ET

**Decision: escalated to you.** [PR #15](https://github.com/BeniCheni/settlement-grader-evals/pull/15) passes every clause of the merge gate at head `d5f4888`, but the merge word is yours. Cursor's Pass 3 then does it. It isn't a release, so there's no tag.

### What ships
- **The comparison page:** `reports/judge-set1.html` shows every row's verdict beside your first-pass and final labels, plus the agreement matrices, your change reasons and every reading.
- **The course export:** `export-course --rubric-provenance` also writes `comparison.html`, byte for byte the same page.
- **Readable on a laptop:** each row has its short facts on one line, with Reason, Change and Reading full width beneath. Phone layout is unchanged.
- **No computed claim of trust:** the in-sample statements are your hand-written files, printed verbatim beside the figures.
- **Nothing else moved:** the Markdown and JSON reports, labels, verdicts and rubrics match main. The calibration page renders as it did, and outside its inlined stylesheet its HTML matches main. No model is called.

### What the passes found
- **Pass 1 (Claude Code): 10 findings, three fix commits.** The worst was that the tests couldn't fail the headline figures: 13 of its 17 mutants survived. It also found the 39 px column and left that to you.
- **Pass 2 (Codex): adjudicated all 10, added 6, five fix commits.** It built your two-tier rows and shared the font links. It gave each disclosure a row-specific name and made the test checks independent of production code.
- **Your three rulings:** Codex recorded them as you gave them (two-tier rows now, keep hiding empty cells, share the fonts in this pass).
- **Differences between the vendors, none of which changes what ships:**
  - **Test finding:** Pass 1 called it medium and Pass 2 high. Pass 2 is right, since the skill rates a test that can't fail as high, and it has its fix.
  - **Column finding:** it stays medium, because the skill rates layout defects medium. It only blocked the merge because you ruled "before".
  - **PR body item 8:** Pass 1 says it was claimed beyond its evidence; Pass 2 says it stated nothing false. Both are partly right: the body admitted the gaps but skipped the "Not verified" heading my build prompt asked for.

### Verification as re-run (this pass only)
- **Tests:** 151 pass on Python 3.9.6 and 3.14.7, and `compileall` is clean. All 11 commits also pass on their own on both Pythons.
- **CI:** [verify run 41321250719](https://github.com/BeniCheni/settlement-grader-evals/actions/runs/41321250719) passed both jobs at `d5f4888`. The PR is clean and mergeable, and the remote has no tags.
- **Regeneration:** all six report files come out unchanged on both Pythons, and the page's printed command rebuilds it exactly.
- **Figures:** my own count from the inputs matches the page and the Markdown:
  - 120 rows, 25 disagreements, 41 readings, 0 unread
  - tiles 1, 6 and 19; changed labels 3, 3 and 11
- **Contrast:** the lowest pair is 4.561 (light theme, blood on ground), above the 4.5 bar.
- **Browser (headless Chrome 156, both themes):**

| Width (px) | 360 | 375 | 390 | 760 | 761 | 899 | 900 | 1000 | 1400 |
|---|---|---|---|---|---|---|---|---|---|
| Page height (px) | 82,770 | 81,135 | 80,040 | 67,035 | 31,587 | 29,476 | 29,938 | **28,622** | 31,960 |

  - **Every cell:** no horizontal scroll, no word split or overrun in a short cell, no labelled empty line and no console warnings. The only external hosts are Google's two font hosts, and a real Tab reaches a visible focus ring.
  - **Your 30,000 px ceiling at 1000 px:** it holds, with readings 854 px wide. Before the fix they were 39 px and the page was 292,114 px.
  - **Page rendered without `--final`:** no gaps at 761, 899, 1000 or 1400 px.
  - **Calibration page:** heights and column widths equal main's at 360, 390 and 1000 px.
- **Gap neither earlier pass could close:** with `prefers-reduced-motion: reduce` emulated, the media query matches and nothing animates. Without it, the page has no animation or transition at all.
- **Accessibility tree:** Chrome keeps all 9 tables, and the 41 disclosures have 41 distinct names.
- **Mutations:** 13 of my 14 mutants turned the suite red. The survivor removes the 80-character line limit above 1200 px, and the skill rates a surviving mutant medium. That doesn't block the gate. It can be pinned in step 8's PR, which also touches the stylesheet.
- **Privacy sweep over the whole diff:**
  - 0 home or temp paths, e-mails, UUIDs or amounts
  - the only 8+ digit runs are inside report digests
  - the 24 capitalised phrases are already on main, except one fixture phrase from the banned-word test
- **Not re-run by me:** Pass 1's 20 mutants and 51-case refusal matrix, Pass 2's mutants, and Pass 1's comparison measurements at old heads. I also didn't test Safari, Firefox or a real screen reader.

### In sample, or held out
**In sample, every figure.** The final labels were adjudicated after you saw the verdicts, and the first-pass figures are blind to the judge but still in sample. A set-2 run is what would give an independent test.

### Risks and accepted costs
- **The page is long:** about 29,000 px on a laptop and 80,000 px on a phone, because it shows all 120 rows in full. Nothing was shortened, so near-duplicate change reasons and readings both print.
- **No shared column header at wide widths:** each row carries its own labels instead.
- **Line length is uneven:** readings run 854 px wide at 1000 px but stop at 573 px on wider screens. Both read fine.
- **Layout tests only pin the CSS rules:** only a browser run proves the geometry, and CI has no browser.
- **`--html` can overwrite an input file**, as `--md` already can on main. It's a small follow-up.

### After the merge (mine, in a docs PR)
- Archive the build prompt and the review briefs for PRs #9–#15.
- Update the README and the spec's "One line per label row" wording.
- Record the follow-ups above.

### Questions for the owner
If you say yes to the merge, I'll also add a short corrections note to the top of the PR body. It still says 158 tests and 134,848 bytes; the truth is 151 tests and 138,664 bytes. Cursor's text stays intact beneath the note.
