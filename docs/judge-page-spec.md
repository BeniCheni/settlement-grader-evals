# The judge comparison page: the spec for step 7

Written Sat 31 Oct 2026 by the PM seat. It is the spec of record for the step 7 build prompt, which will be archived
under `docs/cursor-prompts/`. Precedence: the owner's rulings, then `docs/judge-spec.md`, then this spec, then the build
prompt, then `docs/week-2-package.md`. `AGENTS.md` outranks all of them on process, and nothing here loosens it. Where
this spec says "contract" the name or behaviour is fixed; elsewhere the builder decides and says why in the PR.

## Why this page exists

Assignment 1 asks for a comparison view: per rubric, the judge's verdict on each row next to the hand label, the
agreement rate, and the disagreeing rows with the judge's reasoning (the course's Step 10). The plan's decision 2 makes
that view this repo's own page in the Haunted Ledger style, and the package puts it at
`submissions/week-02/assignment-1/comparison.html`. `report` computes the per-rubric agreement figures; the page also
counts rows, rubrics, changed labels and judges whose numbers meet the bar. The page adds
what the Markdown leaves out: every row's verdict, not only the disagreements, the text of each reading, and the owner's
reason on each changed label.

**Scope (the owner's ruling, Sat 31 Oct 2026).** Step 7 is the judge comparison page only. The A/B page needs inputs
that step 8 decides (the one change, the paired interval's method and the thresholds), so it is specified with step 8
and built after it. The plan records the move.

## The command (contract: `scorer/judge.py`)

`report` gains one output: `--html OUT`. It takes the same inputs and runs the same validation as today, and writes the
page alongside `--md` and `--json` through `write_outputs`, so an error at any point exits with status 2, prints one
message, shows no traceback and writes no file. `OUT` is handled as `--md` and `--json` are; the page never prints its
own path, so no output path reaches a committed file. For the same inputs, the Markdown and the JSON stay byte for byte
what they are on `main` at this spec's merge, so `reports/judge-set1.md` and `reports/judge-set1.json` do not change.

`export-course` writes a fourth file, `comparison.html`, byte for byte what `report --html` writes for the same inputs.
This amends `docs/judge-spec.md`, "The course deliverables": its three files keep their contract.

The page is committed as `reports/judge-set1.html`, regenerated from the committed set-1 inputs:

```bash
python3 -m scorer.judge report --labels labels/set1.jsonl --final labels/set1-final.jsonl --readings labels/set1-readings.json --provenance labels/set1-provenance.txt --verdicts judgments/set1-llama3.1-8b --md reports/judge-set1.md --json reports/judge-set1.json --html reports/judge-set1.html
```

The test that regenerates the committed set-1 report (`tests/test_judge.py`) covers the page too, so a stale page fails
it.

## What the page shows (contract on content, the builder's on layout)

One self-contained page with `ui/ledger.css` inlined, as `scorer/report.py` does for the calibration page. No script
element, no external asset beyond the Google Fonts link the calibration page already uses, and a colophon that gives the
command line the Markdown prints (`report_command`) and says the fonts load from Google Fonts.

1. **The cover.** The labels file, the model and its digest, the row count and the rubric count; the headline question
   "Do the judges agree?"; three stat tiles on the labels the worst-judge rule uses (the final labels when given,
   otherwise the first-pass ones, and the tile says which): judges whose numbers meet the bar, named by `bar_words()`;
   false passes; false fails. The worst judge, worded as the Markdown words it, ties included.
2. **The provenance statement**, on the cover beside the tiles, verbatim from the `--provenance` file under the heading
   `PROVENANCE_HEADING` ("Written by hand, not computed"). Code cannot decide that a result is held out
   (`docs/judge-spec.md`, "The report"), so this hand-written statement is the page's sentence on in sample or held out,
   which `AGENTS.md`'s UI rules require beside every calibration number. Each rubric section repeats one fixed sentence
   beside its numbers: "Whether these figures are in sample or held out is stated by hand on the cover, not computed."
   It is a sentence, never a chip.
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
4. **Every row, per rubric.** One line per label row in the labels file's order: run and case id; the judge's verdict;
   the first-pass human label and, when given, the final one; whether judge and human agree on the labels the cover
   uses; and the judge's reason. A row whose label changed shows the owner's change reason verbatim. A row that
   disagrees on the first-pass or the final labels shows its reading's text verbatim, with a "read" badge when it has
   one (`has_reading`) and "unread" in blood when it does not. A row that agrees on both first-pass and final labels
   (or on the first-pass labels when no final labels are given) shows no reading badge. The table stacks at 760 px and narrower, as `.ledger` does.
5. **The colophon**, as above.

Computed text never contains "held out", "trusted" or "generalise": the first may appear only inside the reproduced
provenance statement. `tests/test_provenance_words.py` already reads every file directly in `reports/`, so the committed
page must also be clear of its guarded phrases.

## The style (contract: `ui/ledger.css`)

`ui/ledger.css` stays the only source of colour and type. A primitive the page needs and the stylesheet lacks (the
matrix table, a disagreement row) is added there, with both themes. Changing the stylesheet changes the bytes of
`reports/calibration-v1.html`, which inlines it, so that page is regenerated in the same commit and its test stays
unmodified. Ink speaks, slime confirms, lamp marks where data came from and nothing else, blood alarms: an agreeing row
is ink, not slime, and blood marks a false pass, a false fail, an unread disagreement and a pill that misses the bar.

## Acceptance

1. `report --html` on the test fixtures and on the committed set-1 inputs; `reports/judge-set1.html` regenerates byte
   for byte on Python 3.9 and 3.14, and `reports/judge-set1.md` and `.json` are byte-identical to `main`.
2. `export-course` writes `comparison.html` equal to `report --html`, with and without `--final`; its other three files
   are unchanged.
3. Every dynamic string is HTML-escaped: a test feeds markup through the judge's reason, a reading, a change reason, the
   provenance text and the labels path, and finds it escaped.
4. A test that strips every string that came from an input file (the provenance statement, reasons, readings, change
   reasons, paths) finds none of "held out", "trusted" or "generalise" in what is left, on a fixture and on the committed
   page, and finds the per-rubric sentence in every rubric section.
5. A test that counts, per rubric, the rows the page renders, its agree and disagree marks, its "read" and "unread"
   badges and its change reasons, against the labels, verdicts, readings and final labels, on both a fixture and the
   committed page.
6. Status 2, one message and nothing written for each existing refusal when `--html` is given, and when `--html` names
   the same path as `--md` or `--json`; no partial file when a later output fails to write.
7. `tests/test_contrast.py`'s list of pairs gains every text and background pair the new primitives add, in both themes,
   and loses none; the PR reports the lowest ratio and its pair.
8. The page at 360, 375, 390 and about 1000 px in dark and light: the viewport is set before any capture,
   `document.documentElement.scrollWidth` equals `window.innerWidth` in all eight, no console error, the only external
   requests are Google Fonts, the focus ring is visible, and `prefers-reduced-motion` is respected.
9. At least three mutations named in the PR body, each turning the suite red for the right reason, among them: swapping
   the matrix's two disagreement cells, dropping one reading's text, and marking an agreeing row as a disagreement.
10. The suite and `python3 -m compileall -q .` on Python 3.9 and 3.14; the existing tests unmodified except three, each
    only gaining, without removing or weakening any existing assertion: the set-1 regeneration test gains the page, the
    export test's set of written file names gains
    `comparison.html`, and the contrast test's list gains pairs (item 7); and the privacy sweep (`AGENTS.md` rule 6),
    patterns stated, counts only.

## Out of scope

The A/B page (step 8); the case files themselves, which `sheet` renders into the ignored `sheets/` and the page does not
embed; links into the trace viewer; any change to the labels, readings, provenance, verdicts or rubrics; `README.md`,
`docs/` and `AGENTS.md`, which the PM seat updates after the merge; a dependency of any kind.
