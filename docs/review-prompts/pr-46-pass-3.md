# PR #46 — Pass 3: the merge-logistics prompt for Cursor (TZ=America/New_York)

The text delivered Thu 5 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

PR #46 — Pass 3, the merge (full cycle), in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 Medium, Pass 3 of the full cycle in AGENTS.md. You built this PR's first two commits, so you review nothing here: Claude Code gave Pass 1, Codex gave Pass 2, and the PM seat re-ran the head in Pass 2.5 and found the gate in AGENTS.md ("How work moves", item 4) satisfied. Your job is merge logistics only. The owner has said to merge. Change no file, push no commit, and create no tag or release. AGENTS.md outranks this prompt on process. Work in a fresh clone from GitHub, not a worktree of any other checkout; confirm that private/ and data/espn_cache/ are absent, and stop if either is present. Write no home-directory path in anything you post.

THE PIN. Merge only head 490f05dfe1dd120a80c0e460fb8cfc1e450fa82f on cursor/jev, whose tree is ed2df61414f3df68edc771ecba43bf7580e3ef07, onto main at 5becaa37d1d334cdac0ee3129d9830c46cec6f4d. First take the head, the base, the state and the checks from GitHub. Stop and report, without merging, if the head has moved, main has moved, the PR is not open, or verify run 42152443449 is not green on both of its jobs at that exact head.

THE MERGE. Mark the draft ready with: gh pr ready 46 --repo BeniCheni/settlement-grader-evals
Then write the body below, byte for byte, to a file outside the clone, and squash-merge pinned to the head with: gh pr merge 46 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit 490f05dfe1dd120a80c0e460fb8cfc1e450fa82f --subject "jev: add the adapter, the decisions and the report" --body-file <that file>

THE BODY, from the line after "BEGIN" to the line before "END":
BEGIN
Add step 9, Jev, for Assignment 3. scorer/jev.py sends each row's free text to TypeSafe's jev-1.14.0 with the owner's key, records the two probabilities as returned, and routes each row to block, allow or review. decide refuses a bad key, a broken or redirected reply and a bad --out before it writes anything, and no path prints the key. report prints catch, over-block and review, whether every visible attack blocked, G2 side by side, the band error rates, three reliability bins on the winning probability with their diagram, and a cost sweep bounded by the review bar. It names the adapter that wrote the decisions and refuses a decisions file that decide could not have written.

Move Jev's catch bar to 17 of 20 (ruling 60). Record rulings 64 and 65 and amend the step 9 spec. No decision or report is committed: the owner's run comes next. 461 tests, OK, 1 skipped, on Python 3.9 and 3.14.

Co-authored-by: Cursor <cursoragent@cursor.com>
Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>
END

AFTER. Fetch main and confirm that its new tip's tree equals ed2df61414f3df68edc771ecba43bf7580e3ef07, that its only parent is 5becaa37d1d334cdac0ee3129d9830c46cec6f4d, and that its message is the subject and body above. Wait for verify on main and give its run id and both jobs' results. Confirm the remote holds zero tags. Do not delete cursor/jev or any clone: they wait for the owner's word. Report back in five lines: the merge SHA, the tree check, the parent check, the verify run on main, and the tag count.
