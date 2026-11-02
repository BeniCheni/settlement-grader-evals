# The A/B: the spec for step 8

Written Sun 1 Nov 2026 by the PM seat. It is the spec of record for step 8's build prompt, archived as
`docs/cursor-prompts/ab-build.md`, and for the PM's run; what review and the run changed is under "Amendments". Precedence:
the owner's rulings, then `docs/judge-spec.md` where this spec reuses its contracts, then this spec, then the build prompt,
then `docs/week-2-package.md`. `AGENTS.md` outranks all of them on process, and nothing here loosens it. Where this spec says
"contract" the name or behaviour is fixed; elsewhere the builder decides and says why in the PR.

## Why this exists

Assignment 2 asks for one full cycle: take the worst failure mode, read ten failing traces together, change exactly one thing,
run the same inputs through both variants, report each judge's delta on its own, and make a ship or no-ship call against
thresholds written before the results. The course's text is at commit `51a59c2` of its repository, in
`week-02-designing-reliable-llm-judges/assignments/02-diagnose-and-compare/`.

**The owner's rulings, Sun 1 Nov 2026.** (1) Variant B changes one thing: step 3 of the grader's system prompt asks for the
comparison before the result. (2) Step 8 runs before step 9. So the `rule_adherence` judge, which answered FAIL on all 40 rows of
set 1, is flagged up front as the delta to trust least, and the verdict rests on the plain-code check for this failure, with
`tool_call_accuracy`, the one judge at the bar, as a guard. (3) He approved the thresholds in `ab_report.md`, which the PM seat drafted.

## What is already decided, and where

| What | Where |
|---|---|
| The failure mode, the ten traces and the root cause | `packages/llm-judges/assignment-2/diagnosis.md` |
| The one change, as a full prompt | `variants/compare-first.txt` |
| The thresholds and the interval's method | `packages/llm-judges/assignment-2/ab_report.md`, and as data in `thresholds.json` beside it |
| The statement beside the figures, written by hand | `packages/llm-judges/assignment-2/statement.txt` |

These merge before variant B runs (`docs/week-2-package.md`, "Gates this repo adds"). The results section of `ab_report.md`
stays empty until the runs are committed.

## The order of work

1. **This spec and the files above**, a PM docs PR, reviewed as a fast-track.
2. **The code and the page**, the builder's PR under the full cycle: everything under "Running a variant" to "The page" below,
   proved on fixtures. It calls no model and commits no real run.
3. **The runs**, by the PM on the owner's machine, under "The run" below, committed with the report in their own PR.
4. **The verdict**, written by hand in `ab_report.md`. It is the owner's call.

## Running a variant (contract: `run_eval.py`, `grader/agent.py`)

`run_eval.py` gains `--prompt-file FILE`. The file's bytes are the system prompt for every ticket in the run, read once at the
start and not stripped. A missing, unreadable, empty or whitespace-only file exits with status 2, prints one message, shows no
traceback, calls no model and writes nothing. `FILE` must be a relative path inside the repository, using the same path
validation as `scorer.judge.relative_path`.

`run_meta.json`'s `system_prompt` records the text the run used. No other key changes. Without the flag the run uses
`SYSTEM_PROMPT`, and the requests sent to the model are byte for byte what they are on `main`.

`variants/compare-first.txt` is `SYSTEM_PROMPT` with one line replaced, step 3. A test proves that: split both on newlines, and
exactly one line differs, the one below. If `SYSTEM_PROMPT` changes later the test fails, because the baseline has moved. The wording
asks for the comparison in the same message as the `settle_ticket` call because `grade_ticket` treats any message with no tool call as
the final answer. A comparison on its own without parseable JSON would end the run as `UNPARSEABLE_FINAL`, counted under
`NO_FINAL_ANSWER`, which has its own threshold. The parser can extract JSON surrounded by other text, so a leaked line does not
necessarily make the final answer unparseable.

```diff
-3. Grade each leg: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a rule says so).
+3. Grade each leg by comparing it with the facts. In the same message as your settle_ticket call, first write one line per leg: the selection, the score or stat from get_match_facts with home and away named, and what that means for the selection. Then give its result: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a rule says so).
```

## Judging two runs (contract: `python3 -m scorer.judge run-ab`)

```bash
python3 -m scorer.judge run-ab --a traces/ab-a --b traces/ab-b --rubrics rubrics --frozen-rubrics judgments/set1-llama3.1-8b/judge_meta.json --adapter ollama:llama3.1:8b --out judgments/ab
```

It judges every ticket of both runs under all three rubrics, with the case text, the rubrics, the adapter and the strict reply
parsing that `run` uses, and it writes `verdicts.jsonl` and `judge_meta.json` in `run`'s shape through `write_outputs`. `--http-fixture` works
as it does on `run`. No human label is read, and no column is added to any label file. `judge_meta.json` has no `labels_sha256`
and gains `runs`, the two run names. The case text carries no run name or system prompt; a test checks that neither run's
name nor the prompt's changed sentence appears in it. The judge may still infer a variant from its output. `render_case`
does not include the assistant's content accompanying a tool call, so the judges cannot directly assess the requested
comparison; their verdicts assess the tool calls and final answer they can see.

It refuses, with status 2, one message, no traceback and nothing written, before any model call, when: the two runs do not hold
the same case ids, or either holds a duplicate; either run's `run_meta.json` lacks a non-empty string for `ollama_version` or `model_digest`, or the
file is missing; the two `run_meta.json` files differ in any key other than `run_id`, `outcome_matches` and `system_prompt`;
the two `system_prompt` values are equal; or a rubric's SHA-256 is not the one the `--frozen-rubrics` file records. The rubrics are
frozen from set 1, so a tightened rubric cannot slip into this comparison.

## The paired interval (contract: `scorer/stats.py`)

`paired_difference(a, b, c, d, z=1.96)`, where `a` is the tickets both runs count, `b` those only A counts, `c` those only B
counts and `d` neither, returns the fall `(b - c) / n`, positive when B counts fewer tickets, with its lower and upper limits. `n` of
0 returns `None`. For a judge, the tickets counted are its FAILs and UNPARSED replies, so the fall in that count is the rise in PASS. The method is Newcombe's
1998 method 10 for paired proportions, the hybrid score interval, built on `stats.wilson`. With `p1 = (a+b)/n`, `p2 = (a+c)/n` and
their Wilson limits `l1, u1` and `l2, u2`:

- `A = a*d - b*c`; `B = max(A - n/2, 0)` when `A > 0`, otherwise `A`; `phi = B / sqrt((a+b)*(c+d)*(a+c)*(b+d))`, and 0 when that
  product is 0.
- `lower = (p1 - p2) - sqrt((p1-l1)**2 - 2*phi*(p1-l1)*(u2-p2) + (u2-p2)**2)`.
- `upper = (p1 - p2) + sqrt((u1-p1)**2 - 2*phi*(u1-p1)*(p2-l2) + (p2-l2)**2)`.

The PM computed this table once, to re-derive by hand:

| a, b, c, d | Fall | Lower | Upper |
|---|---|---|---|
| 10, 5, 0, 17 | 0.1562 | 0.0164 | 0.2853 |
| 11, 4, 0, 17 | 0.1250 | -0.0036 | 0.2454 |
| 8, 7, 1, 16 | 0.1875 | 0.0139 | 0.3438 |
| 9, 6, 1, 16 | 0.1562 | -0.0082 | 0.3067 |
| 0, 0, 0, 32 | 0.0000 | -0.1072 | 0.1072 |
| 6, 6, 6, 14 | 0.0000 | -0.2104 | 0.2104 |

A delta whose interval includes zero has not been shown to do anything (`docs/week-2-package.md`, "Gates this repo adds").

## The report (contract: `python3 -m scorer.judge ab`)

```bash
python3 -m scorer.judge ab --a traces/ab-a --b traces/ab-b --verdicts judgments/ab --thresholds packages/llm-judges/assignment-2/thresholds.json --statement packages/llm-judges/assignment-2/statement.txt --set1 reports/judge-set1.json --md reports/ab.md --json reports/ab.json --html reports/ab.html
```

The outputs are byte-stable, go through `write_outputs` and refuse as the other commands do. It runs the same refusals as `run-ab`,
except the rubric check, which it makes against `judge_meta.json`. It also refuses a missing, extra or duplicate verdict, a verdict
whose run, case or trace id does not match the inputs, or a mismatch between the run names in `judge_meta.json` and the inputs.
The statement file is written by hand, because code cannot decide
that a result is in sample or held out; a missing, empty or whitespace-only file is a refusal. Computed text never contains
"held out", "held-out", "trusted", "generalise" or "generalize", in any case, and never the words "ship" or "no-ship" as a
verdict: the verdict is the owner's sentence in `ab_report.md`. The report states:

- **One row per metric, never blended.** For each judge, the PASS share in A and B, the delta in percentage points, the paired
  interval, how many tickets went from FAIL to PASS and from PASS to FAIL, and each run's `UNPARSED` count. `UNPARSED` is a FAIL, as
  everywhere. For each code in `scorer.checks.CHECKS`, the ticket count in A and B, the delta in tickets and points, the paired
  interval, and how many tickets each way, from the same scoring `scorer.compare` uses. Nothing is summed across metrics.
- **The thresholds.** Each row of `thresholds.json` with its numbers and whether it held, then a count, "k of n thresholds held".
  A `report_only` row says so and is not counted. A code or rubric named in the file that the data lacks is a refusal.
- **The trust flags.** For each judge, whether `meets_bar` held on the final labels of set 1, from `--set1`, both numbers beside it,
  the false passes read beside it, and the sentence naming `weakest_judge` from `thresholds.json` as the delta to read with most care.
- **The setup.** The Ollama version, the grader's model and digest, the judge's model and digest, and the prompt's line-level diff
  between the two runs' `system_prompt`, computed, so a reader sees the one change without trusting a document.
- **Every ticket.** In the order of the runs: the case id, each run's final result, the codes that fired in A and in B, each
  judge's verdict in A and B, and the judge's reason on any row whose verdict differs.

`thresholds.json`'s kinds are a contract: `must_fall` (`min_net_fall` tickets, and `interval_excludes_zero`, so the interval on the
fall lies wholly above zero), `max_rise` (`max_rise` tickets) for a code, and `max_pass_fall` (tickets) and `report_only` for a
judge. Any other kind or key is a refusal.

## The page (contract on content, the builder's on layout)

`--html` writes one self-contained page in the style of `reports/judge-set1.html`, under `AGENTS.md`'s UI rules and with
`ui/ledger.css` as the only source of colour and type. It carries everything the report states, reuses `FONT_LINKS` and the page's
primitives where they fit, and has no script. The cover asks "Did the change work?" and gives the primary code's counts in A and
B, its delta and interval, and the thresholds' count, with the hand-written statement beside them, verbatim. No tile, pill or
sentence presents a threshold count as the trust verdict. The every-ticket section follows the judge page's two-tier rows at 761 px
and wider and stacks at 760 px and narrower, hiding empty cells. A colophon prints the command, which rebuilds the page byte for byte
from the repository root. The package copies it to `packages/llm-judges/assignment-2/comparison.html` at step 10.

## The run (the PM's, after the builder's PR merges)

1. Confirm that this spec's files are on `main`, that `ollama` is the recorded version, and that `qwen3:8b` and `llama3.1:8b` are on
   disk. Nothing is downloaded without the owner's approval.
2. In one session, against one running server, run A and then B over all 32 tickets: `python3 run_eval.py data/gold.json --run-id ab-a`,
   then the same with `--run-id ab-b --prompt-file variants/compare-first.txt`. If either stops early, both are run again.
3. Review `statement.txt` against the actual evidence and update it if needed, then run `run-ab` and `ab`. Read every ticket whose code or verdict changed.
4. Commit `traces/ab-a`, `traces/ab-b`, `judgments/ab/` and `reports/ab.*` in their own PR. Then the results section of
   `ab_report.md` is filled in from the report, and the owner writes the verdict and what would change his mind.

## Acceptance for the builder's PR

1. `--prompt-file`: its refusals, the recorded prompt, and, on a fake transport, a run without the flag sending the same requests as
   `main` and a run with it sending the file's bytes as the system message.
2. `variants/compare-first.txt`'s one-line test.
3. `run-ab` on two fixture runs through `--http-fixture`: 2 × tickets × 3 rubrics verdicts, sorted as `run` sorts them, regenerating
   byte for byte; fixture replies vary by run, case and rubric, and the output preserves their mapping and values; every refusal above,
   each with status 2, one message and nothing written.
4. The test that the case text does not reveal the variant.
5. `paired_difference` against the table above, to 4 decimals, and the table's sign convention, with `n` of 0 and a zero margin
   covered. Also one worked example by hand in the test's comment.
6. `ab` on fixtures with every threshold kind holding and failing, checked against counts the test makes itself from the fixtures, not
   against output of the same code. A byte comparison alone does not count as checking a figure.
7. No blended figure: a test that finds no sum or average across metrics in the JSON's keys, and each metric in its own row.
8. The banned words, on a fixture page and report: exclude the output nodes or spans that render input text, not every occurrence of
   the same string in the output, so a computed sentence cannot hide behind an input (`docs/week-2-package.md`, "Follow-ups").
9. Every dynamic string escaped, including the reasons, the statement, the prompt diff and the paths.
10. AA on every new pair in `tests/test_contrast.py`, both themes, losing none; `reports/calibration-v1.html` and
    `reports/judge-set1.html` regenerated if the stylesheet moves, with their JSON and Markdown unchanged and their layout measured unchanged.
11. In a browser the builder drives, at 360, 375, 390, 761, 899, about 1000 and 1400 px in dark and light, with the viewport set before any
    capture: `scrollWidth` equals `innerWidth`, no short fact breaks across lines, the console is empty, the only external hosts are
    Google Fonts, a real Tab reaches a visible focus ring, and `prefers-reduced-motion` is emulated, not assumed. Report the main text's
    width and the page's height at about 1000 px. `scrollWidth` alone cannot see a column that is too narrow.
12. At least three mutations named in the PR, each red for the right reason, among them: swapping `b` and `c`, blending two metrics into one
    row, and reading a threshold's sign backwards. A survivor is a finding.
13. The suite and `compileall` on Python 3.9 and 3.14, standard library only, every commit green on its own, and the privacy sweep.
14. The 80ch prose measure gains its missing test (`docs/week-2-package.md`, "Follow-ups"), since this PR touches the stylesheet.

## Amendments

What review and the run changed, so a cold reader does not take the contract above for the whole page.

**At review (PR #18, Sun 1 Nov 2026).**

- **One line of short facts (the owner's ruling).** At 761 px and wider a ticket's case, two finals and one cell per judge
  sit on one line, each under its own label, and each judge's cell holds both runs' verdicts. Each run's verdict is one
  unbreakable span, so a cell wraps only between A and B. A codes and B codes sit beneath, side by side, and the Changed
  line and Reasons span the row. This replaces the two-tier sentence under "The page". The first build laid a ticket out in
  two equal columns of seven or eight tiers.
- **The changed mark (the owner's ruling).** A ticket whose final, codes (compared as sets) or any verdict differs carries
  the judge page's blood bar for the row's whole height at every width, and a computed line naming what changed, in a fixed
  order, that never judges it. The Tickets section opens with a computed count, the Markdown prints the same count and
  line, and the JSON's ticket gains `changed`.
- **What "final" means in that mark (the owner's ruling).** The ticket's result, as the A final and B final cells print it.
  A changed `net` or leg grade alone earns no mark. `scorer.compare` counts any difference in the final answer, so its
  count is wider, and it is read beside the page at the run.
- **Metric rows (the owner's ruling).** One table for the judges and one for the codes, on the page and in the Markdown, one
  row per metric and every column under a real head. A judge's count is named Non-PASS and its UNPARSED columns are
  subsets of it. A judge row drops Only A and Only B, which repeat its transition columns. The tables stack at 760 px and
  narrower with each value under its label.
- **The statement twice (the owner's ruling).** The hand-written statement prints on the cover and beside the Set 1 numbers,
  so every calibration number has it beside it.
- **More refusals (Pass 1 and Pass 2).** A `z` that is not finite and above zero, a negative limit, a `min_net_fall` of
  zero, a `kind` that is not a string and a cases file of the wrong shape each exit with status 2. A scoring error names the
  scoring, not the cases file. There is no floor on `z`, because this spec gives no number: a tiny positive `z` collapses the
  interval, the page prints `z`, and `thresholds.json` holds 1.96.
- **Threshold rows and the printed `z` (Pass 1 and Pass 2).** Each row prints its limits and its observed value in words and
  names the subtraction. `z` prints as used.
- **A measured bar (added in the Pass 2 brief).** On one rehearsal at 1000 px, Tickets no more than 55% of its height before
  these rulings and Metrics no more than 40%. At the merge they measured 48.6% and 34.1% on the PM's rehearsal replies.

**At the run (PR #19, Sun 1 Nov 2026).**

- **The statement.** Amended under step 3 of "The run": on none of the 29 tickets where variant B called `settle_ticket` did
  it write the requested comparison beside that call, and it settled in the same message as a lookup on 8 tickets against
  A's 3. So the figures show what this wording did, not whether a comparison made before the grade would help.
- **The result.** 6 of 8 thresholds held. The verdict is the owner's, in `packages/llm-judges/assignment-2/ab_report.md`.

**After the run (Mon 2 Nov 2026).**

- **Page fixes (PR #21).** Each paired interval stays on one line from 761 px. A count of one prints "ticket". A metric's
  name is two spans: the visible one wraps at underscores and is `aria-hidden`, and a visually hidden one carries the whole
  name. `ab` also refuses a wrong type or a non-finite `net` inside a case's `expected`. With web fonts blocked, the longest
  ticket label wraps inside its cell at 761 px, which review accepted. No figure moved.
- **The path (the owner's ruling).** `submissions/week-02/` moved to `packages/llm-judges/`, so the commands above name the
  new path and the report and page print it. The bytes of the thresholds and the statement did not change, `git log --follow`
  shows their history, and the archived prompts keep the old path as delivered.

## Out of scope

Any change to the grader's prompt beyond the variant file; any change to a rubric, label or verdict of set 1; step 9's tightening; a hosted
tool; the real runs, which the builder does not perform; the verdict; `README.md`, `docs/` and `AGENTS.md`, which the PM seat updates after the
merge; a dependency of any kind.
