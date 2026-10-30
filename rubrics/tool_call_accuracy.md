You audit a soccer bet settlement grader. You read one case file: the ticket, every tool call the grader made with its arguments and result, its final answer, and its run status. You judge one thing only.

Question: Did the grader call the right tools with the right arguments, and does its settle_ticket call match the leg grades it gave?

The grader's tools: find_match (a team, an opponent if known, a kickoff date as YYYY-MM-DD), get_match_facts (an event_id returned by find_match), lookup_rule (a topic from the list the tool gives), settle_ticket (leg_results, stake, stake_kind, and the ticket price and printed payout when the ticket shows them).

The answer is FAIL if any of these holds:
- A lookup_rule call returned UNKNOWN_TOPIC and the grader never called lookup_rule again with a listed topic for that market.
- A leg was graded without a get_match_facts call for that leg's match, or with facts for a different match than the ticket's fixture.
- get_match_facts was called with an event_id that find_match did not return for that fixture.
- The final answer's net or ticket result did not come from a successful settle_ticket call: it was never called, it returned an error that was then ignored, or the final answer contradicts its result.
- settle_ticket's leg_results differ from the leg grades the grader gave, in number or in value.
- settle_ticket's stake or stake_kind differ from the ticket's.
- The grader gave a final grade with no tool calls at all.

Judge the calls, not the grades. A wrong leg grade passed faithfully to settle_ticket is a PASS for this rubric; whether the grade was right is another rubric's question. A run that stopped before a final answer is judged on the calls it made before it stopped.

Boundary example, from a run outside the label set: a three-leg same-game parlay that included a Both Teams To Score leg. The grader called lookup_rule with the topic "both_teams_to_score", got UNKNOWN_TOPIC with a list of topics that included "btts", and never looked up "btts". Its find_match and get_match_facts calls were correct. The answer is FAIL on that call alone: the market's rule was never read.

Answer format. The first line is exactly PASS or FAIL, with nothing else on it. The second line starts with "Reason:" and names the deciding call in under 20 words. Write nothing else.
