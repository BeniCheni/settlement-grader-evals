# PR #32 — Pass 3: the merge-logistics prompt for Cursor (TZ=America/New_York)

The text delivered Tue 3 Nov 2026, as archived by the PM seat (Claude) on Wed 4 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

PR #32 — Pass 3 (Cursor): merge logistics for the Week 3 seams, on the owner's word, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 Medium, Pass 3 of the full cycle in AGENTS.md. Your seat is merge logistics only: you review nothing and change no file. The owner has given the word to merge PR #32; you cannot see where it was given, so treat it as the instruction for this pass and do not confirm it second-hand. This PR is not a release: create no tag, no release, no CHANGELOG.md section and no version string. AGENTS.md outranks this prompt on process. Work in a fresh clone or none at all: these steps need only gh. Never open another checkout of this repo. Run no model. Write no home-directory path in anything you post.

THE STATE THE PM VERIFIED, Tue 3 Nov 2026 at about 22:59 EST, as a claim to re-check, not a source. PR #32 is a draft, open, mergeable, head baf7df3687ba934b64e07f03d9b6ecd0128de6dc on cursor/guardrail-seams, base main at f57f380dc787904adb0707b9cfb2b4ed247925f4. Seventeen commits. verify run 41767764787 was green at that head on Python 3.9 and 3.14. The branch forked before main's last commit, which changed only docs/, so the squash result is not the head's tree: the PM computed it with git merge-tree --write-tree as 6d5da8404f3d433f809763d78f323e600cadbfad. The PM's Pass 2.5 re-run of that merge result: 248 tests OK on Python 3.9.6 and 3.14.7, compileall clean.

THE STEPS, in order, stopping at the first that fails. (1) gh pr view 32 --repo BeniCheni/settlement-grader-evals --json headRefOid,isDraft,mergeable,baseRefName,statusCheckRollup, and git ls-remote https://github.com/BeniCheni/settlement-grader-evals.git refs/heads/main: the head must be exactly baf7df3687ba934b64e07f03d9b6ecd0128de6dc, main must be exactly f57f380dc787904adb0707b9cfb2b4ed247925f4, and both verify jobs green at that head. If either has moved or a check is not green, stop and say so; do not merge. (2) gh pr ready 32 --repo BeniCheni/settlement-grader-evals. (3) Squash-merge pinned to that head: gh pr merge 32 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit baf7df3687ba934b64e07f03d9b6ecd0128de6dc --subject "grader: add the Week 3 seams and the Promptfoo exec target" --body with exactly these lines:

Add the seams later Week 3 steps need, proved on fixtures: a poison overlay that marks a changed tool result on the trace and in render_case, follow-up turns under the grader's shared budgets, grade_ticket_guarded with held finals and withheld answers, run_eval.py --drop-field with refusals before anything is written, and the Promptfoo exec target with both configs at timeoutMs 720000. With no new argument, field or flag, the requests the grader sends are unchanged. No model was run and no real run is committed. The Python stays on the standard library; promptfoo@0.124.1 is a pinned Node tool outside CI, on the owner's ruling 1.

Co-authored-by: Cursor <cursoragent@cursor.com>
Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

(4) Post one short PR comment: what you merged, the merge commit SHA, and that it was pinned to baf7df3. (5) Confirm, with the command and what it printed: the merge commit's tree equals 6d5da8404f3d433f809763d78f323e600cadbfad (gh api repos/BeniCheni/settlement-grader-evals/commits/<sha> --jq .commit.tree.sha); main's head is the merge commit; git ls-remote --tags https://github.com/BeniCheni/settlement-grader-evals.git prints nothing; and verify on the push to main is green on both jobs. (6) Leave the branch cursor/guardrail-seams and every clone in place for the owner's word. Report the merge SHA, the tree check, the tag count and the verify run, then stop.
