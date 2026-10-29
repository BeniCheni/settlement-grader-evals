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
5. **INCOMPLETE_LEG_LIST**: an answer was returned and the number of legs in it is fewer than the ticket's, which is the
   code's own wording. A missing `legs` key counts as zero. A final that lists more legs than the ticket is not flagged
   (amendment 6).
6. **WRONG_NON_GRADE**: the final result is VOID, UNSETTLED or NEEDS_HUMAN, differs from the key's result, and is not
   a NEEDS_HUMAN on a case whose `accept_needs_human` is true. PUSH is a settled result and not a refusal to grade, so it
   is not here (amendment 6). **Only the result is compared, never the net**: an
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
      skipped. An event that is missing from the frozen set (the lookup's `RuntimeError`) skips that candidate, and no other
      exception from that lookup is swallowed. When more than one fetched match qualifies for a leg, the one with the highest
      minimum of its two team scores is used; on a tie in that score a `get_match_facts` result beats a synthetic full-time
      score; any remaining tie goes to the first one seen, in trace order (amendment 7).
    - *Re-grade*: `check_gold.auto_grade(leg, facts)`; only `W`, `L` and `P` are decisive. `OPEN`, `None` or an exception means
      skip that leg.
    - *Committed grades*: for leg index `i`, the `i`-th entry of `leg_results` in **every** `settle_ticket` call (including
      one that errored) and the `i`-th leg's `result` in the final answer. A hit when any committed grade among `W`, `L`, `P`,
      `VOID` differs from the re-grade. `MOOT`, `OPEN` and `NEEDS_HUMAN` are not contradictions.

## Statistics (contract: `scorer/stats.py`)

`confusion(predicted, truth)` returns `{tp, fp, fn, tn}` from two equal-length lists of booleans (a positive is a failure;
`fn` is a real failure the check missed, the dangerous error; unequal lengths raise `ValueError`); `agreement(c)`;
`cohen_kappa(c)`, `None` when chance agreement is 1; `wilson(k, n, z=1.96)`, `(0.0, 1.0)` when `n` is 0;
`false_pass_rate(c)`, `fn / (tp + fn)`, or `None` when there are no real failures; `meets_bar(c, min_agreement=None, min_kappa=None)`,
which resolves the two thresholds at call time to `stats.MIN_AGREEMENT` (0.85) and `stats.MIN_KAPPA` (0.6) and is true only
when both are met and neither is `None` (every word a report prints about the bar derives from those two constants, amendment 10).
`meets_bar` tests the two numbers only: the third part of the trust bar, that every
false pass was read, is a human act reported beside it and never folded into it. Tests must include these hand-worked tables: `tp 8, fn 7, fp 4, tn 31` gives
agreement 0.78, kappa about 0.444 and false-pass rate 7/15; `tp 1, fn 6, fp 0, tn 93` gives agreement 0.94 and kappa about
0.237; an always-pass judge (`tp 0, fn 7, fp 0, tn 93`) gives agreement 0.93 and kappa 0.0; `wilson(11, 32)` is about
(0.204, 0.517).

## Calibration (contract: `scorer/calibrate.py`)

`calibrate(run_dir, cases_path="data/gold.json", codes_path="data/codes_v1.json",
readings_path="data/calibration_readings_v1.json")` returns `{"run", "cases", "codes": [row]}`; each row has `code`, `n`, `tp`,
`fp`, `fn`, `tn`, `agreement`, `kappa`, `false_pass_rate`, `meets_bar`, `human_near_miss`, `false_passes` and `false_fails`
(each `{case_id: text}`), and `readings` (the code's entry from the readings file). The command
`python3 -m scorer.calibrate <run_dir> [--cases CASES] [--json OUT] [--md OUT]` prints the Markdown table and optionally writes
both files. A test must fail when any disagreement lacks a reading. `python3 -m scorer.score <run_dir> [--cases CASES]
[--json OUT]` prints, per code, how many tickets it flags, and writes per-ticket flags with evidence. `--cases` names the cases
file the run was graded from (default `data/gold.json`; `traces/smoke-1` is graded from `data/smoke.json`), and `scorer.report`
takes it too. A case or file that is missing is a usage error: exit status 2, a message naming the case id or file and the
flag, no traceback, nothing written (amendment 8).

## The page (contract: `scorer/report.py`) and `ui/ledger.css`

`python3 -m scorer.report <run_dir> --out reports/calibration-v1.html --json reports/calibration-v1.json` writes one
self-contained page with `ui/ledger.css` inlined. It is deterministic (the same inputs give the same bytes; no timestamps, no
machine paths). The committed `reports/calibration-v1.{html,json,md}` are tested against a regeneration, so a stale report
fails a test. Content: a cover (run, model from `run_meta.json`, ticket count; a headline question; three stat tiles: checks
whose numbers meet the bar, false passes, flags the labels lack); **a provenance line on the cover saying the result is in
sample**, because the labels were made on these 32 traces and the checks were built against them, and that it shows the
checks reproduce the labels they were built from, not that they generalise (the wording after amendment 13); a table with one row per check (caught of the human-labelled, agreement,
kappa, false passes, false fails, a pill that says whether the numbers meet the bar and does not say the check is trusted,
and, on a row that has false passes only, a figure for false passes read, "n of n", amendment 5); one note per disagreement
with its recorded reading, which carries a "read" badge only when it has one; a colophon naming the
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
two label gaps, `B01` and `A02`, are the owner's to rule, and he ruled yes on 28 Oct 2026; they land in their own PR with a
`calibration-v2`, and v1 is not rewritten); a dependency of any kind.

## The reference

The PM seat keeps a prototype described as the oracle's source. It is not in this repo; the builder was instructed not to
access it. The oracle and this spec are the contract. The builder's access was not independently verified, as recorded in
the run-history note of `docs/cursor-prompts/slice-1-build.md`.

## Amendments after the build began (Wed 28 Oct 2026)

Made in the docs PR after PR #2 was built against the text above. The reviewer of PR #2 holds it to the amended text and
says which parts of the PR the amendments make stale. The oracle is unchanged, and so is every `meets_bar` value in it.

1. **Page copy (owner's ruling).** The pill and the tile say what `meets_bar` is, the two numbers, and no tile, pill or
   sentence presents the numbers alone as the trust verdict. Each row shows false passes read as "n of n" (`n` is the length
   of `false_passes`; a read one has a non-empty reading), beside the pill and not inside it. The builder chooses the words
   within that constraint and the reports are regenerated. (Refined by amendment 5.)
2. **Corrections.** `wilson(11, 32)` is about (0.204, 0.517), not (0.205, 0.518); `false_pass_rate` is stated as
   `fn / (tp + fn)`. Neither changes a test that was built from the earlier text, which accepts a band.
3. **Known gap: match selection.** When several fetched matches qualify for one leg the spec does not choose. The oracle pins
   the outcome on `traces/v1` only. A builder's tie rule that this spec does not state is untested complexity until the
   Pass 1 on PR #2 measures whether the oracle needs it; the PM closes the gap in the next amendment, with that measurement.
   (Closed by amendment 7.)
4. **Acceptance gaps found in review, for slice 2 and not slice 1's pass or fail.** "Every check has a test built to fail
   it" needs a test-to-check mapping and a negative control per check. "Every dynamic string is escaped" needs the list of
   dynamic fields and adversarial inputs. "Every text pair AA" needs an enumerated procedure (each foreground token over each
   background it is used on, composited for gradients and scrims). Acceptance 4 does not say which command regenerates which
   of the three reports (`report` writes the HTML and JSON, `calibrate --md` the Markdown). "About 1000 px" leaves the width
   open. "One sentence" and "nothing else moves" in the README need a scoped textual comparison. Inputs the spec leaves open:
   a `final` that is valid JSON and not a dict, a null or absent tool result, tool spans with equal start times, duplicate
   candidate event ids, equal match scores. (Amendment 9 records their behaviour and test coverage; the rest stays for slice 2.)

## Amendments after PR #2 was reviewed (Wed 28 Oct 2026, evening)

Made in the docs PR that follows the merge of PR #2 (`701e42a`). The code on `main` already does what these say, because the
owner's rulings were applied in PR #2's Pass 2; this text catches the spec up. The oracle, the readings and the labels are
unchanged.

5. **The false-passes-read figure (owner's ruling).** It appears on a row that has one or more false passes, as "n of n", and
   not on a row with none; the cover tile reports the total. The same holds in the Markdown report. A reading counts as read
   when it is a string that is non-empty after trimming whitespace, by one definition shared by the page, the Markdown
   report, the check that every disagreement has a reading, and the note badges. This refines amendment 1.
6. **Two checks follow their codes' wording (owner's rulings).** INCOMPLETE_LEG_LIST flags only a final that lists fewer legs
   than the ticket, and WRONG_NON_GRADE no longer includes PUSH. Neither moves an oracle field: across the tracked runs the
   only PUSH final is `A13` (in `traces/v1` and in `traces/v1-2026-10-14`, one of the two halves v1 is built from), which matches its key,
   and no tracked final lists more legs than its ticket. The receipt is below the amendments.
7. **Match selection (owner's ruling).** Closes amendment 3; the rule is in check 11. Counting, per leg, the fetched matches
   that qualify (both names at 0.5 or better), on 28 Oct 2026: `traces/v1` has 55 legs with one and 21 with none, the dated
   subset 51 and 17, the adversarial subset 4 and 4, and `traces/smoke-1` 8 and 0 (receipt below the amendments). No leg in a
   tracked run has two, so the oracle cannot tell the rules apart: first wins, last wins, a synthetic score first and the
   lowest score all pass it. A synthetic test with two qualifying matches pins the rule.
8. **Commands and provenance.** `--cases` and the exit-2 usage error are described under Calibration. The provenance text is
   chosen by trace identity and not by directory name. A run whose trace ids are exactly `traces/v1`'s is "in sample", with the
   cover text above. A non-empty proper subset of them is "in sample, a subset, not independent evidence". Any other run has
   `in_sample` null and says that run-specific calibration is not established, because the labels in `data/codes_v1.json`
   were made on `traces/v1` and are not labels for another run's outputs.
9. **Inputs amendment 4 left open.** A `final` that is valid JSON and not a dict is `None`. A null or
   absent tool result is `None`, with the span's error recorded separately. Tool spans with equal start times sort by span id.
   Duplicate candidate event ids keep the first eligible one, and a fetched facts result for an event suppresses the
   synthetic one. An absent `run.tool_calls` is 0 even if tool spans exist. Tests pin these inputs except the combination of
   absent `run.tool_calls` with tool spans. Equal match scores are amendment 7. The remaining
   gaps in amendment 4 (an enumerated contrast procedure, a negative control per check, the widths, the README comparison)
   stay for slice 2.
10. **`meets_bar` signature.** The thresholds are `None` sentinels resolved from `stats.MIN_AGREEMENT` and `stats.MIN_KAPPA`
    at call time, so patching the constants changes both the decisions and the words. The effective defaults are unchanged.
11. **Provenance of the tracked runs (a finding, not a rule).** `traces/v1` is the union of `traces/v1-2026-10-14` (30
    tickets) and `traces/v1-adv` (2): its own `run_meta.json` names its `run_id` "v1 (v1-2026-10-14 + v1-adv)". Their spans are
    byte-identical to its (315 and 14 of its 329, with the same trace and span ids), so they are not independent
    samples and the scorer's flag counts on them sum to v1's. The only tracked run that shares no span with v1 is
    `traces/smoke-1` (3 tickets, 39 spans); the runs that measure the floor are slice 2's, committed as `traces/aa-*`.
    Slice 2's floor must not count the two dated runs as runs (receipt below the amendments).
12. **Not yet written: the failing-row wording.** The pill's "not 85% or 0.6" does not say which number failed. No row fails
    on `traces/v1`, so the words wait for the first held-out calibration that can have a failing row, which is slice 3's.
13. **Not yet written: the provenance sentence stops naming a count (owner's ruling, 29 Oct 2026).** The cover line in
    `scorer/calibrate.py`, the module docstrings of `scorer/__init__.py` and `scorer/calibrate.py`, and the committed
    `reports/calibration-v1.{html,json,md}` say that two checks were fixed while reading the 32 traces, and the line for a run
    outside `traces/v1` says the checks "were tuned on traces/v1". That is history of the withheld prototype and cannot be re-run
    from this repo, so the owner ruled it removed and not backed by a receipt. The three sentences become, for exactly
    `traces/v1`: "In sample. The labels were made on these 32 traces and the checks were built against them. This shows the
    checks reproduce the labels they were built from, not that they generalise."; for a proper subset: "In sample. This is a
    subset of traces/v1, the run the checks were built against. It is not independent evidence that they generalise."; for any
    other run: "Run-specific calibration is not established. The labels in data/codes_v1.json were made on traces/v1, not on
    this run. The supplied labels have not been established as labels for this run; these numbers do not establish held-out
    agreement or generalisation." The code, its tests and the regenerated reports are their own PR: until it lands, the spec
    describes the intended words and the page still says the old ones. No figure moves.

### Receipt for amendments 6, 7 and 11, and the counts in the scope doc

The run counts printed below come from this script, run from the repository root on Python 3.9.6 and 3.14.7 with the same output.
It reads the scorer's own internals (`_facts_seen`, `_teams`, `_orientation_score`, `_leg_count`), so a later rename moves the
script and not the figures; the tests pin the behaviour. Figures from runs that are not tracked in this repo are not claimed.

```
python3 - <<'PY'
import collections, csv, json, os, re, sys
sys.path.insert(0, ".")
from grader import espn
from scorer import checks, traces

RUNS = ["traces/v1", "traces/v1-2026-10-14", "traces/v1-adv", "traces/smoke-1"]
for run in RUNS:
    legs = collections.Counter()  # qualifying fetched matches per ticket leg
    push, more, final_legs, with_evidence = [], 0, 0, 0
    for rec in traces.load_run(run):
        final = rec["final"] or {}
        if str(final.get("ticket_result", "")).upper() == "PUSH":
            push.append(rec["case_id"])
        more += checks._leg_count(final) > checks._leg_count(rec["ticket"])
        for leg in final.get("legs") if isinstance(final.get("legs"), list) else []:
            if isinstance(leg, dict):
                final_legs += 1
                with_evidence += isinstance(leg.get("evidence"), str) and bool(leg["evidence"].strip())
        seen = checks._facts_seen(rec)
        for leg in rec["ticket"].get("legs") or []:
            home, away = checks._teams(leg)
            n = 0
            for _prefer, facts in seen:
                try:
                    teams = espn.team_objects(str(facts.get("event_id")))
                except RuntimeError:
                    continue
                n += checks._orientation_score(home, away, teams) >= 0.5
            legs[n] += 1
    print(run, "legs by matches", dict(sorted(legs.items())), "PUSH finals", push, "finals with more legs", more)
    with open(os.path.join(run, "results.csv"), encoding="utf-8") as handle:
        seconds = sum(float(row["wall_clock_s"]) for row in csv.DictReader(handle))
    print(run, "final legs", final_legs, "with non-empty evidence", with_evidence, "wall_clock_s total", round(seconds, 1))


def spans(run):
    with open(os.path.join(run, "settlement-traces.json"), "rb") as handle:
        text = handle.read().decode("utf-8")
    decoder = json.JSONDecoder()
    found = {}
    for match in re.finditer(r'\{\s*"traceId"\s*:', text):
        span, length = decoder.raw_decode(text[match.start():])
        key = (span["traceId"], span["spanId"])
        if key in found:
            raise ValueError("duplicate span id")
        found[key] = text[match.start():match.start() + length].encode("utf-8")
    if len(found) != len(list(traces._spans(json.loads(text)))):
        raise ValueError("span extraction incomplete")
    return found


base = spans("traces/v1")
for run in RUNS[1:]:
    other = spans(run)
    print(run, sum(base.get(k) == v for k, v in other.items()), "of", len(other), "spans identical to traces/v1's", len(base))
PY
```

```
traces/v1 legs by matches {0: 21, 1: 55} PUSH finals ['A13'] finals with more legs 0
traces/v1 final legs 53 with non-empty evidence 52 wall_clock_s total 745.0
traces/v1-2026-10-14 legs by matches {0: 17, 1: 51} PUSH finals ['A13'] finals with more legs 0
traces/v1-2026-10-14 final legs 48 with non-empty evidence 47 wall_clock_s total 693.2
traces/v1-adv legs by matches {0: 4, 1: 4} PUSH finals [] finals with more legs 0
traces/v1-adv final legs 5 with non-empty evidence 5 wall_clock_s total 51.8
traces/smoke-1 legs by matches {1: 8} PUSH finals [] finals with more legs 0
traces/smoke-1 final legs 6 with non-empty evidence 6 wall_clock_s total 94.7
traces/v1-2026-10-14 315 of 315 spans identical to traces/v1's 329
traces/v1-adv 14 of 14 spans identical to traces/v1's 329
traces/smoke-1 0 of 39 spans identical to traces/v1's 329
```
