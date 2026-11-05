# PR #42 — Pass 1: the cold read, by Cursor (TZ=America/New_York)

The text delivered Thu 5 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 42 --pass 1

PR #42 — Pass 1 (cold review, fast-track): the package for Assignments 1 and 2, ruling 57 and PR #41's archive, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 at High effort, in a session started directly in a fresh clone, on the local branch cursor/pr42-review, which starts at the PR's head. Git records two commits on this PR, authored as Claude, and you wrote neither. This brief names the round a fast-track: one cold review by you takes the place of Passes 1 to 3, as AGENTS.md "How work moves" item 5 says, on the owner's ruling 57, which this PR records. AGENTS.md outranks this prompt on process. Read .claude/skills/grader-pr-review/SKILL.md and follow its method. A claim you could not re-run is listed as not verified.

YOUR PART IN THIS TEXT. Cursor built the first four commits of PR #38, the first version of the guardrails this package describes, so this read is not independent of that build. You wrote none of this PR. Say so in your comment, and check each claim against the files and commands, never against what you remember.

ENVIRONMENT. The working directory must be the fresh clone itself and not a worktree of any other checkout. Say what it is in your environment line and confirm private/ and data/espn_cache/ are absent. If either is present, stop at once, say so, and change nothing. Never print or derive the scale constant, never compute a ratio between a published amount and anything, and write no home-directory path, absolute or tilde, in anything you commit or post.

RUN NO MODEL. Start no Ollama server, run no real ticket and run no Promptfoo. Everything here is proved by reading, or by the commands that need no model, in temporary extractions and never in your working tree. Compute, print and post no payout difference, residual or count at any tolerance.

THE OWNER'S RULINGS, named as the owner's: rulings 1 to 56 are on main in docs/week-3-package.md. Ruling 57 is what this PR adds, stated to you here: the PM's recommendation, "Cursor", chosen by the owner in a dialog on Thu 5 Nov 2026, on who gives this read. You cannot see where it was made, so report it as stated. Ruling 15 is open and blocks nothing here. Ruling 53, no-ship, stands. Changing a ruling's answer is not a fix. A tag and a release number stay the owner's: create none.

STATE, as the PM read it on Thu 5 Nov 2026 at about 13:05 EST (re-check all of it). PR #42 is an open draft, head 64152bb31d998775e07b050ef4286fa6c5a36c7e on docs/step-11-package, tree ffa3685d7b94303d177404ff5de4b6e9473c64cf, base main at dc46dc997f21aa4a7567d1744ebb536d793b1c84, which is the branch's fork point. Two commits: 7e0a380 the package, 64152bb the docs. Nine files, 794 insertions, 6 deletions. Take the head and CI state from GitHub, never from this prompt. The PR body is a claim, not a source.

WHAT TO CHECK, each re-derived and never taken from this prompt or the PR body.

(a) The map against the course. Fetch the course's acceptance lists at the commit the package's README names, under week-03-safety-and-adversarial-testing/assignments/01-scan-and-triage/README.md and 02-build-and-score-guardrails/README.md, from the course repository the plan names. Is every item there, in the course's words, with nothing added and nothing dropped? Does the file named actually meet each item? Open each one and say so row by row. A row that overstates what its file does is a finding. Weigh the hardest ones plainly: the config runs clean, when it was only run by the PM; attack type, target and expected behaviour across three files; and wired "via run_turn_guarded", when the wrapper here has another name.

(b) The retrofit table. Is each row in "This grader in the course's terms" true of the code? Is the claim that the config stays at the root, because its paths resolve there, true? Read how the exec provider and its config resolve paths, and if you can show it without a model, by fixture or by reading, say so. If a copy under the package would work, that is a finding.

(c) Generated files. Run every command in the package's README that needs no model, in a temporary extraction, twice, and compare bytes with the committed files: scan.md, test_set.md, scorecard.md and the report. Paste each command exactly as the README writes it: if one breaks in a shell, that is a finding. Is the scorecard's one line safe to read and to run? Does scan.md say what the plan's step 3 section says, row by row?

(d) The note, guardrails.md. Every number against reports/guardrails.json, and every claim about a row against its trace and labels. Is the account of each guardrail true of scorer/guardrails.py and of the spec? Does it present anything as more than it shows? The stretch answer: are the course's two options described fairly, and are its claims about parse_reply true? Is the description of G3 true of suspicious as the code has it?

(e) The public README. Its new paragraph and its Next line, against reports/guardrails.json, traces/rt-q and AGENTS.md's rules: report both numbers, in sample is not held out, absolute words are claims. Is "half the rows are in sample" fair? Is the Next line's "none of the 13 attacks it ran on broke the grader without that field" what traces/rt-q shows? Does the rest of the README now contradict it?

(f) Provenance. The package's README says who wrote each file or that a command generated it. Is each true by git log? Is "in sample" and "held out only in a narrow sense" stated wherever a rate appears, in the README, the note and the scorecard? Does the scorecard's generated header say so in words that change with the evidence, as AGENTS.md's provenance rule asks? Do the banned phrases appear as claims about a guardrail?

(g) The plan. Ruling 57 in the table and the sentence above it, PR #42 in the Build paragraph, the package tree and the paragraph under it. Is anything now stale, in the plan, the spec or either README? Does step 11's row still say the right thing, given that Assignment 3 is not in the package yet?

(h) The archive. The text under each "---" in pr-41-pass-1.md and pr-41-land.md must not change. That each equals what was delivered is the PM's statement, by a script over the transcript, and you cannot check it: report it as the PM's.

(i) Scope and privacy. git diff --name-only origin/main...HEAD must list only the nine files, and no code, test, data, label, threshold, rubric, trace or report may change. Sweep the added lines, the two commit bodies, the PR body and your own comment by pattern: bet ids, e-mail addresses with agent identities apart, home paths, private folder names, balance or account words, dollar figures, digit runs of six or more, and names beyond the owner and licence notices. Counts only, patterns stated, no hit printed. The package must not name the course's instructor, students or handle. Every number of six or more digits and every capitalised multi-word sequence new to main is classified by reading it. Run the suite and python3 -m compileall -q . on Python 3.9 and 3.14 with real counts, one interpreter at a time.

(j) What comes next. Step 9, Jev, step 10, the page, and step 12, submit. Can a reader of the package tell what is missing and why? List anything the next seat would have to guess, as a finding or a question answerable in one word.

FIX POLICY. Finish the whole audit before you push anything. A wording preference with nothing wrong in it is not a fix: list it and leave it. You may fix only a wrong figure, name, path, command or claim in packages/red-team-guardrails/README.md, packages/red-team-guardrails/assignment-2/guardrails.md, README.md or docs/week-3-package.md, in one push at the end, authored as Cursor via per-commit git -c user.name=Cursor -c user.email=cursoragent@cursor.com commit with the trailer your harness gives you, and a message saying what was wrong, how you proved it and how you verified it. Push only with git push origin HEAD:docs/step-11-package after git fetch origin shows the remote tip unmoved. Change no generated file by hand, no code, no test, no ruling's answer, no verdict, no number in a report, and no text under an archive's "---". If a generated file is wrong, say which command made it and stop.

POST ONE PR COMMENT in the shape of the skill's pr-comment.md, saying whether you wrote to the PR branch and the SHAs, with your verdict, findings, killed findings, the map row by row, the sweep, deliberately not done and the commands as run, and any questions answerable in one word. Report the PM's statement on the archive as the PM's.

THEN, ONE OF TWO. If your verdict is mergeable, or mergeable after only the fixes above, and no finding asks to change a contract or the verdict, nothing is contested, verify is green at the tip and the gate in AGENTS.md holds, land it: run gh pr ready 42 --repo BeniCheni/settlement-grader-evals, then squash-merge pinned to the head you reviewed, with gh pr merge 42 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit <that head> --subject "packages: assemble Assignments 1 and 2" --body with exactly these lines:

Add the package's README, which maps each of the course's acceptance items to its file, an approach note per guardrail with the stretch answered, and the generated scan, test set and scorecard. Say Week 3's result in the public README: no-ship, with dev in sample and reserve held out only in a narrow sense. Record ruling 57 and archive PR #41's two briefs. Assignment 3 is not done, and the package says so. No code, test, data, label, threshold, rubric, trace or report changes.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Cursor <cursoragent@cursor.com>

Otherwise stop, do not mark the PR ready and do not merge. Report your findings and questions, and the PM will answer them. Either way, create no tag and leave the branch and the clone for the owner's word.

REPORT BACK. The head you reviewed, the verify run id, the comment's URL, and if you landed: main's new SHA, that main's tree equals that head's tree, that no tag exists on the remote, and that verify is green on the push to main.
