# RAG spec: the retrieval seams, the golden set, the four scorers and the harness

Written Fri 6 Nov 2026 by the PM seat, for steps 3, 4, 6, 7 and 8 of `docs/week-4-package.md`, and revised the same day to
close Cursor's cold read under the owner's rulings 20 to 29. Revised again on Sat 7 Nov 2026 to record what PR #51 built for
steps 3 and 4: its build prompt's fourteen resolutions, the review's fixes, the owner's rulings 30 to 36 and the PM seat's
decisions A to C. Revised again on Sun 8 Nov 2026 to record what PR #53 built for step 8: its build prompt's sixteen
resolutions, the reviews' fixes and the owner's rulings 37 to 45. Revised again on Mon 9 Nov 2026 to record step 4's first
real draft and the owner's rulings 46 to 48, and again the same day to record the pilot, the freeze and rulings 49 and 50. It is
the spec of record for
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
| 17 | Does `void_postponed` go without rows in v1, named as a gap in `dataset.md`? | Yes | No frozen match is postponed, and adding one is an `ESPN_LIVE=1` PR (Hard Rule 3), so it waits for v2. Ruling 27 amends it |
| 18 | Are the A/B's bars below approved as drafted? | Yes | They are written before any run, as the plan requires |

```bash
python3 -c 'import json; from grader import espn; f=json.load(open("data/espn_frozen.json")); ms=[espn.match_facts(k.split("event=")[1]) for k in f if "summary?event=" in k]; print([(m["status"], m["kickoff_utc"], m["competition"]) for m in ms if m["status"]!="STATUS_FULL_TIME"])'
```

### The owner's answers on the cold read

Cursor's cold read of PR #50 left six high and two medium contract findings and asked seven questions; the PM seat added an
eighth. The owner accepted the PM seat's answers on Fri 6 Nov 2026, the plan's table records them, and the contracts below
carry them. Cursor's second read asked 28 and 29, and the owner answered both as the PM seat recommended, the same day.

| # | Question | Answer | Why |
|---|---|---|---|
| 20 | Is `C13`'s relevancy in `v1` 2/4? | No, 3/4 | The second test reads the final's own numbering, with n its own leg count. The first test already fails a final that drops legs, so reading n from the ticket would charge one fault twice |
| 21 | Does a boost make a one-leg ticket settled on the score `medium`? | Yes | Difficulty takes the first that holds: `hard`, then `medium`, then `easy`. An edge row is one of the owner's `hand_crafted` rows |
| 22 | Does `boosted` replace `cash` in the segment? | Yes | A bonus, free-bet or second-chance stake comes first, then a boost, then cash. All 24 real boosts are on cash stakes |
| 23 | Do ticket-level contexts, which have no leg, sort first? | Yes | The row contract writes the whole sort key, so two builds emit the same bytes |
| 24 | Must the generator's order of draws be pinned before the build? | No | Its lists go in a data file the owner approves in the build PR, a test holds it to the same bytes from the same inputs, and the cuts and the owner's sample are pinned exactly. v1 is fixed by its bytes and its hash, not by a second program drawing it again |
| 25 | Does the early-payout market stay on `moneyline_3way`? | Yes | It is on `C14`, whose match was postponed and is in no frozen file. A real leg with no frozen event needs no event, and also needs `void_postponed` when its key is `VOID` |
| 26 | Is a leg whose key is `None` left out of the faithfulness rate? | Yes, and counted | It leaves the numerator and the denominator, and the report prints how many legs left |
| 27 | Does ruling 17 change to: no synthetic `void_postponed` rows in v1, with `C14` as its one row? | Yes | `C14` is real, its key is verified `VOID`, and under ruling 25 it needs `void_postponed`, so ruling 17's "no rows" was wrong. `dataset.md` names the thin coverage |
| 28 | Is an unknown key inside `variants.a` refused? | Yes | Each variant object holds `rule_match` alone. A stray key there is how a second setting could differ between A and B unseen, so the A/B's one change depends on the refusal |
| 29 | Does that refusal also apply inside `langsmith_version` and `braintrust_experiments` once they are objects? | Yes | Each is null or exactly its written keys, so a misspelt key in a recorded version is refused, not kept |

### The owner's answers on PR #51's review

Claude Code's Pass 1 of PR #51 asked five questions, and the owner accepted the PM seat's answers on Sat 7 Nov 2026 as rulings
30 to 34. The owner set 35 and 36 the same day, because Codex has no credit for now. The plan's table records them all, and
the contracts below carry them.

| # | Question | Answer | Why |
|---|---|---|---|
| 30 | Is a First Goal Scorer key `NEEDS_HUMAN` when the match's first goal is an own goal? | Yes | `grader/rules.py`'s goalscorer rule says so, where `check_gold.auto_grade` grades it W or L |
| 31 | Does a cards key count the cards shown, yellow plus red from `team_stats`? | Yes, for the side the market names or for both | The cards rule says cards shown. Its `NEEDS_HUMAN`, when the card list disagrees with `team_stats` and no counting scheme is defined, stays as it is |
| 32 | Does a boosted synthetic ticket print the boosted price and the payout from it? | Yes | Real slips print the boosted price. The ticket price is the unboosted price's profit, raised by the boost text's percentage, plus 1, as an American price; the printed payout is the stake times its decimal, to cents. Leg prices stay unboosted, and the key still nets from the printed payout, as `profit_boost`'s rule says |
| 33 | Does an owner's `hand_crafted` row's key hold in the pilot by itself? | Yes | The owner wrote it. It does not set `verified_by_beni`, and Hard Rule 5's count of verified keys does not change |
| 34 | Does `freeze` write `packages/rag-eval/assignment-1/golden_set.jsonl` beside v1 and its hash? | Yes | The copy is v1's bytes. `freeze` refuses to write over any of the three that holds other bytes, and then writes none, so a freeze never leaves the suite red until a file is copied by hand |
| 35 | Who gives PR #51's Pass 2? | Cursor on Grok 4.7, in place of Codex, narrowed to answering Pass 1, reading its fixes cold and making rulings 30 to 34; Claude Code then reads Cursor's new commits cold | The owner's amendment to ruling 11, for this PR only: the owner has no Codex credit for now. `AGENTS.md` says the builder reviews nothing it built, so Cursor's pass gives no read of its own code. The PM seat sent Claude Code's fixes from that cold read to Cursor at Pass 3, so no line merges read only by its author |
| 36 | Who gives the cold read of the PM seat's PR that records rulings 30 to 36? | Cursor on Grok 4.7, in place of Codex | The owner's amendment to ruling 11, for that PR only, while Codex has no credit. `AGENTS.md` names Codex for a Claude-authored PR. Its rule that a vendor never gives the only cold read of its own work still holds, because Cursor wrote none of that PR. Cursor built PR #51, which it describes, so this read is not independent of that build |

### The PM seat's decisions on PR #51's review

Pass 1 also left three readings this spec had not settled. The PM seat decided each on Sat 7 Nov 2026, and the contracts below
now say them, so they rank as this spec does. None contradicts the text it settles.

- **A.** A lost parlay's ground truth accepts `MOOT` on a leg once another leg is `L`, as `parlay_moot`'s rule and the
  faithfulness rule already do. ("Ground truth" below.)
- **B.** A cards key reads a counting scheme from the leg's market only, never from `market_wording_on_slip`, so no word a
  model writes can change a key. ("The key" below.)
- **C.** A market that names a half reaches `auto_grade` only when it is on the `half time/` or `ht/ft` row, or is exactly a
  first-half total goals market with a line; every other half market has no key. ("The key" below.)

### The owner's answers on PR #53's review

Claude Code's Pass 1 of PR #53 asked five questions, and the owner accepted the PM seat's answers on Sun 8 Nov 2026 as rulings
37 to 41. The owner set 42 the same day, because Codex has no credit for now. Claude Code's cold read of Cursor's Pass 2 commits
asked 43, and the two vendors differed on the severity that 44 settles; the owner answered both as the PM seat recommended, then
set 45. The plan's table records them all, and the contracts below carry them. Ruling 43's count comes from this command, which
printed `15 659 0` (run directories, `lookup_rule` calls, non-string topics) at `20c3291`:

```bash
python3 -c 'import os; from scorer.traces import load_run; ds=[d for d in sorted(os.listdir("traces")) if os.path.exists("traces/%s/settlement-traces.json"%d)]; ts=[t for d in ds for r in load_run("traces/"+d) for t in r.get("tools") or [] if t.get("name")=="lookup_rule"]; print(len(ds), len(ts), sum(not isinstance((t.get("args") or {}).get("topic"), str) for t in ts))'
```

| # | Question | Answer | Why |
|---|---|---|---|
| 37 | Does `report` refuse a pair of runs whose `run_meta.json` differ anywhere but `run_id`, `rule_match` and `outcome_matches`? | Yes | The A/B's one change has to be `rule_match`. The two session checks this spec named let every other setting differ unseen |
| 38 | Is the weaker half named per variant? | Yes, as the report prints it | Each variant has its own means, so the weaker half can differ between them |
| 39 | May the retrieval pair and the generation pair print as plain lines? | No, in separate tables | The report contract says separate tables, and the change is small |
| 40 | Is a `lookup_rule` error whose requested topic is not a string a retrieved, non-relevant item? | Yes | The plan calls an erred lookup noise, and dropping the call could raise precision for a model that sent a malformed topic |
| 41 | Does the Braintrust uploader print no experiment id when any case carries a scorer error? | Yes | `Eval` completes when a scorer raises, so without the refusal a partly failed experiment could be pinned |
| 42 | Who gives PR #53's Pass 2? | Cursor on Grok 4.7, in place of Codex, in the shape of ruling 35; Claude Code then reads Cursor's new commits cold | The owner's amendment to ruling 11, for this PR only: the owner has no Codex credit for now. `AGENTS.md` says the builder reviews nothing it built, so Cursor's pass gives no read of its own code. The PM seat sent Claude Code's commits from that cold read to Cursor at Pass 3, so no line merges read only by its author |
| 43 | Under ruling 40, may a non-string topic share an id with the string of its JSON, so that the integer 3 and the string "3", or a missing topic and the string "null", count once in one record? | Yes | It takes one ticket sending the same topic both ways, and at `20c3291` none of the 659 recorded `lookup_rule` calls has a non-string topic |
| 44 | What severity does PR #53's Pass 1 finding 5 carry, a `report` that named the default config when `--config` sat outside the repository? | Medium | The review skill's table calls a wrong claim medium and does not weigh how reachable it is. The fix stands either way |
| 45 | Who gives the cold read of the PM seat's PR that records rulings 37 to 45? | Cursor on Grok 4.7, in place of Codex, as a fast-track | The owner's amendment to ruling 11, for that PR only, while Codex has no credit. `AGENTS.md` names Codex for a Claude-authored PR. Its rule that a vendor never gives the only cold read of its own work still holds, because Cursor wrote none of that PR. Cursor built PR #53, which it describes, so this read is not independent of that build |

### The owner's answers after step 4's first real run

The first real draft under step 4's prompt kept none of 8, and PR #55 gave the generator a prompt the model could follow. Claude Code's cold read of that PR
stopped on who may read a prompt the PM seat wrote, and the owner set 46 on Sun 8 Nov 2026. The owner set 47 and 48 on Mon 9 Nov 2026.
The plan's table records them too.

| # | Question | Answer | Why |
|---|---|---|---|
| 46 | Who reads PR #55 after Claude Code's cold read, given that the PM seat wrote the prompt it pins? | Cursor on Grok 4.7, narrowed to what it did not write, the prompt's words and Claude Code's two test commits, and it merges if the gate holds | The owner's amendment to ruling 11, for that PR only, while Codex has no credit. `AGENTS.md` says one vendor never gives the only cold read of work that vendor authored, and the PM seat (Claude) wrote the 864 characters that Claude Code alone had read critically. Cursor typed them and built the rest of the PR, so this read is independent of their author and not of the build |
| 47 | Does a generic slip title count as an error in the owner's check? | No, the check judges each leg's wording | Real rows have no slip title, and no word a model writes can change a key. Counting titles would fail 23 of the 30 sampled rows for a line the grader does not settle on |
| 48 | Who gives the cold read of the PM seat's PR that adds the drafts, the owner's check and the edge rows? | Cursor on Grok 4.7, in place of Codex, as a fast-track | The owner's amendment to ruling 11, for that PR only, while Codex has no credit. `AGENTS.md` names Codex for a Claude-authored PR. Its rule that a vendor never gives the only cold read of its own work still holds, because Cursor wrote none of that PR. Cursor built the generator and typed its prompt, so this read is not independent of that build |

### The owner's answers after the pilot

The pilot ran on Mon 9 Nov 2026 in one session, on the 160 rows `candidates` wrote at `main` `d1e59b0`: `w4-pilot-strong`
from 13:36 to 14:47 and `w4-pilot-weak` to 15:53, both `qwen3:8b` under Ollama 0.34.0 with one model digest. An attempt
earlier that afternoon stopped at its 80th row, most likely because the disk had filled, and wrote no run; none of it was
used. `pilot` kept 159 rows, `keep` 14, `no_rule_signal` 66 and `known_failure` 79, and listed `B10` because its key does
not hold. The owner set 49 the same day, and `freeze` wrote v1 from the 159. The owner then set 50, for the PR that records
them. The plan's table records both.

| # | Question | Answer | Why |
|---|---|---|---|
| 49 | Is `B10`, whose key the pilot could not hold, fixed or dropped before the freeze? | Dropped, so v1 holds 159 rows | Its key is the book's void from the owner's log, the code grades the score a loss, `data/gold_check.json` says `DISAGREE`, and `verified_by_beni` is not set, so under ruling 4 the key does not hold. Keeping it would need the owner to verify the key and `pilot` to run again. 159 rows clear ruling 1's 150 |
| 50 | Who gives the cold read of the PM seat's PR that adds the pilot, v1 and its hash? | Cursor on Grok 4.7, in place of Codex, as a fast-track | The owner's amendment to ruling 11, for that PR only, while Codex has no credit. `AGENTS.md` names Codex for a Claude-authored PR. Its rule that a vendor never gives the only cold read of its own work still holds, because Cursor wrote none of that PR. Cursor built `pilot` and `freeze` in PR #51, so this read is not independent of that build |

### The owner's answers after the A/B

The A/B ran in one session from a fresh clone of `main` at `29702e6`: `w4-a` from 21:43 to 22:56 EST on Mon 9 Nov 2026
and `w4-b` to 00:05, both `qwen3:8b` under Ollama 0.34.0 with the pilot's model digest. Each matched 80 of the 159
outcomes. On Tue 10 Nov 2026 the owner pinned v1 in LangSmith and logged both runs to Braintrust from their own shell,
the report's verdict line read ship, and the owner set 51 and 52. `reports/rag.json` then differed between the two
interpreters verify runs, which PR #58 fixed, and the owner set 53 for its read, 54 for `AGENTS.md`'s Pass 1 seat and 55 for where #58's sum starts. The plan's
table records all five.

| # | Question | Answer | Why |
|---|---|---|---|
| 51 | Is variant B, `rule_match` `alias`, ship or no-ship? | Ship | All three bars, set in `docs/rag-spec.md` before either run, hold: recall's interval [0.003, 0.029] lies above 0, faithfulness's lower bound -0.031 is at least -0.05, and the outcome's fall is at most 0.021 against 0.05. The recall gain is in sample on the six misses the alias table was written from, and faithfulness fell by an amount whose interval excludes zero. The statement says both |
| 52 | Who gives the cold read of the PM seat's PR that adds the A/B runs, the report and the package? | Cursor on Grok 4.7, in place of Codex, as a fast-track | The owner's amendment to ruling 11, for that PR only, while Codex has no credit, as for ruling 50. Cursor wrote none of that PR. Cursor built `scorer/rag.py`, `report` and the Braintrust uploader in PR #53 and the LangSmith uploader in PR #51, so this read is not independent of that build |
| 53 | Who gives the cold read of Cursor's PR #58, which makes `paired_bootstrap`'s observed mean add left to right? | Claude Code, the whole PR, as a fast-track | The owner's amendment to ruling 11, for that PR only, while Codex has no credit. Cursor built it, so Claude Code is the seat `AGENTS.md` names. The PM seat dictated the approach, the docstring's gist and the test's input and pinned value, so that read is not independent of those parts, and Claude Code checks each by running it |
| 54 | Does `AGENTS.md`'s Pass 1 seat name Fable 5.2 in place of Fable 5.1? | Yes | Fable 5.2 is Anthropic's current Fable model. The PM seat's step 9 records PR makes the change, and its cold read is Cursor's (ruling 52), so no Claude seat gives the only read of it |
| 55 | Does `paired_bootstrap`'s running total start from the int 0? | Yes | Then the loop gives what 3.9's `sum()` gives for every input, ints included, which is the standard PR #58's brief set: keep every value a 3.9 run produced. Starting from 0.0 differs once ints pass 2**53. `scorer/rag.py` passes only floats today, and only the tests pass ints |

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
- **Neither runner raises.** A model can send any arguments, and `grade_ticket` does not catch a runner's exception, so one
  malformed call would end a run with nothing written. The alias runner resolves a topic only when the arguments are an object
  whose `topic` is a string or absent; any other `lookup_rule` call goes to `call_tool`, which returns today's error result.
  The disabled runner treats a topic that is not a string as a missing one. `rule_runner` with any mode but `exact` or `alias`
  raises `ValueError`; `run_eval.py` refuses such a mode before it builds a runner.

Words are the normalised key split on `_`, with empty strings dropped and without `the`, `a`, `to`, `of`, `and`, `or`, `bet`
and `market`, compared as a set; "shares the most" counts distinct shared words. A null or empty topic normalises to `""`
and misses, as `lookup_rule`'s does.

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
| `card`, `booking`, `bookings`, `booking_points` | `cards` |
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
- `--disable-tool lookup_rule` runs them through `disabled_rule_runner`, and `run_meta.json` gains `disabled_tools`, as
  `["lookup_rule"]`. Any other tool name is refused with status 2.
- Refused with status 2, one line on stderr and nothing written: the two flags together; a `--rule-match` other than `exact`
  or `alias`; either flag with `--guard-input` or `--guard-output`, which no Week 4 run uses; and either flag when any case
  carries a non-empty `poison` list, as `seam_refusal` reads it, checked over every case before `--only` filters them.
- `grade_ticket` receives `rule_runner` with `--rule-match` and `disabled_rule_runner` with `--disable-tool`. With neither
  flag it receives what it did before the seams: `poison_runner` for a case with a non-empty `poison` list, and no
  `tool_runner` for any other case, so a run without a flag calls it exactly as `main` did at `e7680d5`.
- A cases path ending `.jsonl` is read as one case per line, skipping blank lines; a line that is not a JSON object makes the
  file unreadable, with the existing message and status 2. Any other path is read as it is now, and `cases_file` in
  `run_meta.json` stays a relative path.
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
| `contexts` | The needed items, below, as `{"leg", "kind": "event", "event_id", "fact"}` or `{"leg", "kind": "rule", "topic"}`, with `leg` null for a ticket-level rule and `event_id` a string, as in `data/gold_check.json`. Sorted by the key `(0 if leg is null else 1, leg or 0, 0 for an event or 1 for a rule, event_id or topic)`, so ticket-level rules come first (ruling 23) |
| `ground_truth` | The criteria text, below |
| `expected` | Real rows: unchanged from `data/gold.json`. Synthetic rows: from `key_for_ticket`, as `{"ticket_result", "net", "legs": [{"leg", "result"}], "verified_by_beni": false, "accept_needs_human": false, "adjudication": null, "code_check": "key_for_ticket"}`. The owner's rows: the owner's |
| `difficulty` | The first that holds (ruling 21). `hard`: two or more legs, an `expected.ticket_result` of `NEEDS_HUMAN`, `UNSETTLED` or `VOID`, or `blend` `hand_crafted`, which is what "edge row" means here. `medium`: a leg that is not score-settled, a boosted ticket, or a stake kind other than `cash`. `easy`: otherwise, so one score-settled leg on a cash stake with no boost |
| `intent` | For one leg, the first topic in the Topics column of its market's row; `parlay` for two or more |
| `segment` | `single` for one leg or `parlay` for more, a dash, then the first that holds (ruling 22): the stake kind when it is `bonus_bet`, `free_bet` or `second_chance`; `boosted` for a boosted ticket; `cash`. Any other stake kind is refused |
| `label_checked_by_beni` | True only for a row the owner checked and passed at step 5. It never sets `verified_by_beni` (ruling 12) |
| `pilot` | `keep`, `no_rule_signal` or `known_failure`, set at step 6, and absent before |

**A synthetic row's other fields (contract).** `category` is `S_synthetic`; `why_interesting` is `synthetic: gap <topic>,
batch <batch>`; `log_grade` is null; and `bet_type` is one of the values `data/gold.json` already uses, as `generator.json`
maps them: `DNB` for a single draw-no-bet, `ML` for a single moneyline, `Prop` for any other single, `SGP` for a same-event
parlay, `Boost-SGP` for a boosted one, and `Parlay` otherwise. Each leg carries `data/gold.json`'s leg fields and no others. A
leg's event lives only in the row's `contexts`, as the event entry with that leg; `key_for_ticket`, the ground truth and
`candidates` read it there.

**Two terms (contract).** A ticket is *boosted* when its `boost_or_token` contains `boost`, case ignored, and does not contain
`no boost`. A leg is *score-settled* when the Fact column of its market's row, below, is `score_regulation_90` alone. On the 30
real rows these give 24 boosted tickets, all on cash stakes; difficulty 14 `medium`, 16 `hard` and no `easy`, because every
one-leg real ticket is boosted or has a non-cash stake; segments `single-boosted` 12, `parlay-boosted` 12, `single-second_chance`
2, `parlay-bonus_bet` 2, `single-free_bet` 1 and `parlay-cash` 1; and intents `parlay` 15, `moneyline_3way` 11, `goalscorer` 3
and `draw_no_bet` 1. Every `easy` row is therefore synthetic, and `dataset.md` says so.

**Serialisation (contract).** One row per line, `json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
and a newline, in `case_id` order. No timestamp and no path.

### Needed contexts (contract; ruling 14)

**Events.** A real leg's `espn_event` in `data/gold_check.json`; the event the generator chose for a synthetic leg; the event the
owner names for an edge row, or none for a "no good doc" row. `fact` names the field the market settles on, for the ground truth
only: recall and precision score the event and the topic, which is what the course's `contexts` hold.

**A real leg with no frozen event (ruling 25).** When a real leg's `espn_event` is null, it needs no event. Its topics still come
from the table below, and when its expected leg result is `VOID` it also needs `void_postponed`. Today that is `C14` alone: its
match was postponed, its three legs have no frozen event, and all three keys are `VOID`, so it is `void_postponed`'s one row in v1
(ruling 27).

```bash
python3 -c 'import json; g={c["case_id"]:c for c in json.load(open("data/gold.json"))}; print([(r["case_id"], l["leg"], {e["leg"]:e["result"] for e in g[r["case_id"]]["expected"]["legs"]}[l["leg"]]) for r in json.load(open("data/gold_check.json")) for l in r["legs"] if l["espn_event"] is None])'
```

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
stake; `profit_boost` for a boosted ticket; `parlay_moot` for two or more legs. Per leg, `unsettled` when its
match is not final in the frozen facts. A market no row matches is refused by the generator, and a test fails if any leg of the
30 real rows matches none.

### The key (contract: `key_for_leg`, `key_for_ticket`)

`key_for_leg(leg, facts)` returns `(grade, evidence)` or `(None, reason)`, from the first of these that applies.
`check_gold.py` does not change.

1. **No facts.** A leg with no event in the row's `contexts` gives `(None, "no frozen event")`. An event id outside the frozen
   file is refused, `an event is not in the frozen file` with status 2: never a network call and never a traceback.
2. **A half market (decision C).** A market that, after parenthesised text is removed, names `1st half`, `first half`,
   `2nd half` or `second half` gives `(None, "no branch for this half market")`, unless it is on the `half time/` or `ht/ft`
   row, or its plain text is exactly `1st half total goals` or `first half total goals` and the leg has a line. `auto_grade`
   would grade "1st Half Moneyline" on the whole match, "Second Half Total Goals" as a match total and a team's half total
   ("Arsenal 1st Half Total Goals", "1st Half Total Goals by Arsenal") on the whole half: a wrong key, not a missing one. The
   two real markets that name a half, and `generator.json`'s two `first_half` markets, still reach `auto_grade`.
3. **No topic.** A market that matches no row of the topic table gives `(None, "no topic for this market")`.
4. **Its own branch,** when the market's first topic is one that `auto_grade` lacks or misreads. These never reach
   `auto_grade`, and each is `OPEN` while the match is not final.
   - `double_chance`: from the regulation score.
   - `cards`: the cards shown, yellow plus red from `team_stats`, for the side the market names or for both (ruling 31). It
     is `NEEDS_HUMAN` when the card list disagrees with `team_stats` and the market names no counting scheme (`booking point`
     or `second yellow`). The scheme is read from the market only, never from `market_wording_on_slip`, so no word a model
     writes can change a key (decision B).
   - `shots_on_target`: a team's from `team_stats`, for the side the market names or for both; a player's is `NEEDS_HUMAN`.
     `auto_grade` would grade "Team Total Shots on Target" as a goals total. A team market in `generator.json` names its side,
     as `{side} Team Total Shots on Target`.
   - `to_advance`: from the shootout, or from the final score when extra time was played. With neither in the facts there is
     no grade, because one match's regulation score does not decide a two-legged tie or a "to lift" market.
5. **A whole-line push.** A handicap or spread on a whole line, when the margin plus the line is zero, gives `P`, which
   `auto_grade` grades as a loss.
6. **An own goal first (ruling 30).** A first-goalscorer market on a final match whose first goal is an own goal gives
   `NEEDS_HUMAN`, as the goalscorer rule says, where `auto_grade` grades `W` or `L`.
7. Otherwise, `check_gold.auto_grade`.

A test pins each way the two differ, and item 3 of "What the step 4 PR must show" compares them over every market that reaches
`auto_grade`.

`key_for_ticket(row)` grades every leg against its frozen facts and settles through `grader.tools.settle_ticket` with the row's
stake, stake kind, price and printed payout. It never writes `MOOT`. A synthetic row is drafted only when every leg's key is a
grade, never `None`.

### Ground truth (contract)

One line per leg, then one for the ticket. A leg line says the grade it must commit, the fact that decides it, and the rule,
named by its topic (both topics when the leg has two); code paraphrases no rule's text. For a `W` or `L` it adds that the leg
must never commit the other. A leg with no frozen event names no fact and says `no frozen event` in its place. The ticket line
says the `ticket_result` it must return, the `net` when the ticket settles, and that `net` is null when it does not; when
`expected.accept_needs_human` is true, as on `B10` and `C14`, it adds that `NEEDS_HUMAN` also passes, as `outcome_match`
allows.

**A lost parlay (decision A).** When the key is `LOSS` and the ticket has two or more legs, every leg line ends `MOOT also
passes once another leg is L.` `parlay_moot`'s rule lets a grader stop at the first loss, and the faithfulness rule accepts
that `MOOT`. A `W` leg's `Never L` and an `L` leg's `Never W` stay. On a lost parlay's only `L` leg the sentence can never
apply, because every other leg's line asks for a grade that is not `L`: a `W` leg's also says `Never L`, and a `MOOT` leg's
asks for `MOOT`. Another leg could be `L` only by breaking its own line, so there the sentence is inert, not false. For
example:

```text
Leg 1 must be L: regulation 2-2 (score_regulation_90); rule moneyline_3way. Never W. MOOT also passes once another leg is L.
Leg 2 must be W: halftime 1-0 (score_halftime); rule first_half, totals. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.
```

### The generator (contract: `python3 -m scorer.golden draft`)

`--gap TOPIC`, `--n` (draws, 1 to 20), `--batch NAME`, `--seed-cases` (five real case ids), `--adapter ollama:llama3.1:8b` or
`fake:FILE` (ruling 3), and `--out data/golden/drafts/<batch>.jsonl`. A batch draws its choices from
`random.Random(int(hashlib.sha256(batch.encode()).hexdigest(), 16))`. `--gap void_postponed` is refused: v1 has no synthetic
row for it (ruling 27). Also refused with status 2: a `--batch` that does not match `^[A-Za-z0-9][A-Za-z0-9._-]*$`, because it
names a file; a `--gap` that is not a `RULES` key; and `--seed-cases` that are not five real case ids. The fake adapter is
`scorer.judge`'s, keyed by case id: each draw's case id selects its reply, and a missing reply refuses the batch with status 2.
`draft` collects every reply first and writes both of its files last.

**Every command (contract).** Each subcommand takes its paths as arguments, with defaults under the repository root found from
the module's own location, never the working directory, so the tests write only in temporary directories. A command that
refuses writes nothing.

- **The lists (contract: `data/golden/generator.json`; ruling 24).** Everything the generator draws from is data, not code: for
  each leg topic, its market names, which include the real slips' variants ("Match Result", "Full Time result", "1X2", "BTTS"),
  lines and selections; the American prices; the stakes, 5, 10, 20 and 25; the boost texts; and the leg counts, one to three,
  and two or more for `parlay_moot`. The builder writes it and the owner approves it in the step 4 PR. A test fails when a market
  in it matches, through the topic table, a row whose first topic is not the topic it is listed under, or no row.
- **Same inputs, same bytes (contract; ruling 24).** The same code, `generator.json`, batch name, adapter replies and other
  files under `data/golden/drafts/` give the same bytes in `<batch>.jsonl` and `<batch>.cuts.jsonl`. The order of draws is the
  builder's, written in the module's docstring: v1 is fixed by its bytes and its hash, not by a second program drawing it again.
- **Case ids.** Each draw, kept or cut, takes the next `S` number, at least three digits, after the highest in the other
  batches' files, kept and cut, so a cut leaves a gap that its log names.
- **Code picks the structure.** An event from the 43 frozen summaries that can settle the gap's market: a completed one, a
  scheduled one for `unsettled` (ruling 16), the shootout match for `to_advance`. From the lists: the number of legs, each leg's
  market, line and selection, the stake, the price and, for `profit_boost`, a boost text. The stake kind is cash unless the gap
  is a stake topic, and a printed payout is set only for a cash stake. The book, from the names in `data/gold.json`. `kickoff_et`
  from the facts' `kickoff_utc`, through `zoneinfo`'s `America/New_York`; a system without that zone is refused with status 2,
  because the `tzdata` package would be a dependency. Every amount is invented, and none is derived from a real one (Hard
  Rule 1).
- **Prices and the payout (contract; ruling 32).** A single's price is its leg's. A parlay's is the product of its legs'
  decimals, converted back to a whole-number American price. A boosted ticket prints that price's profit, its decimal minus 1,
  raised by the boost text's percentage, plus 1, as an American price; its legs keep the prices they were drawn with. A cash
  printed payout is the stake times the printed price's decimal, rounded to cents, and the key nets from it, as
  `profit_boost`'s rule says.
- **The model writes only words:** `slip_text` and each leg's `market_wording_on_slip`. It is shown the ticket as
  `ticket_from_case` prints it with those two fields absent, which this spec calls the structure, and each seed row's case id and
  wording fields, and nothing else. Its reply is a JSON object, `{"slip_text": "...", "market_wording_on_slip": ["...", ...]}`, with one
  string per leg in leg order, and any other key is dropped. The system prompt tells it never to state a result, a score or an
  outcome; that the seed rows show style and are never copied; that each string holds its leg's market as the structure gives
  it, with the selection and the line when there is one; and to write no date, time or kickoff, no number outside the leg's
  line or market, and none of the words the prompt lists. The prompt's text is pinned by a test, because the first real batch
  under a shorter prompt lost every draw to these cuts.
- **Cuts (contract), before anyone reads a row.** Each is logged in `<batch>.cuts.jsonl` as `{"case_id", "reason"}`, and the
  first that fires, in this order, is the reason:
  1. `no_key`: a leg's `key_for_leg` is `None`. This is checked before the model is called.
  2. `unparseable`: the reply is not that object, or its list does not hold one string per leg.
  3. `result_word`: `won`, `lost`, `win`, `loss`, `settled`, `void`, `push` or `final score` appears in the slip text or a leg's
     wording as a whole word or phrase, case ignored (`\b` on both sides). `winner` and `pushed` do not trip it.
  4. `digit`: a run of digits in a leg's wording that is not a run of digits in that leg's fields of the structure, or a run in
     the slip text that is in no field of the structure, comparing with leading zeros stripped. A leg's fields include its
     market, teams, line, price and `kickoff_et`, and the ticket's its stake, price, boost and printed payout, so their digits pass.
  5. `topic`: a leg's wording matches no row of the topic table, or another row than its market.
  6. `repeat`: the ticket's legs, as a sorted list of `(event_id, market, line, selection)`, equal those of a real row, a row of
     another batch's `<batch>.jsonl`, or an earlier row of this batch.
- **`expected` comes from `key_for_ticket` and nothing else.** The model's reply never reaches it.

### The owner's check (contract: `python3 -m scorer.golden sample`)

It reads the rows of every `<batch>.jsonl` under `data/golden/drafts/`, which are the synthetic rows that survived the cuts,
sorts them by `case_id`, and shuffles that list once with `random.Random("w4-check").shuffle` (ruling 24). For each `intent`,
in sorted order, it takes the first row of the shuffled list with that intent; then it adds rows in shuffled order, skipping
those taken, until it has 30, or every row when fewer survive. It takes more than 30 only when there are more than 30 intents.
It writes `labels/golden-check-sheet.md`: each row's ticket, its needed contexts, its key with the
evidence. The owner records `labels/golden-check.jsonl`, one `{"case_id", "ok", "error", "note"}` a row, with `error` one of
`wrong_key`, `wording_changes_market`, `duplicate`, `generic` or `other`. `generic` means a leg's wording does not say what the bet is, and a slip title is not judged
(ruling 47). The error rate prints as k of n with its Wilson interval.
A failed row is cut or fixed, and a fixed row is checked again.

### Candidates (contract: `python3 -m scorer.golden candidates`)

It writes `data/golden/candidates.jsonl`, in the row serialisation, from three sources:

1. The 30 real rows of `data/gold.json`, every case id but `X01` and `X02` (ruling 15), with every golden field computed and
   `label_checked_by_beni` false.
2. Every row of every `<batch>.jsonl` under `data/golden/drafts/`, left out when the last record for its case id in
   `labels/golden-check.jsonl` has `ok` false, and with `label_checked_by_beni` true when that record has `ok` true.
3. The owner's rows, from `data/golden/edges.jsonl` when it exists.

A missing drafts folder, check file or edges file means none. A repeated case id is refused with status 2, and so is an edges
row of another shape.

**The owner's rows (contract: `data/golden/edges.jsonl`).** One per line: every `data/gold.json` field, with `slip_text`
optional, plus `case_id` (`E01` upward), `blend` `hand_crafted` and `source` `hand_crafted_by_owner`, and on each leg
`espn_event`, the event the owner names or null. `candidates` takes the contexts' events from `espn_event`, computes the other
golden fields, and writes the legs without it. A test fixture proves the path, and `data/golden/edges.jsonl` is committed with
the owner's check.

### The pilot (contract: `python3 -m scorer.golden pilot`)

It reads the candidates and two runs from one session: `traces/w4-pilot-strong`, with no flag, and `traces/w4-pilot-weak`, with
`--disable-tool lookup_rule`. A run passes a row when `outcome_match` holds against the row's key. Under ruling 4:

| Strong | Weakened | Tag |
|---|---|---|
| Pass | Fail | `keep` |
| Pass | Pass | `no_rule_signal`, kept on its key and its contexts |
| Fail | either | `known_failure`, kept when the key holds: `verified_by_beni`, or `AGREE` as the row's status in `data/gold_check.json`, or computed by code and not failed in the owner's check (a synthetic row the check did not sample, or whose last record has `ok` true), or the owner's `hand_crafted` row, which holds by itself (ruling 33). Otherwise listed for the owner to fix or drop |

It writes `data/golden/kept.jsonl`, the kept rows with their `pilot` tag, in the row serialisation, and
`packages/rag-eval/assignment-1/pilot.md`, where the plan's package puts it: each tag's count, every row not kept and why, both
run ids, and their model digests and Ollama versions. It refuses with status 2, writing nothing, when the two runs'
`model_digest` or `ollama_version` differ, when either run lacks a record for a candidate, or when a record's ticket differs
from `json.loads` of the candidate's `question`, which would mean the run graded another ticket.

### Freeze (contract: `python3 -m scorer.golden freeze`)

It reads `data/golden/kept.jsonl` and writes three files (ruling 34): `data/golden/v1.jsonl`; `data/golden/v1.sha256`, one line,
`<sha256>  data/golden/v1.jsonl`, the format of `data/redteam/frozen.sha256`; and
`packages/rag-eval/assignment-1/golden_set.jsonl`, v1's bytes. It refuses fewer than 150 rows (ruling 1). It checks all three
before it writes any, and when one already holds other bytes it refuses, names that file and writes none: new rows go to `v2`.
A test holds the repository's files, and proves on temporary ones that it can fail: while `v1.jsonl` is absent, the hash and the
package's copy must be absent too; once it is present, its bytes must match the hash and the copy must equal them.

### LangSmith (contract: `uploaders/langsmith_pin.py`, the owner's shell)

Outside `scorer/` and the tests, and never imported by either; it imports `langsmith` inside `main`, which needs the dependency
paragraph `AGENTS.md` asks for. It reads its key from the environment and prints no part of it. It refuses when v1's bytes do
not match their hash, creates the dataset `settlement-grader-golden`, and adds one example per row (inputs `question`; outputs
`ground_truth` and `expected`; metadata `case_id`, `blend`, `difficulty`, `intent`, `segment`). Each example makes a version,
and `update_dataset_tag` needs a version's exact `as_of`, so it lists the versions with `list_dataset_versions`, tags the latest
`v1`, reads it back with `read_dataset_version(dataset_id=..., tag="v1")`, and prints the dataset id and that version's `as_of`. The SDK's
`update_dataset_tag` returns `None` and its `DatasetVersion` carries only `tags` and `as_of`, so that pair is v1's LangSmith
version: wherever this spec or the plan says "version id", it means the pair. The owner writes it into `dataset.md` and the
config's `langsmith_version` (ruling 6). The PR body cites the SDK's documentation for each call it makes.

### What the step 4 PR must show

1. Every distinct market of the 30 real rows maps to the topics a test pins for it, the parenthesised moneyline above among them.
2. The 30 real rows' boosted count, difficulty, segment and intent counts are the ones under "Two terms"; `C14`'s contexts hold
   no event and hold `void_postponed`; and a row mixing ticket-level and leg rules sorts its ticket-level rules first.
3. `key_for_leg` agrees with `auto_grade` on every market that reaches `auto_grade`, over every frozen completed event, except
   the whole-line push and the own-goal first goalscorer, which tests pin; and each half market that item 2 of "The key" stops
   has no key.
4. For the 30 real rows, the count where `key_for_ticket` agrees with the key in `data/gold.json`, and every disagreement listed in
   the PR body. Only 6 keys are verified, so neither side is called right.
5. A hostile fake reply carrying `expected`, `ticket_result` or a score changes nothing in the row's `expected`.
6. Each cut fires on a draw or fake reply built to trip it, and a clean reply is kept; `winner`, `pushed` and a leading zero
   trip nothing.
7. `generator.json`'s markets each match their own topic's row; one batch drafted twice gives the same bytes, and a second batch
   name changes the structure; `--gap void_postponed` is refused; and `sample` picks the same rows twice, one per intent first.
8. Byte-stable serialisation, the freeze refusals and the test that holds the three v1 files.
9. `uploaders/` compiles, and no test imports it or reads a key.
10. At least three mutations named, each turning the suite red for the right reason.
11. The suite and `compileall` on 3.9 and 3.14, the existing tests unmodified, and the privacy sweep.

## Step 8: the four scorers, the bootstrap and the harness

### Retrieved items (contract)

From a record's `tools`, in call order: a `get_match_facts` call whose result has no error and has an `event_id` gives
`("event", str(event_id))`; a `lookup_rule` call whose result has no error gives `("rule", the topic its result resolved)`, so
the alias variant is credited with the rule it fetched, and such a result with no string `topic` gives no item; and a
`lookup_rule` call whose result has an error gives
`("rule_error", the requested topic)`. A result that is not a dict counts as an error. When the requested topic is not a string,
the id is `json.dumps` of it with `sort_keys=True`, or of null when it is missing or the call's `args` are not a dict, so the
item is hashable and byte-stable and sits as a non-relevant position in precision (ruling 40). Such an id may equal the string of
its JSON, and the two then count once in one record (ruling 43). A repeat of a `(kind, id)` pair is dropped, the first kept.
`find_match` and `settle_ticket` give no item. Retrieved items come from the record and never from the row: the row's `contexts`
are needed items only, as the course starter warns.

### The scorers (contract: `scorer/rag.py`)

Needed items are the row's `contexts` as distinct `(kind, id)` pairs in the order of the contexts, first kept, `id` being the
event id or the topic, so two legs on one match need its event once. A retrieved item is relevant when its pair is needed; a `rule_error` item never is.

Each is `f(output, expected, metadata, **kwargs)` and returns a float from 0 to 1, or `None` when it does not apply, with the
reason kept for the report. `output` is `{"answer", "retrieved_contexts", "record"}`, the final, the items and the `load_run`
record; `expected` is the row's `ground_truth`; `metadata` is `{"question", "ground_truth_contexts", "row"}`, the starter's names.
Each of the four public scorers returns a float or `None` and nothing else, so Braintrust can call it, and raises `ValueError` when
`output` or `metadata` does not carry its record or row. `score_case(row, record)` raises `ValueError` when `row` or `record` is not
a dict, and returns each value with its reason, plus faithfulness's claims, supported claims and legs left, and the public scorers go through it.

| Scorer | Half | Rule |
|---|---|---|
| `context_recall` | Retrieval | Needed items found among the retrieved ÷ needed items. `None` when nothing is needed |
| `context_precision` | Retrieval | Over the retrieved list, the sum of precision at k at each relevant position ÷ the number of relevant positions; 0 when none is relevant or nothing was retrieved. `None` when nothing is needed |
| `faithfulness` | Generation | Supported claims ÷ claims. A leg is one claim when any grade is committed for it, by `checks._committed`, and it is supported only when every grade committed for it is. A grade is supported when: with no usable facts for the leg, it is `NEEDS_HUMAN`; when it is `MOOT`, another leg has a committed `L`; otherwise it equals `key_for_leg` on those facts. A leg with usable facts and a key of `None` leaves both the numerator and the denominator, and the count of such legs is kept for the report (ruling 26). A score the final's evidence cites for a leg, either way round, is one more claim, supported when it equals that leg's `score_regulation_90`, `score_halftime` or `score_final`. `None` when there is no claim |
| `answer_relevancy` | Generation | The share of four tests that hold: the final has one leg per ticket leg; its legs are numbered 1 to n in order, n being the final's own leg count, so an empty list passes this test and fails the first (ruling 20); its `ticket_result` is one of the six the system prompt names; and it equals the `ticket_result` of the last `settle_ticket` call that did not err. 0 with no final |

**Faithfulness, as built.** A leg's facts are `_best_facts` of the record's ticket leg over `_facts_seen(record)`, and its key is
`key_for_leg` of the row's leg on those facts. The facts are usable when `_best_facts` returned some and `key_for_leg` did not
raise `KeyError`, `TypeError` or `ValueError` on them; any other exception propagates. The order is: with no usable facts, a
committed grade is supported only when it is `NEEDS_HUMAN`; with usable facts and a key of `None`, the leg leaves the rate, its
score claims with it, and is counted (ruling 26); a `MOOT` grade is supported when another leg has a committed `L`; any other
grade is supported when it equals the key. The rule on a raise is the PM seat's: a run that never fetched the fact a market
settles on made that grade without facts, so the leg stays in the rate. `B05`'s leg 4, "1st Half Total Goals", shows it in `aa-1`, where a `find_match`
full-time score is the leg's only fact and `key_for_leg` raises `KeyError` on `score_halftime`.

A score claim is each distinct score in the evidence of every final leg whose `leg` equals that leg's number: two runs of one or
two digits joined by a hyphen or an en dash, spaces allowed around it, with no digit, hyphen or en dash directly before or after,
so the 10-14 inside 2026-10-14 is not a score. It is supported when it equals, either way round, a score in the facts
`_best_facts` returned, usable or not; with no facts it is unsupported. `_committed` takes the final's legs by position, and the
score claims take them by their `leg` number.

**`answer_relevancy`, as built.** A final that is not a dict scores 0. Legs that are not a list count as an empty list. The
numbering test needs each entry to be a dict whose `leg` is its position, 1 to n. `ticket_result` is compared exactly with `WIN`,
`LOSS`, `PUSH`, `VOID`, `UNSETTLED` and `NEEDS_HUMAN`, and exactly with the `ticket_result` of the last `settle_ticket` call whose
result has no error; with no such call that test fails.

**Worked examples, each a test on a recorded run:**

| Run, case | What happened | Scores |
|---|---|---|
| `v1`, `A01` | One boosted leg, right answer; it read the match and `moneyline_3way`, and never `profit_boost` | recall 2/3, precision 1, faithfulness 2/2, relevancy 1 |
| `aa-1`, `C09` | Right answer, LOSS, with no tool call: four grades and no facts | recall 0, faithfulness 0/4, relevancy 3/4 |
| `v1`, `C09` | Facts read for all four legs; leg 4 committed P where the facts say L | faithfulness 7/8 |
| `v1`, `C13` | Facts read (0-0); legs committed W, L, L where they say L, W, W; right answer, LOSS; the final lists one leg of three, numbered 1 | faithfulness 1/4, relevancy 3/4 (ruling 20) |
| `aa-1`, `B05` | Leg 4 committed L with only a full-time score as its facts, so `key_for_leg` raises and the L was made with no usable facts | faithfulness 2/5 |
| `v1`, `B05` | No final | faithfulness `None`, no claim; relevancy 0 |

And one by hand: needed `{event E1, moneyline_3way}`, retrieved `[rule_error match_result, event E1, rule moneyline_3way]`:
relevant positions 2 and 3, precision `(1/2 + 2/3) / 2 = 0.583`, recall 1.

### The bootstrap (contract: `scorer/stats.py`)

`paired_bootstrap(a, b, n_boot=10000, seed=7)` returns `(mean_delta, lo, hi)` for `mean(b - a)`, by the course starter's
algorithm: `random.Random(seed)`, each resample `n` draws of `rng.choice` over the differences, the means sorted, `lo` at index
`int(0.025 * n_boot)` and `hi` at `int(0.975 * n_boot)`. `mean_delta` adds the differences left to right from the int 0, as
3.9's built-in `sum` does (ruling 55), so its bytes do not depend on the Python version: from 3.12 the built-in `sum` adds floats another way, and
`reports/rag.json` would differ between the two interpreters verify runs (PR #58). Unequal or empty inputs raise `ValueError`. `bootstrap_mean(xs, n_boot,
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

Recall holds when the lower bound is greater than `recall_lo_above`, faithfulness when its lower bound is at least
`faithfulness_lo_at_least`, and outcome when the upper bound on the fall is at most `outcome_fall_hi_at_most`. Outcome counts use
`outcome_match` as `run_eval.main` calls it: a, the cases both variants match; b, those only A matches; c, those only B matches;
d, neither. A bar with no pairs, or a `paired_difference` of `None`, does not hold.

A recall interval that crosses zero is no-ship and still meets the course, which accepts a correctly reported null.

### The config (contract: `packages/rag-eval/assignment-2/config.yaml`)

JSON syntax, which is valid YAML 1.2 (ruling 8). Keys, and no others: `dataset`, `dataset_sha256`, `model`, `variants`
(`{"a": {"rule_match": "exact"}, "b": {"rule_match": "alias"}}`), `runs` (`{"a": "w4-a", "b": "w4-b"}`), `bootstrap`
(`{"n_boot": 10000, "seed": 7}`), `bars` (`{"recall_lo_above": 0.0, "faithfulness_lo_at_least": -0.05,
"outcome_fall_hi_at_most": 0.05}`, the three above), `statement` (`reports/rag-statement.md`), `report`
(`packages/rag-eval/assignment-2/report.md`), `json` (`reports/rag.json`), `langsmith_version` and `braintrust_experiments`,
each null until the owner fills it: `langsmith_version` as `{"dataset_id", "as_of"}`, and `braintrust_experiments` as
`{"a", "b"}`. Every object in the config holds exactly its written keys, at every depth: an unknown or missing key is
refused at the top level; inside `variants`, `runs`, `bootstrap` and `bars`; inside `variants.a` and `variants.b`, which hold
`rule_match` alone (ruling 28); and inside `langsmith_version` and `braintrust_experiments` once they are not null (ruling 29).

`dataset_sha256` is null until the PM seat writes v1's hash into it after the freeze; a non-null hash must equal the one in
`data/golden/v1.sha256`, and a test holds that. A config that cannot be read as JSON is refused, and so is a value of the wrong
type: `dataset_sha256` is null or a string; `model` is a non-empty string; `rule_match` is `exact` or `alias`; a run
id matches `^[A-Za-z0-9][A-Za-z0-9._-]*$`; `n_boot` is a positive int and `seed` an int, neither a bool; each bar is a number and
not a bool; each path is a non-empty string, relative to the repository root, that does not begin with `~` and has no `..` part;
and each value in a filled
`langsmith_version` or `braintrust_experiments` is a non-empty string. The root comes from the module's own location, never the
working directory. The tests on the committed config hold in every planned state, so no later commit turns the suite red: v1's
hash written in; the two ids filled; and the statement, both runs and the report committed.

### The commands (contract)

```bash
python3 -m scorer.rag run    --config packages/rag-eval/assignment-2/config.yaml --variant a   # needs Ollama
python3 -m scorer.rag run    --config packages/rag-eval/assignment-2/config.yaml --variant b
python3 -m scorer.rag report --config packages/rag-eval/assignment-2/config.yaml              # no model
```

`run` refuses with status 2, one line on stderr, nothing written and no model called: a config this contract refuses; a
`--variant` other than `a` or `b`; a null `dataset_sha256`, a missing v1, or v1's bytes not matching the hash; or a run directory
that exists. Otherwise it calls `run_eval.main` in process over the file whose bytes it just hashed, with the run id, the model and
the variant's `--rule-match`. `run_eval` writes under its own repository root, so no test lets `run` reach the real
`run_eval.main`.

`report` calls no model. It refuses the same way, writing nothing, on any of these:

- a config this contract refuses, or one outside the repository root, because the commands it prints must name the file used
  and a path outside the repository cannot be printed in a byte-stable report;
- a null `dataset_sha256`, a missing v1, or v1's bytes not matching the hash;
- a v1 that cannot be read: a line that is not a JSON object, or a `case_id` that is missing, not a string, empty or repeated;
- a run directory missing, or its `run_meta.json` or `settlement-traces.json` missing or unreadable;
- `model_digest` or `ollama_version` missing from either run's `run_meta.json`;
- a `run_meta.json` whose `model` differs from the config's, whose `cases_file` differs from `dataset`, or whose `rule_match`
  differs from its variant's;
- the two runs' `model_digest` or `ollama_version` differing, or their `run_meta.json` differing anywhere else but `run_id`,
  `rule_match` and `outcome_matches` (ruling 37);
- two records for one case in a run, a record for a case v1 does not hold, or a v1 case with no record in either run;
- a record whose ticket differs from `json.loads` of its row's question; and
- the statement file missing or blank.

Otherwise it writes the report and its JSON, byte-stable. While either run directory is absent, the config's report and JSON must
be absent; once both runs are present, the committed files must equal `report`'s output byte for byte. A second test proves on
temporary files that this check can fail.

Each subcommand takes `--config` and `--root`, defaulting from the module's location, and the tests pass temporary paths. The
contract's commands never pass `--root`. `run --root` checks its config, v1 and the run directory under that root while `run_eval`
writes under its own, so a run made that way is not one `report --root` will find.

### The report (contract)

In order: the hand-written statement, verbatim; the dataset (n, the hash, the LangSmith version's dataset id and `as_of`, or "not pinned yet"); for each
variant, the four scorers as a mean, the count scored and the count `None`, and a 95% `bootstrap_mean` interval, with the
retrieval pair and the generation pair in separate tables; the weaker half, the pair whose two means average lower; the A/B, each
metric's delta and interval, each bar's value and whether it holds, and the verdict line; the groundedness candidates, every v1
case where A's outcome matches and recall or faithfulness is below 1, with its scores and tool count; the run metadata, model,
digest, Ollama version and flags; and the commands. Every rate prints k of n. Faithfulness also prints how many legs a `None` key left out of its rate (ruling 26). The statement says the alias table is in sample
on the six misses, and that 29 rows are tickets the earlier runs used: 30 until ruling 49 dropped `B10`.

Each variant prints its retrieval pair and its generation pair as two Markdown tables, one row per scorer, with the columns
scorer, mean, scored, none, interval and k of n; faithfulness's legs left sit in its k-of-n cell (ruling 39). The weaker half is
named per variant (ruling 38). A tie names neither half and says so. So does a half where either scorer's mean is `None`: its
reason says that half has no scored case, even when its other scorer has a mean, as the generation half's does when no case has a
faithfulness claim. The A/B, the candidates and the runs print as lines. Means and interval bounds print to three decimals and counts as integers, and the verdict words are
`ship` and `no-ship`. `reports/rag.json` goes through `stats.canonical_json`, cases go in `case_id` order, and no stake, price,
payout or net is printed. The candidates print A's four scores and the `tool_calls` of A's record. The statement,
`reports/rag-statement.md`, is the PM seat's, written after the runs.

### Braintrust (contract: `uploaders/braintrust_eval.py`, the owner's shell)

Outside `scorer/` and the tests, like the LangSmith script. One `Eval` per variant in the project `settlement-grader-rag`, named
for its run id; the data are v1's rows; the task replays the recorded output for each case from that run's traces and calls no
model; the scores are the four functions from `scorer.rag`. It prints each experiment's id, which the owner writes into the
config's `braintrust_experiments` (ruling 7).

Before it imports the package it reads the pair through `scorer.rag.load_pair`, so it refuses every pair `report` refuses. It reads
its key from the environment and prints no part of it. Every refusal is status 2 and one line on stderr, including a missing key, a
failed login, an `Eval` that raises and an experiment with no id. Each example is v1's question as input, its `ground_truth` as expected, and
`{question, ground_truth_contexts, row}` as metadata; the task returns the recorded `{answer, retrieved_contexts, record}`. `Eval`
completes when a task or a scorer raises, so the uploader reads each case's result and prints no id for an experiment where any case
carries either error (ruling 41). Neither `scorer/` nor the tests import it, and PR #53 did not run it.

### What the step 8 PR must show

1. Each worked example above as a test, and the hand example.
2. A record with no tools scores recall 0 against a row with needed items, so the gold never stands in for the retrieved.
   Two legs on one match need its event once.
3. A leg with usable facts and a key of `None` leaves both sides of the faithfulness rate and is counted, and a final with no legs passes
   relevancy's numbering test and fails its first.
4. At least three mutations named, each turning the suite red for the right reason, among them: recall counting `find_match`
   candidates, faithfulness passing a grade made with no facts, and the bootstrap reusing one index.
5. The config's refusals, among them an unknown or missing key in `bars`, an extra key in `variants.a`, and an extra key in a
   filled `langsmith_version` or `braintrust_experiments`; `run`'s refusals, `report`'s refusals, and a byte-stable report from
   fixture runs.
6. `uploaders/` compiles, and no test imports it or reads a key.
7. The suite and `compileall` on 3.9 and 3.14, the existing tests unmodified, and the privacy sweep.

## The runs

All on the owner's machine, in a fresh clone, with `private/` and `data/espn_cache/` absent. Each pair runs in one session, and
`run_eval.py` records the Ollama version and the model digest.

| Run | Command | Step |
|---|---|---|
| `w4-pilot-strong` | `python3 run_eval.py data/golden/candidates.jsonl --run-id w4-pilot-strong` | 6 |
| `w4-pilot-weak` | the same with `--run-id w4-pilot-weak --disable-tool lookup_rule` | 6 |
| `w4-a`, `w4-b` | `python3 -m scorer.rag run` with `--variant a`, then `b` | 9 |

`data/golden/candidates.jsonl` holds the 30 real rows, the synthetic rows that survived the cuts and the owner's check, and the
owner's edge rows; `python3 -m scorer.golden candidates` writes it. After the two pilot runs, `pilot` writes
`data/golden/kept.jsonl` and `pilot.md`, and `freeze` writes v1, its hash and the package's copy from the kept rows.

## Departures from the plan

- **Step 3 has one knob, not three.** The plan names `rule_match`, `top_k` and `window_days`. `top_k` cannot move on this data,
  as the plan's second fact shows, and the A/B changes only `rule_match`, so the other two wait until a run needs them.
- **`answer_relevancy`'s second test** checks that the legs are numbered in order. The plan said each grade names its leg's
  selection, but the final the system prompt asks for has no selection field.
- **`faithfulness` reads the `settle_ticket` call as well as the final.** The plan said "the facts this run fetched", which
  stands; it did not say which grades. `C13` shows why: its final lists one leg, and its settlement committed three.
- **A synthetic key's leg grades come from `key_for_leg`, not from the re-grader alone.** The plan's "Key from" cell for a
  synthetic row names `check_gold.py`'s re-grader and `settle_ticket`, and its "No synthetic key came from a model" row says
  the key field is written only by the re-grader. `key_for_leg` takes the seven steps "The key" lists, and
  `check_gold.auto_grade` is only the last of them; `key_for_ticket` then settles through `settle_ticket`. What that row
  proves still holds: every synthetic key is written by code, and no text a model writes reaches it.

- **An erred lookup stays in the retrieved list.** The plan's `context_recall` cell says a lookup that erred retrieved nothing.
  For recall that holds, because a `rule_error` item is never a needed pair. For precision it stays as a retrieved, non-relevant
  position, which the plan's `context_precision` cell calls noise, and ruling 40 extends that to a topic that is not a string.
- **`faithfulness` asks `key_for_leg`, not the re-grader alone.** The plan says a claim is supported when "the re-grader agrees
  using only the facts this run fetched". The scorer calls `key_for_leg` on those facts, so a grade is held to the same key a row
  carries, and `check_gold.auto_grade` is only the last of that function's steps. On the four worked examples, calling `auto_grade`
  in its place changes nothing, and `test_auto_grade_in_place_of_the_key_changes_none_of_the_four` holds that.

- **The synthetic source drew 184 tickets, not 160.** The plan drafts 160 to keep about 110. In the real run about 61% survive
  the cuts, so 160 would have fallen short of ruling 1's 150 rows, and a second pass went to the topics still short of a row or an
  outcome. `validation.md` gives the counts.
- **The PM seat drafted the hand-crafted rows.** The plan has the owner write them. The owner asked for help, the PM seat drafted
  20 from the frozen facts, and the owner kept all 20 with their keys. `source` reads `hand_crafted_by_owner` because the contract
  requires that value, and the key holds by ruling 33 because the owner accepted it.

## Out of scope here

Changing `check_gold.py`, a key in `data/gold.json`, or any `verified_by_beni`; extending the frozen facts, which more `void_postponed`
rows need (rulings 17 and 27); an `autoevals` column (ruling 7); and a page.
