# The LLM judges package

The deliverables for Week 2 of the AI Agent Evals course: three judges validated against human labels, and one A/B
decision. Assembled by the PM seat (Claude) on Mon 2 Nov 2026. The notes below say who wrote each file or that a command generated
it. The acceptance items are the course's words, from its repository at commit
`51a59c2f6c9bb55806da764aaf585884b811a747`, under `week-02-designing-reliable-llm-judges/assignments/`.

**In sample, every figure in this package.** Assignment 1's final labels were adjudicated after the owner saw the judge's
verdicts, and Assignment 2's change was chosen by reading the same 32 tickets it was tested on. These files show how the
judges compare with the owner's labels on these rows and what one change did to these tickets, not how either would do on
ones it has not seen. Step 9 of `docs/week-2-package.md`, tightening one rubric and checking it on fresh labels, has not
been done.

## Assignment 1: build and validate a judge

| Acceptance item | File | Note |
|---|---|---|
| 3 judge prompts, one criterion each, strict `PASS`/`FAIL` + reason output format | `assignment-1/rubrics.md` | Generated: each rubric verbatim, with its SHA-256 |
| 40 outputs labeled by hand against all 3 rubrics (120 labels) | `assignment-1/labels.jsonl` | Generated from the owner's final labels. The first-pass labels are `labels/set1.jsonl` |
| Agreement matrix per judge (4 cells with counts) | `assignment-1/results.md`, `assignment-1/comparison.html` | Generated. The page also shows every row's verdict beside the labels |
| Cohen's kappa reported per judge; kappa ≥ 0.6 before the judge is "trusted" | `assignment-1/results.md`, `assignment-1/comparison.html` | Generated. Each judge's agreement and kappa sit beside the owner's statement on the page, and the repo's bar also asks for 85% agreement |
| Written note on the worst judge: its dominant failure mode (false-pass or false-fail?) | `assignment-1/diagnosis.md` | Written by the PM seat from the owner's labels and rulings |
| At least one label changed on adjudication, with the reason written down (if none did, say so and why — perfect first-pass labels are suspicious) | `assignment-1/diagnosis.md`, `assignment-1/comparison.html` | The owner's reasons |

The course's comparison view is `assignment-1/comparison.html`, in place of a Braintrust screenshot; the course says the
rubrics and the validation are graded, not the platform. Its optional stretch, a bias-corrected pass rate, has not been
done.

## Assignment 2: diagnose and compare

| Acceptance item | File | Note |
|---|---|---|
| One-paragraph root-cause diagnosis grounded in 10 traces (trace IDs listed) | `assignment-2/diagnosis.md`, `assignment-2/ab_report.md` | Written by the PM seat |
| Exactly one change between A and B (documented as a diff) | `assignment-2/ab_report.md`, `variants/compare-first.txt`, `assignment-2/comparison.html` | The page computes the diff from the two runs' recorded prompts |
| Same input set (n ≥ 30) run through both variants, full suite, no eyeballing | `traces/ab-a`, `traces/ab-b`, `judgments/ab/` | 32 tickets per variant, 192 verdicts |
| Per-metric deltas reported for all 3 judges (pp deltas, not a blended average) | `assignment-2/ab_report.md`, `assignment-2/comparison.html` | Generated page. The report's table is filled from `reports/ab.md` |
| Ship/no-ship decision with numeric thresholds stated upfront (e.g. "ship if tool-call accuracy ≥ 90% and no metric regresses > 3pp") | `assignment-2/ab_report.md`, `assignment-2/thresholds.json` | The PM seat drafted the thresholds and the owner approved them. The verdict is the owner's. The thresholds merged before variant B ran; see below |
| "What would change my mind" section filled in | `assignment-2/ab_report.md` | The owner's words |
| Any judge below the trust bar is flagged, with which delta you trust least | `assignment-2/ab_report.md`, `assignment-2/comparison.html` | Flagged before the results |

The course's comparison, "or the equivalent from your tool of choice", is `assignment-2/comparison.html`.
`assignment-2/statement.txt` and `assignment-2/thresholds.json` are inputs to the report, and the statement's first line names
who wrote it.

## How to check it

Run these from the repository root. The first writes four files in `assignment-1/` and leaves `diagnosis.md` alone. The
second rebuilds the A/B page, and the third copies it here. No command here calls a model.

```bash
python3 -m scorer.judge export-course --labels labels/set1.jsonl --final labels/set1-final.jsonl --readings labels/set1-readings.json --provenance labels/set1-provenance.txt --verdicts judgments/set1-llama3.1-8b --rubrics rubrics --rubric-provenance labels/set1-rubric-provenance.json --out packages/llm-judges/assignment-1
python3 -m scorer.judge ab --a traces/ab-a --b traces/ab-b --verdicts judgments/ab --thresholds packages/llm-judges/assignment-2/thresholds.json --statement packages/llm-judges/assignment-2/statement.txt --set1 reports/judge-set1.json --cases data/gold.json --html reports/ab.html
cp reports/ab.html packages/llm-judges/assignment-2/comparison.html
```

`assignment-1/results.md` and both `comparison.html` files match their reports in `reports/` byte for byte, and these
commands should leave `git status` empty.

To see that the thresholds came first, compare the commit that added them with the commit that added the runs:

```bash
git log --follow --format='%h %ad %s' --date=iso -- packages/llm-judges/assignment-2/thresholds.json
git log --format='%h %ad %s' --date=iso -- traces/ab-b/run_meta.json
```

This folder was `submissions/week-02/` until Mon 2 Nov 2026. The archived prompts in `docs/` keep the old path, as they
were delivered.
