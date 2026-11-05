# PR #40 — Pass 1: the cold read, by Cursor (TZ=America/New_York)

The text delivered Thu 5 Nov 2026, as archived by the PM seat (Claude) on Thu 5 Nov 2026. It was delivered in chat, one line per paragraph; this copy is recovered from the session's transcript, and the comment it led to is on the PR.

---

/grader-pr-review 40 --pass 1

PR #40 — Pass 1 (cold review, fast-track): step 7, the held-out slice, rulings 49 and 50 and PR #39's archive, in github.com/BeniCheni/settlement-grader-evals

You are Cursor on Grok 4.7 at High effort, in a session started directly in a fresh clone, on the local branch cursor/pr40-review, which starts at the PR's head. Git records two commits on this PR, authored as Claude, and you wrote neither. This brief names the round a fast-track: one cold review by you takes the place of Passes 1 to 3, as AGENTS.md "How work moves" item 5 says, on the owner's ruling 50, which this PR records. AGENTS.md outranks this prompt on process. Read .claude/skills/grader-pr-review/SKILL.md and follow its method. A claim you could not re-run is listed as not verified.

YOUR PART IN THIS TEXT. Cursor built the first four commits of PR #38, including G1 and suspicious, before these rows were public, and that build has merged. You wrote none of this PR. Say so in your comment. The PM seat wrote these rows and is not blind to them. Check each claim against the files and commands, never against what you remember.

ENVIRONMENT. The working directory must be the fresh clone itself and not a worktree of any other checkout. Say what it is in your environment line and confirm private/ and data/espn_cache/ are absent. If either is present, stop at once, say so, and change nothing. Never print or derive the scale constant, never compute a ratio between a published amount and anything, and write no home-directory path, absolute or tilde, in anything you commit or post.

RUN NO MODEL, AND NO GUARDRAIL ON THESE ROWS. Start no Ollama server, run no real ticket and run no Promptfoo: a real run with other apps open has already frozen this machine once. Do not run G1, G2, G3, G4, suspicious, the payout check or any oracle check on a row of the reserve, or on the whole of data/gold.json, data/adversarial.json or a run holding every ticket. Step 8 is the first time a guardrail meets these rows, and only the PM seat runs it. You may read the rows and run expand, reserve_order, _union_rows and report as item (d) says. Compute, print and post no payout difference, residual or count at any tolerance.

THE OWNER'S RULINGS, named as the owner's: rulings 1 to 48 are on main in docs/week-3-package.md. Rulings 49 and 50 are what this PR adds, stated to you here, each the PM's recommendation, chosen by the owner in a dialog on Thu 5 Nov 2026. Ruling 49 is "Push now", on making the held-out rows public. Ruling 50 is "Cursor", on who gives this read. You cannot see where these were made, so report them as stated. Ruling 15 is open and blocks nothing here. Changing a ruling's answer is not a fix. A tag and a release number stay the owner's: create none.

STATE, as the PM read it on Thu 5 Nov 2026 at about 10:30 EST (re-check all of it). PR #40 is an open draft, head 2f3156ba69c671721073dc1545ddaa5c4e79f783 on data/step-7-reserve, tree a0638310af0c7c104281eb3d51e8c69b2bd93e8f, base main at 90502209c50dd589baf28c615666c1bf2b25383b, which is the branch's fork point. Two commits: 2d10660 the four data files, 2f3156b the docs. Six files, 1,578 insertions, 3 deletions. Take the head and CI state from GitHub, never from this prompt. The PR body is a claim, not a source.

WHAT TO CHECK, each re-derived and never taken from this prompt or the PR body.

(a) The bytes. shasum -a 256 -c data/redteam/reserve.sha256 for the three named files. Show from git log that the manifest merged at step 5 and has not changed since, and that this PR adds these files and edits none. Does the manifest name anything this PR does not hold, or the reverse?

(b) The rule for the real tickets. docs/guardrail-spec.md's "The real tickets, by a fixed rule" says how the five are chosen. Re-derive them by your own script from data/gold.json and data/redteam/reserve-salt.txt's exact bytes, and compare with the real rows in reserve-spec.json. Then call scorer.guardrails.reserve_order on the same inputs and compare. No row in common with dev's five real tickets?

(c) expand. python3 -m scorer.guardrails expand --slice reserve must leave reserve-cases.json byte for byte, and test_reserve_cases_match_the_committed_bytes_once_both_files_exist must read it and not print that a file is absent. Flip one byte in a temporary extraction and show that test fail. Every real row's ticket fields and source equal data/gold.json's, every row with a twin has source synthetic, and no key is outside the allow-list.

(d) The shapes, for step 8. Counts of attack, legitimate and control rows, and that cases and labels pair. Every attack's base has exactly one control in its slice. Every oracle name is valid. Which case ids are in both dev and reserve, and is each a control in both with an equal case row and an equal label row? Then rehearse report on the two real slices and the real thresholds file with invented decisions, all allowing, and invented runs whose records hold an empty ticket, in a temporary extraction, so that no check reads a real row. Say what sections it prints, which bars it judges on which section, and whether it repeats byte for byte. Say what stops it.

(e) The labels. No row claims a key is verified, and nothing here adds to the verified count of 6. Is any label inconsistent with its row?

(f) The docs. Rulings 49 and 50 in the table and the sentence above it, PR #40 in the Build paragraph. The reachability command in the plan: does it print 10 10, and is its sentence true? Run the command as written. Search both documents, the README and AGENTS.md for anything these files make stale: reserve is not in the repository, stays outside, has not been inspected, held-out file. Name each, and say whether it is history that stays true or a claim that is now wrong.

(g) Fairness, as information and not a fix. Reading the rows, not running anything: does any attack or hard negative look shaped to G1's patterns or to suspicious, in either direction? Which rows would you expect to be hardest for a regex, and which for a judge? Changing a row voids the hash and needs the owner's ruling, so anything you find goes in the comment for the hand-written statement at step 8. Say plainly that you built G1, so this read is not independent.

(h) Scope and privacy. git diff --name-only origin/main...HEAD must list only the six files. Sweep the added lines, the two commit bodies, the PR body and your own comment by pattern: bet ids, e-mail addresses with agent identities apart, home paths, private folder names, balance or account words, dollar figures, digit runs of six or more, and names beyond the owner and licence notices. Counts only, patterns stated, no hit printed. Each dollar figure in the data files must already be in data/gold.json on main, and every capitalised multi-word sequence in them classified by reading it. Run the suite and python3 -m compileall -q . on Python 3.9 and 3.14 with real counts, one interpreter at a time.

(i) Step 8 from here. What does the seat running it have to do that neither document says? List anything it would have to guess, as a finding or as a question answerable in one word.

FIX POLICY. Finish the whole audit before you push anything. A wording preference with nothing wrong in it is not a fix: list it and leave it. You may fix only a wrong figure, name, path or claim in docs/week-3-package.md or docs/guardrail-spec.md, in one push at the end, authored as Cursor via per-commit git -c user.name=Cursor -c user.email=cursoragent@cursor.com commit with the trailer your harness gives you, and a message saying what was wrong, how you proved it and how you verified it. Push only with git push origin HEAD:data/step-7-reserve after git fetch origin shows the remote tip unmoved. Change no byte of the four data files, no code, no test, no ruling's answer and no text under an archive's "---". If a data file looks wrong, stop and report it: that needs the owner's ruling.

POST ONE PR COMMENT in the shape of the skill's pr-comment.md, saying whether you wrote to the PR branch and the SHAs, with your verdict, findings, killed findings, the reproductions, the fairness read, the sweep, deliberately not done and the commands as run, and any questions answerable in one word. Report the PM's statement on the archive as the PM's.

THEN, ONE OF TWO. If your verdict is mergeable, or mergeable after only the fixes above, and no finding asks to change a data file or a contract, nothing is contested, verify is green at the tip and the gate in AGENTS.md holds, land it: run gh pr ready 40 --repo BeniCheni/settlement-grader-evals, then squash-merge pinned to the head you reviewed, with gh pr merge 40 --repo BeniCheni/settlement-grader-evals --squash --match-head-commit <that head> --subject "data: merge the held-out slice for step 8" --body with exactly these lines:

Merge the reserve's three files byte for byte, as data/redteam/reserve.sha256 has named them since step 5, with expand's output. G1 to G4 merged before these rows were public, and no guardrail has run on them. Record rulings 49 and 50, replace the plan's assumption about the reserve's reach with a command, and archive PR #39's brief. Cursor gives the cold read (ruling 50). No code, test, threshold, rubric, config or trace changes.

Co-authored-by: Claude <noreply@anthropic.com>
Co-authored-by: Cursor <cursoragent@cursor.com>

Otherwise stop, do not mark the PR ready and do not merge. Report your findings and questions, and the PM will answer them. Either way, create no tag and leave the branch and the clone for the owner's word.

REPORT BACK. The head you reviewed, the verify run id, the comment's URL, and if you landed: main's new SHA, that main's tree equals that head's tree, that no tag exists on the remote, and that verify is green on the push to main.
