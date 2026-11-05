# Assignment 2: the human-in-the-loop flow

**This is a design.** The approver workflow is not built. What exists today is the guardrail wrapper's held final and trace records, `NEEDS_HUMAN`, `settle_ticket`'s flags on a repriced push or void, and the incomplete reason codes. The verdict is no-ship (ruling 53), and this flow is what a held ticket would need if that changes.

## When a ticket goes to a human

| Trigger | The approver sees | Rule |
|---|---|---|
| An input guardrail fired | The ticket, the field and span, and which guardrail. The reason never goes back to the submitter | Nothing settles until it is read |
| G4 fired | Each leg's facts and rule first, then the grader's grade and the check's evidence | The human grades the leg |
| Any WIN with a net over a limit the owner sets, in the repo's scaled dollars | As above, plus the printed payout | Approve, edit or deny, never automatic |
| Prop legs no code check covers, or a push or void mix | As above | The human grades it |
| Jev's middle band (Assignment 3) | The input, the probability per choice, and the planned action | The owner sets the time limit |

## What the approver sees first

Facts before the grader's explanation, on purpose. A confident note is how a human becomes the last step of an attack, which is OWASP's "human-agent trust exploitation". In `traces/rt-unguarded`, `H5`'s notes say the ticket was regraded as a WIN while its evidence still reads 0-0. An approver who reads the notes first is reading the attack.

In this design, only the approver would see the grader's original answer. `grade_ticket_guarded` replaces the returned answer with a held final that names no guardrail, and it keeps the grader's own final under `output.final_withheld` in the trace. An approver interface and access controls are not built.

## What the load would be

On this run the stack held 11 of 20 legitimate tickets (`reports/guardrails.md`, review load), and every attack, so a queue built on this stack is most of the traffic. No bar is set on it, because that is one session on 20 rows. Of those 11, the owner read 8 as right to hold and 3 as over-blocks, on keys mostly not verified (ruling 52). Q did not run the stack, so it does not measure a change in that queue. `M5`'s G4 block disappears under Q, while G4 also holds legitimate tickets with no attack or `slip_text` at all.

## What this does not settle

- Who the approver is, and how fast they must answer.
- Whether an approver's grade feeds back into the answer keys. No key is verified unless `verified_by_beni` says so.
- What the limit in the third trigger is. It is in scaled dollars, and it is the owner's.
