# PR #17 — the PM's read of Codex's fixes and its own, and the instruction to land (TZ=America/New_York)

The text delivered Sun 1 Nov 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 17 --pass 1 (land)

The PM read 029dadc37fe7baff67d90c9566f459ddae44fc05 and accepts it, and re-ran two of its claims: 1 of the 12 tickets ending WIN against an expected LOSS has a verified key, and the false passes read on set 1 are 6 of 6, 0 of 0 and 0 of 0. Your findings 3, 4 and 10 were the PM's to fix. It pushed c3c72e861e8169b4ae60093762f5023382773932, which you did not write. ("Touch no report" in your brief meant the generated files under reports/; it did not mean ab_report.md, so leaving that file to the PM was a fair reading, and you may fix it if the check below finds something.)

Read c3c72e8 cold, and only that. Confirm that its diff against 029dadc touches only submissions/week-02/assignment-2/ab_report.md and one clause of decision 7 in docs/week-2-package.md; that thresholds.json and variants/compare-first.txt did not change, so no threshold's number and no word of the variant moved; that finding 3 is fixed (the report no longer says the judge cannot register an improvement, and it still keeps rule_adherence report-only); that finding 4 is fixed (the thresholds read as necessary and not sufficient, the report-only row has no condition, and the accepted regression has its reason); that "Why 5" holds at every count for A, as the commit says; and that the PR body's updated lines are true. The new reason sentence is the PM's draft and the owner approved the numbers, so judge it for accuracy and not for taste. Your audit of the rest stands: do not repeat it, and do not extend it.

Run no model and start no Ollama server. Re-check on GitHub that the head is still c3c72e861e8169b4ae60093762f5023382773932 and that verify is green there on both jobs. Then, if the gate holds and you push nothing, land under the original brief's rule: gh pr merge 17 --squash --match-head-commit c3c72e861e8169b4ae60093762f5023382773932 --subject "docs: specify the A/B and write its thresholds before any run" with a --body of exactly these lines:

Add the A/B's spec, the ten-trace diagnosis, the variant prompt, the thresholds and the in-sample statement, all merged before variant B runs, and leave the report's results and verdict empty. Rule 6 now says a public footballer's name already on main is a match fact. No code, label, verdict or generated report changes, and no model was run.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

After the merge, confirm with the command and what it printed: main's head is the merge commit; its tree equals the tree of c3c72e861e8169b4ae60093762f5023382773932; no tag exists on the remote; and verify is green on both jobs on the push to main. Update your existing comment with the landing and your read of c3c72e8, and say that it was updated. Leave the branch and the clone for the owner's word. Report the merge SHA, the tree check, the tag count and the verify run, then stop. If you find something in c3c72e8 that is wrong, fix it in one push under the original brief's fix policy, then stop, say the SHA, and do not land until the PM has read it. If it touches a threshold's number or the variant's text, do not fix it: stop and ask the owner in one word.
