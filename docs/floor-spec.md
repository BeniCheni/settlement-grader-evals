# Floor spec: what a run records about its setup, and how two runs compare

Written Fri 30 Oct 2026 by the PM seat, for the builder half of step 2 of `docs/week-2-package.md`. It is the spec of
record for that step's build prompt. `AGENTS.md` outranks it on process, and no line here loosens it. Within that,
precedence runs: the owner's rulings, then this spec, then the build prompt, then `docs/week-2-package.md`. Where this
spec says "contract" the name, format or behaviour is fixed, because a later step reads it; elsewhere the builder
decides and says why in the PR.

## Why this slice exists

Three A/A runs of the v1 configuration (`traces/aa-1`, `traces/aa-2`, `traces/aa-3`) gave the same final answer on all
32 tickets, and 21 of those 32 differ from `traces/v1`. Every one of the four `run_meta.json` files records the same
configuration, and none records the Ollama server version or the model's digest, so nothing in the repo can say what
changed. The owner ruled on Thu 29 Oct 2026 (decision 5 in the plan) that a run records both, that an A/B is read in one
recorded setup, and that a difference between setups is reported as a change of environment. This slice gives the runs
that record and gives the repo one command that compares two runs.

## What a run records (contract: `run_meta.json`)

`run_eval.py` adds two keys to the `run_meta.json` it writes, and changes no other key:

- `ollama_version`: the `version` string from `GET http://127.0.0.1:11434/api/version`.
- `model_digest`: the `digest` of the entry in `GET http://127.0.0.1:11434/api/tags` whose `name` equals the model the
  run uses (`--model`).

Both are read once, before the first ticket is graded. If either request fails, or the reply lacks the value, the run
stops with a one-line message and a non-zero status before it grades a ticket or writes a file; a run is never written
with either key missing or null. Standard library only (`urllib`, as `grader/agent.py` uses), and the requests go to the
same local server the grader already calls. No test opens a network connection: the code that reads the two values takes
an opener (or an equivalent seam) that the tests replace.

The four committed runs are not edited. They stay as they were recorded, without the two keys, and the compare command
says so (below).

## Comparing two runs (contract: `python3 -m scorer.compare`)

`python3 -m scorer.compare <run_a> <run_b> [--cases data/gold.json] [--json OUT]` reads both runs with
`scorer.traces.load_run`, scores each with `scorer.score.score_run` (reuse it; do not re-run the checks another way), and
reports, in this order:

1. **Tickets.** How many case ids each run holds, how many they share, and the case ids found in only one run, each list
   in `case_id` order. A run that holds two records with the same `case_id` is an error.
2. **Final answers.** Over the shared case ids, how many have a different final answer, compared as canonical JSON (sorted
   keys), and those case ids in `case_id` order. A final that is null in one run and not in the other differs.
3. **Codes.** For every code in `scorer.checks.CHECKS`, in that order: its count in A, its count in B and B minus A; then
   the shared case ids whose set of codes differs between the runs, in `case_id` order.
4. **Setup.** The `run_meta.json` keys whose values differ between the runs, other than `run_id`, `n_cases` and
   `outcome_matches`, in sorted order; then, for each run, whether it records `ollama_version` and `model_digest`. When
   either run lacks either key, the output says that the setup of that run is not recorded, so a difference between the
   runs cannot be traced to its setup. It never says the setups were the same when they were not recorded.
5. **Provenance.** For each run, the sentence `scorer.calibrate.provenance_for` gives for its records, verbatim, because
   the code counts come from checks built against `traces/v1` (`AGENTS.md`, "In sample is not held out").

The text goes to standard output. `--json OUT` writes the same facts as JSON with `scorer.stats.canonical_json`. Both are
byte-stable: no timestamp, no absolute path, the same bytes on Python 3.9 and 3.14, and the same bytes for `./traces/x/`
and `traces/x`. A usage or validation error (a missing run, a duplicate `case_id`, a case missing from the cases file, an
unreadable `run_meta.json`) exits with status 2, prints one message, shows no traceback and writes nothing, as the slice 1
commands do. A run without a `run_meta.json` is reported as not recording its setup, not refused.

The command reports differences and draws no conclusion from them: no verdict, no "noise" or "drift" label, no
threshold. Reading a delta is the A/B's job (step 8), with the paired interval decision 5 names.

## What the PR must show

1. `compare traces/aa-1 traces/aa-2` and `compare traces/aa-2 traces/aa-3`: 32 shared tickets, 0 final answers differ, every
   code's difference 0, 0 tickets whose codes differ, and the setup section saying neither run records its setup.
2. `compare traces/v1 traces/aa-1`: 21 final answers differ, matching the plan's floor command; the code counts and the
   tickets whose codes differ, as the command prints them and as `python3 -m scorer.score` on each run confirms.
3. A run pair with a case in only one run, a null final against a non-null one, and a duplicate `case_id`, on fixture
   runs, each with the right output or status 2.
4. The setup section on a fixture pair where both runs record the two keys and they differ, where they are equal, and
   where one run lacks them, with a test that fails if a missing key is ever reported as the same setup.
5. The `run_meta.json` keys from a stand-in server: both values recorded; a failed `/api/version`, a failed `/api/tags`
   and a model missing from the tags each stop the run before any ticket is graded or any file is written; and no
   network connection in any test.
6. The text and JSON regenerate byte for byte on 3.9 and 3.14, with a committed fixture output and a test that fails when
   it is stale.
7. At least three mutations named in the PR body, each turning the suite red for the right reason, among them: comparing
   finals without sorting keys, reporting a missing setup as the same setup, and dropping the provenance sentence.
8. The suite and `python3 -m compileall -q .` on 3.9 and 3.14, the existing tests unmodified, no committed run edited,
   and the privacy sweep.

## Out of scope here

A new grader run; editing any committed run; the paired interval and anything else the A/B reads (step 8); a page for the
comparison (step 7); the judge harness, the rubrics and the labels.
