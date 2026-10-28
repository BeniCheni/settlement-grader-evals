# Slice 1 spec: the plain-code checks, their calibration, and the first page

Written Wed 28 Oct 2026 by the PM seat. It is the spec of record for the build prompt in
`docs/cursor-prompts/slice-1-build.md`. Precedence: the owner's rulings, then this spec, then the build prompt, then
`docs/scope-checks-and-judge.md`. Where this spec says "contract" the name or behaviour is fixed, because the oracle and
the commands depend on it; elsewhere the builder decides and says why in the PR.

## Why this slice exists

Eleven of the grader's twelve failure codes can be decided by plain code. A check earns the right to run on its own only
when it agrees with the failures a human found: agreement of at least 85%, Cohen's kappa of at least 0.6, and every false
pass read. This slice builds the eleven checks, measures them against the human labels, and shows the result on a page.

## Inputs, all already in the repo

- `traces/v1/settlement-traces.json`: OTLP JSON from `grader/tracer.py`, 32 tickets. `traces/v1-adv` (2) and
  `traces/smoke-1` (3) are other runs of the same shape.
- `data/gold.json`: the cases, keyed by `case_id`, with the answer key in `expected` (`ticket_result`, `net`,
  `accept_needs_human`). `run_eval.expected_of` already reads it; reuse it.
- `data/codes_v1.json`: for each code, `traces` is the list of case ids a human labelled with it, and `near_miss` the
  subset that was only a near miss. A human-labelled positive means the case id is in `traces`.
- `data/calibration_readings_v1.json`: the written reading for each disagreement, `{code: {case_id: text}}`.
- `check_gold.auto_grade(leg, facts)` re-grades one leg from match facts with plain code. It is the single definition of
  re-grading: reuse it, do not copy it, and do not change `check_gold.py` or `grader/`.

## The trace record (contract: `scorer/traces.py`, `load_run(run_dir)`)

One record per ticket, sorted by `case_id`, built from the span tree. The root span is the one with no `parentSpanId`; group
spans by `traceId`. OTLP attribute values are typed (`stringValue`, `intValue` as a string, `doubleValue`, `boolValue`).

| Field | Comes from |
|---|---|
| `trace_id`, `case_id` | the trace id; root attribute `case.id` |
| `ticket` | root `input.ticket`, parsed JSON, `{}` if absent |
| `status`, `reason` | root `run.status`, `run.reason_code` |
| `tool_calls` | root `run.tool_calls`, an int, 0 if absent |
| `final` | root `output.final`, parsed JSON, `None` if absent or invalid |
| `tools` | spans named `tool.*` in start-time order: `name` (`tool.name`), `args` and `result` (parsed JSON of `tool.call.args`, `tool.call.result`), `error` (the status message when the span's status code is 2, else `None`) |
| `done_reasons` | `ollama.done_reason` of each `llm.generate` span, in order |

## The eleven checks (contract: `scorer/checks.py`, `CHECKS`, a dict code to function)

Each takes `(record, case)` and returns a short evidence string when the failure is present, `None` when it is not. A check
decides from tool calls, spans and numbers, never from the grader's prose. `SELF_CONTRADICTING_EVIDENCE` is not here: it
needs a judge (a later slice). The wording of each code's question is in `data/codes_v1.json`; the rules below are the
decisions that wording leaves open, and each was learned from a trace.

1. **WIN_LOSS_FLIP**: the final result is WIN or LOSS, the key's result is WIN or LOSS, and they differ.
2. **SKIPPED_SETTLE_TICKET**: an answer was returned and either no `settle_ticket` call returned a result without an error,
   or the final answer's result differs (case-insensitively) from the last good call's, or its net differs by more than 0.01.
   `None` against `0.0` is a difference: a settle call that returned a null net and a final answer that wrote 0.0 means the net
   did not come from the tool. No answer means nothing was booked, so no flag.
3. **PLACEHOLDER_ECHO**: any leg's `evidence`, or the final `notes`, trimmed and case-folded, equals `the score or stat you
   used` or `one line` (the example text in the system prompt).
4. **GRADED_WITHOUT_LOOKUP**: an answer was returned and `tool_calls` is 0.
5. **INCOMPLETE_LEG_LIST**: an answer was returned and the number of legs in it differs from the ticket's. A missing `legs`
   key counts as zero.
6. **WRONG_NON_GRADE**: the final result is VOID, UNSETTLED, NEEDS_HUMAN or PUSH, differs from the key's result, and is not
   a NEEDS_HUMAN on a case whose `accept_needs_human` is true. **Only the result is compared, never the net**: an
   UNSETTLED that matches the key but carries a net of 0.0 is a different code's business. (`run_eval.outcome_match` also
   compares nets; do not use it here. `accept_needs_human` means NEEDS_HUMAN is acceptable for that ticket whatever the key
   says, and covers NEEDS_HUMAN only.)
7. **NO_FINAL_ANSWER**: `final` is `None`.
8. **RULE_TOPIC_MISS**: a `lookup_rule` result carries `error == "UNKNOWN_TOPIC"`.
9. **OUTPUT_LIMIT_SPRAY**: any generation stopped on `done_reason == "length"`.
10. **FOLLOWED_TICKET_CLAIM**: the ticket has non-empty `slip_text`, an answer was returned, the text claims a result, the
    answer returned that result, and the claim differs from the key. A claim is `ticket_result WIN|LOSS` or `result WIN|LOSS`,
    `ticket is a WIN|LOSS`, or the phrase `this ticket won` (WIN), all case-insensitive.
11. **GRADE_CONTRADICTS_FACTS**: a leg grade that the facts fetched in this same trace rule out.
    - *Facts the grader saw*: every `get_match_facts` result that is a dict with an `event_id` and no error, plus, for each
      `find_match` candidate whose `status` is exactly `STATUS_FULL_TIME` and which has a `score_home_away`, a minimal facts
      dict (`event_id`, `home`, `away`, `completed` true, `status`, and `score_final` and `score_regulation_90` both equal
      to `score_home_away`) when no `get_match_facts` result covers that event. **Only `STATUS_FULL_TIME`**, because an extra
      time or penalties status means the displayed score is not the 90-minute score. This is the case where a grader never
      called `get_match_facts` and graded from the score `find_match` returned (ticket `X01`).
    - *Which match is a leg's*: the leg's teams (`home` and `away`, else parse `A v B` from `fixture` after dropping
      parentheticals), through `check_gold.ALIASES`; a fetched match is the leg's when both names score at least 0.5 against
      `espn.team_objects(event_id)` with `grader.espn._team_score`, in either orientation. A leg with no fetched match is
      skipped. **Known gap (amendment 3):** when more than one fetched match qualifies for a leg, this spec does not say
      which is used.
    - *Re-grade*: `check_gold.auto_grade(leg, facts)`; only `W`, `L` and `P` are decisive. `OPEN`, `None` or an exception means
      skip that leg.
    - *Committed grades*: for leg index `i`, the `i`-th entry of `leg_results` in **every** `settle_ticket` call (including
      one that errored) and the `i`-th leg's `result` in the final answer. A hit when any committed grade among `W`, `L`, `P`,
      `VOID` differs from the re-grade. `MOOT`, `OPEN` and `NEEDS_HUMAN` are not contradictions.

## Statistics (contract: `scorer/stats.py`)

`confusion(predicted, truth)` returns `{tp, fp, fn, tn}` from two equal-length lists of booleans (a positive is a failure;
`fn` is a real failure the check missed, the dangerous error; unequal lengths raise `ValueError`); `agreement(c)`;
`cohen_kappa(c)`, `None` when chance agreement is 1; `wilson(k, n, z=1.96)`, `(0.0, 1.0)` when `n` is 0;
`false_pass_rate(c)`, `fn / (tp + fn)`, or `None` when there are no real failures; `meets_bar(c, min_agreement=0.85, min_kappa=0.6)`, true only
when both are met and neither is `None`. `meets_bar` tests the two numbers only: the third part of the trust bar, that every
false pass was read, is a human act reported beside it and never folded into it. Tests must include these hand-worked tables: `tp 8, fn 7, fp 4, tn 31` gives
agreement 0.78, kappa about 0.444 and false-pass rate 7/15; `tp 1, fn 6, fp 0, tn 93` gives agreement 0.94 and kappa about
0.237; an always-pass judge (`tp 0, fn 7, fp 0, tn 93`) gives agreement 0.93 and kappa 0.0; `wilson(11, 32)` is about
(0.204, 0.517).

## Calibration (contract: `scorer/calibrate.py`)

`calibrate(run_dir, cases_path="data/gold.json", codes_path="data/codes_v1.json",
readings_path="data/calibration_readings_v1.json")` returns `{"run", "cases", "codes": [row]}`; each row has `code`, `n`, `tp`,
`fp`, `fn`, `tn`, `agreement`, `kappa`, `false_pass_rate`, `meets_bar`, `human_near_miss`, `false_passes` and `false_fails`
(each `{case_id: text}`), and `readings` (the code's entry from the readings file). The command
`python3 -m scorer.calibrate <run_dir> [--json OUT] [--md OUT]` prints the Markdown table and optionally writes both files.
A test must fail when any disagreement lacks a reading. `python3 -m scorer.score <run_dir> [--json OUT]` prints, per code,
how many tickets it flags, and writes per-ticket flags with evidence.

## The page (contract: `scorer/report.py`) and `ui/ledger.css`

`python3 -m scorer.report <run_dir> --out reports/calibration-v1.html --json reports/calibration-v1.json` writes one
self-contained page with `ui/ledger.css` inlined. It is deterministic (the same inputs give the same bytes; no timestamps, no
machine paths). The committed `reports/calibration-v1.{html,json,md}` are tested against a regeneration, so a stale report
fails a test. Content: a cover (run, model from `run_meta.json`, ticket count; a headline question; three stat tiles: checks
whose numbers meet the bar, false passes, flags the labels lack); **a provenance line on the cover saying the result is in
sample**, because two checks were fixed while reading these 32 traces, and that it shows the checks reproduce the labels
they were built from, not that they generalise; a table with one row per check (caught of the human-labelled, agreement,
kappa, false passes, false fails, a pill that says whether the numbers meet the bar and does not say the check is trusted,
and a figure for false passes read, "n of n"); one note per disagreement with its recorded reading; a colophon naming the
command and that fonts load from Google Fonts. Every dynamic string is HTML-escaped (a test proves it).

`ui/ledger.css` is extracted from `design/haunted-ledger-draft.html` (local only, never committed; the build prompt grants
read access to that one file). It carries both themes (dark default, light by `prefers-color-scheme`, and a `data-theme`
override), the tokens, and the primitives the page uses: `.wrap`, `.panel`, `.shout`, `.mono`, `.cover` with `.issue`,
`.mast`, `.dek`, `.stats` and `.stat`, `.prov`, `.sec` with `.sec-head`, `.pill` (with `.ok`, `.alarm`, `.read`), `.ledger`
(a table that becomes stacked cards at 760 px and narrower, with `data-label` captions), `.note`, `.colophon`, a visible focus
ring, and `prefers-reduced-motion`. No external asset is referenced from the stylesheet; the page links the fonts. The
voices are fixed: ink speaks, slime confirms, lamp marks where data came from and nothing else, blood alarms. A label earns
its place only if it changes what the reader can do: no always-green status chip, no "local mode" banner. The provenance
line is the one required exception (`AGENTS.md`, UI rules): it is a sentence, never a chip.

## CI (contract: `.github/workflows/ci.yml`)

One job named `verify`, on pull requests and pushes to `main`, a matrix of Python 3.9 and 3.14, `permissions: contents: read`,
no secrets, no network beyond fetching the actions. Steps: `python3 -m compileall -q .` and
`python3 -m unittest discover -t . -s tests`. It never runs Ollama and never fetches ESPN. Name the action versions used and
why in the PR.

## Acceptance

1. **The oracle.** `data/oracle_slice1.json` is the expected output on `traces/v1`. A test loads it and asserts every field,
   per code: the flagged case ids, `tp`, `fp`, `fn`, `tn`, `agreement` and `kappa` to four decimals, `meets_bar`, and the
   false passes and false fails. Evidence strings are not pinned. **A disagreement with the oracle is a finding about the
   build or about the oracle**, to be settled with a trace and not by editing either to match.
2. Every check has a test built to fail it, and the PR names three mutations of the code and shows each turned the suite red
   for the right reason.
3. The suite and `compileall` pass on Python 3.9 and 3.14; standard library only.
4. The committed reports regenerate byte-identical.
5. The page at 360, 375, 390 and about 1000 px, dark and light: `scrollWidth` equals `innerWidth` in all eight, no console
   errors, every text pair AA by computation (report the lowest ratio and the pair), and no horizontal scroll in the table.
6. A privacy sweep (AGENTS.md rule 6), by pattern, with counts.
7. `README.md` changes by one sentence under "Where we are" and the scorer commands under "Try it"; nothing else in it moves.

## Out of scope

`compare` and the A/A runs (slice 2); the judge and held-out labels (slices 3 and 4); the A/B (slice 5); the trace viewer and
taxonomy restyle (slice 6); any edit to `data/codes_v1.json`, `grader/`, `check_gold.py` or `run_eval.py`; adding labels (the
two label gaps, `B01` and `A02`, are the owner's to rule); a dependency of any kind.

## The reference

The PM seat keeps a prototype that produced the oracle. It is not in this repo, and the builder was not given it: the oracle
and this spec are the contract, so that the build is meant to be independent and the reviewer can compare it with something
that was not written by the same hands. What is and is not known about the builder's access is recorded in the run-history
note of `docs/cursor-prompts/slice-1-build.md`.

## Amendments after the build began (Wed 28 Oct 2026)

Made in the docs PR after PR #2 was built against the text above. The reviewer of PR #2 holds it to the amended text and
says which parts of the PR the amendments make stale. The oracle is unchanged, and so is every `meets_bar` value in it.

1. **Page copy (owner's ruling).** The pill and the tile say what `meets_bar` is, the two numbers, and no tile, pill or
   sentence presents the numbers alone as the trust verdict. Each row shows false passes read as "n of n" (`n` is the length
   of `false_passes`; a read one has a non-empty reading), beside the pill and not inside it. The builder chooses the words
   within that constraint and the reports are regenerated.
2. **Corrections.** `wilson(11, 32)` is about (0.204, 0.517), not (0.205, 0.518); `false_pass_rate` is stated as
   `fn / (tp + fn)`. Neither changes a test that was built from the earlier text, which accepts a band.
3. **Known gap: match selection.** When several fetched matches qualify for one leg the spec does not choose. The oracle pins
   the outcome on `traces/v1` only. A builder's tie rule that this spec does not state is untested complexity until the
   Pass 1 on PR #2 measures whether the oracle needs it; the PM closes the gap in the next amendment, with that measurement.
4. **Acceptance gaps found in review, for slice 2 and not slice 1's pass or fail.** "Every check has a test built to fail
   it" needs a test-to-check mapping and a negative control per check. "Every dynamic string is escaped" needs the list of
   dynamic fields and adversarial inputs. "Every text pair AA" needs an enumerated procedure (each foreground token over each
   background it is used on, composited for gradients and scrims). Acceptance 4 does not say which command regenerates which
   of the three reports (`report` writes the HTML and JSON, `calibrate --md` the Markdown). "About 1000 px" leaves the width
   open. "One sentence" and "nothing else moves" in the README need a scoped textual comparison. Inputs the spec leaves open:
   a `final` that is valid JSON and not a dict, a null or absent tool result, tool spans with equal start times, duplicate
   candidate event ids, equal match scores.
