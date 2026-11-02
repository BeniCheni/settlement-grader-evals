# PR #18 — Pass 3: the merge-logistics prompt for Cursor (TZ=America/New_York)

The text delivered Sun 1 Nov 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

PR #18 — Pass 3 (Cursor): merge logistics for the A/B harness and page, on the owner's word, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 Medium, Pass 3 of the full cycle in AGENTS.md. Your seat is merge logistics only: you review nothing and change no file. The owner has given the word to merge PR #18; you cannot see where it was given, so treat it as the instruction for this pass and do not confirm it second-hand. This PR is not a release: create no tag, no release, no CHANGELOG.md section and no version string. AGENTS.md outranks this prompt on process. Work in a fresh clone or none at all: these steps need only gh. Run no model. Write no home-directory path in anything you post.

THE STATE THE PM VERIFIED, Sun 1 Nov 2026, as a claim to re-check, not a source. PR #18 is a draft, open, mergeable, head 76e990d17b593dfcc874cbf40a18b8bc66882606 on cursor/ab-report, base main at b946b073421a4b9925139359a7d11f010ba7729b, tree 01253ab3931cc6daef4f9df615fe3a63026955b0. verify run 41371502233 was green at that head on Python 3.9 and 3.14. The PM's Pass 2.5 re-run there: 187 tests OK on 3.9.6 and 3.14.7, compileall clean, both existing reports regenerated with git status --porcelain reports/ empty on both, and labels, judgments, rubrics, data, traces, submissions, variants and the Markdown and JSON of both existing reports identical to main.

THE STEPS, in order, stopping at the first that fails. (1) gh pr view 18 --repo BeniCheni/settlement-grader-evals --json headRefOid,isDraft,mergeable,baseRefName,statusCheckRollup: the head must be exactly 76e990d17b593dfcc874cbf40a18b8bc66882606 and both verify jobs green there. If the head has moved or a check is not green, stop and say so; do not merge. (2) gh pr ready 18 --repo BeniCheni/settlement-grader-evals. (3) Squash-merge pinned to that head: gh pr merge 18 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit 76e990d17b593dfcc874cbf40a18b8bc66882606 --subject "scorer: run a prompt variant and report the A/B" --body with exactly these lines:

Add run_eval.py --prompt-file, the paired interval (Newcombe 1998 method 10), and scorer.judge run-ab and ab: one row per metric with nothing blended, each threshold with its limit and what was observed, every ticket with a changed mark that names and never judges, and the hand-written statement on the cover and beside the Set 1 numbers. Proved on fixtures and a rehearsal with fake replies: no model was run and no real run is committed. The thresholds came first; variant B's first run comes after this merge.

Co-authored-by: Cursor <cursoragent@cursor.com>
Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

(4) Post one short PR comment: what you merged, the merge commit SHA, and that it was pinned to 76e990d. (5) Confirm, with the command and what it printed: the merge commit's tree equals the tree of 76e990d17b593dfcc874cbf40a18b8bc66882606 (gh api repos/BeniCheni/settlement-grader-evals/commits/<sha> --jq .commit.tree.sha for each); main's head is the merge commit; git ls-remote --tags https://github.com/BeniCheni/settlement-grader-evals.git prints nothing; and verify on the push to main is green on both jobs. (6) Leave the branch cursor/ab-report and every clone in place for the owner's word. Report the merge SHA, the tree check, the tag count and the verify run, then stop.
