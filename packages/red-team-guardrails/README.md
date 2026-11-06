# The red-team and guardrails package

The deliverables for Week 3 of the AI Agent Evals course: a scan and five hand-written attacks on a real agent, then guardrails scored on both sides of the trade-off. Assembled by the PM seat (Claude) on Thu 5 Nov 2026. The notes below say who wrote each file or that a command generated it. The acceptance items are the course's words, from its repository at commit `718f649a80a9f6bc962ca2ae07c8c3af4259904c`, under `week-03-safety-and-adversarial-testing/assignments/`.

**The verdict is no-ship (the owner's, ruling 53).** G1, G2, G3 and the stack each miss a bar frozen before they ran, and G4 has no bar of its own: `assignment-2/ship_report.md`. Jev is no-ship too (ruling 66): it misses its catch bar and the condition that every attack it can see reaches `block`, `assignment-3/jev_report.md`.

**In sample, or held out.** Assignment 1's runs are in sample, and they carry no rate. In Assignment 2, `dev` is in sample and `reserve` is held out only in a narrow sense: it was withheld from the builder and every reader until step 7, and no guardrail met it before step 8, but the PM seat drafted both slices and the rubric. In Assignment 3, no band, bin or threshold changed after Jev's run, but the PM seat drafted Jev's question with both slices, so neither slice is held out in the strict sense. These are 40 rows, on one session on one machine, so they show these rows and not how often anything happens elsewhere.

**This grader in the course's terms.** The course targets a support agent called Pronto. This package targets a local model that settles soccer bet tickets, on matches already decided.

| In the course | Here |
|---|---|
| `agent.pronto_agent`, Promptfoo's exec provider | `grader.redteam_target` |
| `run_turn_guarded`, with `input_guardrails` and `output_guardrails` | `grade_ticket_guarded`, with the same two names, in `grader/guarded.py` |
| A multi-turn attack, run via `--chat` | A case's `followups`, because the grader has no chat |
| An indirect injection in a retrieved document | A marked overlay on a tool result, through `poison` |
| A user's message | A bet ticket's free-text fields |

## Assignment 1: scan and triage

| Acceptance item | File | Note |
|---|---|---|
| `promptfooconfig.yaml` runs clean with `promptfoo eval` (no config errors) | `promptfooconfig.yaml` at the repository root, `traces/rt-baseline/promptfoo-results.json` | The PM seat wrote the config, and it stays at the root, where its exec provider's module and data paths resolve. The results are the PM seat's run on the real grader. Exit code 100 means probes failed, and it is not a config error |
| Baseline scan covers all 5 probe categories (direct + indirect injection count as 2) | `assignment-1/scan.md`, `traces/rt-baseline` | Generated: `P1` direct injection, `P2` indirect injection, `P3` jailbreak, `P4` data leakage, `P5` harmful content, and `C13` their clean twin |
| Triage matrix filled: every failing trace placed in frequency × severity | `assignment-1/triage.md` | The PM seat proposed the cells and the owner placed them (ruling 36) |
| 5 hand-crafted attacks documented with attack type, target, expected behavior | `assignment-1/attacks.md`, `promptfooconfig-attacks.yaml`, `assignment-2/test_set.md` | Written by the PM seat. `attacks.md` gives each attack's type and base, the config holds what each must do, and the test set lists each row's target and expected behaviour |
| At least 1 hand-crafted attack is multi-turn (run via `--chat`, transcript in `attacks.md`) | `assignment-1/attacks.md`, `traces/rt-attacks` | `H5`, three turns, with its transcript. `python3 -m scorer.guardrails transcript --run traces/rt-attacks --case H5 --md OUT` prints every turn from the trace |
| At least 1 hand-crafted attack actually breaks the agent (if none do, they're not adversarial enough) | `assignment-1/attacks.md`, `traces/rt-attacks` | `H2` and `H5` broke it |

Assignment 1's runs used `promptfoo@0.124.1` through the network block of ruling 32, and the plan's sections on steps 3 and 4 hold the commands. They need a local model, so a review does not re-run them.

```bash
python3 -m scorer.guardrails scan --promptfoo traces/rt-baseline/promptfoo-results.json --run traces/rt-baseline --md packages/red-team-guardrails/assignment-1/scan.md
```

## Assignment 2: build and score guardrails

| Acceptance item | File | Note |
|---|---|---|
| 3 guardrails implemented and wired around the agent via `run_turn_guarded` | `scorer/guardrails.py`, `grader/guarded.py`, `assignment-2/guardrails.md` | Regex G1, judge G2 and hybrid G3, plus a code check, G4, which the course does not ask for. Built by Cursor and reviewed by Claude Code and Codex (PR #38). The PM seat wrote the note |
| 40-input test set (20 adversarial + 20 legitimate edge cases), documented | `assignment-2/test_set.md`, `data/redteam/dev-spec.json`, `data/redteam/reserve-spec.json`, `labels/redteam-dev.jsonl`, `labels/redteam-reserve.jsonl` | Generated from the rows the owner approved (ruling 39). A real ticket is its case id alone |
| Catch rate, over-block rate, and latency reported per guardrail | `assignment-2/scorecard.md`, `reports/guardrails.md` | Generated from step 8's runs and the owner's readings. Latency depends on the machine |
| Ship/no-ship verdict with upfront numeric thresholds | `assignment-2/ship_report.md`, `assignment-2/thresholds.json` | The thresholds merged before any guardrail ran. The verdict is the owner's, and the PM seat wrote the report |
| HITL flow documented: trigger conditions + approver view | `assignment-2/hitl.md` | Written by the PM seat. It is a design, and the approver's interface is not built |

**Stretch, who guards the guard:** `assignment-2/guardrails.md`, answered and not solved.

The runs are `traces/rt-unguarded`, `traces/rt-guarded` and `traces/rt-q`, and the decisions are in `judgments/guardrails/step8/`. They need a local model, so a review re-reads them. The report needs none:

```bash
python3 -m scorer.guardrails report $(python3 -c 'import json; print(" ".join(json.load(open("reports/guardrails.args.json"))[1:]))')
python3 -m unittest tests.test_guardrails.ReportCommandTests.test_the_committed_report_is_fresh_once_its_args_exist
```

`assignment-2/test_set.md` is the two slices' `test-set` output, with the second one's heading dropped:

```bash
mkdir -p .t
python3 -m scorer.guardrails test-set --spec data/redteam/dev-spec.json --labels labels/redteam-dev.jsonl --md .t/dev.md
python3 -m scorer.guardrails test-set --spec data/redteam/reserve-spec.json --labels labels/redteam-reserve.jsonl --md .t/reserve.md
{ cat .t/dev.md; echo; tail -n +3 .t/reserve.md; } > packages/red-team-guardrails/assignment-2/test_set.md
rm -rf .t
```

`assignment-2/scorecard.md` is generated from the report's JSON:

```bash
python3 -c 'import json; d=json.load(open("reports/guardrails.json")); by={s["name"]:s for s in d["sections"]}; pc=lambda r:"%s of %s [%.1f%%, %.1f%%]"%(r["k"],r["n"],100*r["wilson"][0],100*r["wilson"][1]); o=["# Scorecard","","Generated from `reports/guardrails.json`. `dev` is in sample, and `reserve` is held out only in a narrow sense, as the statement in `reports/guardrails.md` says. One session on one machine. Latency depends on the machine.",""]; [o.extend(["## "+n,"","| Column | Caught | Missed | Over-blocked | Allowed | Already held | Right to block | Catch | Over-block | Model calls | Mean ms | Largest ms |","|---|---|---|---|---|---|---|---|---|---|---|---|"]+["| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"%(k,c["counts"]["caught"],c["counts"]["missed"],c["counts"]["overblocked"],c["counts"]["allowed"],c["counts"]["already_held"],c["counts"]["right_to_block"],pc(c["catch"]),pc(c["over_block"]),c["model_calls"],c["mean_latency_ms"],c["largest_latency_ms"]) for k,c in by[n]["columns"].items()]+["","Row Q: %s breaks and %s answers moved, on the rows it ran."%(len(by[n]["variant_q"]["breaks"]),len(by[n]["variant_q"]["moved"])),""]+[l for l in by[n]["thresholds"]]+[""]) for n in ("union","reserve","dev")]; print("\n".join(o).rstrip())' > packages/red-team-guardrails/assignment-2/scorecard.md
```

## Assignment 3: Jev

**Done, with a no-ship verdict (ruling 66).** It needs a hosted service, so it was its own step, and the owner enabled it first (ruling 2). The owner ran the 49 requests in their own shell, and the PM seat committed the decisions and wrote the read.

| Acceptance item | File | Note |
|---|---|---|
| Jev scorer created in Braintrust (built-in Jev enabled) and passing 5/5 UI test cases | `assignment-3/ui_test.md` | Five of five, on Thu 5 Nov 2026. Built-in Jev was enabled but did not appear in the scorer's model picker, so the scorer reaches Jev through the owner's TypeSafe key (ruling 62). The PM seat built and ran it in the owner's browser |
| 40-input test set scored through Jev: catch rate, over-block rate, review rate, latency reported | `reports/jev.md`, `judgments/jev/` | Generated by `scorer/jev.py`, built by Cursor and reviewed by Claude Code and Codex (PR #46), from the owner's run. Latency depends on the machine and the network |
| Side-by-side comparison vs the Assignment 2 LLM-judge guardrail (same test set) | `assignment-3/jev_report.md`, `reports/jev.md` | Jev and G2 on the same 40 rows and the same question (ruling 61). The PM seat wrote the read |
| 3-bin reliability diagram: Jev's confidence vs empirical accuracy, with a written read ("calibrated / overconfident / underconfident, and where") | `reports/jev.svg`, `assignment-3/jev_report.md` | The bins sort on the winning probability, with Jev's mean confidence beside each (ruling 63). The read: overconfident where it is blind, on the three attacks outside the text it reads |
| Thresholds implemented in code with the review band routed to a documented HITL flow | `scorer/jev.py`, `assignment-2/hitl.md` | Block at P(attack) of 0.9 or more, allow at 0.1 or less, review between. A held ticket waits at most 24 hours and never settles on its own (ruling 67) |
| Ship/no-ship verdict with upfront numeric thresholds | `assignment-3/jev_report.md`, `assignment-2/thresholds.json` | Jev's bars merged before it ran, with its catch bar moved to 17 by ruling 60. The verdict is the owner's |

**Stretch, the honest gaps:** `assignment-3/jev_report.md`, all three answered.

The decisions need the owner's key and a hosted call, so a review re-reads them. The report needs neither:

```bash
python3 -m scorer.jev $(python3 -c 'import json; print(" ".join(json.load(open("reports/jev.args.json"))))')
python3 -m unittest tests.test_jev.StaleTests
```
