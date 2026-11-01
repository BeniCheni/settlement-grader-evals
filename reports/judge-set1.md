# Judge agreement

Command: `python3 -m scorer.judge report --labels labels/set1.jsonl --final labels/set1-final.jsonl --readings labels/set1-readings.json --provenance labels/set1-provenance.txt --verdicts judgments/set1-llama3.1-8b`

Worst judge on the final labels: rule_adherence.

Model: llama3.1:8b. Digest: 46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e.

## needs_human_correctness

Rubric SHA-256: 95c8bb718c854167c8ad55426ceb62bf446ac4ca61573dd6c82aaf96be0f26ab.
Labels SHA-256: dd37a1885e4c7f58a3600db9ae7edc12c90eb783693e560cf4b42573c25c9a94.
same text as when the labels were made
UNPARSED: 0.

### First-pass labels

JP_HP (tn): 29
JP_HF (fn): 6
JF_HP (fp): 3
JF_HF (tp): 2

Agreement: 0.7750. Kappa: 0.1818. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 6 of 6.

False passes:
- traces/v1 B02: The ticket is decided because every leg that matters has a final result.. Reading: yes.
- traces/v1 B05: The ticket is decided because every leg that matters has a final result, but the grader did not settle it because the run status is incomplete.. Reading: yes.
- traces/v1 B06: The ticket is decided, but the grader's premature finalization of the ticket is not a failure to settle or escalate correctly.. Reading: yes.
- traces/v1 B08: The ticket is decided because every leg that matters has a final result, but the grader did not settle it because it ran out of turns.. Reading: yes.
- traces/v1 C02: The ticket is unsettled because all legs are still ongoing, and the grader did not settle it when the facts decided it.. Reading: yes.
- traces/v1 C03: The ticket was decided, but the grader did not settle it because the match results were not final.. Reading: yes.

False fails:
- traces/v1 A02: No match found for the given date and teams.. Reading: yes.
- traces/v1 B10: The ticket was not decided because the match facts are not available.. Reading: yes.
- traces/v1 C10: The ticket is decided, but the final answer is UNSETTLED, which is only correct when a leg that matters is not final.. Reading: yes.

### Final labels

JP_HP (tn): 29
JP_HF (fn): 6
JF_HP (fp): 2
JF_HF (tp): 3

Agreement: 0.8000. Kappa: 0.3191. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 6 of 6.

False passes:
- traces/v1 B01: The ticket is decided because the match was found, its status is final, and the fact the market needs is in the results.. Reading: yes.
- traces/v1 B05: The ticket is decided because every leg that matters has a final result, but the grader did not settle it because the run status is incomplete.. Reading: yes.
- traces/v1 B06: The ticket is decided, but the grader's premature finalization of the ticket is not a failure to settle or escalate correctly.. Reading: yes.
- traces/v1 B08: The ticket is decided because every leg that matters has a final result, but the grader did not settle it because it ran out of turns.. Reading: yes.
- traces/v1 C02: The ticket is unsettled because all legs are still ongoing, and the grader did not settle it when the facts decided it.. Reading: yes.
- traces/v1 C03: The ticket was decided, but the grader did not settle it because the match results were not final.. Reading: yes.

False fails:
- traces/v1 B10: The ticket was not decided because the match facts are not available.. Reading: yes.
- traces/v1 C10: The ticket is decided, but the final answer is UNSETTLED, which is only correct when a leg that matters is not final.. Reading: yes.

## rule_adherence

Rubric SHA-256: 146510e20d1e62ab03819404703201065a9a8ab062735970071295dc0e3ebbf2.
Labels SHA-256: dd37a1885e4c7f58a3600db9ae7edc12c90eb783693e560cf4b42573c25c9a94.
same text as when the labels were made
UNPARSED: 0.

### First-pass labels

JP_HP (tn): 0
JP_HF (fn): 0
JF_HP (fp): 17
JF_HF (tp): 23

Agreement: 0.5750. Kappa: 0.0000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 0 of 0.

False passes:
none

False fails:
- traces/aa-1 A01: Leg 1, Portugal won 2-4 in regulation, but the grader should have used the exact score 2-4, not just that Portugal won.. Reading: yes.
- traces/aa-1 A05: Leg 1, USA selection, regulation score 3-0, rule "Money Line 3-Way / Match Result settles on the 90-minute regulation result...". Reading: yes.
- traces/aa-1 A08: Leg 1, Slovenia selection, regulation score 1-2, Draw selection wins on a regulation draw.. Reading: yes.
- traces/aa-1 A13: Leg 1, Draw No Bet, Rayo Vallecano selection, score 1-1.. Reading: yes.
- traces/aa-1 B01: Leg 1, Sehrou Guirassy did not score in regulation time, but the grader's rule was "Anytime goalscorer wins if the player scores in regulation time. Own goals do not count for the player.". Reading: yes.
- traces/aa-1 B04: Leg 3, Total goals: the tool results show 4 goals, but the rule says a whole line pushes on exactly that number.. Reading: yes.
- traces/v1 A01: Leg 1, Portugal won 2-4 in regulation, but the grader should have used the exact score 2-4, not just that Portugal won.. Reading: yes.
- traces/v1 A02: Leg 1, no match found for the given date and teams.. Reading: yes.
- traces/v1 A05: Leg 1, USA selection in a Money Line 3-Way market, but the score_regulation_90 is 3-0, which is a win for Mexico.. Reading: yes.
- traces/v1 A08: Leg 1, Slovenia won the regulation 90-minute match (score 1-2) contradicts the rule that the Draw selection wins on a regulation draw.. Reading: yes.
- traces/v1 A13: Leg 1, Draw No Bet market, the selected team Rayo Vallecano did not win or lose.. Reading: yes.
- traces/v1 B01: Leg 1, Sehrou Guirassy did not score in regulation time.. Reading: yes.
- traces/v1 B04: Leg 3, Total goals market, regulation score is 3-1, but the grader graded it W instead of L.. Reading: yes.
- traces/v1 C06: Leg 1, Brighton won 0-2, but the rule says the Draw selection wins on a regulation draw.. Reading: yes.
- traces/v1 C09: Leg 2, result "L" for Juventus, but the grader did not apply the rule for Money Line 3-Way / Match Result, which requires checking the exact score, not just who won.. Reading: yes.
- traces/v1 C12: Leg 1, Manchester City selection, regulation score 2-1, Money Line 3-Way rule.. Reading: yes.
- traces/v1 C13: Leg 1, selection "Bayern Munich" in Moneyline 3-Way market, score_regulation_90 is 0-0, which is a draw, and the selection should win.. Reading: yes.

### Final labels

JP_HP (tn): 0
JP_HF (fn): 0
JF_HP (fp): 14
JF_HF (tp): 26

Agreement: 0.6500. Kappa: 0.0000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 0 of 0.

False passes:
none

False fails:
- traces/aa-1 A01: Leg 1, Portugal won 2-4 in regulation, but the grader should have used the exact score 2-4, not just that Portugal won.. Reading: yes.
- traces/aa-1 A05: Leg 1, USA selection, regulation score 3-0, rule "Money Line 3-Way / Match Result settles on the 90-minute regulation result...". Reading: yes.
- traces/aa-1 A08: Leg 1, Slovenia selection, regulation score 1-2, Draw selection wins on a regulation draw.. Reading: yes.
- traces/aa-1 A13: Leg 1, Draw No Bet, Rayo Vallecano selection, score 1-1.. Reading: yes.
- traces/aa-1 B01: Leg 1, Sehrou Guirassy did not score in regulation time, but the grader's rule was "Anytime goalscorer wins if the player scores in regulation time. Own goals do not count for the player.". Reading: yes.
- traces/aa-1 B04: Leg 3, Total goals: the tool results show 4 goals, but the rule says a whole line pushes on exactly that number.. Reading: yes.
- traces/v1 A01: Leg 1, Portugal won 2-4 in regulation, but the grader should have used the exact score 2-4, not just that Portugal won.. Reading: yes.
- traces/v1 A02: Leg 1, no match found for the given date and teams.. Reading: yes.
- traces/v1 A05: Leg 1, USA selection in a Money Line 3-Way market, but the score_regulation_90 is 3-0, which is a win for Mexico.. Reading: yes.
- traces/v1 A08: Leg 1, Slovenia won the regulation 90-minute match (score 1-2) contradicts the rule that the Draw selection wins on a regulation draw.. Reading: yes.
- traces/v1 A13: Leg 1, Draw No Bet market, the selected team Rayo Vallecano did not win or lose.. Reading: yes.
- traces/v1 B04: Leg 3, Total goals market, regulation score is 3-1, but the grader graded it W instead of L.. Reading: yes.
- traces/v1 C06: Leg 1, Brighton won 0-2, but the rule says the Draw selection wins on a regulation draw.. Reading: yes.
- traces/v1 C12: Leg 1, Manchester City selection, regulation score 2-1, Money Line 3-Way rule.. Reading: yes.

## tool_call_accuracy

Rubric SHA-256: b784093e855cba00c6a29a68c6b1c829fc91f93017d78de4a0c87f6a6d3154e4.
Labels SHA-256: dd37a1885e4c7f58a3600db9ae7edc12c90eb783693e560cf4b42573c25c9a94.
same text as when the labels were made
UNPARSED: 0.

### First-pass labels

JP_HP (tn): 10
JP_HF (fn): 7
JF_HP (fp): 7
JF_HF (tp): 16

Agreement: 0.6500. Kappa: 0.2839. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 7 of 7.

False passes:
- traces/aa-1 A11: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.
- traces/v1 A03: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.
- traces/v1 A06: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.
- traces/v1 A09: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.
- traces/v1 A11: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.
- traces/v1 A12: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.
- traces/v1 B12: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.. Reading: yes.

False fails:
- traces/aa-1 B04: Tool call 3, lookup_rule, returned UNKNOWN_TOPIC for "btts" and no subsequent lookup_rule call with a listed topic for that market.. Reading: yes.
- traces/v1 B01: lookup_rule call with topic "goalscorer" returned UNKNOWN_TOPIC, but the grader never looked up "goalscorer" again.. Reading: yes.
- traces/v1 B04: Tool call 3, lookup_rule with topic "btts", returned UNKNOWN_TOPIC, and the grader never looked up "btts" again.. Reading: yes.
- traces/v1 C06: lookup_rule call returned "moneyline_3way" topic, but the grader never called it again with a listed topic for that market.. Reading: yes.
- traces/v1 C09: Tool call 5: lookup_rule returned UNKNOWN_TOPIC, but the grader never looked up "moneyline_3way" again.. Reading: yes.
- traces/v1 C13: Tool call 3 with args {"topic": "moneyline_3way"} returned {"rule": "Money Line 3-Way / Match Result settles on the 90-minute regulation result including stoppage time. Extra time and penalties are ignored. Use score_regulation_90. The Draw selection wins on a regulation draw; both team selections lose on a draw.", "topic": "moneyline_3way"} but the grader never called lookup_rule again with a listed topic for that market.. Reading: yes.
- traces/v1 X02: The grader gave a final grade with no tool calls at all.. Reading: yes.

### Final labels

JP_HP (tn): 17
JP_HF (fn): 0
JF_HP (fp): 3
JF_HF (tp): 20

Agreement: 0.9250. Kappa: 0.8500. Kappa at least 0.6: yes.
meets_bar (85% and 0.6): yes. False passes read: 0 of 0.

False passes:
none

False fails:
- traces/aa-1 B04: Tool call 3, lookup_rule, returned UNKNOWN_TOPIC for "btts" and no subsequent lookup_rule call with a listed topic for that market.. Reading: yes.
- traces/v1 B04: Tool call 3, lookup_rule with topic "btts", returned UNKNOWN_TOPIC, and the grader never looked up "btts" again.. Reading: yes.
- traces/v1 C09: Tool call 5: lookup_rule returned UNKNOWN_TOPIC, but the grader never looked up "moneyline_3way" again.. Reading: yes.

## Written by hand, not computed

Written by Claude, in the PM seat, at the owner's request on 31 Oct 2026, from the repository record and the adjudication log. The owner made every label and every ruling it describes. Set 1: the rubrics merged in PR #11 (37b6e7f) before the labels merged in PR #12 (0055d07). Each verdict carries its rubric's hash, and every hash matches the one recorded in labels/set1-meta.json, so no rubric changed after labelling or during adjudication. Decision 6: each rubric's boundary example shares an underlying bet with labelled rows (needs_human_correctness: v1 A12; tool_call_accuracy: v1 C08; rule_adherence: v1 C09 and X01), so those rows are in sample for that rubric. Adjudication: the owner ruled on all 40 first-pass disagreements one at a time, each shown with the ticket, the tool calls, the final answer, the run status and the judge's verdict and reason. 17 labels changed, each with the owner's reason recorded in labels/set1-final.jsonl, and every disagreement that remains has a reading in labels/set1-readings.json. The PM seat wrote the readings from the owner's rulings; the note that the judge gave a stock PASS sentence on the seven tool_call rows that changed to PASS is the PM seat's observation, not the owner's. 16 of the 17 changes moved the label to the judge's verdict. The one that did not, needs_human_correctness v1 B01 (PASS to FAIL), created a new disagreement in which the judge passes a row the owner fails. Because the owner saw the judge's verdicts before ruling, the final labels are not blind to the judge and the final agreement figures are optimistic; the first-pass figures are the blind ones, and set 2 is the independent test. The report covers all 40 rows of each rubric; it does not compute the 39/39/38-row held-out figures. Per rubric, every result in this report is in sample, not held out. needs_human_correctness: in sample, because v1 A12 shares its bet with the boundary example and the final labels were adjudicated after the verdicts were seen. tool_call_accuracy: in sample, for the same two reasons, through v1 C08. rule_adherence: in sample, for the same two reasons, through v1 C09 and X01. For each rubric the figures show how closely llama3.1:8b reproduces the owner's labels on these 40 rows; they do not show how it would agree on rows the rubric's examples and the adjudication never touched, and the first-pass figures are the nearest this set comes to that.
