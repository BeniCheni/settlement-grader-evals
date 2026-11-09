# Validation of the synthetic drafts (TZ=America/New_York)

Step 5 of `docs/week-4-package.md`. A hand-check is a label check. It does not set `verified_by_beni` (ruling 12).

## How the drafts were made

`python3 -m scorer.golden draft` ran on Mon 9 Nov 2026 at `main` `5d42fe9`, on the owner's machine, in a fresh clone without
`private/` or `data/espn_cache/`, with Ollama 0.34.0 and `llama3.1:8b` (model id `46e0c10c039e`) at temperature 0 and seed 0.
There were 26 batches in order: 18 named `w4-s1-<gap>`, 147 draws, then 8 named `w4-s2-<gap>`, 37 draws. Case ids and repeats
depend on earlier batches, so the order is part of the result.

Five seed rows per gap came from one rule fixed before any draw: rank the 30 real rows by whether they need the gap's topic,
then by how many non-null slip wordings they hold, then by case id, and take the first five. Batch sizes were chosen from a
structure-only dry run, with no model, so that each topic could reach at least 5 rows and both outcomes. No batch name was
changed after seeing a result.

| Draws | Kept | `unparseable` | `topic` | `repeat` | `result_word` | `digit` | `no_key` |
|---|---|---|---|---|---|---|---|
| 184 | 113 | 42 | 17 | 6 | 5 | 1 | 0 |

The first real batch, under the prompt step 4 shipped, kept none of 8, and those drafts were discarded. PR #55 replaced that
prompt, so every row here was written under the prompt it pins.

## The owner's check

`python3 -m scorer.golden sample` chose 30 rows, one per intent first and the rest in the fixed shuffled order, and prints:

```text
2 of 30 [0.018477, 0.213238]
```

That is an error rate of 6.7%, with a 95% Wilson interval of 1.8% to 21.3%. The records are in `labels/golden-check.jsonl`.

| Case | In the sample | Error | What the slip got wrong |
|---|---|---|---|
| `S094` | yes | `wording_changes_market` | The bet is a draw, and the slip reads "Denmark ML 3-Way" |
| `S157` | yes | `wording_changes_market` | The bet is on AFC Bournemouth's cards, and the slip names Manchester City |
| `S054` | no | `wording_changes_market` | Three whole-match first-half totals, each worded as one team's total |

`S054` is outside the sample and not in the rate. The three rows are left out of the candidates.

**Read the rate with this in mind.** The owner's first pass marked all 31 rows OK. The PM seat then flagged these three from
the same sheet, and the owner changed them after reading the bet and the slip side by side. So both sampled errors came from
the PM seat's flag, and the rate is the combined result of the two reads, not the owner's alone. The PM seat looked closely
at those three and did not go through the other 28 in the same way, so the true rate may be higher.

Under ruling 47 a generic slip title is not an error: 84 of the 113 rows carry a title such as "Multi-Bet Ticket". The check
judges each leg's wording.

## What was not checked

Of the 110 synthetic rows that go on, 28 carry `label_checked_by_beni` true and 82 were not hand-checked. At 2 in 30 about 5 of
those 82 have wording that describes another bet, and the interval allows more. Their keys are unaffected, because no word a
model writes reaches a key.

## Where this leaves the set

`python3 -m scorer.golden candidates` gives 160 rows: 110 synthetic, 30 real and 20 hand-crafted. Each of the 19 topics has at
least 5 rows except `void_postponed`, which has its one row by rulings 17 and 27. Every topic that can win or lose has both.
`draw_no_bet`, `first_half`, `goalscorer`, `second_chance_token` and `team_total` each rest on one winning row. All of this is
before the pilot.

The PM seat drafted the 20 hand-crafted rows at the owner's request, and the owner kept all 20 with the keys shown. Those keys
come from the frozen facts through `key_for_ticket`, or are `NEEDS_HUMAN` by design, except `E19`, whose market the code cannot
grade. Rows `E01` to `E04` name matches that are in no frozen file, and no result is claimed for them.
