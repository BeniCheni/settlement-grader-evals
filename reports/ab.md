# Did the change work?

Command: `python3 -m scorer.judge ab --a traces/ab-a --b traces/ab-b --verdicts judgments/ab --thresholds submissions/week-02/assignment-2/thresholds.json --statement submissions/week-02/assignment-2/statement.txt --set1 reports/judge-set1.json --cases data/gold.json --html reports/ab.html`

## GRADE_CONTRADICTS_FACTS

A 15. B 16.
Delta -1 tickets, -3.1 points.
Interval -17.1 to 11.2 points.
Delta is A minus B: a plus means fewer tickets with the code in B. The interval is the paired interval on that delta, z 1.96.

6 of 8 thresholds held.

## Written by hand, not computed

<!-- input:statement -->
Written by Claude, in the PM seat, at the owner's request on 1 Nov 2026; amended by Codex during review, and by Claude after the runs, on reading them. In sample. The change was chosen by reading these 32 tickets, and the code checks were built against traces/v1, which holds them, so these figures show what the change did to these tickets and not what it would do to tickets it has not seen. The judges' rubrics are frozen from set 1, and their agreement with the owner's labels, in sample too, is the only reason to read their deltas at all; rule_adherence answered FAIL on all 40 rows of set 1, so its delta says least. Two runs in one session with the same recorded setup reduce known setup differences but do not rule out unrecorded differences or chance: each delta has its interval beside it. Read the traces beside these figures: on none of the 29 tickets where variant B called settle_ticket did it write the requested comparison beside that call, and it settled in the same message as a lookup on 8 tickets against A's 3. So these figures show what this wording did to these tickets, not whether a comparison made before the grade would help.

<!-- /input:statement -->

## Setup

Ollama 0.34.0.
Grader model qwen3:8b. Digest 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41.
Judge model llama3.1:8b. Digest 46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e. Adapter ollama.
Interval method newcombe-1998-method-10, z 1.96.
A traces/ab-a.
B traces/ab-b.

## Prompt

<!-- input:diff -->
--- A
+++ B
@@ -5,3 +5,3 @@
 2. Call lookup_rule for each kind of market you grade.
-3. Grade each leg: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a rule says so).
+3. Grade each leg by comparing it with the facts. In the same message as your settle_ticket call, first write one line per leg: the selection, the score or stat from get_match_facts with home and away named, and what that means for the selection. Then give its result: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a rule says so).
 4. Call settle_ticket with your leg results, the stake, the stake_kind, and the ticket price and printed payout if the ticket gives them.
<!-- /input:diff -->

## Set 1

rule_adherence is the delta to read with most care.

### needs_human_correctness

meets_bar: no. Agreement 80.0% (0.8000). Kappa 0.3191. False passes read: 6 of 6.

### rule_adherence

meets_bar: no. Agreement 65.0% (0.6500). Kappa 0.0000. False passes read: no false passes.

### tool_call_accuracy

meets_bar: yes. Agreement 92.5% (0.9250). Kappa 0.8500. False passes read: no false passes.

### Written by hand, not computed

<!-- input:statement -->
Written by Claude, in the PM seat, at the owner's request on 1 Nov 2026; amended by Codex during review, and by Claude after the runs, on reading them. In sample. The change was chosen by reading these 32 tickets, and the code checks were built against traces/v1, which holds them, so these figures show what the change did to these tickets and not what it would do to tickets it has not seen. The judges' rubrics are frozen from set 1, and their agreement with the owner's labels, in sample too, is the only reason to read their deltas at all; rule_adherence answered FAIL on all 40 rows of set 1, so its delta says least. Two runs in one session with the same recorded setup reduce known setup differences but do not rule out unrecorded differences or chance: each delta has its interval beside it. Read the traces beside these figures: on none of the 29 tickets where variant B called settle_ticket did it write the requested comparison beside that call, and it settled in the same message as a lookup on 8 tickets against A's 3. So these figures show what this wording did to these tickets, not whether a comparison made before the grade would help.

<!-- /input:statement -->

## Metrics

Delta is A minus B. For a code, a plus means fewer tickets with the code in B. For a judge, the tickets counted are FAIL and UNPARSED, so a plus means more PASS in B. Each interval is the paired interval on that delta, z 1.96.

### Judges

Judges — 32 tickets per run. Non-PASS includes UNPARSED; the UNPARSED columns are subsets. FAIL in the transition columns includes UNPARSED.

| Judge | PASS A (%) | PASS B (%) | Non-PASS A (tickets) | Non-PASS B (tickets) | Delta (tickets) | Delta (points) | Paired interval (points) | FAIL to PASS (tickets) | PASS to FAIL (tickets) | UNPARSED A (subset) | UNPARSED B (subset) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| needs_human_correctness | 90.6% | 96.9% | 3 | 1 | +2 | +6.3 | -6.3 to 20.7 | 2 | 0 | 0 | 0 |
| rule_adherence | 0.0% | 0.0% | 32 | 32 | +0 | +0.0 | -10.7 to 10.7 | 0 | 0 | 0 | 0 |
| tool_call_accuracy | 43.8% | 34.4% | 18 | 21 | -3 | -9.4 | -25.2 to 7.3 | 2 | 5 | 0 | 0 |

### Codes

Codes — 32 tickets per run.

| Code | A (tickets) | B (tickets) | Delta (tickets) | Delta (points) | Paired interval (points) | Only A (tickets) | Only B (tickets) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GRADE_CONTRADICTS_FACTS | 15 | 16 | -1 | -3.1 | -17.1 to 11.2 | 2 | 3 |
| WIN_LOSS_FLIP | 15 | 11 | +4 | +12.5 | -0.4 to 24.5 | 4 | 0 |
| SKIPPED_SETTLE_TICKET | 8 | 5 | +3 | +9.4 | -10.1 to 28.2 | 6 | 3 |
| PLACEHOLDER_ECHO | 5 | 3 | +2 | +6.3 | -10.9 to 23.5 | 4 | 2 |
| GRADED_WITHOUT_LOOKUP | 5 | 1 | +4 | +12.5 | -1.6 to 28.4 | 4 | 0 |
| INCOMPLETE_LEG_LIST | 7 | 2 | +5 | +15.6 | -1.8 to 33.0 | 6 | 1 |
| WRONG_NON_GRADE | 2 | 1 | +1 | +3.1 | -8.8 to 16.4 | 1 | 0 |
| NO_FINAL_ANSWER | 1 | 1 | +0 | +0.0 | -13.0 to 13.0 | 1 | 1 |
| RULE_TOPIC_MISS | 5 | 6 | -1 | -3.1 | -19.0 to 12.6 | 2 | 3 |
| OUTPUT_LIMIT_SPRAY | 0 | 1 | -1 | -3.1 | -15.7 to 7.9 | 0 | 1 |
| FOLLOWED_TICKET_CLAIM | 2 | 1 | +1 | +3.1 | -8.8 to 16.4 | 1 | 0 |

## Thresholds

GRADE_CONTRADICTS_FACTS. Not held. Minimum fall (A minus B) 5 tickets, lower limit above 0 points required: yes. Observed A minus B -1 tickets, lower limit -17.1 points.
WIN_LOSS_FLIP. Held. Maximum rise (B minus A) 0 tickets. Observed B minus A -4 tickets.
FOLLOWED_TICKET_CLAIM. Held. Maximum rise (B minus A) 0 tickets. Observed B minus A -1 tickets.
NO_FINAL_ANSWER. Held. Maximum rise (B minus A) 1 tickets. Observed B minus A +0 tickets.
SKIPPED_SETTLE_TICKET. Held. Maximum rise (B minus A) 1 tickets. Observed B minus A -3 tickets.
GRADED_WITHOUT_LOOKUP. Held. Maximum rise (B minus A) 1 tickets. Observed B minus A -4 tickets.
tool_call_accuracy. Not held. Maximum PASS fall (A minus B) 1 tickets. Observed PASS A minus B +3 tickets.
needs_human_correctness. Held. Maximum PASS fall (A minus B) 2 tickets. Observed PASS A minus B -2 tickets.
rule_adherence. Report only. Not counted.

6 of 8 thresholds held.

## Tickets

22 of 32 tickets changed a final, a code or a verdict.

### A01

A final WIN. B final WIN.
A codes none.
B codes none.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### A02

Changed: codes

A final VOID. B final VOID.
A codes SKIPPED_SETTLE_TICKET, INCOMPLETE_LEG_LIST, WRONG_NON_GRADE.
B codes WRONG_NON_GRADE.
needs_human_correctness A FAIL. B FAIL.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### A03

Changed: codes

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, PLACEHOLDER_ECHO.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### A05

A final WIN. B final WIN.
A codes none.
B codes none.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### A06

Changed: codes

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, PLACEHOLDER_ECHO.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### A08

A final WIN. B final WIN.
A codes none.
B codes none.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### A09

Changed: codes, tool_call_accuracy

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, PLACEHOLDER_ECHO.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B FAIL.
<!-- input:reason -->
A: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
B: Tool call 2, get_match_facts, returned an error, but the grader continued with a lookup_rule call.
<!-- /input:reason -->

### A11

Changed: tool_call_accuracy

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B FAIL.
<!-- input:reason -->
A: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
B: Tool call 3, lookup_rule, returned an unknown topic, "moneyline_3way", which was not looked up again.
<!-- /input:reason -->

### A12

Changed: final, codes, tool_call_accuracy

A final WIN. B final PUSH.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
B codes GRADE_CONTRADICTS_FACTS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B FAIL.
<!-- input:reason -->
A: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
B: Tool call 2, get_match_facts, returned an error, but the grader continued with a successful settle_ticket call.
<!-- /input:reason -->

### A13

A final PUSH. B final PUSH.
A codes PLACEHOLDER_ECHO.
B codes PLACEHOLDER_ECHO.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### B01

A final LOSS. B final LOSS.
A codes none.
B codes none.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### B02

Changed: codes, tool_call_accuracy

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, INCOMPLETE_LEG_LIST, RULE_TOPIC_MISS.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, RULE_TOPIC_MISS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B PASS.
<!-- input:reason -->
A: lookup_rule call 4 returned UNKNOWN_TOPIC and no subsequent lookup_rule call with a listed topic for that market.
B: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
<!-- /input:reason -->

### B04

Changed: codes

A final WIN. B final WIN.
A codes none.
B codes RULE_TOPIC_MISS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### B05

A final LOSS. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS, RULE_TOPIC_MISS.
B codes GRADE_CONTRADICTS_FACTS, RULE_TOPIC_MISS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### B06

Changed: codes

A final LOSS. B final LOSS.
A codes WIN_LOSS_FLIP, SKIPPED_SETTLE_TICKET, GRADED_WITHOUT_LOOKUP.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, RULE_TOPIC_MISS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### B08

Changed: final, codes

A final none. B final LOSS.
A codes NO_FINAL_ANSWER, RULE_TOPIC_MISS.
B codes RULE_TOPIC_MISS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### B09

Changed: codes, tool_call_accuracy

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, INCOMPLETE_LEG_LIST.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B PASS.
<!-- input:reason -->
A: Tool call 3: lookup_rule with topic "team_total" returned UNKNOWN_TOPIC, but the grader never looked up "totals" or "double_chance" for that market.
B: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
<!-- /input:reason -->

### B10

Changed: final, codes, tool_call_accuracy

A final WIN. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS, RULE_TOPIC_MISS.
B codes SKIPPED_SETTLE_TICKET.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B FAIL.
<!-- input:reason -->
A: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
B: The grader called settle_ticket with leg_results that included a result of "L" for a leg that was graded as "L", but the result was invalid.
<!-- /input:reason -->

### B12

A final WIN. B final WIN.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### B13

Changed: codes

A final LOSS. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS.
B codes PLACEHOLDER_ECHO.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C02

Changed: final, codes

A final WIN. B final LOSS.
A codes WIN_LOSS_FLIP, SKIPPED_SETTLE_TICKET, GRADED_WITHOUT_LOOKUP.
B codes GRADE_CONTRADICTS_FACTS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C03

Changed: final, codes, needs_human_correctness

A final WIN. B final none.
A codes WIN_LOSS_FLIP, SKIPPED_SETTLE_TICKET, GRADED_WITHOUT_LOOKUP.
B codes NO_FINAL_ANSWER, RULE_TOPIC_MISS, OUTPUT_LIMIT_SPRAY.
needs_human_correctness A FAIL. B PASS.
<!-- input:reason -->
A: The ticket was decided, but the grader settled it anyway, despite the PREMATURE_FINAL reason.
B: The ticket is decided because every leg that matters has a final result.
<!-- /input:reason -->
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C04

A final LOSS. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C06

A final WIN. B final WIN.
A codes SKIPPED_SETTLE_TICKET.
B codes SKIPPED_SETTLE_TICKET.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C08

Changed: codes

A final LOSS. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, INCOMPLETE_LEG_LIST, RULE_TOPIC_MISS.
B codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, SKIPPED_SETTLE_TICKET.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C09

Changed: codes

A final LOSS. B final LOSS.
A codes SKIPPED_SETTLE_TICKET, GRADED_WITHOUT_LOOKUP.
B codes GRADE_CONTRADICTS_FACTS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C10

Changed: final, codes, tool_call_accuracy

A final NEEDS_HUMAN. B final LOSS.
A codes SKIPPED_SETTLE_TICKET, INCOMPLETE_LEG_LIST, WRONG_NON_GRADE.
B codes PLACEHOLDER_ECHO, INCOMPLETE_LEG_LIST.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B FAIL.
<!-- input:reason -->
A: The grader called the right tools with the right arguments, and its settle_ticket call matches the leg grades it gave.
B: Tool call 4, get_match_facts, returned an error, but the grader continued with other calls.
<!-- /input:reason -->

### C12

A final WIN. B final WIN.
A codes none.
B codes none.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A PASS. B PASS.

### C13

Changed: codes

A final LOSS. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS, INCOMPLETE_LEG_LIST.
B codes GRADE_CONTRADICTS_FACTS.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### C14

Changed: codes

A final LOSS. B final LOSS.
A codes none.
B codes INCOMPLETE_LEG_LIST.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### X01

Changed: final, codes

A final WIN. B final LOSS.
A codes GRADE_CONTRADICTS_FACTS, WIN_LOSS_FLIP, FOLLOWED_TICKET_CLAIM.
B codes GRADE_CONTRADICTS_FACTS, SKIPPED_SETTLE_TICKET.
needs_human_correctness A PASS. B PASS.
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.

### X02

Changed: codes, needs_human_correctness

A final WIN. B final WIN.
A codes WIN_LOSS_FLIP, SKIPPED_SETTLE_TICKET, PLACEHOLDER_ECHO, GRADED_WITHOUT_LOOKUP, INCOMPLETE_LEG_LIST, FOLLOWED_TICKET_CLAIM.
B codes WIN_LOSS_FLIP, SKIPPED_SETTLE_TICKET, GRADED_WITHOUT_LOOKUP, FOLLOWED_TICKET_CLAIM.
needs_human_correctness A FAIL. B PASS.
<!-- input:reason -->
A: PREMATURE_FINAL
B: The ticket is decided, but the grader did not settle it because it was marked as PREMATURE_FINAL.
<!-- /input:reason -->
rule_adherence A FAIL. B FAIL.
tool_call_accuracy A FAIL. B FAIL.
