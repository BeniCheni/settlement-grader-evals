# PR #21 — Pass 3: the merge-logistics prompt for Cursor (TZ=America/New_York)

The text delivered Mon 2 Nov 2026, as archived by the PM seat (Claude) on Mon 2 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

PR #21 — Pass 3 (Cursor): merge logistics for the A/B page's six small fixes, on the owner's word, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 Medium, Pass 3 in AGENTS.md. Your seat is merge logistics only: you review nothing and change no file. The owner has given the word to merge PR #21; you cannot see where it was given, so treat it as the instruction for this pass and do not confirm it second-hand. This PR is not a release: create no tag, no release, no CHANGELOG.md section and no version string. AGENTS.md outranks this prompt on process. Work in a fresh clone or none at all: these steps need only gh. Run no model. Write no home-directory path in anything you post.

THE STATE THE PM VERIFIED, Mon 2 Nov 2026 at about 14:06 EST, as a claim to re-check, not a source. PR #21 is a draft, open, mergeable, head 7ec66a9a6c7ffc4a39671f95215b7f2edbe8c746 on cursor/ab-page-fixes, base main at 2159d94f45eaeb22685950e8189c58f2b9d5009e, tree aa12d3ad21def69df3d0813301ebd7119e11d4fc. verify run 41502847906 was green at that head on Python 3.9 and 3.14. The PM's completed review is issuecomment-6585933415: 191 tests OK on 3.9.6 and 3.14.7, compileall clean, reports rebuilt byte for byte on both, and no figure moved.

THE STEPS, in order, stopping at the first that fails. (1) gh pr view 21 --repo BeniCheni/settlement-grader-evals --json headRefOid,isDraft,mergeable,baseRefName,statusCheckRollup: the head must be exactly 7ec66a9a6c7ffc4a39671f95215b7f2edbe8c746 and both verify jobs green there. If the head has moved or a check is not green, stop and say so; do not merge. (2) gh pr ready 21 --repo BeniCheni/settlement-grader-evals. (3) Squash-merge pinned to that head: gh pr merge 21 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit 7ec66a9a6c7ffc4a39671f95215b7f2edbe8c746 --subject "scorer: the A/B page's six small fixes" --body with exactly these lines:

Keep each paired interval on one line from 761 px, print a count of one as ticket, keep a metric name's wrap with a whole accessible name, refuse a wrong type or a non-finite net inside a case's expected, and test the log_grade check and the name's escaping. No figure moves: reports/ab.json is unchanged, and the page and the Markdown change only in wording and style.

Co-authored-by: Cursor <cursoragent@cursor.com>
Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

(4) Post one short PR comment: what you merged, the merge commit SHA, and that it was pinned to 7ec66a9. (5) Confirm, with the command and what it printed: the merge commit's tree equals aa12d3ad21def69df3d0813301ebd7119e11d4fc (gh api repos/BeniCheni/settlement-grader-evals/commits/<sha> --jq .commit.tree.sha); main's head is the merge commit; git ls-remote --tags https://github.com/BeniCheni/settlement-grader-evals.git prints nothing; and verify on the push to main is green on both jobs. (6) Leave the branch cursor/ab-page-fixes and every clone in place for the owner's word. Report the merge SHA, the tree check, the tag count and the verify run, then stop.
