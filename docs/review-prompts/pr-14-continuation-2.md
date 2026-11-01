# PR #14 — the owner's answers on the colophon and the UI rule (TZ=America/New_York)

The text delivered Sat 31 Oct 2026, as archived by the PM seat (Claude) on Sun 1 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 14 --pass 1 (continuation 2)

The owner's answers to your two questions, named as his and made Sat 31 Oct 2026: (1) Yes. The colophon names a fixed relative output, --html comparison.html, so its command runs as printed and report --html and export-course write the same bytes. (2) Yes. AGENTS.md's UI rule now says it explicitly: "a statement beside it, of one or more sentences, says whether it is in sample or held out and what it does and does not show", and "It is prose, never a chip". Both facts are still required beside every calibration number. The ruling is recorded in the rule's own paragraph.

The PM pushed 7520c74da9440701f62514e8f1db58572f6c2b9c with both changes. It touches the spec's command paragraph, its colophon sentence, the provenance item's last sentence and acceptance item 1, which now has a test that runs the printed command in a scratch copy and compares the comparison.html it writes with the committed page. It also touches the one paragraph of AGENTS.md's UI rules, reworded and rewrapped.

Re-read 7520c74 as a PM fix you did not write. Confirm that its word-level diff against 77fa3cc touches only those passages. Confirm that the AGENTS.md edit keeps every requirement the rule had (both facts beside every calibration number, prose and never a chip, changing when the evidence changes) and changes only what the owner ruled. Confirm that no other file still says the colophon prints the page's own path or that a provenance sentence must be single. docs/slice-1-spec.md's "it is a sentence, never a chip" is a historical spec for slice 1. Say whether it needs a pointer, and do not edit it unless it would mislead a builder now.

Then land under the brief's rule if the gate holds and you push nothing. First re-check on GitHub that the head is still 7520c74da9440701f62514e8f1db58572f6c2b9c and that verify is green there. Then run gh pr merge 14 --squash --match-head-commit 7520c74da9440701f62514e8f1db58572f6c2b9c, with a terse factual message and Co-authored-by lines for Claude <noreply@anthropic.com> and Codex <noreply@openai.com>. After the merge, confirm that main's tree equals that head, that no tag exists on the remote, and that verify is green on the push to main. Add the landing to your existing comment, and leave the branch and the clone for the owner's word. If you push a fix instead, push, stop, say the SHA, and do not land until the PM has read it. If a new question for the owner comes up, ask it in one word and stop.
