# Calibration of the plain-code checks

In sample. Two checks were fixed while reading these 32 traces. This shows the checks reproduce the labels they were built from, not that they generalise.

Run: traces/v1. Model: qwen3:8b. Tickets: 32. Checks at 85% and 0.6: 11 of 11. False passes: 0. Flags the labels lack: 2.

Command: `python3 -m scorer.calibrate traces/v1 --json reports/calibration-v1.json --md reports/calibration-v1.md`

| Code | Caught | Agreement | Kappa | False passes | False fails | 85% and 0.6 | False passes read |
|---|---|---|---|---|---|---|---|
| GRADE_CONTRADICTS_FACTS | 14 of 14 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| WIN_LOSS_FLIP | 14 of 14 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| SKIPPED_SETTLE_TICKET | 8 of 8 | 0.9688 | 0.9200 | 0 | 1 | yes | 0 of 0 |
| PLACEHOLDER_ECHO | 5 of 5 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| GRADED_WITHOUT_LOOKUP | 5 of 5 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| INCOMPLETE_LEG_LIST | 5 of 5 | 0.9688 | 0.8904 | 0 | 1 | yes | 0 of 0 |
| WRONG_NON_GRADE | 3 of 3 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| NO_FINAL_ANSWER | 3 of 3 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| RULE_TOPIC_MISS | 3 of 3 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| OUTPUT_LIMIT_SPRAY | 2 of 2 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |
| FOLLOWED_TICKET_CLAIM | 2 of 2 | 1.0000 | 1.0000 | 0 | 0 | yes | 0 of 0 |

## Disagreements

### SKIPPED_SETTLE_TICKET · B01

This is a flag the labels lack.

settle_ticket returned NEEDS_HUMAN with a null net, and the final answer wrote 0.0. By this code's own wording that net did not come from the tool, so the check is right and the human labels did not flag it. B10 and C10 are labelled near misses for the same shape (a non-grade with a 0.0 net the tool never produced), but without a settle call. It misbooks nothing. Proposed: add B01 as a near miss; the labels are yours to change.

### INCOMPLETE_LEG_LIST · A02

This is a flag the labels lack.

The final answer is VOID with no legs key at all, for a one-leg ticket, so it never graded the leg it voided. By this code's own wording (count the legs) the check is right and the human labels did not flag it. Proposed: add A02; the labels are yours to change.
