# Diagnose-and-fix report

The course's template, filled as far as it can be before the runs. Everything down to "A/B results" is written and merged before variant B runs, so
Git shows the thresholds came first. Drafted by Claude, in the PM seat, on 1 Nov 2026; the failure mode's reading is in `diagnosis.md`, and the one change, the order of
the steps and the verdict are the owner's.

## Root-cause diagnosis

**Failure mode:** `GRADE_CONTRADICTS_FACTS`, the grader committing a leg grade the facts contradict: 15 of 32 tickets in `traces/aa-1`, level with `WIN_LOSS_FLIP` for the most of any code.

**Evidence (10 traces):** A03, A06, A09, A11, A12, B02, B09, B12, B13 and C13, with their trace ids in `diagnosis.md`. On each, the tool calls returned the
deciding fact and `settle_ticket` was given W on a leg the facts lose. Where the final answer gives evidence, it is the prompt's example text, a score read
backwards, or a fact that contradicts the grade beside it.

**Root cause (one paragraph):** The grader fetches the deciding fact and then gives a result without ever setting that fact beside the selection.
`settle_ticket` takes a bare list of results, and the prompt's step 3 asks for a result with no comparison before it, so nothing in the loop makes the model
say what the score means for this selection, and W is what it reaches for. Expect the next failure on any leg whose selection did not come true while its fixture
is plain to read.

## The fix

**Variant A (baseline):** the grader's `SYSTEM_PROMPT`, unchanged.

**Variant B (fix):** exactly one change, step 3 of the system prompt. The whole prompt is `variants/compare-first.txt`, and a test proves only this line differs.

```diff
-3. Grade each leg: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a rule says so).
+3. Grade each leg by comparing it with the facts. In the same message as your settle_ticket call, first write one line per leg: the selection, the score or stat from get_match_facts with home and away named, and what that means for the selection. Then give its result: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a rule says so).
```

## The method, written before the runs

The same 32 tickets of `data/gold.json`, both variants, the two adversarial ones kept, run in one session against one Ollama server with the version and the model's digest recorded and
identical. Each delta is read with a paired 95% interval over those tickets: Newcombe's 1998 method 10, the hybrid score interval, with z of 1.96. A delta whose interval includes zero has not
been shown to do anything. Each metric is reported on its own row, and nothing is blended.

**In sample, and said now.** The change was chosen by reading these tickets and the checks were built against `traces/v1`, so every figure this report will hold is in sample. It can show the change moved
these 32 tickets; it cannot show how the change does on tickets it has not seen. The statement the report prints is `statement.txt`.

**The judges, flagged before the results.** On set 1's final labels only `tool_call_accuracy` meets 85% and 0.6 (92.5%, 0.8500, false passes read 0 of 0). `needs_human_correctness` does not (80.0%, 0.3191, false passes read 6 of 6). `rule_adherence` does not (65.0%, 0.0000, false passes read 0 of 0): it answered FAIL on all 40 rows there, so it showed no ability to tell a right grade from a wrong one. That does not prove it will answer FAIL on these runs, but a move in its delta cannot be read as a move in grades, and **its delta is the one to trust least**, though it is the judge closest to this failure. All of those figures are in sample as well.
So the primary metric is the plain-code check, which re-grades legs from the facts in the trace, not from the answer keys.

## A/B results

Not run. Filled in from `reports/ab.md` after both runs are committed.

| Metric | A (baseline) | B (fix) | Delta (pp) | Paired 95% interval |
|--------|--------------|---------|------------|---------------------|
| policy adherence (`rule_adherence`) | | | | |
| escalation correctness (`needs_human_correctness`) | | | | |
| tool-call accuracy (`tool_call_accuracy`) | | | | |
| `GRADE_CONTRADICTS_FACTS` (code check) | | | | |

Sample size: n = 32 per variant.

## Ship / no-ship decision

**Thresholds (written before seeing results):** these are necessary for a ship and not sufficient: ship only if every row with a condition holds, and the owner can still say no. The PM seat drafted them and the owner approved them on Sun 1 Nov 2026. The same numbers are in `thresholds.json`, which the report reads.

| Metric | Source | Holds when |
|---|---|---|
| `GRADE_CONTRADICTS_FACTS` | Code check | B has at least 5 fewer tickets than A, and the paired interval on that fall lies wholly above zero |
| `WIN_LOSS_FLIP` | Code check, on keys mostly unverified | Does not rise |
| `FOLLOWED_TICKET_CLAIM` | Code check, the two adversarial tickets | Does not rise |
| `NO_FINAL_ANSWER` | Code check | Rises by at most 1 ticket |
| `SKIPPED_SETTLE_TICKET` | Code check | Rises by at most 1 ticket |
| `GRADED_WITHOUT_LOOKUP` | Code check | Rises by at most 1 ticket |
| `tool_call_accuracy` | Judge, at the bar | PASS falls by at most 1 ticket (3.1 points) |
| `needs_human_correctness` | Judge, below the bar | PASS falls by at most 2 tickets (6.3 points) |
| `rule_adherence` | Judge, below the bar | Reported only, with no condition: on set 1 it answered FAIL on every row, so a move here is not evidence about grades either way |

Why 5: with n of 32 and no ticket made worse, at any count for A, a fall of 4 has an interval that still includes zero and a fall of 5 does not, so 5 is the smallest fall this method can distinguish. If any ticket gets worse, the interval
rule asks for more: a net fall of 5 with 1 ticket made worse still includes zero. If A has fewer than 5 tickets, this row cannot hold. Why one ticket on the guards: one ticket is 3.1 points, the smallest step 32 tickets allow.

**Which regression is acceptable, and why:** at most one ticket on `tool_call_accuracy`, and at most two on `needs_human_correctness`, in exchange for the primary fall. A wrong WIN books money that is not there, while a wrong escalation costs a manual look, so a small move on the guards is worth a real fall in wrong grades. `needs_human_correctness` gets the wider margin because its kappa of 0.3191 on set 1, in sample, means a move of one or two tickets may be the judge as much as the grader. Anything larger stops the ship even if the primary falls.

**Verdict:** not yet. The owner writes it after the results.

**Why:** not yet.

**What would change my mind:** not yet.
