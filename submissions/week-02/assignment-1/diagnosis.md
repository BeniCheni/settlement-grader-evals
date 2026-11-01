# Set 1 diagnosis

Written by Claude, in the PM seat, at the owner's request on 31 Oct 2026, from the committed verdicts, the final labels,
the readings and the judge report. The owner made every label and every ruling it describes; the sorting of the judge's
errors into causes below is the PM seat's. Judge model: llama3.1:8b (digest `46e0c10c…666e`), Ollama 0.34.0. The labels
are not blind to the judge (see the report's hand-written section), so every final figure here is optimistic.

## The worst judge: rule_adherence

| Labels | Agreement | Kappa | False passes | False fails |
|---|---|---|---|---|
| First pass | 57.5% | 0.00 | 0 | 17 |
| Final | 65.0% | 0.00 | 0 | 14 |

It answered FAIL on all 40 rows. A judge that never varies its answer has a kappa of 0 whatever the labels say, and its
agreement is just the share of rows the owner failed (26 of 40 after adjudication). It cannot tell a right grade from a
wrong one, so its FAILs carry no information: the 26 it got "right" it would have failed anyway.

**Dominant failure mode: false fail, 14 of 14 errors.** Its reasons show six ways of failing a correctly graded leg:

| Cause | Rows | Count |
|---|---|---|
| The reason states a correct fact or rule and names no fault | aa-1 A05, v1 C12, v1 A13, aa-1 A13, aa-1 B01 | 5 |
| The Draw-selection sentence applied to a team selection that won | v1 A08, aa-1 A08, v1 C06 | 3 |
| "Check the exact number, not only who won" read as a demand for the exact score on a moneyline | v1 A01, aa-1 A01 | 2 |
| A half-goal line treated as a whole line (4 goals called a push or a loss on Over 3.5) | v1 B04, aa-1 B04 | 2 |
| The score read backwards (USA 3-0 at home called a Mexico win) | v1 A05 | 1 |
| The rubric's "graded no leg is PASS" clause ignored | v1 A02 | 1 |

**Its loophole.** The rubric asks the reason to give "the deciding leg and fact in under 20 words", and the judge meets
that format without re-grading anything: it names a leg and quotes a fact or a rule sentence, then answers FAIL. Nothing
in the answer format makes it state the grader's grade and its own re-grade side by side, which is the comparison the
rubric's question depends on. The only worked example in the rubric is a FAIL (a 2-2 draw graded W on a team selection),
and the judge's commonest specific error echoes that example's Draw sentence. Five of its fourteen wrong reasons are
correct statements followed by FAIL, which is the loophole in its plainest form.

What a step-9 tightening could change, for the owner to choose one: an answer format that requires "grader: X; re-graded:
Y" before the verdict, or a PASS boundary example alongside the FAIL one. Either is a set-2 rubric change and is
measured on set 2, never on these labels.

## The other two judges

**tool_call_accuracy** meets the bar on the final labels (92.5%, kappa 0.85; first pass 65.0%, kappa 0.28), but it is
often right for the wrong reason. Its three remaining errors are all false fails in which it reported an UNKNOWN_TOPIC
that no tool call returned (aa-1 B04, v1 B04, v1 C09), echoing its own boundary example; it gave the same invention on
v1 B01, where its FAIL verdict happened to be right. On the seven rows the owner changed to PASS it gave one stock
sentence, word for word ("called the right tools with the right arguments"), that names no argument or result. On v1 C06 and v1 C13 its verdict was right and its reason cited the wrong
call. A judge that reaches the right verdict this way has not shown that it read the calls, so the 0.85 should not be
read as trust in its reasons.

**needs_human_correctness** stays under the bar (80.0%, kappa 0.32; first pass 77.5%, kappa 0.18). Its errors lean the
costlier way: 6 false passes against 2 false fails, so it more often lets a wrong settle-or-escalate decision through
than it flags a right one.

## Every changed label and why

Seventeen labels changed on adjudication; 16 moved to the judge's verdict. The full reasons, in the owner's words, are
in `labels/set1-final.jsonl`. In short:

| Rubric | Row | Change | Why |
|---|---|---|---|
| needs_human_correctness | v1 A02 | PASS → FAIL | find_match returned no candidates, so the rubric requires NEEDS_HUMAN; the grader settled VOID with no fact showing a void. |
| needs_human_correctness | v1 B01 | PASS → FAIL | The facts decide the first-goalscorer leg (Svensson scored first, no own goal, nothing shows Guirassy did not play), so NEEDS_HUMAN escalated a decided ticket. The one change away from the judge. |
| needs_human_correctness | v1 B02 | FAIL → PASS | Final 3-0 with no Yamal goal decides the leg; settling was the right kind of answer, and the wrong WIN belongs to rule_adherence. |
| rule_adherence | v1 B01 | PASS → FAIL | Same facts as above: the leg is L, and NEEDS_HUMAN is a wrong grade. |
| rule_adherence | v1 C09 | PASS → FAIL | Leg 4 is a team selection on a 2-2 draw, so L; the grader gave P, and a right ticket result does not rescue it. |
| rule_adherence | v1 C13 | PASS → FAIL | settle_ticket was sent W, L, L against the final answer's L on leg 1, and legs 2 and 3 are W on 0-0. |
| tool_call_accuracy | v1 A03, A06, A09, A11, A12, B12; aa-1 A11 | FAIL → PASS | The first-pass label judged the grade, not the calls. Every call was right and settle_ticket received the grades the answer gave; the rubric passes a wrong grade sent faithfully. The wrong grades stay failed under rule_adherence. |
| tool_call_accuracy | v1 B01 | PASS → FAIL | settle_ticket returned a null net and the final answer wrote 0.0. |
| tool_call_accuracy | v1 C06 | PASS → FAIL | settle_ticket returned PRICE_REQUIRED and the answer still wrote net 15.0 and WIN, ignoring the error. |
| tool_call_accuracy | v1 C13 | PASS → FAIL | settle_ticket's leg results differ from the final answer's grades. |
| tool_call_accuracy | v1 X02 | PASS → FAIL | No tool calls at all, yet a final WIN with a net that never came from settle_ticket. |

The owner's standing readings from these rulings: where no lineup is given, the facts decide a goalscorer leg;
tool_call_accuracy judges the calls, not the grades; a missing ticket price is not on any rubric's FAIL list, and a
stricter price rule is a set-2 rubric question, not a relabel.
