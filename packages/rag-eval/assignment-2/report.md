Written by the PM seat on Tue 10 Nov 2026, after both runs, with the verdict the owner gave (ruling 51). Nothing in this statement is computed.

**What this rests on.** One session on one machine, from a fresh clone of `main` at `29702e6`, on Mon 9 Nov 2026 from 21:43 to 00:05 EST: variant a, then variant b, back to back, one pass each over v1's 159 rows. Both ran `qwen3:8b` at temperature 0 with thinking off, under one model digest and Ollama 0.34.0. The intervals come from resampling the 159 rows, and both variants graded the same rows, so the A/B is paired. One pass each cannot show how much a second pass would move. On the rows, A gave the same ticket result as the pilot's strong run, made that afternoon under the same model, on every one of the 159.

**The alias table is in sample on the six misses.** B differs from A in one parameter, `rule_match`: `alias` lets a rule lookup resolve a name the grader drifted to, where `exact` refuses it. The alias table was written knowing the six misses on record, `match_result`, `anytime_goalscorer`, `total_goals`, `both_teams_to_score`, `goals` and `combo`, so B's effect on those six is in sample. B also resolved names outside those six, which the table already held. No alias, bar or threshold changed after the runs.

**29 rows are tickets the earlier runs used.** v1's 29 real rows come from `data/gold.json`. The grader graded them in earlier runs (`v1`, `aa-1` to `aa-3`, `ab-a` and `ab-b`), and the six misses were seen in those runs. There were 30 until `B10` was dropped before the freeze (ruling 49). The 130 synthetic and hand-crafted rows were new to the grader until Week 4's pilot. v1 was then chosen with the pilot's strong run, which is A's config, but the pilot cut only `B10`, and for its key, not for how the grader did.

**What the A/B shows.** Recall and precision rose a little under B, with intervals above zero. Faithfulness fell a little, with an interval below zero that stays inside its bar. Both variants matched 80 of 159 outcomes, and one row moved each way. On `B08`, A's lookup of `both_teams_to_score` was refused and the grader ran out of turns, while B resolved it and graded the ticket right. On `S099`, B's alias sent `player_shots_on_target` to the team rule, which says a player's shots need a human, and the grader then graded `VOID` where the key is `LOSS`. The report's verdict line reads ship because all three bars, set in the spec before either run, hold.

**What it does not show.** The four scorers are plain functions written for this grader: retrieval is the tool calls it made, and faithfulness checks each committed grade against the facts it read. They are not the course library's model-based scorers. The pilot's strong run, which is A's config, graded 79 of v1's rows differently from their keys, and A matches only about half the outcomes here, so these means describe a grader that is often wrong. Only 5 of the 159 keys are `verified_by_beni`. The rest are code-checked or the owner's. The weaker half is generation in both variants.

**The verdict is the owner's: ship (ruling 51).** B meets all three bars. Its recall gain is partly in sample, and its faithfulness fell by a small amount that is still real. This package changes no code: `alias` becoming the grader's default would be a PR of its own.

# RAG report

## Dataset

n: 159
sha256: 2438ce0a7b0d336b75706620ba89ae1b2bfd449b485eb0487a45e53af02027a9
langsmith dataset_id 13709a92-acc2-4067-9d86-b4b9cdf4f53c as_of 2026-11-10 14:31:08.482415+00:00

## Variant a

### Retrieval

| scorer | mean | scored | none | interval | k of n |
| --- | --- | --- | --- | --- | --- |
| context_recall | 0.591 | 159 | 0 | [0.540, 0.642] | found 352 of 643 needed |
| context_precision | 0.826 | 159 | 0 | [0.777, 0.873] | relevant 352 of 464 retrieved |

### Generation

| scorer | mean | scored | none | interval | k of n |
| --- | --- | --- | --- | --- | --- |
| faithfulness | 0.501 | 144 | 15 | [0.435, 0.567] | supported 203 of 383 claims legs left 26 |
| answer_relevancy | 0.857 | 159 | 0 | [0.821, 0.892] | held 545 of 636 tests |

## Variant b

### Retrieval

| scorer | mean | scored | none | interval | k of n |
| --- | --- | --- | --- | --- | --- |
| context_recall | 0.605 | 159 | 0 | [0.554, 0.655] | found 364 of 643 needed |
| context_precision | 0.837 | 159 | 0 | [0.788, 0.884] | relevant 364 of 442 retrieved |

### Generation

| scorer | mean | scored | none | interval | k of n |
| --- | --- | --- | --- | --- | --- |
| faithfulness | 0.489 | 145 | 14 | [0.423, 0.554] | supported 206 of 391 claims legs left 26 |
| answer_relevancy | 0.865 | 159 | 0 | [0.829, 0.898] | held 550 of 636 tests |

## Weaker half

variant a: generation is the weaker half
variant b: generation is the weaker half

## A/B

context_recall delta 0.014 interval [0.003, 0.029] paired 159 left 0
context_precision delta 0.011 interval [0.004, 0.020] paired 159 left 0
faithfulness delta -0.016 interval [-0.031, -0.003] paired 144 left 15
answer_relevancy delta 0.008 interval [-0.003, 0.024] paired 159 left 0
outcome fall 0.000 interval [-0.021, 0.021] paired 159 left 0 a 79 b 1 c 1 d 78
recall: lower bound 0.003 above 0.000: yes
faithfulness: lower bound -0.031 at least -0.050: yes
outcome: upper bound 0.021 at most 0.050: yes
verdict: ship

## Groundedness candidates

A01 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
A05 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
A08 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
A13 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
B01 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
B04 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 7
B05 recall 0.429 precision 0.917 faithfulness 0.400 relevancy 1.000 tool_calls 8
B13 recall 0.714 precision 1.000 faithfulness 0.667 relevancy 1.000 tool_calls 7
C12 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
C13 recall 0.667 precision 1.000 faithfulness 0.250 relevancy 0.750 tool_calls 6
E01 recall 0.000 precision 0.000 faithfulness 1.000 relevancy 0.750 tool_calls 1
E02 recall 0.000 precision 0.000 faithfulness 1.000 relevancy 0.750 tool_calls 1
E03 recall 0.000 precision 0.000 faithfulness 1.000 relevancy 0.750 tool_calls 1
E10 recall 0.143 precision 1.000 faithfulness 1.000 relevancy 0.750 tool_calls 11
E11 recall 0.167 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 10
E12 recall 1.000 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 4
E15 recall 0.500 precision 0.806 faithfulness 1.000 relevancy 0.750 tool_calls 7
S007 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
S009 recall 0.200 precision 1.000 faithfulness 0.500 relevancy 0.750 tool_calls 9
S011 recall 0.250 precision 1.000 faithfulness 1.000 relevancy 0.750 tool_calls 5
S012 recall 0.250 precision 0.500 faithfulness 1.000 relevancy 0.750 tool_calls 4
S017 recall 1.000 precision 0.506 faithfulness 0.333 relevancy 0.750 tool_calls 12
S020 recall 0.400 precision 0.417 faithfulness none relevancy 1.000 tool_calls 11
S021 recall 0.200 precision 0.500 faithfulness none relevancy 0.750 tool_calls 9
S024 recall 0.750 precision 0.917 faithfulness 1.000 relevancy 1.000 tool_calls 7
S025 recall 0.200 precision 0.500 faithfulness 0.000 relevancy 1.000 tool_calls 9
S026 recall 0.200 precision 0.500 faithfulness 0.000 relevancy 0.750 tool_calls 9
S027 recall 0.200 precision 0.500 faithfulness 0.500 relevancy 1.000 tool_calls 9
S028 recall 0.750 precision 1.000 faithfulness 0.000 relevancy 0.750 tool_calls 7
S029 recall 0.750 precision 0.917 faithfulness 0.000 relevancy 1.000 tool_calls 7
S031 recall 0.750 precision 0.639 faithfulness 1.000 relevancy 0.750 tool_calls 7
S034 recall 0.800 precision 1.000 faithfulness 0.667 relevancy 1.000 tool_calls 8
S036 recall 1.000 precision 0.796 faithfulness 0.833 relevancy 1.000 tool_calls 11
S047 recall 1.000 precision 0.877 faithfulness 0.500 relevancy 1.000 tool_calls 10
S049 recall 0.200 precision 1.000 faithfulness 0.667 relevancy 1.000 tool_calls 5
S053 recall 1.000 precision 1.000 faithfulness 0.667 relevancy 1.000 tool_calls 10
S066 recall 0.200 precision 0.500 faithfulness 0.000 relevancy 1.000 tool_calls 10
S067 recall 0.200 precision 0.500 faithfulness 0.000 relevancy 1.000 tool_calls 9
S070 recall 0.200 precision 0.500 faithfulness 0.000 relevancy 1.000 tool_calls 9
S076 recall 0.400 precision 1.000 faithfulness 0.400 relevancy 1.000 tool_calls 10
S077 recall 0.200 precision 1.000 faithfulness 0.833 relevancy 1.000 tool_calls 10
S080 recall 1.000 precision 0.877 faithfulness 0.833 relevancy 1.000 tool_calls 11
S082 recall 0.400 precision 1.000 faithfulness 0.667 relevancy 1.000 tool_calls 10
S085 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
S087 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
S097 recall 0.200 precision 1.000 faithfulness 0.000 relevancy 1.000 tool_calls 9
S098 recall 0.200 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 9
S099 recall 0.750 precision 1.000 faithfulness 1.000 relevancy 0.750 tool_calls 8
S100 recall 0.200 precision 1.000 faithfulness 0.000 relevancy 1.000 tool_calls 9
S106 recall 0.400 precision 1.000 faithfulness 0.000 relevancy 0.750 tool_calls 9
S113 recall 0.200 precision 1.000 faithfulness 0.667 relevancy 1.000 tool_calls 9
S114 recall 0.200 precision 0.500 faithfulness 0.500 relevancy 1.000 tool_calls 9
S115 recall 0.750 precision 1.000 faithfulness 0.000 relevancy 1.000 tool_calls 9
S117 recall 0.750 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 9
S119 recall 1.000 precision 0.917 faithfulness 0.500 relevancy 0.750 tool_calls 6
S120 recall 0.667 precision 0.833 faithfulness 0.500 relevancy 1.000 tool_calls 6
S121 recall 0.667 precision 0.833 faithfulness 0.667 relevancy 1.000 tool_calls 6
S123 recall 1.000 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 4
S128 recall 1.000 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 4
S131 recall 1.000 precision 1.000 faithfulness 0.667 relevancy 0.750 tool_calls 5
S148 recall 0.667 precision 1.000 faithfulness 1.000 relevancy 1.000 tool_calls 4
S153 recall 0.750 precision 0.478 faithfulness 1.000 relevancy 0.750 tool_calls 8
S155 recall 0.750 precision 0.917 faithfulness 0.500 relevancy 1.000 tool_calls 10
S158 recall 0.200 precision 0.500 faithfulness none relevancy 1.000 tool_calls 6
S159 recall 0.800 precision 1.000 faithfulness 1.000 relevancy 0.750 tool_calls 7
S160 recall 1.000 precision 1.000 faithfulness 0.500 relevancy 1.000 tool_calls 10
S164 recall 0.200 precision 1.000 faithfulness 0.500 relevancy 0.750 tool_calls 10
S173 recall 0.200 precision 1.000 faithfulness 0.000 relevancy 1.000 tool_calls 10
S174 recall 0.400 precision 1.000 faithfulness 0.000 relevancy 1.000 tool_calls 9

## Runs

model: qwen3:8b
model_digest: 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
ollama_version: 0.34.0
variant a rule_match exact run_id w4-a think False
variant b rule_match alias run_id w4-b think False
braintrust a 425d69e4-1d27-4091-838b-286c13aab2a7 b e5729bff-99e7-4687-89dd-77a5671a89ab

## Commands

python3 -m scorer.rag run --config packages/rag-eval/assignment-2/config.yaml --variant a
python3 -m scorer.rag run --config packages/rag-eval/assignment-2/config.yaml --variant b
python3 -m scorer.rag report --config packages/rag-eval/assignment-2/config.yaml
