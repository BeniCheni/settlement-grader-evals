# Judge agreement

Command: `python3 -m scorer.judge report --labels tests/fixtures/judge/labels.jsonl --final tests/fixtures/judge/labels-final.jsonl --readings tests/fixtures/judge/readings.json --provenance tests/fixtures/judge/provenance.txt --verdicts tests/fixtures/judge/verdicts`

Worst judges on the final labels tied: rule_adherence, tool_call_accuracy.

Model: none. Digest: none.

## needs_human_correctness

Rubric SHA-256: 752bd8591fc27bb5125208effdb2b9bc89aab4a2ee4624b60dd481477b2b65b9.
Labels SHA-256: 005dcc4f65f0aa84cceed3a16ef37abcf4c33a39c1fdabfe1e1d4edc0cb9498a.
same text as when the labels were made
UNPARSED: 0.

### First-pass labels

JP_HP (tn): 1
JP_HF (fn): 1
JF_HP (fp): 0
JF_HF (tp): 1

Agreement: 0.6667. Kappa: 0.4000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 1 of 1.

False passes:
- tests/fixtures/judge/runs/base C1: missed. Reading: yes.

False fails:
none

### Final labels

JP_HP (tn): 2
JP_HF (fn): 0
JF_HP (fp): 0
JF_HF (tp): 1

Agreement: 1.0000. Kappa: 1.0000. Kappa at least 0.6: yes.
meets_bar (85% and 0.6): yes. False passes read: 0 of 0.

False passes:
none

False fails:
none

## rule_adherence

Rubric SHA-256: a409a395dc16771cad2512ab32ccb2e71f1d37c4622c2f9402eb4d38aa0854e9.
Labels SHA-256: 005dcc4f65f0aa84cceed3a16ef37abcf4c33a39c1fdabfe1e1d4edc0cb9498a.
same text as when the labels were made
UNPARSED: 0.

### First-pass labels

JP_HP (tn): 1
JP_HF (fn): 0
JF_HP (fp): 1
JF_HF (tp): 1

Agreement: 0.6667. Kappa: 0.4000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 0 of 0.

False passes:
none

False fails:
- tests/fixtures/judge/runs/base C3: flagged. Reading: no.

### Final labels

JP_HP (tn): 1
JP_HF (fn): 0
JF_HP (fp): 1
JF_HF (tp): 1

Agreement: 0.6667. Kappa: 0.4000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 0 of 0.

False passes:
none

False fails:
- tests/fixtures/judge/runs/base C3: flagged. Reading: no.

## tool_call_accuracy

Rubric SHA-256: 935c99aa24b6d8eabc3270044fddc7b7084a7597bf2605ccb293a8167f4b6aa9.
Labels SHA-256: 005dcc4f65f0aa84cceed3a16ef37abcf4c33a39c1fdabfe1e1d4edc0cb9498a.
same text as when the labels were made
UNPARSED: 1.

### First-pass labels

JP_HP (tn): 1
JP_HF (fn): 0
JF_HP (fp): 1
JF_HF (tp): 1

Agreement: 0.6667. Kappa: 0.4000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 0 of 0.

False passes:
none

False fails:
- tests/fixtures/judge/runs/base C2: no. Reading: no.

### Final labels

JP_HP (tn): 1
JP_HF (fn): 0
JF_HP (fp): 1
JF_HF (tp): 1

Agreement: 0.6667. Kappa: 0.4000. Kappa at least 0.6: no.
meets_bar (85% and 0.6): no. False passes read: 0 of 0.

False passes:
none

False fails:
- tests/fixtures/judge/runs/base C2: no. Reading: no.

## Written by hand, not computed

Hand written for this fixture. The numbers below are made up. They are in sample. They are not held out. They show nothing about a judge.
