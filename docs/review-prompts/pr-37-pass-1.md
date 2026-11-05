# PR #37 — Pass 1: the cold read, by Cursor (TZ=America/New_York)

The text delivered Wed 4 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 37 --pass 1

PR #37 — Pass 1 (cold review, fast-track): step 6's spec amendment, rulings 41 to 43 and PR #36's archive, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 at High effort, in a session started directly in a fresh clone, on the local branch cursor/pr37-review, which starts at the PR's head. Git records three commits on this PR, authored as Claude, and you wrote none of them. This brief names the round a fast-track: one cold review by you takes the place of Passes 1 to 3, as AGENTS.md "How work moves" item 5 says, on the owner's ruling 43, which this PR records. AGENTS.md outranks this prompt on process. Read .claude/skills/grader-pr-review/SKILL.md and follow its method. A claim you could not re-run is listed as not verified.

YOUR PART IN THIS TEXT. Cursor built PR #32, the seams this amendment changes, and Cursor will build step 6 from this amendment, so this read is not independent of either. You wrote none of this PR's docs. Say so in your comment, and check each claim against the files and commands, never against what you remember of them. Read as the seat that has to build this: anything you would have to guess at build time is a finding.

ENVIRONMENT. The working directory must be the fresh clone itself and not a worktree of any other checkout. Say what it is in your environment line and confirm private/ and data/espn_cache/ are absent. If either is present, stop at once, say so, and change nothing. Never print or derive the scale constant, never compute a ratio between a published amount and anything, and write no home-directory path, absolute or tilde, in anything you commit or post.

RUN NO MODEL. Start no Ollama server and run no real ticket: a real run with other apps open has already frozen this machine once. Everything here is proved by reading, on a fake _chat, or on recorded traces, in temporary extractions and never in your working tree. Compute, print and post no payout difference, residual or count at any tolerance. The one exception is item 16 below: the payout check's pass or fail at the spec's own bound, on H2, A05 and CT-A05 in traces/rt-attacks and nowhere else, printing only the result.

THE OWNER'S RULINGS, named as the owner's: rulings 1 to 40 are on main in docs/week-3-package.md. Rulings 41 to 43 are what this PR adds, stated to you here, each the PM's recommendation, chosen by the owner in a dialog on Wed 4 Nov 2026. Ruling 41 is "Leave it", to whether G4's fact check should exempt a poisoned fact. Ruling 42 is "Record delivery", to whether a run records that each attack reached the grader. Ruling 43 is "Cursor", to who gives this read. You cannot see where these were made, so report them as stated. Ruling 15 is open and blocks nothing here. Changing a ruling's answer is not a fix. A tag and a release number stay the owner's: create none.

WHAT IS WITHHELD. The held-out slice's three files are outside every checkout, and data/redteam/reserve.sha256 is all of it that is in the repo. Do not ask for them, and do not try to work out their contents. You build from dev only, and nothing in this read needs them.

STATE, as the PM read it on Wed 4 Nov 2026 at about 19:35 EST (re-check all of it). PR #37 is an open draft, head f3208d01b40ac2d7256ccd0630323b63f25d1966 on docs/step-6-amendment, tree 762d33c00337cf08280b13ff8268e07f0da67051, base main at e969a21af6170e2faee874266a00baef03b0fb4d, which is the branch's fork point. Three commits: 9d3e55f the amendment and rulings, cc0f8cf the archive, f3208d0 a correction to the delivery rule. Five files: docs/guardrail-spec.md, docs/week-3-package.md and three docs/review-prompts/pr-36-*.md. Take the head and CI state from GitHub, never from this prompt. The PR body is a claim, not a source.

WHAT TO CHECK, each re-derived and never taken from this prompt or the PR body. Read docs/guardrail-spec.md whole, the plan's rulings and "What PR #32's reviews left for later steps", and the code: grader/agent.py (finish, the follow-up branch), grader/guarded.py, grader/redteam_target.py, scorer/traces.py, scorer/checks.py (_facts_seen), scorer/judge.py (render_case, _guard_rubrics, build_adapter) and run_eval.py.

(a) The undercount. The amendment says comparing input.followups with output.final_by_turn undercounts a follow-up sent on a turn that then ends with no parsed final. Reproduce it on a fake _chat: a first turn that completes, then a reply that does not parse. Print how many follow-ups went out as user messages and how many entries the list has. If the claim is wrong, that is a high finding.

(b) The fields fit. In a temporary extraction, add run.followups_sent, the record's final_text, followups_sent and followups_total, and the target's poisoned mark and followups_sent as the amendment states them, and run the whole suite on Python 3.9 and 3.14. The PM ran an equivalent patch on 3.9 only. Do any existing tests or the golden byte-identity test have to change? "The existing tests unmodified" is a contract, so a test that must change is a finding. That patch stays in scratch. Do not push it: the build comes later.

(c) The raw text. Is output.final_text on the root span for each ending, and is it absent from load_run's record on this tree? Does anything in the repo pin a record's exact keys or render final_text, so that the new key would change a byte? Does the no_answer exception leave every row in exactly one of the six counts and keep the oracle line summing to the attacks?

(d) Delivery. Can every row reach a sensible delivery reading, and can the status 2 rule misfire: an input block in --guarded, an output block, a poison entry that changes nothing and so leaves no mark, a run with both seams, a --variant run? Is reading delivery from --unguarded alone stated plainly enough to build?

(e) Ruling 41's test. Does "any data/redteam/*-spec.json in the tree" work with only dev-spec.json present, and is P2 in dev-spec.json really the only row with poison, on lookup_rule alone? Do the other JSON files under data/redteam/ fall outside that glob, and should they?

(f) The payout check. Does a recorded record's ticket hold every field the check gates on, through grade_ticket_guarded as well as load_run? Compare the keys, with no amounts.

(g) Step 6's report. Does committing no reports/guardrails.* contradict anything in the spec, the plan's "Validate" table, the README or the course mapping? Is the reports/guardrails.args.json contract enough to write the stale test now, with step 8 adding only data? What should a --md or --json output path inside that file do?

(h) The guard flags. With g4 alone, or g1 alone, does anything read a rubric or reach a server? Can a server that fails partway through a guarded run produce a row scored as a catch, given G2's contract that a connection failure is never a verdict and the wrapper's rule that a raising guardrail is held closed? Follow it through decide-input and report --guarded, and say what actually happens.

(i) Committed decisions. Does decide-output --run traces/rt-attacks --cases data/redteam/attacks-cases.json have what it needs: the same case ids, no blocked record, a run_meta.json? And decide-input --guardrails g1 on data/redteam/dev-cases.json, which expand has yet to write? Are the paths under judgments/guardrails/ free of conflict with anything that reads judgments/?

(j) Item 16. Using the three checks and the payout result as stated above, is new PRINTED_PAYOUT alone for H2 and empty for H5, against A05, CT-A05, C13 and CT-C13 in traces/rt-attacks? Does the spec tell the builder plainly not to route this through report?

(k) expand and scan. Does every leg_patch key in dev-spec.json name a leg by its leg value? Does --slice leave any other spec line stale? Does scan's rule leave it enough to report pass or fail per probe from the raw output in traces/rt-attacks and traces/rt-baseline?

(l) The plan and spec agree. Rulings 41 to 43 in the table and the sentence above it, PR #37 in the Build paragraph, step 6's row, the answered questions, the header's claim, items 13 to 16. Is any other line now stale, in either document or the README? Is every name in the amendment either on this tree or stated as new?

(m) The archive. The text under each docs/review-prompts/pr-36-*.md's "---" must not change. That each equals what was delivered is the PM's statement, by a script over the transcript, and you cannot check it: report it as the PM's. You can compare the land note's commands with what PR #36's merge did on GitHub.

(n) Scope and privacy. git diff on data/, labels/, rubrics-guardrails/, packages/, traces/, code, tests and the three configs must be empty. Sweep the added lines, the three commit bodies, the PR body and your own comment by pattern: bet ids, e-mail addresses with agent identities apart, home paths, private folder names, balance or account words, dollar figures, digit runs of six or more, and names beyond the owner and licence notices. Counts only, patterns stated, no hit printed. Run the suite and python3 -m compileall -q . on Python 3.9 and 3.14 with real counts, one interpreter at a time.

(o) What you would have to guess. List every place in step 6's contracts, amended or not, where you would have to choose something a later step depends on and the spec does not settle it. Leave out what the spec says is the builder's choice. Each goes in the comment as a finding or as a question answerable in one word, to the owner or the PM.

FIX POLICY. Finish the whole audit before you push anything. A wording preference with nothing wrong in it is not a fix: list it and leave it. You may fix only a wrong figure, name, path or claim in docs/guardrail-spec.md or docs/week-3-package.md, in one push at the end, authored as Cursor via per-commit git -c user.name=Cursor -c user.email=cursoragent@cursor.com commit with the trailer your harness gives you, and a message saying what was wrong, how you proved it and how you verified it. Push only with git push origin HEAD:docs/step-6-amendment after git fetch origin shows the remote tip unmoved. Do not change what a contract requires, a ruling's answer, the text under an archive's "---", or anything outside those two documents. A defect in what a contract requires goes to the PM as a finding, because you will build from it and should not set your own terms.

POST ONE PR COMMENT in the shape of the skill's pr-comment.md, saying whether you wrote to the PR branch and the SHAs, with your verdict, findings, killed findings, the reproductions, the sweep, deliberately not done and the commands as run, and any questions answerable in one word. Report the PM's statement on the archive as the PM's.

THEN, ONE OF TWO. If your verdict is mergeable, or mergeable after only the fixes above, and no finding asks to change a contract, nothing is contested, verify is green at the tip and the gate in AGENTS.md holds, land it: run gh pr ready 37 --repo BeniCheni/settlement-grader-evals, then squash-merge pinned to the head you reviewed, with gh pr merge 37 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit <that head> --subject "docs: amend step 6's spec and record rulings 41 to 43" --body with exactly these lines:

Amend step 6's contracts before the build. A run records whether each attack arrived (ruling 42). A poisoned fact stays read as real, with a test that keeps rows off the fact tools (ruling 41). Every record carries the raw final text, so the leak check has something to read. Step 6 commits no report, because no model runs in it. Cursor gives the cold read (ruling 43). Archive PR #36's three briefs. No code, data, label, rubric, threshold, config or trace changes.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Cursor <cursoragent@cursor.com>

Otherwise stop, do not mark the PR ready and do not merge. Report your findings and questions, and the PM will answer them. Either way, create no tag and leave the branch and the clone for the owner's word.

REPORT BACK. The head you reviewed, the verify run id, the comment's URL, and if you landed: main's new SHA, that main's tree equals that head's tree, that no tag exists on the remote, and that verify is green on the push to main.
