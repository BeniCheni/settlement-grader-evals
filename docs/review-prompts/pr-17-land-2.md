# PR #17 — the PM's read of Codex's last fix, and the instruction to land (TZ=America/New_York)

The text delivered Sun 1 Nov 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 17 --pass 1 (land)

The PM read bc867e8ff8a6640fd4ed476b00aaf1a7de58d39d and accepts it: the rubric does fail a settlement made when a needed fact is missing, so the rationale needed both directions. The diff against c3c72e8 is that one line of ab_report.md; thresholds.json and variants/compare-first.txt did not change. You wrote this commit, and the PM has now read it, so it needs no further read from you. Your audit stands. Do not repeat or extend it, and push nothing more.

Run no model and start no Ollama server. Re-check on GitHub that the head is still bc867e8ff8a6640fd4ed476b00aaf1a7de58d39d and that verify is green there on both jobs. If either fails, stop and say so. Otherwise run gh pr merge 17 --squash --match-head-commit bc867e8ff8a6640fd4ed476b00aaf1a7de58d39d --subject "docs: specify the A/B and write its thresholds before any run" with a --body of exactly these lines:

Add the A/B's spec, the ten-trace diagnosis, the variant prompt, the thresholds and the in-sample statement, all merged before variant B runs, and leave the report's results and verdict empty. Rule 6 now says a public footballer's name already on main is a match fact. No code, label, verdict or generated report changes, and no model was run.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

After the merge, confirm with the command and what it printed: main's head is the merge commit; its tree equals the tree of bc867e8ff8a6640fd4ed476b00aaf1a7de58d39d; no tag exists on the remote; and verify is green on both jobs on the push to main. Add the landing to your existing comment and say it was updated. Leave the branch and the clone for the owner's word. Report the merge SHA, the tree check, the tag count and the verify run, then stop.
