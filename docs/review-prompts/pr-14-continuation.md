# PR #14 — the owner's answer on the per-rubric file, and the PM's fix to review (TZ=America/New_York)

The text delivered Sat 31 Oct 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 14 --pass 1 (continuation)

The owner's answer to your question, named as his and made Sat 31 Oct 2026: Yes, with a per-rubric file. The PM read your 6bd4dcc and accepts all three of its fixes (findings 3 to 5). The PM then pushed f89ed042325d0ae36d26c0443b3b5d5d95a48f01, which resolves your findings 1 and 2 on his ruling: report gains --rubric-provenance FILE, given with --html or not at all, a JSON object of one hand-written sentence per rubric that the page shows verbatim beside that rubric's figures; the computed pointer sentence is gone, so no computed text says "held out"; export-course writes comparison.html only when given the file, so its three-file test needs no change and only two existing tests may gain; and the ban now names "held-out" and "generalize" too, in any case, as your appendix note asked. The commit also adds labels/set1-rubric-provenance.json, set 1's three sentences, written by Claude at the owner's request.

Review f89ed04 cold, in the same brief's terms, as a PM fix you did not write. In particular: (a) the per-rubric file contract as a builder would read it (keys, values, every refusal, the together-or-not-at-all rule, relative_path on its path, the colophon naming it, the Markdown and JSON not reading it), and whether any line elsewhere in the spec, the plan or docs/judge-spec.md still assumes the old pointer sentence or the four-file export; (b) every fact in labels/set1-rubric-provenance.json against docs/week-2-package.md decision 6, labels/set1-provenance.txt and git (the shared-bet rows for each rubric, the adjudication after the verdicts, the first-pass figures blind to the judge but in sample), and whether each sentence states in sample or held out and what the figures do and do not show; (c) whether the file is canonical JSON as labels/set1-readings.json is; (d) the privacy sweep over the whole diff against main, counts only, now including the new file.

The skill's three-mutation requirement does not apply to this docs-only PR: there is no code in it to mutate, and the page's mutations are acceptance item 9 of the spec, for the build PR. Say so in one line instead of running any. For the bet-ID sweep, report numbers of 8 or more digits and any token labelled as a bet, wager or ticket id, counts only; that is the pattern the earlier PRs here used.

Then land under the brief's rule if the gate holds and you push nothing: the PM has read your fix, verify must be green at f89ed04 (re-check on GitHub), and nothing may remain contested. If you push a fix, push, stop, say the SHA, and do not land until the PM has read it.
