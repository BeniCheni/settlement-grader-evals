# The Week 2 package: three validated judges and one A/B decision

Written Thu 29 Oct 2026 by the PM seat; the owner approved its scope and defaults the same day. It turns the two Week 2
assignments of the *AI Evals in Practice* course into this repo's next milestone, so that every file the course asks for
comes out of this repo's own judge, run against this repo's own grader. The judge harness it needs is specified in
`docs/judge-spec.md`. Precedence: the owner's rulings, then the specs, then this plan, then
`docs/scope-checks-and-judge.md`.

## What the course asks for

The assignments live in the course repository, which is MIT-licensed:
`github.com/coachmanjeet/AI-Agent-Evals-Course`, under `week-02-designing-reliable-llm-judges/assignments/`. Read them
there; this is a summary, and where it differs from them, they win.

**Assignment 1, build and validate a judge** (`01-build-and-validate-judge/README.md`). Three binary LLM judges, one
criterion each. Each prompt has five elements: an auditor role, one binary question, a concrete standard, a boundary
example, and a strict output format (`PASS` or `FAIL` on the first line, then `Reason:` in under 20 words). Forty agent
outputs are labelled by hand against all three, 120 labels, with roughly a third expected to fail. For each judge: the
agreement matrix, agreement, and Cohen's kappa, with kappa of at least 0.6 before the judge is called trusted; the worst
judge's dominant failure mode, false pass or false fail; and at least one label changed on adjudication with the reason, or
a note saying none changed and why. Deliverables: `rubrics.md`, `labels.jsonl`, `results.md`, `diagnosis.md`. Stretch: a
bias-corrected pass rate with a 95% interval for one judge.

**Assignment 2, diagnose and compare** (`02-diagnose-and-compare/README.md`). Pick the worst failure mode, read ten failing
traces together and write a one-paragraph root cause with the trace ids. Change exactly one thing. Run the same set of at
least 30 inputs through the baseline and the change, score both with the three judges, and report each judge's delta in
percentage points, never blended. Write the ship or no-ship thresholds before the results, then the verdict and what would
change it. Flag any judge below the trust bar and say which delta it makes least trustworthy. Deliverables: `ab_report.md`,
the diagnosis, and the comparison from Braintrust "or the equivalent from your tool of choice".

Assignment 1's README says the rubrics and the validation are graded, not the platform ("Prefer LangSmith or another tool?
Fine"), and Assignment 2's accepts the equivalent of Braintrust's comparison from another tool. Step 9 below, which
tightens the weakest judge once and validates it on fresh labels, is not in Assignment 2's README; it follows Assignment 1's
pitfall "Keep a held-out slice if you iterate". Whether the course grades it is a question for the course.

## Where this repo stands

| Course item | In this repo | Source |
|---|---|---|
| Judge prompts, judge calls, per-rubric labels | None yet | |
| Agreement matrix, agreement, kappa, the bar | Built for the code checks: `confusion`, `agreement`, `cohen_kappa`, `wilson`, `false_pass_rate`, `meets_bar` (85% and 0.6) | `scorer/stats.py` |
| Outputs to judge, about a third failing | 32 tickets; 11 match the expected outcome | `traces/v1/results.csv`, column `outcome_match` |
| Failure codes to turn into rubrics | 12 codes with the traces a human labelled; 11 have a plain-code check | `data/codes_v1.json`, `scorer/checks.py` (`CHECKS`) |
| Reading every disagreement | Done for the code checks, in sample | `data/calibration_readings_v1.json` |
| Noise floor between identical runs, A/B | None yet | |

## The three rubrics for this grader

The course's rubrics are written for a grocery-support agent. Each maps onto this grader, which settles a ticket with four
tools (`find_match`, `get_match_facts`, `lookup_rule`, `settle_ticket`) and returns graded legs with evidence. The judge
sees the ticket, every tool call with its arguments and result, the final answer and the run status, and never the answer
key, which holds only 4 keys the owner has verified (`data/gold.json`, `expected.verified_by_beni`).

| Course rubric | Here | One binary question | Failure codes it draws on |
|---|---|---|---|
| policy adherence | `rule_adherence` | Did the grader apply the market's own rule, as `lookup_rule` returned it, to the facts it fetched, for every leg? | `GRADE_CONTRADICTS_FACTS` (the code check covers result, total and both-teams-to-score legs; props are left to a human), `RULE_TOPIC_MISS` |
| escalation correctness | `needs_human_correctness` | Did it answer NEEDS_HUMAN, VOID or UNSETTLED exactly when a needed fact was missing or a rule said so, and settle when the facts decided the ticket? | `WRONG_NON_GRADE`, `GRADED_WITHOUT_LOOKUP` |
| tool-call accuracy | `tool_call_accuracy` | Did it call the right tool with the right arguments, and does its `settle_ticket` call match the leg grades it gave? | `SKIPPED_SETTLE_TICKET`, `RULE_TOPIC_MISS` |

The prompts are the owner's to write, from drafts the PM seat supplies; each is one criterion with its own boundary example
drawn from a real trace. `SELF_CONTRADICTING_EVIDENCE` stays this repo's planned fourth judge and comes after this package.

## Decisions (the owner's, 29 Oct 2026)

1. **The judge is a local model of another family than the grader's**, called through Ollama with the standard library,
   so a stranger reproduces it without a key. Which model is chosen by the procedure in `docs/judge-spec.md`, before any
   labelled case is judged. A hosted judge can be added later behind the same adapter.
2. **The comparison view is this repo's own report**, in the Haunted Ledger style. A Braintrust export is optional and
   would live outside `scorer/` with its dependency named in its PR.
3. **The 120 labels are the owner's.** No model output is ever written into a human column.
4. **The 40 outputs** are the 32 of `traces/v1` and 8 from fresh runs of the same configuration, chosen by a fixed rule
   (`docs/judge-spec.md`, "The label set") rather than by reading them.

## The order of work

Each step is its own pull request, unless it says otherwise. Who reviews it follows who wrote it (the owner's ruling,
29 Oct 2026, which is the seat table in `AGENTS.md`):

- **Code** (the `compare` command in step 2, the harness in step 3, the pages in step 7, and any code the A/B in step 8
  needs, such as a way to run a prompt variant) is built by Cursor and goes through the full cycle: Claude Code is Pass 1
  in a fresh session that wrote none of it, Codex is Pass 2, and Cursor merges in Pass 3 on the owner's word.
- **Docs and data** the PM seat writes (this plan and the spec, the runs, the verdicts and reports, the package) are
  Claude's, so Codex gives the cold read, as `AGENTS.md` says for any PR a Claude session wrote.

| Step | Work | Seat | Done when |
|---|---|---|---|
| 1. This plan and the judge spec | `docs/week-2-package.md`, `docs/judge-spec.md` | PM | Reviewed and merged |
| 2. The floor | Three more runs of the v1 configuration, committed as `traces/aa-1`, `traces/aa-2`, `traces/aa-3`, and a `compare` command that reports the range of every code count across runs | PM (runs), builder (`compare`) | Each code has a range; the runs also supply the 8 fresh outputs |
| 3. The judge harness | Everything in `docs/judge-spec.md` | Builder | Its acceptance list holds |
| 4. The rubrics, frozen | `rubrics/rule_adherence.md`, `rubrics/needs_human_correctness.md`, `rubrics/tool_call_accuracy.md` | Owner, from PM drafts | Merged before any label is written |
| 5. The labels, frozen | `labels/set1.jsonl`: 40 rows, three labels each | Owner | Merged before any judge call on them |
| 6. The judges run | The model chosen, the verdicts committed, the report, every disagreement read, adjudication into `labels/set1-final.jsonl`, `diagnosis.md` | PM runs; owner reads and adjudicates | Assignment 1's acceptance list holds |
| 7. The pages | The judge comparison page (Assignment 1's comparison view) and the A/B page (per-metric deltas) | Builder | The UI rules in `AGENTS.md` hold |
| 8. The A/B | One change to the grader as variant B; thresholds written first; both variants through the three judges and the code checks; `ab_report.md` | Owner decides; PM runs and drafts | Assignment 2's acceptance list holds |
| 9. The weakest judge again | Its rubric tightened once, validated on fresh labels (`labels/set2.jsonl`, that one rubric, at least 30 rows) | Owner, PM | Its kappa on labels it was never tuned on is reported |
| 10. The package | `submissions/week-02/`, below | PM | Every course item maps to a file |

The rubrics are frozen before labelling so the labels judge the rubric as written; the labels are frozen before the judge
runs so no label is read from a verdict. Git shows the order: each lands in its own merge.

## Gates this repo adds to the course's

- A result says whether it is in sample or held out. Set 1 is held out for the judges, because the rubrics never saw it
  before they were frozen; once a rubric is tightened on set 1's disagreements, set 1 is in sample for that rubric and only
  set 2 can validate it.
- The trust bar is the repo's: agreement of at least 85% and kappa of at least 0.6, with every false pass read. The course
  asks only for the kappa; both are reported.
- A verdict the judge did not give in the required format is counted on its own, not hidden.
- An A/B delta is read against the range the floor gives. A delta inside that range has not been shown to do anything.
- Thresholds are written in `ab_report.md` and merged before variant B runs.

## The package

```
submissions/week-02/
  README.md                 each course acceptance item, and the file that meets it
  assignment-1/
    rubrics.md              the three rubrics, verbatim, with their hashes
    labels.jsonl            the 40 rows in the course's format, after adjudication
    results.md              per judge: matrix, agreement, kappa, false passes and false fails
    diagnosis.md            the worst judge's failure mode, its loophole, every changed label and why
    comparison.html         the judge comparison page
  assignment-2/
    ab_report.md            the course template, filled
    diagnosis.md            the ten trace ids and the root cause
    comparison.html         the A/B page
```

## Open

- The due dates.
- Whether the weakest-judge cycle (step 9) is graded.
- The judge model, chosen by the procedure in the spec.
- The course estimates 4 to 6 hours for Assignment 1, most of it labelling, and 3 to 4 hours for Assignment 2.
