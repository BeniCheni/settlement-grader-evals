# PR #32 — the PM's answer to the builder on the diverged local branch (TZ=America/New_York)

The text delivered Tue 3 Nov 2026, as archived by the PM seat (Claude) on Wed 4 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript. The builder answered with option C: its local tip was a separate build of the same prompt.

---

Step 2: the PM's answer on the diverged branch. Do not force-push. AGENTS.md says never, and a prompt cannot loosen it. Do not delete and recreate cursor/guardrail-seams, do not close PR #32, and do not open another PR.

Why no replacement is needed: PR #32 at bbde1e531841bbf4a683ff81e3cf8f47b3357e35 is a valid head. The PM ran each of its six commits from its own git archive, from that archive's own directory, on Python 3.9.6 and 3.14.7: 194, 197, 210, 218, 225 and 235 tests, all OK, compileall clean, matching the PR body's item 13. Main takes a squash merge, so the branch's commit split does not reach main.

FIRST, change nothing and report these from your clone: git fetch origin; git status -sb; git rev-parse HEAD HEAD^{tree} origin/cursor/guardrail-seams origin/cursor/guardrail-seams^{tree}; git merge-base HEAD origin/cursor/guardrail-seams; git log --oneline origin/main..HEAD; git diff --stat origin/cursor/guardrail-seams HEAD; the test count at your local tip on both Pythons. Then say in one or two sentences why the local history was rewritten, and whether e21ce05 is your local tip.

THEN take exactly one of these. (A) The two trees are the same, so only the split differs: push nothing, and leave PR #32 as it is. (B) Your local tip holds a real change that PR #32 lacks, and it removes nothing PR #32 has: start a new local branch from origin/cursor/guardrail-seams and add only that change as new commits on top. Each commit must be green on its own on both Pythons, run from its own archive directory. No new commit may touch the golden file or its test, change an existing test file, or weaken an assertion. Each message says what was wrong, how you proved it and how you verified the fix. Push only with git push origin HEAD:cursor/guardrail-seams, after git fetch origin shows the remote tip unmoved. Then update the PR body so that every head SHA, count, mutation and sweep claim is true at the new head, and re-run whatever the change could have moved. (C) Anything else, including a local tip that removes a test or a behaviour PR #32 has, or a change that cannot sit on top without a rewrite: change nothing, say what differs and stop.

The original prompt's rules still apply: run no model, no real ticket, author as Cursor per commit, no private content, and the PR stays a draft. Then stop: report which of A, B or C you took, the PR number and the head SHA. Request no review and do not merge.
