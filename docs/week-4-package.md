# The Week 4 package: a pinned golden set, and the grader's retrieval measured apart from its answers

Written Fri 6 Nov 2026 by the PM seat; the owner approved it the same day, with the rulings at the end. It lands through a
fast-track cold read by Cursor, in place of Codex (ruling 13), as most of Week 3's docs did. It turns the Week 4 assignments of
the *AI Evals in Practice* course into this repo's next milestone, the way `docs/week-3-package.md` did for Week 3.
`AGENTS.md` outranks it on process, and no line here loosens it. Within that, precedence runs: the owner's rulings, then the
specs, then this plan.

## What the course asks for

The assignments live in the course repository, `github.com/coachmanjeet/AI-Agent-Evals-Course`, at commit
`718f649a80a9f6bc962ca2ae07c8c3af4259904c` (the same commit Week 3 pinned; it is still the head), under
`week-04-rag-evaluation/assignments/`. The course's `solutions/` holds no Week 4 answer yet. Where the sources differ, the
course repository wins, as in Week 3.

**Assignment 1, build and version the dataset** (`01-build-and-version-dataset/`). A golden set of 150+ cases after cuts,
each with `question`, `contexts` (what should be retrieved), criteria-based `ground_truth`, and `source`, `difficulty`,
`intent`, `segment`. A blend of real, synthetic and hand-crafted cases. Pilot every scenario: keep it only if it passes on the
strong config and fails on a weakened one (policy lookup disabled). Hand-check 30+ synthetic labels and report the error
rate. One paragraph on each of the four qualities: representative, diverse, correctly labelled, versioned. Upload to
LangSmith, tag `v1`, and write the version id in `dataset.md`.

**Assignment 2, measure and test** (`02-measure-and-test/`). Four scorers, plain functions returning 0 to 1:
`faithfulness`, `answer_relevancy` (generation) and `context_precision`, `context_recall` (retrieval), run over v1 with
`braintrust.Eval()`, reported as two pairs. One groundedness failure, dissected as a retrieval miss or a generation fault.
Change ONE retrieval parameter, re-run, and report the paired-bootstrap delta with its 95% interval. A null result with a
correctly reported interval passes. One config, one command, one reproducible `report.md`.

**Submit** (deck, slide 38): `golden_set.jsonl`, `dataset.md`, `groundedness_failure.md`, `report.md`, `config.yaml`.

| Question | Classroom page | Deck | Live session | Course repo | Here |
|---|---|---|---|---|---|
| Size | 150+ | 150+ after cuts; 60 + 120 − 22 = 158 is illustrative | "If 150 is too high... at least 50 to 100" | 150+ after cuts; the blend is not a quota | 150+ after cuts (ruling 1) |
| The metrics | "four RAGAS metrics" | "four Braintrust scorers" | the RAGAS and autoevals libraries | Braintrust scorers, plain functions | The same four. Braintrust's `autoevals` implements the RAGAS four, so the names describe one set |
| What the A/B changes | "a prompt change" | a retrieval change, `top_k` 3 vs 5 | | ONE retrieval parameter | One retrieval parameter: how `lookup_rule` matches a topic (ruling 5) |
| Where v1 is pinned | LangSmith | LangSmith | Braintrust datasets, in the demo | LangSmith, id in `dataset.md` | LangSmith (ruling 6), plus a hash in this repo |
| Hand-check | "validate" | 30+, error rate | about 15%, or 30 to 40 of 200 | 30+, error rate | 30+, by the owner |
| Pilot weakened config | | | | `lookup_policy` disabled | `lookup_rule` disabled, with an amendment (ruling 4) |

## Why this is not a rename

The course's agent retrieves policy chunks for a chat. This grader settles a ticket from tools it calls itself. Five facts
change the work.

1. **There is no vector index.** Retrieval is three tools the model chooses to call: `find_match` over 854 frozen scoreboard
   events across 41 days, `get_match_facts` over 43 frozen event summaries, and `lookup_rule` over 19 rule topics by exact
   key. `grader/rules.py` already says the model reads them "the same way the Pronto agent reads its policy through
   lookup_policy". There are no chunks and no embeddings, so "chunk size" has no meaning here.
2. **The course's `top_k` does nothing here.** `find_match` keeps 3 candidates (`grader/espn.py:134`). Across `v1`, `aa-1`
   and `ab-a` it returned one candidate in 90 of 107 calls, two in 14, none in 3, and never three, and the model never fetched
   facts for a second candidate. A `top_k` change is a null result on these calls. The retriever that misses is
   `lookup_rule`: 19 calls returned `UNKNOWN_TOPIC`, across 13 records, for `both_teams_to_score` (5), `match_result`,
   `anytime_goalscorer`, `total_goals`, `goals` (3 each) and `combo` (2).
3. **Ground truth is computed, not written.** A leg's result follows from the frozen facts and the rule, and `check_gold.py`
   re-grades it in plain code. So a synthetic ticket's key comes from code and the owner's check, never from a model, and
   never from `qwen3:8b`, the model under test. That is the deck's "correctly labelled" quality, met by construction.
4. **The strong config is often wrong.** 11 or 12 of 32 tickets matched their key in each recorded run. The course's pilot
   discards a case the strong config fails as "mislabeled or too hard". Applied as written, it would throw away the failures
   this eval exists to measure and keep the easy tickets, which the deck warns against ("easy cases cannot hide hard ones").
5. **A correct answer already hides a retrieval failure, on the record.** `C09`, a verified LOSS key, is answered LOSS with
   no tool call at all in `aa-1`, `aa-2`, `aa-3` and `ab-a`: context recall 0, final answer right. That is slide 20 exactly.
   `C13`, also verified LOSS, is answered LOSS in all five runs while `GRADE_CONTRADICTS_FACTS` fires: it read the facts, a
   0-0, and committed W, L and L to `settle_ticket` where they give L, W and W, so its two wrong losses carried the ticket to the
   right result. One retrieval miss and one generation fault, both in sample.

```bash
python3 -c 'import sys; sys.path.insert(0,"."); from scorer.traces import load_run; from grader import espn; print(espn.match_facts("401884801")["score_regulation_90"]); [print(n, [t["args"].get("leg_results") for t in r["tools"] if t["name"]=="settle_ticket"], (r.get("final") or {}).get("ticket_result")) for n in ("v1","aa-1","aa-2","aa-3","ab-a") for r in load_run("traces/"+n) if r["case_id"]=="C13"]'
```

```bash
python3 -c 'import sys; sys.path.insert(0,"."); from collections import Counter; from scorer.traces import load_run; n=Counter(len((t.get("result") or {}).get("candidates") or []) for r_ in ("v1","aa-1","ab-a") for r in load_run("traces/"+r_) for t in r["tools"] if t["name"]=="find_match"); e=Counter(t["args"].get("topic") for r_ in ("v1","aa-1","ab-a") for r in load_run("traces/"+r_) for t in r["tools"] if t["name"]=="lookup_rule" and (t.get("result") or {}).get("error")); print(dict(n), dict(e))'
```

```bash
python3 -c 'import json; from grader.rules import RULES; f=json.load(open("data/espn_frozen.json")); sb=[v for k,v in f.items() if "scoreboard" in k]; print(len(sb), sum(len(v.get("events",[])) for v in sb), sum(1 for k in f if "summary" in k), len(RULES))'
python3 -c 'import json; from scorer.traces import load_run; g={c["case_id"]:c["expected"]["ticket_result"] for c in json.load(open("data/gold.json"))}; print({n:sum(1 for r in load_run("traces/"+n) if (r.get("final") or {}).get("ticket_result")==g.get(r["case_id"])) for n in ("v1","aa-1","aa-2","aa-3","ab-a")})'
```

```bash
python3 -c 'import json,sys; sys.path.insert(0,"."); from scorer.traces import load_run; from scorer.checks import grade_contradicts_facts as f, graded_without_lookup as w; g={c["case_id"]:c for c in json.load(open("data/gold.json"))}; [print(n, cid, (r.get("final") or {}).get("ticket_result"), g[cid]["expected"]["ticket_result"], len(r["tools"]), bool(w(r,g[cid])), bool(f(r,g[cid]))) for n in ("v1","aa-1","aa-2","aa-3","ab-a") for r in load_run("traces/"+n) for cid in ("C09","C13") if r["case_id"]==cid]'
```

## The retrofit

| Course's word | Pronto | Here |
|---|---|---|
| `question` | A customer question | The ticket: its fields, rendered to one string for LangSmith's input |
| DEMO_DOCS | Six policy snippets | `grader/rules.py` (19 topics) and `data/espn_frozen.json` (43 summaries, 854 events) |
| `contexts` (gold) | Docs that should be retrieved | Per leg: the `event_id`, the fact the market settles on (`score_regulation_90`, `score_halftime`, `team_stats.corners`, ...) and the rule topic. Derived by code, hand-checked |
| `retrieved_contexts` | Chunks retrieval returned | `tools[].result` in the trace: the candidates, the facts fetched, the topics read. Never the gold |
| `ground_truth` | `must_include` / `must_not` | Must: each leg's grade, `ticket_result`, `net` when settled, the settling fact ("regulation 2–2"). Must never: a WIN on a regulation draw; a net on an UNSETTLED ticket |
| A "real" case | Hand-written from DEMO_DOCS | The 30 real tickets. Real traffic, which is stronger than the course's "real" |
| Synthetic | Model-written | Invented tickets on the 43 frozen matches, keys by code, `source: synthetic`, invented amounts |
| Hand-crafted | A domain expert | Edge cases the owner writes: no good doc, ambiguous, multi-doc |
| Weakened config | `lookup_policy` returns `[]` | `lookup_rule` returns nothing |
| One retrieval parameter | `top_k`, `chunk_size` | `rule_match`: exact key (today) or alias match |
| `braintrust.Eval()` | A hosted experiment | The same scorer functions, run locally, then logged by a thin uploader in the owner's shell |
| LangSmith v1 | A hosted dataset version | The same bytes, uploaded in the owner's shell, plus their sha256 in this repo |

## Where this repo stands

| Course item | In this repo | Source |
|---|---|---|
| Real cases | 30 real tickets and 2 attacks; 6 keys verified (`A05`, `A13`, `C09`, `C13`, `C14`, `X01`) | `data/gold.json` |
| A label check that is not the model | The plain-code re-grader | `check_gold.py` |
| The documents | Frozen facts and rules; a lookup outside the file raises | `data/espn_frozen.json`, `grader/espn.py`, `grader/rules.py`, `grader/frozen.py` |
| Retrieved context per case | Every tool call's arguments and result, in each run | `traces/*/`, `scorer/traces.py` |
| Faithfulness, in parts | `GRADE_CONTRADICTS_FACTS`, `GRADED_WITHOUT_LOOKUP`, `SKIPPED_SETTLE_TICKET`, `PLACEHOLDER_ECHO`, `INCOMPLETE_LEG_LIST`; `SELF_CONTRADICTING_EVIDENCE` needs a judge that has not met the bar | `scorer/checks.py`, `README.md` |
| Intervals | `wilson`; `paired_difference` (Newcombe, for paired yes/no). No bootstrap yet | `scorer/stats.py` |
| Freezing a file | A committed sha256 and a test, from Week 3 | `data/redteam/frozen.sha256` |
| A hosted call | Jev: the owner's shell holds the key, the PM seat never reads it | `packages/red-team-guardrails/assignment-3/` |

Week 3's 40 rows stay out of v1 (ruling 10). They measure guardrails, and `P2` poisons `lookup_rule`, which would corrupt the
retrieval numbers. The reserve is already in the tree and was held out only in the narrow sense `docs/week-3-package.md`
records; it stays out of v1 with the rest.

## The golden set

**Target: 150+ after cuts (ruling 1).** The blend cannot match the deck's 50/35/15, because real tickets are capped by the
owner's log. The course calls the blend a target, not a rule.

| Source | Drafted | Kept, about | How | Key from |
|---|---|---|---|---|
| Real | 30 | 30 | As in `data/gold.json`, `source` unchanged | Existing keys; 6 verified, the rest code-checked |
| Synthetic | 160 | 110 | Seed: 5 real tickets and a named gap. Code picks the event, market, line, selection and legs from the frozen facts; `llama3.1:8b` (ruling 3) writes only the slip wording, in batches of 20 | `check_gold.py`'s re-grader and `settle_ticket`, never a model |
| Hand-crafted | 20 | 20 | The owner writes them (below) | The owner |

**Gaps to name** (the live session's "jobs × 5–10, positive and negative"). Across `v1`, `aa-1` and `ab-a` the grader read
`moneyline_3way` 51 times and `totals` 25, `double_chance` and `to_advance` 3 times each, and never read `bonus_bet_stake`,
`second_chance_token`, `cards` or `shots_on_target`. The first two are already a recall miss: the gold set holds 2 bonus-bet
and 2 second-chance tickets. Synthetic rows fill each of the 19 topics to at least 5 cases, both outcomes, and the spec gives
the table. The first command prints the records, the records with an erred lookup (the 13 of 96 the A/B below rests on), the
topics read and the topics never read; the second, the stake kinds.

```bash
python3 -c 'from collections import Counter; from grader.rules import RULES; from scorer.traces import load_run; rs=[r for n in ("v1","aa-1","ab-a") for r in load_run("traces/"+n)]; t=[x for r in rs for x in r["tools"] if x["name"]=="lookup_rule"]; ok=Counter((x.get("result") or {}).get("topic") for x in t if not (x.get("result") or {}).get("error")); print(len(rs), sum(1 for r in rs if any(x["name"]=="lookup_rule" and (x.get("result") or {}).get("error") for x in r["tools"])), dict(ok), sorted(set(RULES)-set(ok)))'
python3 -c 'import json; from collections import Counter; print(Counter(c["stake_kind"] for c in json.load(open("data/gold.json"))))'
```

**Hand-crafted edges**, the course's three kinds. *No good doc:* a ticket on a match absent from the frozen file, key
`NEEDS_HUMAN`, and a test proves it never reaches the network. *Ambiguous:* a slip that says "Tomorrow"; a team that plays
twice inside the date window. *Multi-doc:* a cross-match parlay; `to_advance`, which needs extra time and penalties; a
cards market with no counting scheme, key `NEEDS_HUMAN`. Plus rule-name drift: the slip says "Match Result" or "Both Teams
To Score".

**Schema.** The course's fields, plus the structured `expected` block `data/gold.json` already uses, so every existing check
reads a golden row unchanged. `intent` is the market family; `segment` is single, parlay, boosted, or bonus stake;
`difficulty` comes from the leg count and whether the market needs a rule.

**Validation.** The owner hand-checks 30+ synthetic rows, stratified across intents, and records each error: a wrong key, a
wording that changed the market, a duplicate. The error rate prints as k of n with its Wilson interval. A hand-check is a
label check, not a `verified_by_beni` key (ruling 12).

**The pilot, amended (ruling 4).** Strong (as is) and weakened (`lookup_rule` returns nothing), one pass each, in one session.

| Strong | Weakened | Course says | Here |
|---|---|---|---|
| Pass | Fail | KEEP | KEEP |
| Pass | Pass | Discard, no signal | Keep only on its own evidence (key code-checked, gold contexts hand-checked) and tag it `pilot: no_rule_signal`, as the course does for order and refund cases |
| Fail | either | Discard, mislabelled or too hard | Check the key. If it holds, keep it and tag it `pilot: known_failure`. If not, fix or drop it |

The pilot's output is saved as `pilot.md`, with what was discarded and why.

**Versioning.** `data/golden/v1.jsonl`, its sha256 committed beside it, and a test that fails if a byte changes. New cases go
to `v2`. In the owner's shell: a LangSmith dataset, the same rows uploaded, tag `v1`, and the version id into `dataset.md`.

## The four scorers

Plain code in `scorer/rag.py`, standard library, each with the course starter's signature `(output, expected, metadata, **kwargs) -> float`.
The starter annotates a float. A scorer here may return `None`, with a reason, when it does not apply. Each has a mutation test, as `AGENTS.md` requires.

| Scorer | Half | Definition here |
|---|---|---|
| `context_recall` | Retrieval | Needed items retrieved ÷ needed items. Needed: each leg's event (through `get_match_facts`) and each leg's rule topic. A lookup that erred retrieved nothing |
| `context_precision` | Retrieval | RAGAS-style ranked precision over the retrieved items in call order. An erred lookup, or facts for an event no leg needs, is noise |
| `faithfulness` | Generation | Supported leg claims ÷ leg claims. A claim is a leg grade and the score its evidence cites; supported means the re-grader agrees using only the facts this run fetched. A grade with no facts fetched is unsupported. Markets code cannot grade are left out and counted |
| `answer_relevancy` | Generation | The share of four tests that hold: one grade per ticket leg; each grade names that leg's selection; `ticket_result` is in the enum; the final came from `settle_ticket` |

The report prints the two pairs apart, each as a mean with k of n and an interval, then names the weaker half. There is
no `autoevals` column (ruling 7).

## The A/B: one retrieval parameter

Written and merged before any run, with its thresholds.

- **A**, `rule_match: exact`, today's behaviour, byte for byte.
- **B**, `rule_match: alias`. A fixed alias table (`match_result` → `moneyline_3way`, `both_teams_to_score` → `btts`,
  `anytime_goalscorer` → `goalscorer`, `total_goals` → `totals`, ...), then the closest topic name by shared words. The 19
  texts do not change.
- **Primary:** per-case `context_recall`, B − A, paired bootstrap, 10,000 resamples, seed fixed, 95% interval.
- **Guards:** `faithfulness` and outcome match must not fall; outcome match uses the existing `paired_difference`.
- **In sample, and said so:** the alias table is written from the misses in `v1`, `aa-1` and `ab-a`, and those runs share
  30 tickets with v1.
- **What to expect:** 13 of 96 recorded runs hit a miss, so about one ticket in seven can move. The deck says a 3-point gap
  needs 1,000+ paired cases; on about 160 an outcome effect will probably be a null. The course accepts a correctly reported
  null.

`scorer/stats.py` gains `paired_bootstrap(a, b, n_boot=10000, seed=7)` on `random.Random(seed)`, so the report is byte-stable,
tested against a hand-checked table. A and B run in one session with the Ollama version and model digest recorded. An A/A run
to show the noise floor is a stretch.

## The harness: one config, one command

`config.yaml` is written in JSON syntax. JSON is valid YAML 1.2, so the course's filename holds, and `json.load` reads it with
no dependency (ruling 8). It holds the dataset path and sha256, the model, both variants (`rule_match`, `top_k`,
`window_days`), the seed and the output paths.

```bash
python3 -m scorer.rag run    --config packages/rag-eval/assignment-2/config.yaml   # both variants; needs Ollama
python3 -m scorer.rag report --config packages/rag-eval/assignment-2/config.yaml   # report.md from the traces; no model
```

Neither command exists until step 8 lands. A test fails when the committed `report.md` is stale, as Week 3's do. The Braintrust uploader is a separate script with the
`braintrust` dependency, outside `scorer/` and CI. The owner runs it in their own shell, it logs the same per-case scores as
one experiment per variant, and the report records the experiment ids.

## The plan

| Step | Work | Seat | Done when |
|---|---|---|---|
| 1. Plan | This file, as `docs/week-4-package.md`, with a cold read | PM | Merged |
| 2. Spec | `docs/rag-spec.md`: the schema, how gold contexts are derived, the four scorers with worked examples, the A/B and thresholds, the config contract, the build prompt | PM | Merged before any build |
| 3. Seams | `rule_match`, `top_k`, `window_days` as knobs whose defaults are today; a switch that disables `lookup_rule` for the pilot | Builder | A test shows the idle requests are byte for byte `main`'s |
| 4. Draft the set | The generator (code structure, model wording), the gold-context derivation, the owner's hand-crafted rows | Builder for the generator, PM drafts, owner writes the edges | About 210 candidates |
| 5. Hand-check | 30+ synthetic rows; error rate; cuts | Owner | `validation.md` |
| 6. Pilot | Strong and weakened, one session | PM runs on the owner's machine | `pilot.md`, the kept list |
| 7. Freeze v1 | `data/golden/v1.jsonl`, the hash and its test; LangSmith upload and tag; the four qualities | Owner and PM | Merged, id in `dataset.md` |
| 8. Scorers and harness | `scorer/rag.py`, `paired_bootstrap`, `run` and `report`, mutation and stale tests; the uploader | Builder | Full review cycle |
| 9. Run | A and B on v1 in one session; Braintrust upload | PM runs; owner's shell for keys | `report.md` |
| 10. Read | `groundedness_failure.md`, from the new run, with `C09` and `C13` as the in-sample priors; the verdict on B | PM drafts, owner decides | |
| 11. Package | Below; the README's "Where we are" | PM | Every acceptance item maps to a file |
| 12. Submit | | Owner | |

Machine time: one grader pass is about 23 s a ticket (`traces/ab-a`'s mean), so the pilot (2 × 210) is about 2.7 hours and
the A/B (2 × 160) about 2 hours. Week 5 went live on Wed 4 Nov, so if time presses: steps 1 and 2 merge into one docs PR,
steps 3 and 8 into one build PR, and the A/A run is dropped. Every acceptance item still holds.

## Validate

| Claim | How it is proved |
|---|---|
| The seams change nothing when idle | A byte-for-byte test on a fake chat |
| No synthetic key came from a model | The generator's tests: the key field is written only by the re-grader, and the model's text never reaches it |
| v1 does not move | The sha256 test |
| Each scorer does something | Mutate it, and a named test goes red for that reason |
| Retrieval is not scored against itself | A test feeds the gold contexts as retrieved and expects the scorer to refuse, as the starter warns |
| A difference is real | One session, version and digest recorded, the paired interval printed beside every delta |
| Reports do not go stale | Byte-stable output and a test |
| Nothing private entered | The pattern sweep on every PR, counts and patterns stated, no hit printed |

## Privacy traps

| Rule | The trap | The answer |
|---|---|---|
| 1, scale | A synthetic stake or payout derived from a real one | Invented round figures, tagged synthetic; no figure computed from a published amount |
| 1, hosted | Uploading anything outside tracked rows | LangSmith and Braintrust get tracked and synthetic rows only, from a fresh clone |
| 3, frozen | A "no good doc" ticket that fetches live | `ESPN_LIVE` unset, and a test proves the lookup raises |
| 4, predictions | A synthetic ticket on an undecided match | Decided frozen fixtures only |
| 5, keys | Calling a code-computed or hand-checked key "verified" | A separate field; the verified count stays 6 unless the owner rules otherwise |
| 6, names | Students or the instructor from the sessions | None appear here or in the package |

## The package

```
packages/rag-eval/
  README.md                each course acceptance item, and the file that meets it
  assignment-1/
    golden_set.jsonl       v1, byte-identical to data/golden/v1.jsonl
    dataset.md             the blend, the four qualities, the LangSmith version id
    validation.md          the 30+ hand-checks and the error rate
    pilot.md               strong vs weakened, what was kept and why
  assignment-2/
    config.yaml            the one config
    report.md              the four scorers in two pairs, the A/B, the interval; generated
    groundedness_failure.md
```

## Rulings (the owner's, from Fri 6 Nov 2026)

The owner accepted rulings 1 to 12 as the PM seat recommended them, and set ruling 13. `docs/rag-spec.md` asked rulings 14 to
18, and the owner accepted each as recommended the same day.

| # | Question | Answer | Why |
|---|---|---|---|
| 1 | 150+ after cuts, as the course repo says, or about 100, as the live session allowed? | 150+ | The repo wins, and the generator makes volume cheap |
| 2 | Add real tickets settled since 15 Oct? | No, v2 | Each needs an `ESPN_LIVE=1` PR and the owner's scaling |
| 3 | Which model writes synthetic wording? | `llama3.1:8b`, local | Not the model under test, and nothing leaves the machine |
| 4 | Amend the pilot as above? | Yes | Otherwise it discards the failures the eval exists for |
| 5 | The A/B parameter: `rule_match` instead of `top_k`? | Yes | `top_k` cannot move on this data; `rule_match` misses are on record |
| 6 | Upload and pin v1 in LangSmith from the owner's shell? | Yes | The course asks; the rows are already public or synthetic |
| 7 | Stdlib scorers, a Braintrust uploader outside `scorer/`, no `autoevals` column? | Yes | Reproducible without a key, as Week 2's first decision keeps judges |
| 8 | `config.yaml` in JSON syntax? | Yes | Keeps the course's filename and the stdlib rule |
| 9 | `packages/rag-eval/` as the path? | Yes | |
| 10 | Week 3's rows stay out of v1? | Yes | They poison `lookup_rule` and test another layer |
| 11 | Who gives the cold reads: Codex, as `AGENTS.md` says, or Cursor, as most of Week 3 did? | Codex, unless a ruling names another seat for a PR | |
| 12 | A field for the owner's hand-checks, apart from `verified_by_beni`? | Yes | Hard Rule 5 |
| 13 | Who gives the cold read of the PR that lands this plan? | Cursor on Grok 4.7, in place of Codex, as a fast-track | The owner's amendment to ruling 11, for this PR only. `AGENTS.md` names Codex for a Claude-authored PR. Its rule that a vendor never gives the only cold read of its own work still holds, because Cursor wrote none of this PR. Cursor will build from this plan's spec, so this read is not independent of that build. The plan holds no row of the golden set and no threshold a build is measured on |
| 14 | Is the market-to-topic table in `docs/rag-spec.md` the source of every row's needed contexts? | Yes | Recall's denominator is a rubric, and the owner writes rubrics |
| 15 | Do `X01` and `X02` stay out of v1? | Yes | They are attacks, and ruling 10 keeps attacks out |
| 16 | May synthetic tickets use the four Champions League matches of 14 Oct that the frozen file holds as scheduled? | Yes | They are the only way to test `unsettled`. They have been played since, so a ticket on them tips nothing (Hard Rule 4), and the grader can only answer UNSETTLED |
| 17 | Does `void_postponed` go without rows in v1, named as a gap in `dataset.md`? | Yes | No frozen match is postponed, and adding one is an `ESPN_LIVE=1` PR (Hard Rule 3), so it waits for v2 |
| 18 | Are the A/B's bars in `docs/rag-spec.md` approved as drafted? | Yes | They are written before any run, as this plan requires |
