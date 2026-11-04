# PR #35 — the PM's read of the added checks: land (TZ=America/New_York)

The text delivered Wed 4 Nov 2026, as archived by the PM seat (Claude) on Wed 4 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comments it led to are on the PR.

---

PR #35 — the PM's read of your added checks: land.

The PM read 58df13ed81b2b4f40e8a18cb708d19bdec46c5b9. It changes only tests/test_attacks_data.py and no frozen file: git diff f774107 on data/, both configs and traces/ is empty. The PM re-ran that head from its own archive: 279 tests OK and compileall clean on Python 3.9.6 and 3.14.7. The PM then re-applied its mutations in throwaway copies, 29 in all, and all 29 are killed, including the six that survived and both README reversions. This is the read ruling 37 asks for, so the test may land. Your verdict stands: no high finding is open.

THE PM'S STATEMENTS, which your seat cannot check. Report each as the PM's. (1) The real run went through the spec's sandbox-exec profile, with the local-request and errno checks passing just before it, as the PM's resource log outside the repo records. (2) The memory and swap figures in the plan's step 4 section come from that same log. (3) docs/review-prompts/pr-35-pass-1.md and the three pr-34 texts equal their fenced blocks in the session's transcript, by the PM's scripts.

LANDING. Run git fetch origin and re-check. If the PR head is still 58df13ed81b2b4f40e8a18cb708d19bdec46c5b9, main is still 60d9e479581101b00542c6af391e37f4014a358f, verify is green at that head and the gate in AGENTS.md holds, post one short PR comment recording the PM's statements above and that this read was done. Then run gh pr ready 35 --repo BeniCheni/settlement-grader-evals, and squash-merge pinned to that head: gh pr merge 35 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit 58df13ed81b2b4f40e8a18cb708d19bdec46c5b9 --subject "data: step 4's attacks and controls, the A05 key, and the triage" --body with exactly these lines:

Add H1 to H5 with clean twins and benign controls, traces/rt-attacks from one real session under ruling 32's block, Assignment 1's attacks.md and triage.md, and the owner's verification of A05's result (ruling 35) and placement of the matrix cells (ruling 36). A harmless note derails C13 the way step 3's probes did, so those flips may be fragility and not obedience; the same note on A13 and A05 changes nothing. H2 and H5 really broke the grader. In sample, and no rate. A new test file ties the run to its data, config and documents, and README's verified-key count is corrected to 5. Records ruling 37.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Cursor <cursoragent@cursor.com>

If the head or main has moved, or verify is not green, stop and say so. Push nothing else and change nothing else.

AFTER THE MERGE. Confirm that main's tree equals 1dbc1cff203df7c91f3448fdcb9e931cdab57bb8, that no tag exists on the remote, and that verify is green on the push to main. Leave the branch and the clone for the owner's word. Report main's new SHA and the verify run id. Write no home-directory path, absolute or tilde, in anything you post.
