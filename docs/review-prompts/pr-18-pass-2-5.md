# PR #18 — Pass 2.5: the Executive Summary Brief (TZ=America/New_York)

The text delivered Sun 1 Nov 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026; its handoff block is `pr-18-pass-3.md`. It was delivered in chat; this copy is recovered from the session's transcript.

---

## Executive Summary Brief: PR #18 · Pass 2.5 · Sun 1 Nov 2026, ET

**Decision: escalated to you.** [PR #18](https://github.com/BeniCheni/settlement-grader-evals/pull/18) passes every clause of the merge gate at head `76e990d`, but the merge word is yours, and Cursor's Pass 3 then does it. It isn't a release, so there's no tag.

### What ships
- **Run a prompt variant:** `run_eval.py --prompt-file` uses the file's bytes as the system prompt. Without the flag, the requests are the same as on main.
- **Judge two runs:** `scorer.judge run-ab` judges every ticket of both runs under the frozen rubrics and reads no human label.
- **Report the A/B:** `scorer.judge ab` gives each metric its own row and nothing is blended. Each threshold shows its limit, what was observed and whether it held.
- **Your ticket rows:** short facts sit on one line with one cell per judge. A changed ticket carries the blood bar and words that name the change without judging it, under a computed "k of n" count.
- **No computed verdict:** your hand-written statement sits on the cover and beside the Set 1 numbers. The ship call stays your sentence.

### What the passes found
- **Pass 1 (Claude): 13 findings, 12 fixed in five commits.** The worst was that no test could catch a wrong figure on the page. The 13th was the ticket layout, which Pass 1 said couldn't fit on one line.
- **Pass 2 (Codex): adjudicated all 13, added 6, six commits.** It built your three rulings and found one more high: malformed threshold input crashed instead of being refused. It also caught its own phone-caption bug from the screenshots.
- **Your four rulings:** Codex recorded them second-hand, and I confirm them as your answers: rebuild the rows now, bar plus words, real metric rows, statement twice.
- **Differences between the vendors, none of which changes what ships:**
  - **Finding 13 (layout):** Pass 2 is right on both counts. It fits on one line, and it's medium under the skill's severity rules because the figures themselves were correct.
  - **Finding 3 (cases file):** Pass 1's fix blamed the cases file for any scoring error. Pass 2 narrowed it, and my probes agree.
  - **Finding 8 (unnamed columns):** Pass 1 said low, Pass 2 medium. It's fixed either way.
  - **Finding 12 (reuse the helpers):** Pass 2 couldn't confirm the attribution to the build prompt, because that prompt isn't archived yet. I hold it, but my search for that wording found nothing clear, so the attribution stays unconfirmed. The fix itself stands.
- **One of my suspicions was wrong:** I doubted Pass 1's statsmodels citation. Pass 2 found the paired function, and I checked the published example myself (below).

### Verification as re-run (this pass only)
- **Tests:** 187 pass on Python 3.9.6 and 3.14.7, and `compileall` is clean. Each of Codex's six commits also passes alone on both, with 180, 182, 184, 185, 187 and 187 tests.
- **CI:** [verify run 41371502233](https://github.com/BeniCheni/settlement-grader-evals/actions/runs/41371502233) passed both jobs at `76e990d`. The PR is clean and mergeable, and the remote has no tags.
- **Figures:** on three rehearsals (24, 23 and 0 of 32 tickets changed), all 14 metric rows and all 32 ticket rows match my own recount. That covers the page, and the Markdown and JSON for what each carries. Code flags came from `scorer.score`, as the spec names; the rest I counted separately.
- **The interval:**
  - It matches my own copy of the formula on all 6,545 possible 32-ticket tables, with a largest difference of 0.
  - It matches the six rows in the spec.
  - It matches the [statsmodels example](https://www.statsmodels.org/dev/generated/statsmodels.stats.proportion.confint_proportions_paired.html) on the digits published there: -0.0643926050711 and 0.2211160178958.
- **Why the threshold is 5 holds:** with no ticket worse, a fall of 4 always has a negative lower limit and a fall of 5 always a positive one. A net 5 with one ticket worse never clears zero.
- **Dress rehearsal, which no earlier pass ran:** I ran the real `run_eval.py` entry path for both variants on fake transports, then `run-ab` and `ab`, and everything exited 0. The two `run_meta.json` files differ only in `run_id` and `system_prompt`. The suite stays green with the outputs in place.
- **Refusals:**
  - All 21 bad threshold files exit 2 with one error, no traceback and outputs untouched.
  - 9 of 10 bad cases files are refused the same way. The tenth has an integer `ticket_result` inside `expected` and is accepted (see follow-ups).
- **Regeneration:** the A/B outputs are byte-identical on both Pythons, and the page's printed command rebuilds it exactly. Both existing reports regenerate with `git status --porcelain reports/` empty, and every protected path matches main.
- **Mutations:** I wrote 77 of my own against the whole suite, and 75 turned it red. The two survivors are listed under the follow-ups.
- **Browser (headless Chrome, both themes):** rehearsal page height at each width:

| Width (px) | 360 | 375 | 390 | 761 | 899 | 1000 | 1400 |
|---|---|---|---|---|---|---|---|
| Page height (px) | 32,043 | 31,510 | 31,114 | 11,364 | 10,385 | **10,057** | 10,545 |

  - **56 cells across four pages:** no horizontal scroll and an empty console. The only external hosts are Google's two font hosts, a real Tab reaches a visible focus ring, and reduced motion matches. Short ticket facts stayed on one line and whole. Verdicts wrapped only between A and B, on the long-value pages at 761 and 899 px.
  - **21 more widths from 320 to 1920 px, on three pages:** also clean.
  - **Your size targets at 1000 px, on the same fake replies:**

| Section | Before (px) | After (px) | Kept | Limit |
|---|---|---|---|---|
| Tickets | 14,115 | 6,853 | 48.6% | 55% |
| Metrics | 2,280 | 778 | 34.1% | 40% |

  - **The whole page at 1000 px:** it fell from 18,797 to 10,057 px, and a run with nothing changed is 7,523 px. The tallest row is B10 at 304 px, which has two judges' reasons, the changed line and its codes.
  - **The bar, by pixel, at 360, 390, 761 and 1000 px:** on the 24 changed rows sampled it runs the full height, and it's absent from the 24 unchanged rows.
  - **The judge and calibration pages:** every element's position and size equals main's in all 20 cells, and their HTML outside the stylesheet is identical.
  - **Contrast:** the lowest I measured is 4.947 in light (lamp ink on lamp background) and 5.239 in dark (blood on panel).
  - **Accessibility tree:** at 1000 px there are 20 real column heads. At 360 px each value is announced with its label.
- **Privacy sweep over the whole diff and commit messages:**
  - No home or temp paths, UUIDs, dollar amounts or private-folder terms, and no e-mails in the diff.
  - Commit e-mails are only the three agents.
  - The three long hashes are in the fixture `frozen.json`, the long digit run is a synthetic z, and the two money words are the tracked system prompt copied into fixtures.
- **Not re-run by me:**
  - Pass 2's 80 mutants and Pass 1's 42 mutants and 90 probes; I ran my own set instead.
  - Safari, Firefox or a real screen reader.
  - Newcombe's paper itself.
  - Text over the cover's gradient: my probe can't compute it, so that pair is Pass 2's claim, on the same cover style as main.

### In sample, or held out
**This PR reports no real result.** Every figure comes from fixtures or rehearsals with fake replies, so none of them means anything about the grader. The real A/B will be in sample too, because the change was chosen by reading these 32 tickets. Only a run on tickets it hasn't seen could show how the change generalizes.

### Risks and accepted costs
- **A tiny `z` can make the primary row read "Held":** with `z` of 1e-05 and a minimum fall edited down to 1, the interval collapses to 3.1 to 3.1. The committed file holds 1.96 and the page prints `z`. Codex added no floor and I agree, because the spec gives no number.
- **Metrics is longer on a phone:** 6,436 px against 2,827 at 360 px, because your ruling puts each value under its own label. The whole phone page still shrank slightly, from 32,531 to 32,043 px.
- **The layout tests only pin the CSS rules:** only a browser proves the geometry, and CI has no browser.

### Follow-ups, none blocking
These can go in one small PR before the package, since re-running `ab` needs no model:
- **Judge table intervals wrap:** all three judge intervals break across lines at every width from 761 to 1920 px, while the code table's never do. They stay readable, but the spec says no short fact breaks.
- **"1 tickets":** the threshold rows print this, as in "Maximum rise (B minus A) 1 tickets".
- **`<wbr>` in metric names:** no test pins it (first survivor), and it makes Chrome's accessibility tree read "needs_ human_ correctness".
- **`log_grade` check:** no test covers it (second survivor). If it were removed, a malformed value would be accepted silently.
- **Google Fonts blocked at 761 px:** `needs_human_correctness` runs 12 px over its cell. The page doesn't overflow, and it fits by 899 px.
- **Inner field types in the cases file:** a wrong type inside `expected` isn't checked, which is next to the follow-up already listed for a non-object `expected`.

### After the merge (mine)
- Add the corrections note to the top of the PR body, as on #15. It still says 168 tests and a two-column grid; the truth is 187 tests and your row layout. Cursor's text stays intact beneath it.
- Record your four rulings in the spec, and archive the build prompt and the briefs.
- Then the real run, on your machine, in its own PR.

### Questions for the owner
Should a changed `net` alone earn the bar: yes or no? I recommend no.
- **What the mark does now:** "Changed: final" means the ticket result, matching the A final and B final cells. Net and leg grades aren't on the page.
- **How often it would matter:** on my rehearsal, 4 tickets moved `net` with the same result, and 2 of those had no mark at all. Your three A/A runs are identical on all 32 tickets, so in the real A/B any such move would come from the prompt.
- **What I'd do instead:** at the run I'd read `scorer.compare` beside the page and name any net-only move in the report. If you say yes, it joins the follow-up PR.
