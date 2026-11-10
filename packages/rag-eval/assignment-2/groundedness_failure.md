# One groundedness failure: `S115`

Assignment 2 of Week 4. Written by the PM seat (Claude) on Tue 10 Nov 2026, from the A/B's run `w4-a`. The commands at the end print every fact below from the committed traces and v1.

**The verdict: a generation fault, not a retrieval miss.** The grader retrieved the facts both legs needed, quoted them correctly, and then graded both legs backwards. The ticket came out right only because one wrong leg was a loss.

## The case

`S115` is a synthetic row in v1: a two-leg parlay, `hard`, tagged `no_rule_signal` by the pilot. Its key is `LOSS`, from `key_for_ticket`, and it is not `verified_by_beni`.

| Leg | Market | Selection | Facts (`score_regulation_90`) | Key | Committed |
|---|---|---|---|---|---|
| 1 | Total Goals by Marseille, line 0.5 | Under | Troyes v Marseille, 0-2 | `L`: Marseille scored 2 | `W` |
| 2 | Total Goals by Juventus, line 1.5 | Under | Cagliari v Juventus, 1-1 | `W`: Juventus scored 1 | `L` |

The final answer reads like a correct one. It gives `LOSS`, which matches the key, with an evidence line per leg: "Marseille scored 2 goals, which is over 0.5" for a `W`, and "Juventus scored 1 goal, which is under 1.5" for an `L`. Each evidence line is true. Each grade is the opposite of what that evidence implies for an Under bet.

## The scores

| Scorer | `S115` in `w4-a` | What it says |
|---|---|---|
| `context_recall` | 0.750, 3 of 4 | It found both events and `parlay_moot`. It missed `team_total` |
| `context_precision` | 1.000, 3 of 6 | The three needed items it found came first, and `void_postponed`, `unsettled` and `general` came after them |
| `faithfulness` | 0.000, 0 of 2 | Neither committed grade is supported by the facts it read |
| `answer_relevancy` | 1.000, 4 of 4 | It answered the question asked, leg by leg, with a ticket result |
| outcome | match | `LOSS`, as keyed |

This is the case the course asks for: an answer that sounds right but is not supported by its retrieved context. The outcome check passes it. Faithfulness gives it zero.

## Retrieval or generation

**Generation.** The context held what was needed to grade both legs: both regulation scores, read from `get_match_facts` for the events `find_match` returned. The evidence text proves the model read them, because it quotes each team's goals correctly. The fault came after retrieval, at the step that turns "2 goals against Under 0.5" into a grade.

**The one retrieval miss doesn't explain it.** Recall is 3 of 4 because the grader never asked for `team_total`. That rule says only goals credited to the named team count, and the model already counted the named team's goals. It did read `general`, which says to verify the exact number the leg needs. So the missing rule would not have changed either grade.

**B changes nothing here.** In `w4-b` the grader made the same calls and committed the same `W`, `L`. No lookup on this row missed under exact matching, so the alias table had nothing to resolve.

**A plain-code check already catches it.** `GRADE_CONTRADICTS_FACTS` fires on `S115` in both runs ("leg 1 committed W; facts re-grade L"), as it does on `C13`.

## The priors, in sample

The plan names two earlier failures with this shape, both real tickets whose `LOSS` key the owner has verified. They were known before this run, and `C13` was a worked example in the spec (`docs/rag-spec.md`), so they are in sample.

- **`C09`, a retrieval miss.** In `aa-1` the grader answered `LOSS` with no tool call at all: four grades and no facts, recall 0 and faithfulness 0 of 4.
- **`C13`, a generation fault.** In `v1` it read the facts (0-0), committed `W`, `L`, `L` where they say `L`, `W`, `W`, and still answered `LOSS`. Faithfulness was 1 of 4. It is among this run's groundedness candidates again, at faithfulness 0.250.

`S115` is new. It is synthetic, so no run before Week 4 saw it, and it fails the way `C13` fails.

**The other kind, from the same run.** `S097` is a retrieval miss. `find_match` returned all three events, and the grader then called `get_match_facts` with three ids that no `find_match` returned (`123456`, `789012`, `345678`). It got nothing back, and graded all three legs with evidence it never read. Recall is 1 of 5. It answered `LOSS`, as keyed, so the outcome check passes it too. `GRADE_CONTRADICTS_FACTS` does not fire on it, because there are no facts to contradict.

## How it was picked

The report lists 69 groundedness candidates: every v1 row where variant a's outcome matches and recall or faithfulness is below 1. The PM seat read the candidates with faithfulness 0 and picked `S115`, because its retrieval was nearly complete. That leaves no doubt about which half failed. It was picked by reading, not by a rule, after the runs.

## The commands

```bash
python3 -m scorer.rag report --config packages/rag-eval/assignment-2/config.yaml
python3 -c 'import sys; sys.path.insert(0,"."); from scorer.traces import load_run; [print(n, [(t["name"], t["args"].get("event_id") or t["args"].get("topic") or t["args"].get("leg_results"), (t["result"] or {}).get("score_regulation_90")) for t in r["tools"]], [(l["leg"], l["result"], l["evidence"]) for l in r["final"]["legs"]], r["final"]["ticket_result"]) for n in ("w4-a","w4-b") for r in load_run("traces/"+n) if r["case_id"] in ("S115","S097")]'
python3 -c 'import json,sys; sys.path.insert(0,"."); from scorer import rag; c=rag.load_config("packages/rag-eval/assignment-2/config.yaml"); rows,_,recs=rag.load_pair(c,"."); g={r["case_id"]:r for r in rows}; [print(v, cid, {k:(s["value"], s.get("reason")) for k,s in rag.score_case(g[cid], recs[v][cid]).items()}) for v in ("a","b") for cid in ("S115","S097","C13")]'
python3 -c 'import json,sys; sys.path.insert(0,"."); from scorer.traces import load_run; from scorer.checks import grade_contradicts_facts as f; g={json.loads(l)["case_id"]:json.loads(l) for l in open("data/golden/v1.jsonl")}; [print(n, cid, f(r,g[cid])) for n in ("w4-a","w4-b") for r in load_run("traces/"+n) for cid in ("S115","S097","C13") if r["case_id"]==cid]'
```
