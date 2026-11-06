# RAG spec: the retrieval seams, the golden set, the four scorers and the harness

Written Fri 6 Nov 2026 by the PM seat, for steps 3, 4, 6, 7 and 8 of `docs/week-4-package.md`. It is the spec of record for
their build prompts, which follow its merge. `AGENTS.md` outranks it on process, and no line here loosens it. Within that,
precedence runs: the owner's rulings in the plan, then this spec, then the build prompts, then the plan. Where this spec
says "contract" the name, format or behaviour is fixed, because a row, a run or a report depends on it; elsewhere the builder
decides and says why in the PR. Where it departs from the plan's wording, "Departures from the plan" says so.

## Why this exists

Week 4 asks for a golden set pinned as v1, four RAG scorers reported in two pairs, one groundedness failure, and a paired
bootstrap on one retrieval change. The report comes from one config and one command. The repo has a gold set of 32, traces that record every
tool result, a plain-code re-grader and fact checks. It has no golden-set row, no way to change how `lookup_rule` matches a
topic, no retrieval or groundedness score, and no bootstrap. Two builder PRs add them: the seams and the set tooling (steps 3
and 4), then the scorers and the harness (step 8). The owner may merge the two into one PR if time presses, as the plan allows.
The rows, the hand-checks, the runs and the uploads are the PM seat's and the owner's. No test calls a model or a hosted
service.

## Inputs

Reuse these, and copy none of them: `scorer.traces.load_run`; `scorer/stats.py`; from `scorer/checks.py`, `_facts_seen`,
`_best_facts`, `_committed` and `_teams`; from `check_gold.py`, `auto_grade`, `side`, `score` and `ou`; `run_eval.ticket_from_case`,
`outcome_match`, `TICKET_FIELDS` and `LEG_FIELDS`; `grader.rules.RULES` and `lookup_rule`; `grader.tools.call_tool` and
`settle_ticket`; `grader.espn.match_facts`; from `scorer/judge.py`, `build_adapter`, which gives the Ollama and fake adapters
the wording model needs; and each real leg's `espn_event` in `data/gold_check.json`.

## The owner's rulings on this spec

The owner accepted each as the PM seat recommended it, on Fri 6 Nov 2026, and the plan's table records them. The contracts
below carry them.

| # | Question | Answer | Why |
|---|---|---|---|
| 14 | Is the market-to-topic table below the source of every row's needed contexts? | Yes | Recall's denominator is a rubric, and the owner writes rubrics |
| 15 | Do `X01` and `X02` stay out of v1? | Yes | They are attacks, and ruling 10 keeps attacks out |
| 16 | May synthetic tickets use the four Champions League matches of 14 Oct that the frozen file holds as scheduled? | Yes | They are the only way to test `unsettled`. They have been played since, so a ticket on them tips nothing (Hard Rule 4), and the grader can only answer UNSETTLED |
| 17 | Does `void_postponed` go without rows in v1, named as a gap in `dataset.md`? | Yes | No frozen match is postponed, and adding one is an `ESPN_LIVE=1` PR (Hard Rule 3), so it waits for v2 |
| 18 | Are the A/B's bars below approved as drafted? | Yes | They are written before any run, as the plan requires |

```bash
python3 -c 'import json; from grader import espn; f=json.load(open("data/espn_frozen.json")); ms=[espn.match_facts(k.split("event=")[1]) for k in f if "summary?event=" in k]; print([(m["status"], m["kickoff_utc"], m["competition"]) for m in ms if m["status"]!="STATUS_FULL_TIME"])'
```

## Step 3: the retrieval seams

### Nothing changes when idle (contract)

`SYSTEM_PROMPT`, `TOOLS`, `DEFAULT_BUDGETS`, `RULES`, `lookup_rule`, `grader/espn.py`, `check_gold.py` and
`data/espn_frozen.json` do not change. Without the new flags, the requests `grade_ticket` sends are byte for byte what they are on
`main`, and `run_eval.py` writes the same files with the same keys. Both variants and the pilot's weakened config are tool
runners, the seam Week 3 added to `grade_ticket`, so no grader function changes.

### Two runners (contract: `grader/retrieval.py`)

- **`rule_runner(mode)`.** `"exact"` returns a runner that behaves exactly as `call_tool`. `"alias"` returns one that differs
  only on `lookup_rule`: it normalises the topic as `lookup_rule` does, then takes the first that applies: the key itself if it
  is in `RULES`; the key's entry in `ALIASES`; the one topic sharing the most words with the key, when exactly one shares the
  most and it shares at least one; otherwise the key unchanged. It returns `lookup_rule` of that choice, so a hit has exactly
  the keys today's hit has, and a miss returns today's `UNKNOWN_TOPIC` result byte for byte. The model sees no new key.
- **`disabled_rule_runner()`.** Every `lookup_rule` call returns `{"topic": <the normalised key>, "rule": ""}`: the call
  succeeds and carries no rule, as the course's weakened config returns an empty list. Every other tool goes to `call_tool`.

Words are the normalised key split on `_`, without `the`, `a`, `to`, `of`, `and`, `or`, `bet` and `market`.

**`ALIASES` (contract).** It was written knowing the six misses on record (`match_result`, `anytime_goalscorer`, `total_goals`,
`both_teams_to_score`, `goals`, `combo`), so B's effect on those six is in sample, and the report says so.

| Key after normalising | Topic |
|---|---|
| `match_result`, `full_time_result`, `full_time`, `result`, `moneyline`, `money_line`, `ml`, `1x2`, `three_way`, `3_way`, `90_minutes` | `moneyline_3way` |
| `both_teams_to_score`, `both_teams_score`, `gg` | `btts` |
| `total_goals`, `goals`, `over_under`, `total` | `totals` |
| `anytime_goalscorer`, `first_goalscorer`, `goal_scorer`, `scorer` | `goalscorer` |
| `team_total_goals`, `team_goals` | `team_total` |
| `half_time`, `halftime`, `1st_half`, `second_half`, `2nd_half` | `first_half` |
| `corner`, `total_corners` | `corners` |
| `card`, `bookings`, `booking_points` | `cards` |
| `sot`, `shots` | `shots_on_target` |
| `dnb` | `draw_no_bet` |
| `combo`, `parlay`, `accumulator`, `acca`, `same_game_parlay`, `sgp` | `parlay_moot` |
| `boost`, `odds_boost` | `profit_boost` |
| `bonus_bet`, `free_bet` | `bonus_bet_stake` |
| `second_chance`, `insurance` | `second_chance_token` |
| `advance`, `qualify`, `to_qualify` | `to_advance` |
| `postponed`, `abandoned`, `void` | `void_postponed` |
| `not_final`, `live`, `in_progress` | `unsettled` |

### `run_eval.py` (contract)

- `--rule-match exact|alias` runs the cases through `rule_runner`, and `run_meta.json` gains `rule_match`. A's run gives
  `exact` explicitly, so both runs record which variant they were.
- `--disable-tool lookup_rule` runs them through `disabled_rule_runner`, and `run_meta.json` gains `disabled_tools`. Any other
  tool name is refused with status 2.
- The two flags exclude each other, and either one with a case that carries `poison`: refused with status 2, nothing written.
- A cases path ending `.jsonl` is read as one case per line, skipping blank lines. Any other path is read as it is now.
- Neither metadata key appears without its flag.

### What the step 3 PR must show

1. Byte identity: on a fake `_chat`, the payloads with no flag and with `--rule-match exact` equal
   `tests/fixtures/redteam/idle-requests.json`, the golden file `tests/test_idle_requests.py` already checks.
2. The alias runner: each `ALIASES` key reaches its topic; each of the six recorded misses reaches its topic; every `RULES` key
   returns what `lookup_rule` returns; a key with a tie, or no shared word, returns `lookup_rule`'s `UNKNOWN_TOPIC` result byte
   for byte; and every hit's keys equal `lookup_rule`'s.
3. The disabled runner: every `lookup_rule` call returns an empty rule, every other tool's result equals `call_tool`'s, and
   `data/espn_frozen.json`'s bytes are the same before and after.
4. `run_eval.py`: both metadata keys, both refusals, and a `.jsonl` file that reads to the same cases as the `.json` it was made from.
5. At least three mutations named in the PR body, each turning the suite red for the right reason, among them: the alias runner
   adding a key to a hit, and the exact runner differing from `call_tool`.
6. The suite and `python3 -m compileall -q .` on 3.9 and 3.14, the existing tests unmodified, and the privacy sweep.

## Step 4: the golden set tooling

### The row (contract: `scorer/golden.py`)

A golden row carries every field a row of `data/gold.json` carries, so `ticket_from_case`, `outcome_match` and every check read
it unchanged, plus these:

| Field | Value |
|---|---|
| `case_id` | Real rows keep theirs (`A01` to `C14`). Synthetic rows are `S001` upward, and the owner's are `E01` upward |
| `blend` | `real`, `synthetic` or `hand_crafted` |
| `source` | Real rows keep `data/gold.json`'s value. Synthetic rows say exactly `synthetic`. The owner's say `hand_crafted_by_owner` |
| `question` | `json.dumps(ticket_from_case(row), indent=1, ensure_ascii=False)`: what follows `Grade this ticket:\n` in the model's first message |
| `contexts` | The needed items, below, as `{"leg", "kind": "event", "event_id", "fact"}` or `{"leg", "kind": "rule", "topic"}`, with `leg` null for a ticket-level rule, sorted by leg, then kind, then id |
| `ground_truth` | The criteria text, below |
| `expected` | Real rows: unchanged from `data/gold.json`. Synthetic rows: from `key_for_ticket`. The owner's rows: the owner's |
| `difficulty` | `easy`: one leg, settled on the final or regulation score. `medium`: one leg needing another fact, or a boosted, bonus or second-chance stake. `hard`: two or more legs, a key of `NEEDS_HUMAN`, `UNSETTLED` or `VOID`, or an edge row |
| `intent` | The leg's first topic for one leg; `parlay` for two or more |
| `segment` | `single` or `parlay`, a dash, then `cash`, `boosted`, `bonus_bet`, `free_bet` or `second_chance` |
| `label_checked_by_beni` | True only for a row the owner checked and passed at step 5. It never sets `verified_by_beni` (ruling 12) |
| `pilot` | `keep`, `no_rule_signal` or `known_failure`, set at step 6, and absent before |

**Serialisation (contract).** One row per line, `json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
and a newline, in `case_id` order. No timestamp and no path.

### Needed contexts (contract; ruling 14)

**Events.** A real leg's `espn_event` in `data/gold_check.json`; the event the generator chose for a synthetic leg; the event the
owner names for an edge row, or none for a "no good doc" row. `fact` names the field the market settles on, for the ground truth
only: recall and precision score the event and the topic, which is what the course's `contexts` hold.

**Topics, per leg.** The first row whose words the market contains, case ignored, after any text in parentheses is removed.
The removal matters: "Moneyline (live, placed in-play at 0-1, 34:06 1st half)" is a real leg, and without it the first-half row
would claim it.

| Market contains | Topics | Fact |
|---|---|---|
| `half time/` or `ht/ft` | `first_half`, `moneyline_3way` | `score_halftime`, `score_regulation_90` |
| `double chance` | `double_chance` | `score_regulation_90` |
| `draw no bet` | `draw_no_bet` | `score_regulation_90` |
| `advance`, `qualify` or `to lift` | `to_advance` | `penalty_shootout` |
| `corner` | `corners` | `team_stats.corners` |
| `card` or `booking` | `cards` | `team_stats.yellow_cards` |
| `shots on target` | `shots_on_target` | `team_stats.shots_on_target` |
| `goalscorer` or `goal scorer` | `goalscorer` | `goals` |
| `both teams` or `btts` | `btts` | `score_regulation_90` |
| `1st half`, `first half`, `2nd half` or `second half` | `first_half`, and `totals` when it also says `total` | `score_halftime` |
| `total goals by` or `team total` | `team_total` | `score_regulation_90` |
| `total`, or a market that starts with `goals` | `totals` | `score_regulation_90` |
| `handicap`, `spread` or `first team to score` | `general` | `score_regulation_90`, or `goals` for first to score |
| `money`, `match result`, `full time`, `90 min`, `1x2`, or the word `ml` | `moneyline_3way` | `score_regulation_90` |

**Topics, per ticket.** `bonus_bet_stake` for a `bonus_bet` or `free_bet` stake; `second_chance_token` for a `second_chance`
stake; `profit_boost` when `boost_or_token` names a boost; `parlay_moot` for two or more legs. Per leg, `unsettled` when its
match is not final in the frozen facts. A market no row matches is refused by the generator, and a test fails if any leg of the
30 real rows matches none.

### The key (contract: `key_for_leg`, `key_for_ticket`)

`key_for_leg(leg, facts)` returns `(grade, evidence)` or `(None, reason)`. It calls `check_gold.auto_grade` for every market that
handles, except one: a handicap on a whole line pushes when the margin plus the line is zero, which `auto_grade` grades as a loss.
It adds the markets `auto_grade` lacks, each by its rule's text: double chance; cards, as `NEEDS_HUMAN` when the slip defines no
counting scheme and `team_stats` disagrees with the card list, and otherwise from `team_stats`; team shots on target from
`team_stats`, and a player's as `NEEDS_HUMAN`; and to advance, from the shootout or extra time when the facts record them.
`check_gold.py` does not change; the PR body lists every market where the two differ.

`key_for_ticket(row)` grades every leg against its frozen facts and settles through `grader.tools.settle_ticket` with the row's
stake, stake kind, price and printed payout. A synthetic row is drafted only when every leg's key is a grade, never `None`.

### Ground truth (contract)

One line per leg, then one for the ticket. A leg line says the grade it must commit, the fact and rule that decide it, and, for
a `W` or `L`, that it must never commit the other. The ticket line says the `ticket_result` it must return, the `net` when the
ticket settles, and that `net` is null when it does not. For example:

```text
Leg 1 must be L: regulation 2-2 (score_regulation_90); moneyline_3way says a team selection loses on a draw. Never W.
Ticket must be LOSS with net -10.0.
```

### The generator (contract: `python3 -m scorer.golden draft`)

`--gap TOPIC`, `--n` up to 20, `--batch NAME`, `--seed-cases` (five real case ids), `--adapter ollama:llama3.1:8b` or
`fake:FILE` (ruling 3), and `--out data/golden/drafts/<batch>.jsonl`. A batch draws its choices from
`random.Random(int(sha256(batch).hexdigest(), 16))`, so a batch name reproduces its structure.

- **Code picks the structure.** An event from the 43 frozen summaries that can settle the gap's market: a completed one, a
  scheduled one for `unsettled` (ruling 16), the shootout match for `to_advance`. The market name, from a fixed list per topic
  that includes the real slips' variants ("Match Result", "Full Time result", "1X2", "BTTS"); the line; the selection; one to
  three legs, and two or more for `parlay_moot`. The stake, from 5, 10, 20 or 25. The stake kind, cash unless the gap is a stake
  topic. A price from a fixed list of American prices, a boost text for `profit_boost`, and a printed payout only for a cash stake.
  The book, from the names in `data/gold.json`. `kickoff_et` from the facts' `kickoff_utc`, through `zoneinfo`'s
  `America/New_York`. Every amount is invented, and none is derived from a real one (Hard Rule 1).
- **The model writes only words:** `slip_text` and each leg's `market_wording_on_slip`, given the structure and the seed rows'
  wording fields and nothing else. Its reply is JSON with those keys, and any other key is dropped. The system prompt tells it
  never to state a result, a score or an outcome.
- **Cuts, before anyone reads a row,** each logged with the case id and the reason in `<batch>.cuts.jsonl`: an unparseable
  reply; a digit in the words that is not in the leg's line, price or date; a result word (`won`, `lost`, `win`, `loss`,
  `settled`, `void`, `push`, `final score`); words whose market maps to another topic than the structure's; and a repeat of an
  earlier row's event, market, line and selection.
- **`expected` comes from `key_for_ticket` and nothing else.** The model's reply never reaches it.

### The owner's check (contract: `python3 -m scorer.golden sample`)

It picks 30 or more synthetic rows that survived the cuts, at least one per `intent`, the rest at random from
`random.Random("w4-check")`, and writes `labels/golden-check-sheet.md`: each row's ticket, its needed contexts, its key with the
evidence. The owner records `labels/golden-check.jsonl`, one `{"case_id", "ok", "error", "note"}` a row, with `error` one of
`wrong_key`, `wording_changes_market`, `duplicate`, `generic` or `other`. The error rate prints as k of n with its Wilson interval.
A failed row is cut or fixed, and a fixed row is checked again.

### The pilot (contract: `python3 -m scorer.golden pilot`)

It reads the candidates and two runs from one session: `traces/w4-pilot-strong`, with no flag, and `traces/w4-pilot-weak`, with
`--disable-tool lookup_rule`. A run passes a row when `outcome_match` holds against the row's key. Under ruling 4:

| Strong | Weakened | Tag |
|---|---|---|
| Pass | Fail | `keep` |
| Pass | Pass | `no_rule_signal`, kept on its key and its contexts |
| Fail | either | `known_failure`, kept when the key holds: `verified_by_beni`, or `AGREE` in `data/gold_check.json`, or computed by code and passed in the owner's check where sampled. Otherwise listed for the owner to fix or drop |

It writes `pilot.md`: each tag's count, every row not kept and why, both run ids and their model digest.

### Freeze (contract: `python3 -m scorer.golden freeze`)

It writes `data/golden/v1.jsonl` from the kept rows and `data/golden/v1.sha256`, one line, `<sha256>  data/golden/v1.jsonl`, the
format of `data/redteam/frozen.sha256`. It refuses fewer than 150 rows (ruling 1), and refuses to write over a `v1.jsonl` with
other bytes: new rows go to `v2`. A test fails when v1's bytes differ from its hash, and another when
`packages/rag-eval/assignment-1/golden_set.jsonl` differs from v1 by a byte.

### LangSmith (contract: `uploaders/langsmith_pin.py`, the owner's shell)

Outside `scorer/` and the tests, and never imported by either; it imports `langsmith` inside `main`, which needs the dependency
paragraph `AGENTS.md` asks for. It reads its key from the environment and prints no part of it. It refuses when v1's bytes do
not match their hash, creates the dataset `settlement-grader-golden`, adds one example per row (inputs `question`; outputs
`ground_truth` and `expected`; metadata `case_id`, `blend`, `difficulty`, `intent`, `segment`), tags that version `v1`, and prints
the dataset id and the version id, which the owner writes into `dataset.md` (ruling 6). The PR body cites the SDK's documentation
for each call it makes.

### What the step 4 PR must show

1. Every distinct market of the 30 real rows maps to the topics a test pins for it, the parenthesised moneyline above among them.
2. `key_for_leg` agrees with `auto_grade` on every market `auto_grade` decides, over every frozen completed event, except the
   whole-line handicap push, which a test pins.
3. For the 30 real rows, the count where `key_for_ticket` agrees with the key in `data/gold.json`, and every disagreement listed in
   the PR body. Only 6 keys are verified, so neither side is called right.
4. A hostile fake reply carrying `expected`, `ticket_result` or a score changes nothing in the row's `expected`.
5. Each cut fires on a fake reply built to trip it, and a clean reply is kept.
6. Byte-stable serialisation, the freeze refusals and both hash tests.
7. `uploaders/` compiles, and no test imports it or reads a key.
8. At least three mutations named, each turning the suite red for the right reason.
9. The suite and `compileall` on 3.9 and 3.14, the existing tests unmodified, and the privacy sweep.

## Step 8: the four scorers, the bootstrap and the harness

### Retrieved items (contract)

From a record's `tools`, in call order: a `get_match_facts` call whose result has no error gives `("event", event_id)`; a
`lookup_rule` call gives `("rule", topic)` when its result has no error, and `("rule_error", the requested topic)` when it has
one. A repeat of an item already listed is dropped. `find_match` and `settle_ticket` give no item. Retrieved items come from the
record and never from the row: the row's `contexts` are needed items only, as the course starter warns.

### The scorers (contract: `scorer/rag.py`)

Each is `f(output, expected, metadata, **kwargs)` and returns a float from 0 to 1, or `None` when it does not apply, with the
reason kept for the report. `output` is `{"answer", "retrieved_contexts", "record"}`, the final, the items and the `load_run`
record; `expected` is the row's `ground_truth`; `metadata` is `{"question", "ground_truth_contexts", "row"}`, the starter's names.

| Scorer | Half | Rule |
|---|---|---|
| `context_recall` | Retrieval | Needed items found among the retrieved ÷ needed items. `None` when nothing is needed |
| `context_precision` | Retrieval | Over the retrieved list, the sum of precision at k at each relevant position ÷ the number of relevant positions; 0 when none is relevant or nothing was retrieved. `None` when nothing is needed |
| `faithfulness` | Generation | Supported claims ÷ claims. A leg is one claim when any grade is committed for it, by `checks._committed`, and it is supported only when every grade committed for it is. A grade is supported when: with no facts for the leg (`_best_facts` over `_facts_seen`), it is `NEEDS_HUMAN`; when it is `MOOT`, another leg has a committed `L`; otherwise it equals `key_for_leg` on those facts. A leg whose key is `None` is left out and counted. A score the final's evidence cites for a leg, either way round, is one more claim, supported when it equals that leg's `score_regulation_90`, `score_halftime` or `score_final`. `None` when there is no claim |
| `answer_relevancy` | Generation | The share of four tests that hold: the final has one leg per ticket leg; its legs are numbered 1 to n in order; its `ticket_result` is one of the six the system prompt names; and it equals the `ticket_result` of the last `settle_ticket` call that did not err. 0 with no final |

**Worked examples, each a test on a recorded run:**

| Run, case | What happened | Scores |
|---|---|---|
| `v1`, `A01` | One boosted leg, right answer; it read the match and `moneyline_3way`, and never `profit_boost` | recall 2/3, precision 1, faithfulness 2/2, relevancy 1 |
| `aa-1`, `C09` | Right answer, LOSS, with no tool call: four grades and no facts | recall 0, faithfulness 0/4, relevancy 3/4 |
| `v1`, `C09` | Facts read for all four legs; leg 4 committed P where the facts say L | faithfulness 7/8 |
| `v1`, `C13` | Facts read (0-0); legs committed W, L, L where they say L, W, W; right answer, LOSS | faithfulness 1/4, relevancy 3/4 |

And one by hand: needed `{event E1, moneyline_3way}`, retrieved `[rule_error match_result, event E1, rule moneyline_3way]`:
relevant positions 2 and 3, precision `(1/2 + 2/3) / 2 = 0.583`, recall 1.

### The bootstrap (contract: `scorer/stats.py`)

`paired_bootstrap(a, b, n_boot=10000, seed=7)` returns `(mean_delta, lo, hi)` for `mean(b - a)`, by the course starter's
algorithm: `random.Random(seed)`, each resample `n` draws of `rng.choice` over the differences, the means sorted, `lo` at index
`int(0.025 * n_boot)` and `hi` at `int(0.975 * n_boot)`. Unequal or empty inputs raise `ValueError`. `bootstrap_mean(xs, n_boot,
seed)` is `paired_bootstrap` against zeros. Tests: constant differences give a zero-width interval; the same seed gives the same
bytes; `lo <= mean <= hi`; one small input's output is pinned.

### Pairing and the bars (contract; ruling 18)

The A/B pairs cases by `case_id` over v1. A case where a metric is `None` in either variant leaves that metric's pairs, and the
report prints how many left. B ships only when all three hold, and the report prints each with its value:

| Bar | Holds when |
|---|---|
| Recall | The 95% interval of mean(B − A) `context_recall` lies above 0 |
| Faithfulness | Its interval's lower bound is −0.05 or more |
| Outcome | On `outcome_match`, `paired_difference`'s upper bound on the fall is 0.05 or less: B loses at most 5 points |

A recall interval that crosses zero is no-ship and still meets the course, which accepts a correctly reported null.

### The config (contract: `packages/rag-eval/assignment-2/config.yaml`)

JSON syntax, which is valid YAML 1.2 (ruling 8). Keys, and no others: `dataset`, `dataset_sha256`, `model`, `variants`
(`{"a": {"rule_match": "exact"}, "b": {"rule_match": "alias"}}`), `runs` (`{"a": "w4-a", "b": "w4-b"}`), `bootstrap`
(`{"n_boot": 10000, "seed": 7}`), `bars` (the three above, as numbers), `statement` (`reports/rag-statement.md`), `report`
(`packages/rag-eval/assignment-2/report.md`), `json` (`reports/rag.json`), `langsmith_version` and `braintrust_experiments`,
each null until the owner fills it. An unknown or missing key is refused.

### The commands (contract)

```bash
python3 -m scorer.rag run    --config packages/rag-eval/assignment-2/config.yaml --variant a   # needs Ollama
python3 -m scorer.rag run    --config packages/rag-eval/assignment-2/config.yaml --variant b
python3 -m scorer.rag report --config packages/rag-eval/assignment-2/config.yaml              # no model
```

`run` refuses when v1's bytes do not match `dataset_sha256`, or when the run directory exists, and then runs `run_eval.py` over
v1 with the variant's `--rule-match`. `report` calls no model. It refuses when the two runs' `model_digest` or `ollama_version`
differ, or when a v1 case has no record in either, and writes the report and its JSON, byte-stable. A test fails when the
committed report is stale once its runs exist.

### The report (contract)

In order: the hand-written statement, verbatim; the dataset (n, the hash, the LangSmith version id or "not pinned yet"); for each
variant, the four scorers as a mean, the count scored and the count `None`, and a 95% `bootstrap_mean` interval, with the
retrieval pair and the generation pair in separate tables; the weaker half, the pair whose two means average lower; the A/B, each
metric's delta and interval, each bar's value and whether it holds, and the verdict line; the groundedness candidates, every v1
case where A's outcome matches and recall or faithfulness is below 1, with its scores and tool count; the run metadata, model,
digest, Ollama version and flags; and the commands. Every rate prints k of n. The statement says the alias table is in sample
on the six misses, and that 30 rows are tickets the earlier runs used.

### Braintrust (contract: `uploaders/braintrust_eval.py`, the owner's shell)

Outside `scorer/` and the tests, like the LangSmith script. One `Eval` per variant in the project `settlement-grader-rag`, named
for its run id; the data are v1's rows; the task replays the recorded output for each case from that run's traces and calls no
model; the scores are the four functions from `scorer.rag`. It prints each experiment's id, which the owner writes into the
config's `braintrust_experiments` (ruling 7).

### What the step 8 PR must show

1. Each worked example above as a test, and the hand example.
2. A record with no tools scores recall 0 against a row with needed items, so the gold never stands in for the retrieved.
3. At least three mutations named, each turning the suite red for the right reason, among them: recall counting `find_match`
   candidates, faithfulness passing a grade made with no facts, and the bootstrap reusing one index.
4. The config's refusals, `run`'s refusals, `report`'s refusals, and a byte-stable report from fixture runs.
5. `uploaders/` compiles, and no test imports it or reads a key.
6. The suite and `compileall` on 3.9 and 3.14, the existing tests unmodified, and the privacy sweep.

## The runs

All on the owner's machine, in a fresh clone, with `private/` and `data/espn_cache/` absent. Each pair runs in one session, and
`run_eval.py` records the Ollama version and the model digest.

| Run | Command | Step |
|---|---|---|
| `w4-pilot-strong` | `python3 run_eval.py data/golden/candidates.jsonl --run-id w4-pilot-strong` | 6 |
| `w4-pilot-weak` | the same with `--run-id w4-pilot-weak --disable-tool lookup_rule` | 6 |
| `w4-a`, `w4-b` | `python3 -m scorer.rag run` with `--variant a`, then `b` | 9 |

`data/golden/candidates.jsonl` holds the 30 real rows, the synthetic rows that survived the cuts and the owner's check, and the
owner's edge rows.

## Departures from the plan

- **Step 3 has one knob, not three.** The plan names `rule_match`, `top_k` and `window_days`. `top_k` cannot move on this data,
  as the plan's second fact shows, and the A/B changes only `rule_match`, so the other two wait until a run needs them.
- **`answer_relevancy`'s second test** checks that the legs are numbered in order. The plan said each grade names its leg's
  selection, but the final the system prompt asks for has no selection field.
- **`faithfulness` reads the `settle_ticket` call as well as the final.** The plan said "the facts this run fetched", which
  stands; it did not say which grades. `C13` shows why: its final lists one leg, and its settlement committed three.

## Out of scope here

Changing `check_gold.py`, a key in `data/gold.json`, or any `verified_by_beni`; extending the frozen facts, which `void_postponed`
needs (ruling 17); an `autoevals` column (ruling 7); and a page.
