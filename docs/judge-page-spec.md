# The judge comparison page: the spec for step 7

Written Sat 31 Oct 2026 by the PM seat. It is the spec of record for the step 7 build prompt, archived as
`docs/cursor-prompts/judge-page-build.md`; what review changed is under "Amendments at review".
Precedence: the owner's rulings, then `docs/judge-spec.md`, then this spec, then the build
prompt, then `docs/week-2-package.md`. `AGENTS.md` outranks all of them on process, and nothing here loosens it. Where
this spec says "contract" the name or behaviour is fixed; elsewhere the builder decides and says why in the PR.

## Why this page exists

Assignment 1 asks for a comparison view: per rubric, the judge's verdict on each row next to the hand label, the
agreement rate, and the disagreeing rows with the judge's reasoning (the course's Step 10). The plan's decision 2 makes
that view this repo's own page in the Haunted Ledger style, and the package puts it at
`submissions/week-02/assignment-1/comparison.html`. `report` computes the per-rubric agreement figures; the page also
counts rows, rubrics, changed labels and judges whose numbers meet the bar. The page adds what the Markdown leaves out:
every row's verdict, not only the disagreements, the text of each reading, and the owner's reason on each changed label.

**Scope (the owner's ruling, Sat 31 Oct 2026).** Step 7 is the judge comparison page only. The A/B page needs inputs
that step 8 decides (the one change, the paired interval's method and the thresholds), so it is specified with step 8
and built after it. The plan records the move.

## The command (contract: `scorer/judge.py`)

`report` gains two options, `--html OUT` and `--rubric-provenance FILE`, given together or not at all: either one alone
is a usage error. With them it takes the same inputs and runs the same validation as today, validates the new file, and
writes the page alongside `--md` and `--json` through `write_outputs`, so an error at any point exits with status 2,
prints one message, shows no traceback and writes no file. `OUT` is handled as `--md` and `--json` are. The page does not use
the actual output path in its contents: its colophon names the fixed output `comparison.html` instead (the owner's ruling,
Sat 31 Oct 2026), so that `report --html` and `export-course` write the same bytes and the printed command runs as
shown. `FILE` passes through `relative_path`, as `--provenance` does, because the page's colophon names it. For the same
inputs, the Markdown and the JSON stay byte for byte what they are on `main` at this spec's merge: neither reads the new
file, so `reports/judge-set1.md` and `reports/judge-set1.json` do not change.

**The per-rubric provenance file (contract; the owner's ruling, Sat 31 Oct 2026).** `--rubric-provenance` names a JSON
object whose keys are exactly the labels' rubric names and whose values are strings with at least one non-whitespace
character. It is written by hand, like the `--provenance` file, and for the same reason: code cannot decide that a
result is held out (`docs/judge-spec.md`, "The report"). Each value is that rubric's statement: prose of one or more
sentences saying whether its figures are in sample or held out, and what they do and do not show. A file that is
missing, is not that object, lacks a rubric, names one the labels do not have, or holds an empty value is a validation
error. The set-1 file is `labels/set1-rubric-provenance.json`, committed with this spec; its statements restate, rubric
by rubric, what `labels/set1-provenance.txt` says.

`export-course` gains `--rubric-provenance FILE`. Given, it writes a fourth file, `comparison.html`, byte for byte what
`report --html` writes for the same inputs; not given, it writes the same three files as today. This amends
`docs/judge-spec.md`, "The course deliverables": its three files keep their contract.

The page is committed as `reports/judge-set1.html`, regenerated from the committed set-1 inputs:

```bash
python3 -m scorer.judge report --labels labels/set1.jsonl --final labels/set1-final.jsonl --readings labels/set1-readings.json --provenance labels/set1-provenance.txt --verdicts judgments/set1-llama3.1-8b --md reports/judge-set1.md --json reports/judge-set1.json --html reports/judge-set1.html --rubric-provenance labels/set1-rubric-provenance.json
```

The test that regenerates the committed set-1 report (`tests/test_judge.py`) covers the page too, so a stale page fails
it.

## What the page shows (contract on content, the builder's on layout)

One self-contained page with `ui/ledger.css` inlined, as `scorer/report.py` does for the calibration page. No script
element, no external asset beyond the Google Fonts link the calibration page already uses, and a colophon that gives the
command line the Markdown prints (`report_command`) followed by `--rubric-provenance` and its path and by `--html
comparison.html`, which, run from the repository root, writes a page byte for byte equal to this one, and says the fonts
load from Google Fonts.

1. **The cover.** The labels file, the model and its digest, the row count and the rubric count; the headline question
   "Do the judges agree?"; three stat tiles on the labels the worst-judge rule uses (the final labels when given,
   otherwise the first-pass ones, and the tile says which): judges whose numbers meet the bar, named by `bar_words()`;
   false passes; false fails. The worst judge, worded as the Markdown words it, ties included.
2. **The provenance.** The statement from the `--provenance` file, verbatim, on the cover beside the tiles, under the
   heading `PROVENANCE_HEADING` ("Written by hand, not computed"). Beside each rubric's figures, in that rubric's
   section, its own statement from the `--rubric-provenance` file, verbatim, under the same heading, and no other
   rubric's. These hand-written statements are the page's sentences on in sample or held out, which `AGENTS.md`'s UI
   rules require beside every calibration number. Code writes no sentence of its own about it. Each is prose, never a
   chip, and may run to several sentences, as that rule says (the owner's ruling, Sat 31 Oct 2026).
3. **One section per rubric, in the report's order.** The rubric's SHA-256 and its text fact ("same text as when the
   labels were made", or the changed form) exactly as the report states them, and the `UNPARSED` count. For the
   first-pass labels and, when given, the final ones, side by side where width allows:
   - the agreement matrix as a two-by-two table, judge PASS and FAIL by human PASS and FAIL, each cell with its count,
     report name and statistical name (`JP_HF` and `fn`, and so on), and the false-pass or false-fail description for
     the disagreement cells;
   - agreement as a percentage and to four decimals as in the report, kappa to four decimals or "none" when it cannot be
     computed, and whether kappa is at least 0.6, named as the course's bar;
   - a pill naming `bar_words()` or `not_bar_words()` for `meets_bar`, with the false passes read beside it as "k of n"
     when there are any. Nothing presents the numbers alone as the trust verdict: the word "trusted" appears nowhere in
     computed text, because `meets_bar` tests two numbers and not whether every false pass was read;
   - the number of labels the owner changed on adjudication for this rubric, when final labels are given.
4. **Every row, per rubric.** One entry per label row in the labels file's order: run and case id; the judge's verdict;
   the first-pass human label and, when given, the final one; whether judge and human agree on the labels the cover
   uses; and the judge's reason. A row whose label changed shows the owner's change reason verbatim. A row that
   disagrees on the first-pass or the final labels shows its reading's text verbatim, with a "read" badge when it has
   one (`has_reading`) and "unread" in blood when it does not. A row that agrees on both first-pass and final labels (or
   on the first-pass labels when no final labels are given) shows no reading badge. The table stacks at 760 px and
   narrower, as `.ledger` does.
5. **The colophon**, as above.

Computed text never contains "held out", "held-out", "trusted", "generalise" or "generalize", in any case. Any of them
may appear only inside text the page reproduces from an input file. `tests/test_provenance_words.py` already reads every
file directly in `reports/`, so the committed page must also be clear of its guarded phrases.

## The style (contract: `ui/ledger.css`)

`ui/ledger.css` stays the only source of colour and type. A primitive the page needs and the stylesheet lacks (the
matrix table, a disagreement row) is added there, with both themes. Changing the stylesheet changes the bytes of
`reports/calibration-v1.html`, which inlines it, so that page is regenerated in the same commit and its test stays
unmodified. Ink speaks, slime confirms, lamp marks where data came from and nothing else, blood alarms: an agreeing row
is ink, not slime, and blood marks a false pass, a false fail, an unread disagreement and a pill that misses the bar.

## Acceptance

1. `report --html` on the test fixtures and on the committed set-1 inputs; `reports/judge-set1.html` regenerates byte
   for byte on Python 3.9 and 3.14, and `reports/judge-set1.md` and `.json` are byte-identical to `main`. A test runs
   the colophon's command as the page prints it, from a scratch copy of the repository root, and finds the
   `comparison.html` it writes equal to the committed page.
2. `export-course` with `--rubric-provenance` writes `comparison.html` equal to `report --html`, with and without
   `--final`, and its other three files are unchanged; without it, it writes the same three files as on `main`.
3. Every dynamic string is HTML-escaped: a test feeds markup through the judge's reason, a reading, a change reason, the
   provenance text, a per-rubric provenance statement and the labels path, and finds it escaped.
4. A test that strips every string that came from an input file (the provenance statement, the per-rubric statements,
   reasons, readings, change reasons, paths) finds none of the five banned words, in any case, in what is left, on a
   fixture and on the committed page; and a test that finds each rubric's own statement in its section and in no other.
5. A test that counts, per rubric, the rows the page renders, its agree and disagree marks, its "read" and "unread"
   badges and its change reasons, against the labels, verdicts, readings and final labels, on both a fixture and the
   committed page.
6. Status 2, one message and nothing written for each existing refusal when `--html` is given; when `--html` names the
   same path as `--md` or `--json`; when `--html` or `--rubric-provenance` is given without the other; and for each
   refusal of the per-rubric file above. No partial file when a later output fails to write.
7. `tests/test_contrast.py`'s list of pairs gains every text and background pair the new primitives add, in both themes,
   and loses none; the PR reports the lowest ratio and its pair.
8. The page at 360, 375, 390 and about 1000 px in dark and light: the viewport is set before any capture,
   `document.documentElement.scrollWidth` equals `window.innerWidth` in all eight, no console error, the only external
   requests are Google Fonts, the focus ring is visible, and `prefers-reduced-motion` is respected.
9. At least three mutations named in the PR body, each turning the suite red for the right reason, among them: swapping
   the matrix's two disagreement cells, dropping one reading's text, and marking an agreeing row as a disagreement.
10. The suite and `python3 -m compileall -q .` on Python 3.9 and 3.14; the existing tests unmodified except two, each
    only gaining, without removing or weakening any existing assertion: the set-1 regeneration test gains the page, and
    the contrast test's list gains pairs (item 7); and the privacy sweep (`AGENTS.md` rule 6), patterns stated, counts
    only.

## Amendments at review (PR #15, Sun 1 Nov 2026)

What review changed, so a cold reader does not take the contract above for the whole page.

- **Two-tier rows (the owner's ruling).** At 761 px and wider each row's short facts (run, case, verdict, first-pass
  label, final label when given, agreement) sit on one line, each under its own label, and its reason, change reason and
  reading each span the row beneath. The first build inherited `.ledger`'s 26% first column, which gave every reading a
  39 px column and a 292,114 px page at 1000 px while every test and the overflow check stayed green. The rules are
  scoped to `.judge-rows`, and the calibration page's `.ledger` keeps its layout.
- **Empty cells (the owner's ruling).** A row's empty change or reading cell is hidden at every width, so no label sits
  over nothing.
- **Font links (the owner's ruling).** `scorer.report.FONT_LINKS` is the one source, used by both pages.
- **Disclosures (Pass 2).** Each reading's summary is named with its rubric, run and case for assistive technology. An
  unread disagreement is the blood badge alone, with no disclosure.
- **Prose measure (Pass 2).** Above 1200 px the prose stops at 80ch. No test pins it; see the follow-ups in
  `docs/week-2-package.md`.
- **A measured bar for acceptance item 8 (the PM's, in the Pass 2 brief).** `scrollWidth` cannot see a column that is
  too narrow. So item 8 also measures 761, 899 and 1400 px; at about 1000 px the page is no taller than 30,000 px, and
  at each of those widths no short fact breaks across lines. At the merge it was 28,622 px at 1000 px in Chrome 156.

## Out of scope

The A/B page (step 8); the case files themselves, which `sheet` renders into the ignored `sheets/` and the page does not
embed; links into the trace viewer; any change to the labels, readings, either provenance file, verdicts or rubrics;
`README.md`, `docs/` and `AGENTS.md`, which the PM seat updates after the merge; a dependency of any kind.
