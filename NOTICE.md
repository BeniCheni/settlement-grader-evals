# Notices

## Course material

`viewer/` is the trace viewer from Manjeet Singh's
[AI-Agent-Evals-Course](https://github.com/coachmanjeet/AI-Agent-Evals-Course) (MIT), adapted here
to annotate settlement-grader traces. Its copyright and permission notice is in
[`viewer/LICENSE`](viewer/LICENSE). This repo was built as coursework for ByteByteGo's
*AI Evals in Practice*, taught by Manjeet Singh; the evaluation method (failure taxonomy, binary
judges, human-label agreement, red teaming) is his course's, applied here to a different agent.

## Match data

Match facts (team names, scores, half-time lines, a few team stats, goal and card events) come from
ESPN's public soccer API. ESPN's responses are not republished here: `data/espn_frozen.json` is a
pruned copy holding only the fields the grader reads, for the matches this eval can query, so a
re-run sees the same facts as the original. This project is not affiliated with or endorsed by ESPN.

## Ticket data

`data/gold.json` holds the author's own real bet tickets (books, prices, results, and stakes scaled by a constant; see the README), logged
and settled between August and October 2026. `data/adversarial.json` holds synthetic variants of two
of them. No bet IDs, account details or balances are included. Nothing here is betting advice, and
the grader settles tickets that have already been decided; it does not predict anything.
