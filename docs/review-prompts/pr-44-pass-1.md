# PR #44 — Pass 1: the cold read, by Cursor (TZ=America/New_York)

The text delivered Thu 5 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 44 --pass 1

PR #44 — Pass 1 (cold review, fast-track): two sentences that overstated the verdict, ruling 58 and PR #42's archive, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 at High effort, in a session started directly in a fresh clone, on the local branch cursor/pr44-review, which starts at the PR's head. Git records one commit on this PR, authored as Claude, and you wrote none of it. This brief names the round a fast-track: one cold review by you takes the place of Passes 1 to 3, as AGENTS.md "How work moves" item 5 says, on the owner's ruling 58, which this PR records. AGENTS.md outranks this prompt on process. Read .claude/skills/grader-pr-review/SKILL.md and follow its method. A claim you could not re-run is listed as not verified.

YOUR PART IN THIS TEXT. Your read of PR #42 found this overclaim in the public README, and named the ship report as still wrong. This PR corrects it in the ship report and the package's README. You wrote none of this PR. Check it against the files, never against what you remember.

ENVIRONMENT. The working directory must be the fresh clone itself and not a worktree of any other checkout. Say what it is in your environment line and confirm private/ and data/espn_cache/ are absent. If either is present, stop at once, say so, and change nothing. Never print or derive the scale constant, never compute a ratio between a published amount and anything, and write no home-directory path, absolute or tilde, in anything you commit or post. Run no model, no Ollama server and no Promptfoo.

THE OWNER'S RULINGS, named as the owner's: rulings 1 to 57 are on main in docs/week-3-package.md. Ruling 58 is what this PR adds, stated to you here: the PM's recommendation, "Cursor", chosen by the owner in a dialog on Thu 5 Nov 2026, on who gives this read. You cannot see where it was made, so report it as stated. Ruling 53, no-ship, stands. Changing a ruling's answer is not a fix. A tag and a release number stay the owner's: create none.

STATE, as the PM read it on Thu 5 Nov 2026 at about 14:00 EST (re-check all of it). PR #44 is an open draft, head ddf4a6d5d1e1241a54777caaa1a1284716b755ec on docs/verdict-bars, tree 62bbc7da973dc08df15e7152301f7feda1327d1b, base main at 93ae657c66dbee0852d76e97af0b3bdde0d292fd, which is the branch's fork point. One commit. Four files, 63 insertions, 4 deletions. Take the head and CI state from GitHub, never from this prompt. The PR body is a claim, not a source. PR #43 was the PM's mistake: it was opened on docs/package-wording, a name that still held PR #23's merged branch, so it showed that old commit, and it is closed. Neither it nor that old branch is part of this review.

WHAT TO CHECK. (a) Each corrected sentence against thresholds.json, reports/guardrails.json and the table under it. Is it now true? Does it say anything new that is not? (b) Search main and this branch for any other place that says every guardrail misses a bar, or that names G4 as missing a bar of its own. Search the statement in reports/guardrails-statement.md, the scorecard, the note and the plan. If a generated file says it, name the command and stop. (c) Ruling 58 in the table and the sentence above it, and PR #44 in the Build paragraph. (d) The text under pr-42-pass-1.md's "---" must not change, and that it equals what was delivered is the PM's statement. (e) git diff --name-only origin/main...HEAD lists only the four files. Sweep the added lines, the commit body, the PR body and your own comment by pattern: e-mail addresses with agent identities apart, home paths, private folder names, balance or account words, dollar figures, digit runs of six or more, and names beyond the owner and licence notices. Counts only, patterns stated, no hit printed. Run the suite and python3 -m compileall -q . on Python 3.9 and 3.14, one at a time.

FIX POLICY. You may fix only a wrong figure, name, path or claim in packages/red-team-guardrails/assignment-2/ship_report.md, packages/red-team-guardrails/README.md, packages/red-team-guardrails/assignment-2/guardrails.md or docs/week-3-package.md, in one push at the end, authored as Cursor via per-commit git -c user.name=Cursor -c user.email=cursoragent@cursor.com commit with the trailer your harness gives you, and a message saying what was wrong, how you proved it and how you verified it. Push only with git push origin HEAD:docs/verdict-bars after git fetch origin shows the remote tip unmoved. Change no generated file by hand, no code, no test, no report, no ruling's answer and no text under an archive's "---".

POST ONE SHORT PR COMMENT in the shape of the skill's pr-comment.md: your verdict, what you checked with the commands, the sweep's counts, whether you wrote to the branch and the SHAs, and any question answerable in one word.

THEN, ONE OF TWO. If nothing is wrong, or only what the fix policy allows, nothing is contested, verify is green at the tip and the gate in AGENTS.md holds, land it: run gh pr ready 44 --repo BeniCheni/settlement-grader-evals, then squash-merge pinned to the head you reviewed, with gh pr merge 44 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit <that head> --subject "docs: say which bars the verdict rests on" --body with exactly these lines:

The ship report and the package's README said every guardrail misses a bar, and G4 has no bar of its own. Name G1, G2, G3 and the stack instead, as the tables under them do. Record ruling 58 and archive PR #42's brief. No code, test, data, report or number changes.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Cursor <cursoragent@cursor.com>

Otherwise stop, do not mark the PR ready and do not merge, and report what you found. Either way, create no tag and leave the branch and the clone for the owner's word.

REPORT BACK. The head you reviewed, the verify run id, the comment's URL, and if you landed: main's new SHA, that main's tree equals that head's tree, that no tag exists on the remote, and that verify is green on the push to main.
