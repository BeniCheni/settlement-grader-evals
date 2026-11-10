# The golden set, v1

Assignment 1 of Week 4. Written by the PM seat (Claude) on Tue 10 Nov 2026. Every count below comes from `data/golden/v1.jsonl`, and the commands at the end print them.

pinned version: v1

| | |
|---|---|
| LangSmith dataset | `settlement-grader-golden` |
| Dataset id | `13709a92-acc2-4067-9d86-b4b9cdf4f53c` |
| v1's `as_of` | `2026-11-10 14:31:08.482415+00:00` |
| Rows | 159 |
| sha256 | `2438ce0a7b0d336b75706620ba89ae1b2bfd449b485eb0487a45e53af02027a9` |

The owner uploaded the rows on Tue 10 Nov 2026 from their own shell, with `python -m uploaders.langsmith_pin` under `langsmith` 0.14.17, in a fresh clone of `main` at `29702e6`. The script tagged the dataset's latest version `v1` and read it back by that tag. The SDK's `DatasetVersion` carries only `tags` and `as_of`, so the dataset id and `as_of` together are v1's version id (`docs/rag-spec.md`). The same pair is in `packages/rag-eval/assignment-2/config.yaml` as `langsmith_version`.

## The blend

| Blend | Rows | Where they come from | Where the key comes from |
|---|---|---|---|
| `real` | 29 | Tickets from the author's own betting log, as in `data/gold.json` | `data/gold.json`'s keys. 5 are `verified_by_beni` (`A05`, `A13`, `C09`, `C13`, `C14`); the rest are code-checked |
| `synthetic` | 110 | Code picked each event, market, line, selection and leg from the frozen facts, and `llama3.1:8b` wrote only the slip wording | `key_for_ticket`, from the frozen facts. The model's text never reaches a key |
| `hand_crafted` | 20 | Written by the owner: no good doc, ambiguous, multi-doc, and rule-name drift | The owner's. They hold by ruling 33, which does not make them `verified_by_beni` |

The deck's blend is a target, not a rule (ruling 1), and real tickets are capped by the owner's log. `data/gold.json` holds 30 real tickets: v1 holds 29 of them, because `B10` was dropped before the freeze (ruling 49). The hand-check, the pilot and the freeze are in `validation.md` and `pilot.md`.

## The four qualities

**Representative.** Partly, and on purpose not in its mix. The 29 real rows are the traffic this grader actually sees: one person's tickets, mostly boosted singles and parlays. The 110 synthetic rows were drawn to fill rule topics the grader had read rarely or never in earlier runs (`bonus_bet_stake`, `second_chance_token`, `cards`, `shots_on_target`), so they over-weight cash parlays: `parlay-cash` is 90 of 159 rows, and only 1 of the 29 real tickets. 106 of the 110 synthetic rows are on matches already decided in `data/espn_frozen.json`, as a real ticket is. The other four, `S142` to `S145`, are on two of the four Champions League matches of 14 Oct that the frozen file holds as scheduled, two rows each, and their key is `UNSETTLED`. Ruling 16 allows them because they are the only way to test `unsettled`, and those matches have been played since, so a ticket on them tips nothing. The owner's no-good-doc rows name matches absent from the frozen file, on purpose: `E01` to `E03` have no event in it, and `E04` has one leg in it and one not. The 5 `easy` rows are all synthetic, because every one-leg real ticket is boosted or on a non-cash stake. So a rate over v1 describes these rows, and it is not a rate over the owner's log.

**Diverse.** 10 intents, from `parlay` 105 and `moneyline_3way` 33 down to `cards` 1. Contexts need all 19 rule topics, `parlay_moot` in 105 rows and `void_postponed` in 3 contexts on one row. There are 6 ticket results: `LOSS` 94, `WIN` 40, `NEEDS_HUMAN` 16, `UNSETTLED` 6, `PUSH` 2 and `VOID` 1. Tickets have 1 to 4 legs (54, 46, 51 and 8), and there are 8 segments. The owner's 20 rows cover the three edge kinds the course names: no good doc 4, ambiguous 5 and multi-doc 6, plus rule-name drift 5. The gap is `void_postponed`. The frozen scoreboard lists 5 postponed events, but the grader reads a match's facts from its summary, and none of the 43 frozen summaries is one of them. Adding one is its own `ESPN_LIVE=1` PR (Hard Rule 3), so v1 has no synthetic void row. `C14`, a real ticket whose key is verified `VOID`, is its one row (rulings 17 and 27). A rate on void handling rests on that one ticket.

**Correctly labelled.** The owner hand-checked 30 synthetic rows and found 2 errors, a rate of 6.7% with a 95% Wilson interval of 1.8% to 21.3% (`validation.md`). Both errors were slip wording that changed the market, not a wrong key. Those rows, and a third with the same fault found outside the sample, are not in v1, and 28 rows carry `label_checked_by_beni`. A hand-check is a label check, and it never sets `verified_by_beni` (ruling 12). The pilot's strong run graded 79 rows differently from their keys (`known_failure`). A wrong key would hide there, so each was checked before it was kept (ruling 4). In PR #57's cold read, Cursor read 53 of the 79 against the frozen facts by hand, and all 53 held. `B10`'s key did not hold, and it was dropped. Cursor also noted that `B02`, `C02` and `B13` store `MOOT` on leg 4, where the code grades `W` for `B02` and `C02` and `L` for `B13`. The ticket's key is `LOSS` either way. Only 5 of v1's 159 keys are `verified_by_beni`.

**Versioned.** `data/golden/v1.jsonl` is frozen. Its sha256 is committed beside it in `data/golden/v1.sha256`, and a test fails if a byte changes. `golden_set.jsonl` here is a byte-identical copy. The config names v1 and its hash, and `python3 -m scorer.rag run` and `report` both refuse v1 bytes that do not match. LangSmith holds the same rows under the tag `v1`, with the version id above. New rows go to v2, never into v1.

## The commands

```bash
shasum -a 256 -c data/golden/v1.sha256
cmp data/golden/v1.jsonl packages/rag-eval/assignment-1/golden_set.jsonl
python3 -c 'import json,collections as c; r=[json.loads(l) for l in open("data/golden/v1.jsonl")]; print(len(r)); [print(k, sorted(c.Counter(str(x[k]) for x in r).items())) for k in ("blend","difficulty","segment","intent","pilot","label_checked_by_beni")]; print("verified", sorted(x["case_id"] for x in r if x["expected"].get("verified_by_beni"))); print("easy", sorted(c.Counter(x["blend"] for x in r if x["difficulty"]=="easy").items())); print("results", sorted(c.Counter(x["expected"]["ticket_result"] for x in r).items())); print("legs", sorted(c.Counter(len(x["legs"]) for x in r).items())); print("edges", sorted(c.Counter(x["why_interesting"].split(".")[0] for x in r if x["blend"]=="hand_crafted").items())); print("parlay-cash", sorted(c.Counter(x["blend"] for x in r if x["segment"]=="parlay-cash").items())); print("void_postponed", [x["case_id"] for x in r if any(t.get("topic")=="void_postponed" for t in x["contexts"])]); print("no good doc", [(x["case_id"], len([t for t in x["contexts"] if t["kind"]=="event"]), len(x["legs"])) for x in r if "no good doc" in x["why_interesting"]]); print("topics", sorted(c.Counter(t["topic"] for x in r for t in x["contexts"] if t["kind"]=="rule").items()))'
python3 -c 'import json,sys; sys.path.insert(0,"."); from grader import espn; r=[json.loads(l) for l in open("data/golden/v1.jsonl")]; s=[x for x in r if x["blend"]=="synthetic"]; st=lambda x: [espn.match_facts(t["event_id"])["status"] for t in x["contexts"] if t["kind"]=="event"]; print(len(s), sum(1 for x in s if set(st(x)) <= {"STATUS_FULL_TIME","STATUS_FINAL_PEN","STATUS_FINAL_AET"}), [(x["case_id"], st(x), x["expected"]["ticket_result"]) for x in s if "STATUS_SCHEDULED" in st(x)])'
python3 -c 'import json; d=json.load(open("data/espn_frozen.json")); p=[str(e["id"]) for k,v in d.items() if "scoreboard" in k for e in v.get("events") or [] if e["status"]["type"]["name"]=="STATUS_POSTPONED"]; m=[k for k in d if "summary" in k]; print("postponed", len(p), "summaries", len(m), "postponed with a summary", sum(1 for e in p if any("event="+e in k for k in m)))'
```
