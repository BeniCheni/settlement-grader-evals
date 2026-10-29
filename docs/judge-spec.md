# Judge harness spec: rubrics, labels, a local judge, and its agreement with a human

Written Thu 29 Oct 2026 by the PM seat, for step 3 of `docs/week-2-package.md`. It is the spec of record for the judge
harness's build prompt. Precedence: the owner's rulings, then this spec, then the build prompt, then
`docs/week-2-package.md`. Where this spec says "contract" the name, format or behaviour is fixed, because the labels, the
reports or the course deliverables depend on it; elsewhere the builder decides and says why in the PR.

## Why this slice exists

The course's Week 2 asks for three LLM judges and the proof that each agrees with a human before it is trusted. This repo
already measures agreement for its plain-code checks (`scorer/stats.py`). This slice adds what a judge needs around that:
rubric files, a readable case file for each grader output, a label sheet the owner fills in, a call to a local model, a
strict reading of its reply, and a report of the judge against the labels. It calls no model in its tests.

## Inputs, all already in the repo or made by this slice

- Trace records from `scorer.traces.load_run(run_dir)`: `trace_id`, `case_id`, `ticket`, `status`, `reason`,
  `tool_calls`, `final`, `tools` (each `name`, `args`, `result`, `error`), `done_reasons`. Reuse it; do not parse traces
  again.
- `scorer/stats.py`: `confusion`, `agreement`, `cohen_kappa`, `false_pass_rate`, `meets_bar`. Reuse them; do not copy them.
- Rubric files, `rubrics/<name>.md`, written by the owner in a later pull request. Tests use fixture rubrics.
- The grader's runs: `traces/v1` (32 tickets) and the floor's runs `traces/aa-1`, `traces/aa-2`, `traces/aa-3`. Tests use
  fixtures and the tracked runs only.

## The case file (contract: `scorer/judge.py`, `render_case(record)`)

The judge and the owner read the same text for an output. It is deterministic: the same record gives the same bytes on
Python 3.9 and 3.14.

```
TICKET
<the ticket as JSON, sorted keys, indent 2>

TOOL CALLS
1. <name>
   args: <JSON, sorted keys, one line>
   result: <JSON, sorted keys, one line>
   error: <the span's error, or "none">
2. ...

FINAL ANSWER
<the final answer as JSON, sorted keys, indent 2, or "none">

RUN STATUS
<status>, reason <reason or "none">
```

A tool with no calls reads `TOOL CALLS` then `none`. A case file longer than 24,000 characters is an error, never cut: the
command that met it exits with status 2 and names the case. On `traces/v1` the ticket, tool calls and final answer as one
sorted JSON object run from 892 to 9,679 characters, on Python 3.9 and 3.14 alike; from the repository root:

```
python3 -c 'import json,sys; sys.path.insert(0,"."); from scorer import traces; s=sorted(len(json.dumps({"ticket":r["ticket"],"tools":[{k:t.get(k) for k in ("name","args","result","error")} for t in r["tools"]],"final":r["final"]},sort_keys=True)) for r in traces.load_run("traces/v1")); print(s[0], s[-1])'
```

The answer key is never in a case file.

## Rubrics (contract)

One file per rubric, `rubrics/<name>.md`, UTF-8 with LF line ends; the file's whole text is the judge's system prompt,
sent as it is. The rubric names are the file names without `.md`, in sorted order. For this package they are
`needs_human_correctness`, `rule_adherence` and `tool_call_accuracy` (`docs/week-2-package.md`). The harness records each
file's SHA-256 wherever it reports a verdict made with it. It checks only what code can check: the file is non-empty, at
most 6,000 characters, and contains `PASS`, `FAIL` and `Reason:`. Whether a rubric has the five elements is the owner's
and the reviewers' to judge.

## The reply (contract: `parse_reply(text)`)

Text inside `<think>...</think>` is removed first. The first non-empty line, stripped of surrounding whitespace, must be
exactly `PASS` or `FAIL`; anything else, including `Pass`, `**PASS**` and `PASS.`, gives the verdict `UNPARSED`. The reason
is the rest of the first later line that starts with `Reason:`, stripped; a missing reason is an empty string and does not
change the verdict. `parse_reply` returns `(verdict, reason)`.

In every count an `UNPARSED` verdict is a FAIL, which is the course's convention, and every report also prints, per
rubric, how many verdicts were `UNPARSED`. None is hidden.

## The judge call (contract: an adapter)

`run_judge(rubric_text, case_text, adapter)` returns the reply text. The adapter is a callable `(system, user) -> text`.

- **The Ollama adapter** posts to `http://127.0.0.1:11434/api/chat` with `urllib`, as `grader/agent.py` does: `stream`
  false, `think` false, options `temperature` 0, `seed` 0, `num_ctx` 16384, `num_predict` 256. It records the model name,
  the model's digest from `/api/tags` and the server version from `/api/version`. A connection failure exits with status
  2 and a message; it is never a verdict.
- **The fake adapter** (`--adapter fake:<file>`) reads a JSON object mapping `"<run>|<case_id>|<rubric>"` to a reply. It is
  how the tests and the CI drive the commands. No test opens a network connection.
- A hosted adapter can come later behind the same callable; it is not in this slice.

## The label set (contract)

**Selection** (`select`). The rows are every record of `--base` (here `traces/v1`), then `--n-fresh` records (here 8)
from the `--fresh` runs, taken in the order the runs are named and, within a run, in `case_id` order: a record is taken
when its `final`, as canonical JSON, differs from the base record's `final` for the same `case_id`, and its `case_id` has not
been taken from a fresh run already. If fewer than `--n-fresh` qualify, the command says how many and exits with status 2;
it never fills the set by another rule. The output, `labels/<set>-plan.json`, lists `{"run", "case_id", "trace_id"}` rows,
base rows first, each group in `case_id` order. Nobody reads an output before it is chosen.

**The sheet** (`sheet`). From a plan and the rubrics it writes, into a directory that is not committed (`sheets/` is
added to `.gitignore`), `case-files.md` (each row's case file under a heading `<n>. <run> <case_id>`) and `labels.csv`
(columns `n`, `run`, `case_id`, `trace_id`, one per rubric, `unsure`, `note`; rubric cells empty).

**Import** (`import-labels`). It reads the filled sheet and writes `labels/<set>.jsonl`, one row per plan row, in plan
order: `{"run", "case_id", "trace_id", "human": {<rubric>: "PASS" | "FAIL"}, "unsure": [<rubric>, ...], "note": "..."}`.
It refuses, with status 2, a message and nothing written: a row missing from the plan or extra to it, a duplicate, a cell
that is not exactly `PASS` or `FAIL`, a missing rubric, an `unsure` entry that is not a rubric name. It prints the count of
rows and, per rubric, the count of FAILs. It also writes `labels/<set>-meta.json`: the plan file's SHA-256 and each rubric
file's SHA-256 as it stood when the labels were imported.

**Adjudication** (`check-final`). `labels/<set>-final.jsonl` has the same rows plus `"changes": [{"rubric", "from", "to",
"reason"}]`. Each change's `from` is the first-pass label, `to` is the final one, the two differ, and `reason` is non-empty
after trimming. Any other difference between the two files is refused.

**Readings.** `labels/<set>-readings.json` is `{<rubric>: {"<run>|<case_id>": "<text>"}}`, one reading for each row where
the judge and the final label disagree. A reading counts when it is non-empty after trimming, the same definition the code
checks use (`scorer.calibrate.has_reading`); reuse it.

## Running the judges (`run`)

`run --labels labels/<set>.jsonl --rubrics rubrics --adapter ollama:<model> --out judgments/<id>` judges every row against
every rubric and writes `judgments/<id>/verdicts.jsonl`, one row per (row, rubric), sorted by run, case id and rubric:
`{"run", "case_id", "trace_id", "rubric", "rubric_sha256", "verdict", "reason", "reply"}`; and
`judgments/<id>/judge_meta.json`: the model, its digest, the server version, the options, each rubric's SHA-256 and the
labels file's SHA-256. The human labels are not sent to the model and not copied into the verdicts. Neither file has a
timestamp or a machine path. Both are committed: every report is computed from them without calling a model.

**Choosing the model** (`pick-model`). Before any labelled row is judged, each candidate model the owner has approved for
download is run on the three records of `traces/smoke-1` against every rubric. The first candidate whose every reply parses
is chosen, and `judgments/model-choice.json` records each candidate's parse counts and the choice. The choice uses no label
and no correctness, only the format, so the labelled rows stay unseen.

## The report (`report`)

`report --labels labels/<set>.jsonl [--final labels/<set>-final.jsonl] [--readings ...] --verdicts judgments/<id>
[--md OUT] [--json OUT]`. Per rubric, for the first-pass labels and, when given, the final ones:

- the four cells, named both ways: a failure is the positive class, so `JP_HP` is `tn`, `JP_HF` is `fn` (a false pass,
  the judge passed a real failure), `JF_HP` is `fp` (a false fail) and `JF_HF` is `tp`, computed with `stats.confusion`;
- agreement, Cohen's kappa, whether kappa is at least 0.6 (the course's bar) and whether `meets_bar` holds (this repo's
  bar), each from `scorer/stats.py`;
- the `UNPARSED` count;
- the false passes and the false fails, each as `<run> <case_id>`, with the judge's reason, and whether it has a reading;
- the rubric's SHA-256, the labels file's SHA-256 and the model and digest from `judge_meta.json`.

It names the worst judge as the one with the lowest kappa on the final labels (a kappa that cannot be computed ranks
lowest), with ties going to the one with more false passes. For each rubric it says whether the labels are held out or in
sample, by one rule: held out when the rubric's SHA-256 in `judge_meta.json` equals the one in `labels/<set>-meta.json`,
because the rubric is then the text the labels were made against; in sample otherwise, because the rubric changed after the
labels existed. It never calls a model. The Markdown and JSON are byte-stable, and a test fails when a committed report is stale.

## The course deliverables (`export-course`)

`export-course --final labels/<set>-final.jsonl --verdicts judgments/<id> --rubrics rubrics --out <dir>` writes:

- `rubrics.md`: each rubric under its name, verbatim in a fenced block, with its SHA-256;
- `labels.jsonl`: one row per label row, in the course's shape and only that shape: `{"input": <the ticket section of the
  case file>, "output": <the tool calls, final answer and run status sections>, "human": {<rubric>: "PASS" | "FAIL"}}`;
- `results.md`: the report's Markdown.

`diagnosis.md` is the owner's to write and is not generated.

## Commands and errors (contract)

`python3 -m scorer.judge <command> ...` with the commands above: `select`, `sheet`, `import-labels`, `pick-model`,
`run`, `check-final`, `report`, `export-course`. A usage or validation error exits with status 2, prints one message, shows
no traceback and writes nothing, as the slice 1 commands do. Standard library only; Python 3.9 and 3.14.

## What the PR must show

1. `parse_reply` against a table of replies, including the strict cases above, each with its verdict and reason.
2. `render_case` on one `traces/v1` record, compared with a committed golden file, and the size-limit error.
3. `select` on fixture runs: the rule above, a case with too few qualifying records, and the same output twice.
4. `sheet` then `import-labels` round-trip, and each refusal in "Import", each with status 2 and nothing written.
5. `run` with the fake adapter: one verdict per row and rubric, the meta file's hashes, and no network call (a test that
   makes `urllib.request.urlopen` raise and still passes).
6. `report`: the cell naming (a test that fails if `JP_HF` and `JF_HP` are swapped), kappa equal to `stats.cohen_kappa` on
   the same counts, an `UNPARSED` reply counted as a FAIL and on its own, first-pass and final side by side, the worst
   judge and its tie rule, and a committed fixture report that regenerates byte for byte.
7. `check-final`: a valid change, and each refusal.
8. `export-course`: the course row shape exactly, rubrics verbatim, `results.md` equal to the report.
9. At least three mutations named in the PR body, each turning the suite red for the right reason, among them: accepting
   `Pass`, counting `UNPARSED` as PASS, and swapping the two disagreement cells.
10. The suite and `python3 -m compileall -q .` on 3.9 and 3.14, the existing tests unmodified, and the privacy sweep.

## Out of scope here

The rubrics themselves, the labels, the model download and the real judge run (steps 4 to 6 of the plan); the comparison
and A/B pages (step 7); a hosted adapter; the A/B mechanics (step 8); the fourth judge.
