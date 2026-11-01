# PR #10 — Pass 3: the merge-logistics prompt for Cursor (TZ=America/New_York)

The text delivered Fri 30 Oct 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

PR #10 — Pass 3 (Cursor): merge logistics for the run record and the compare command, on the owner's word, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 Medium, Pass 3 of the full cycle in AGENTS.md. Your seat is merge logistics only: you review nothing and change no file in the repository. The owner has given his word to merge PR #10; you cannot see where he gave it, so treat it as the instruction for this pass and do not confirm it second-hand. This PR is not a release: create no tag, no release, no CHANGELOG.md section and no version string. AGENTS.md outranks this prompt on process. Write no home-directory path in anything you post.

THE STATE THE PM VERIFIED, Fri 30 Oct 2026, as a claim to re-check, not a source. PR #10 is a draft, open, mergeable, head 17e185ac6eb9c6253dc4a8e1325c121eaff7bce2 on cursor/floor-compare, base main at 726789b4c88f8c781d2dbea0746cf98f4ef7c4d0. verify run 41083233317 was green at that head on Python 3.9 and 3.14. The PM's Pass 2.5 re-run there: 134 tests OK on 3.9.6 and 3.14.7, the three committed compare outputs regenerate byte-identical on both, and no committed run under traces/ changed.

THE STEPS, in order, stopping at the first that fails. (1) gh pr view 10 --repo BeniCheni/settlement-grader-evals --json headRefOid,isDraft,mergeable,baseRefName,statusCheckRollup: the head must be exactly 17e185ac6eb9c6253dc4a8e1325c121eaff7bce2 and both verify jobs green there. If the head has moved or a check is not green, stop and say so; do not merge. (2) gh pr ready 10. (3) Write the squash message to a file outside the repository, exactly these lines, with the one blank line between the body and the trailers:

Record a run's Ollama version and model digest in run_meta.json, read before the first ticket, and add python3 -m scorer.compare, which reports two runs' tickets, final answers, code counts, setup and provenance, and refuses a run outside the working directory or one with no records. The committed runs are unchanged.

Co-authored-by: Cursor <cursoragent@cursor.com>
Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

Then squash-merge pinned to that head: gh pr merge 10 --squash --match-head-commit 17e185ac6eb9c6253dc4a8e1325c121eaff7bce2 --subject "scorer: record a run's setup and compare two runs" --body-file <that file>. (4) Post one short PR comment: what you merged, the merge commit SHA, and that it was pinned to 17e185a. (5) Confirm, with the command and what it printed: the merge commit's tree equals the tree of 17e185ac6eb9c6253dc4a8e1325c121eaff7bce2 (gh api repos/BeniCheni/settlement-grader-evals/commits/<sha> --jq .commit.tree.sha for each); main's head is the merge commit; git log -1 --format='%(trailers:key=Co-authored-by)' on a fresh fetch of main prints all three trailers; git ls-remote --tags origin prints nothing; and verify on the push to main is green on both jobs. (6) Leave the branch cursor/floor-compare and every clone in place for the owner's word. Report the merge SHA, the tree check, the trailers, the tag count and the verify run, then stop.
