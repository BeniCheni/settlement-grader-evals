# PR #36 — the PM's read of the added checks: land (TZ=America/New_York)

The text delivered Wed 4 Nov 2026, as archived by the PM seat (Claude) on Wed 4 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comments it led to are on the PR.

---

PR #36 — the PM's read of your added checks: land.

The PM read af8f60dfde924ae68d09e6c0075caa7129121475. It changes only tests/test_frozen_data.py, docs/week-3-package.md and docs/guardrail-spec.md, and no frozen file: git diff 935937c on data/, labels/, rubrics-guardrails/, thresholds.json, the configs and traces/ is empty. Your two doc corrections are accepted: a hash shows consistency and not approval, and the reachability counts rest on the PM's statement about the reserve. The PM re-ran that head from its own archive: 297 tests OK and compileall clean on Python 3.9.6 and 3.14.7. The PM then re-applied its 23 mutations in throwaway copies, and all 23 are killed, including the 10 that survived. This is the PM read your first comment asked for, so the tests may land. No high finding is open.

THE PM'S STATEMENTS, which your seat cannot check. Report each as the PM's. (1) The three held-out files are outside every checkout and match data/redteam/reserve.sha256, checked again at this head. (2) All 10 held-out attacks touch a field an input guardrail reads, by a script over those files. (3) The base check went through the spec's sandbox-exec profile, with the local-request and errno checks passing just before it, as the PM's resource log outside the repo records. (4) docs/review-prompts/pr-35-continuation.md and pr-35-land.md equal their fenced blocks in the session's transcript, by the PM's script.

LANDING. Run git fetch origin and re-check. If the PR head is still af8f60dfde924ae68d09e6c0075caa7129121475, main is still 1a9f36f6ecff91fa4ed247a56bfb651207ede509, verify is green at that head and the gate in AGENTS.md holds, post one short PR comment recording the PM's statements above and that this read was done. Then run gh pr ready 36 --repo BeniCheni/settlement-grader-evals, and squash-merge pinned to that head: gh pr merge 36 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit af8f60dfde924ae68d09e6c0075caa7129121475 --subject "data: freeze step 5's slices, rubric, thresholds and held-out hash" --body with exactly these lines:

Add the dev slice and its labels, G2's rubric, the thresholds, the held-out hash and a manifest of the approved bytes, all approved by the owner before any guardrail runs (rulings 39 and 40). A13 is verified for its push, not its amounts (ruling 38), and a base check shows a harmless note derails B01 as it does C13, so the input probes move to A13. The bars are set to what each guardrail can reach: no input guardrail can see P2, H2 or H5, and P2 and H5 on C13 read as already held. New tests tie the rows, the bars' reasoning and the base check's run to the documents. In sample, and no rate.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Codex <noreply@openai.com>

If the head or main has moved, or verify is not green, stop and say so. Push nothing else and change nothing else.

AFTER THE MERGE. Confirm that main's tree equals ef0642dacb51d6aff902900a284765872e5373ca, that no tag exists on the remote, and that verify is green on the push to main. Leave the branch and the clone for the owner's word. Report main's new SHA and the verify run id. Write no home-directory path, absolute or tilde, in anything you post.
