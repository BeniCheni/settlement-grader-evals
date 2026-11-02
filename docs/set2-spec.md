# Set 2: the spec for step 9

Written Mon 2 Nov 2026 by the PM seat. It is the spec of record for step 9 of `docs/week-2-package.md`. Precedence: the
owner's rulings, then `docs/judge-spec.md` where this spec reuses its contracts, then this spec, then the plan. `AGENTS.md`
outranks all of them on process, and nothing here loosens it. Where this spec says "contract" the name or behaviour is fixed.

## Why this exists

`rule_adherence` answered FAIL on all 40 rows of set 1, so its FAILs carry no information
(`packages/llm-judges/assignment-1/diagnosis.md`). Once a rubric is tightened on set 1's disagreements, set 1 is in sample
for it and only fresh labels can validate it (`docs/week-2-package.md`, "Gates"). Step 9 tightens that rubric once, has the
owner label rows it was not tuned on, and reports its kappa on them. The course does not ask for this; it follows
Assignment 1's pitfall "Keep a held-out slice if you iterate".

**The owner's rulings, Mon 2 Nov 2026.** (1) The tightening is a PASS boundary example beside the FAIL one, the second of the
two options the diagnosis names. The owner chose it without either option being tried on any row. (2) The NEEDS_HUMAN wording
goes in as well, from the owner's ruling of Sat 31 Oct 2026. (3) The rows below stand: the PM seat proposed them and the
owner did not change them.

## The rubric (contract)

`rubrics-set2/rule_adherence.md` is `rubrics/rule_adherence.md` with two changes, drafted by the PM seat and approved by the
owner. `rubrics/` does not change, because set 1's hashes and the A/B's frozen-rubric check read it.

The last "How to judge" bullet becomes:

> A leg graded NEEDS_HUMAN counts as graded. If no leg result was written at all, the answer is PASS for this rubric.

A paragraph follows the existing boundary example:

> A second boundary example: a one-leg Money Line 3-Way on the away team. The tool results showed the match final at 2-4 to
> that team, and the grader graded the leg W. The answer is PASS: re-grading the leg from the facts gives the same W. Stating
> a correct fact is never a reason to FAIL.

The answer format does not change, so the first line is still exactly PASS or FAIL, as the course requires. The judge's model
stays `llama3.1:8b`. **Tightened once:** whatever set 2 shows, this file is not edited and re-measured on set 2.

## The rows (contract)

`labels/set2-plan.json` holds 32 rows in the shape of `labels/set1-plan.json`. They are chosen by this rule, without reading
any output:

1. Every record of `traces/ab-b`, then every record of `traces/aa-1`, each run in `case_id` order, stopping at 32 rows.
2. Skip a record whose `case_id` is A01, C09 or X01, because those tickets share a bet with a boundary example: A01 is the PASS
   example above, and C09 and X01 share three of their four fixtures with the FAIL example's `SMOKE3`. No other case in
   `data/gold.json` shares a fixture with either example.
3. Skip a record whose `tools`, `final` and `status`, as `scorer.traces.load_run` returns them, equal those of a set 1 row for
   the same `case_id`.
4. Skip a `traces/aa-1` record whose `tools`, `final` and `status` equal the `traces/ab-b` record's for the same `case_id`.

That gives 28 rows from `traces/ab-b` (all but A01, A13, C09 and X01; A13 is identical to its set 1 row) and 4 from
`traces/aa-1` (A03, A06, B05 and B06).

**What these rows can show.** They are outputs no label or tuning has touched, so the result can show how the judge agrees with
the owner on outputs it was not tuned on. They are not new tickets: the owner and the rubric's tightening have both seen these
bets, and the owner has seen parts of some of these outputs in the A/B's reading. The judge's earlier `rule_adherence` verdicts
on `traces/ab-b` are in `judgments/ab/`, under the old rubric. The hand-written statement beside the result must say all of
this. New tickets would be a cleaner test, and they need new bets and frozen match facts, so they are out of scope here.

## The order of work

Each step is its own PR, and Git shows the order.

1. **This spec, the rubric and the plan.** Docs and data from the PM seat, reviewed as a fast-track. They merge before any label
   exists. No judge runs on the new rubric before step 3.
2. **The labels, the owner's.** The owner fills the sheet, and no model output or code check goes on it. They merge before any
   judge call on these rows. `sheet` writes outside the repository, because a test refuses a `sheets/` folder at its root.

   ```bash
   python3 -m scorer.judge sheet --plan labels/set2-plan.json --rubrics rubrics-set2 --out ../set2-sheet
   python3 -m scorer.judge import-labels --plan labels/set2-plan.json --sheet ../set2-sheet/labels.csv --rubrics rubrics-set2 --labels labels/set2.jsonl --meta labels/set2-meta.json
   ```

3. **The judge and the report, the PM's.** On Ollama 0.34.0 with the `llama3.1:8b` digest set 1 recorded. If either differs, stop
   and ask. The PM seat writes `labels/set2-provenance.txt` and `labels/set2-rubric-provenance.json` by hand from the record, and
   the owner reads every false pass into `labels/set2-readings.json`.

   ```bash
   python3 -m scorer.judge run --labels labels/set2.jsonl --rubrics rubrics-set2 --adapter ollama:llama3.1:8b --out judgments/set2-llama3.1-8b
   python3 -m scorer.judge report --labels labels/set2.jsonl --readings labels/set2-readings.json --provenance labels/set2-provenance.txt --rubric-provenance labels/set2-rubric-provenance.json --verdicts judgments/set2-llama3.1-8b --md reports/judge-set2.md --json reports/judge-set2.json --html reports/judge-set2.html
   ```

4. **The package.** `packages/llm-judges/README.md` gains the result and its statement. The plan and `README.md` catch up.

**First-pass labels only.** The reported figure uses the labels as imported, with no `--final`. A label changed after seeing a
verdict is no longer blind to the judge, so any correction the owner wants is recorded and reported apart, as in sample.

## Done when

The report gives `rule_adherence`'s agreement, kappa and false passes on set 2, whatever they are, with the hand-written statement
beside them. The bar stays 85% agreement, kappa of at least 0.6 and every false pass read. Meeting it or missing it both finish
this step.

**Calling it held out.** The plan's four conditions decide, and the statement says how each stands: the rubric merged before the
labels (the merge order), it has not changed since (the report's "same text as when the labels were made"), its boundary examples
come from outside the set (rule 2 above), and it was not otherwise tuned on the set (nothing here reads these rows before the
labels merge). The statement also names the shared tickets, and says what a kappa on 32 rows cannot settle.

## Out of scope

The other two rubrics, a fourth judge, new tickets, any retuning after set 2, and re-running the A/B under the new rubric. No code
changes: a dry run with fake replies took these commands from the sheet to the report on the current `main`.
