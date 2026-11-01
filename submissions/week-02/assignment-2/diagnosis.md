# Assignment 2 diagnosis

Written by Claude, in the PM seat, at the owner's request on 1 Nov 2026, from the traces of `traces/aa-1` and the code checks in
`scorer/checks.py`. The choice of the change is the owner's; the reading below is the PM seat's. `traces/aa-1` is one of three repeat runs
of the v1 configuration that gave the same final answer on all 32 tickets, so it stands for how the grader behaves in that setup.

## The failure mode

`GRADE_CONTRADICTS_FACTS`: the grader commits a leg grade that the facts contradict. It fires on 15 of 32 tickets in `traces/aa-1`, level with
`WIN_LOSS_FLIP` for the most of any code, and the two overlap on 11. The course says to take the worst numbers, and of those two this one re-grades from
the facts, while `WIN_LOSS_FLIP` reads the expected result, and only 4 of the 32 expected results are `verified_by_beni`. It is also the failure that costs
money: 12 tickets end WIN where the expected result is LOSS. Its plain-code check matched the labels on 14 of 14 tickets on `traces/v1`, in sample.

## Ten traces, read together

On each, the tool calls returned the deciding fact, and `settle_ticket` was given W on a leg the facts lose.

| Case | Trace id | Leg, selection | The fact in hand | What the final answer's evidence says |
|---|---|---|---|---|
| A03 | `bd92895dbf14d5dfce0dcf233c950b1b` | 1, Austria, 3-way | 2-2 at 90 minutes | "the score or stat you used", the prompt's own example text |
| A06 | `4b8146a16cf1cfcd534d8f4958d63e2e` | 1, Republic of Ireland, 3-way | 1-1 at 90 minutes | the same example text |
| A09 | `01a6d354b9cdc8ab6d0aa60ca502f14b` | 1, Tie (Draw) | 3-1 at 90 minutes | the same example text |
| A11 | `4913e468dbcf93c754cfb47b5fe03a36` | 1, NYCFC, away, 3-way | 2-1 to the home side | "New York City FC won 2-1", the score read backwards |
| A12 | `5e60b2010fa85e07a369196fa714088f` | 1, Draw, 3-way | 0-3 at 90 minutes | "score_regulation_90: 0-3", the fact that loses the leg, beside a W |
| B02 | `31b2e2461ba2cb011f864d978dfd4bab` | 2, Lamine Yamal, anytime scorer | three goals, none of them his | none: the answer lists 1 leg of 4 |
| B09 | `cb6951d1354fe8ff78e8c1cab78da651` | 3, Tie/Manchester City, half time/full time | 0-1 at half time | none: the answer lists 1 leg of 3 |
| B12 | `0cdb160f5abdc00ef088aea45d16f7d5` | 1, Bukayo Saka, first scorer | first goal to a Leeds player at 55' | names another Arsenal player as the first scorer, beside a W |
| B13 | `71a28a3f0e5e2905935dfd73e33146e2` | 1, Columbus Crew, 90-minute moneyline | 1-1 at 90 minutes | calls it a draw and says Columbus lost, beside a W |
| C13 | `cf3e5164c93c094f2e72965fc78305c1` | 1, Bayern Munich, 3-way | 0-0 at 90 minutes | "score_regulation_90: 0-0" with result L, after `settle_ticket` was given W |

## Root cause

The grader fetches the deciding fact and then gives a result without ever setting that fact beside the selection. `settle_ticket` takes a bare list
of results, and the prompt's step 3 asks for a result with no comparison before it, so nothing in the loop makes the model say what the score
means for this selection; W is what it reaches for. The only place fact and grade meet is the final answer's evidence, written after settlement,
and there the grader echoes the prompt's example, reads a score backwards, or quotes a fact that contradicts the W beside it. So expect the next
failure on any leg whose selection did not come true while its fixture is plain to read: a draw on a team selection, an away team losing a score printed
home first, a draw pick on a decided match, or a player absent from the goals list. Grades go wrong in the other direction far less often: of the 15 tickets
on which the check fires, 13 commit W on a lost leg and 2 commit L on a won one. C13 is the one hopeful sign: once it wrote the 0-0 down, it graded the leg L,
the opposite of what it had just settled.

## What this does not cover

The other five tickets on which the check fires are a different shape. On B05 and X01, `get_match_facts` returned an error because the match is outside the
frozen set, and the grader graded anyway; B10's expected result is VOID, which is its own question; and C04 and C08 commit L on a leg the facts win. Five tickets
make no tool call at all (`GRADED_WITHOUT_LOOKUP`), and comparing facts cannot help a ticket that fetched none. The change is not expected to move those, and a
comparison asked for in a prompt can simply be ignored, since `settle_ticket` still accepts a bare list. That is what the A/B is for.
