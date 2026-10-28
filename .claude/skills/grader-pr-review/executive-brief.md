# The Executive Summary Brief: shape (Pass 2.5)

One brief per cycle, delivered in chat, written for the owner, who relies on the seats to have read everything. Decision
first. Every number comes from a command run in this session; a number lifted from a PR body or a comment is labelled as that
vendor's claim.

```markdown
## Executive Summary Brief: PR #<N> · Pass 2.5 · <date, TZ=America/New_York>

**Decision:** merged at `<sha>` (gate satisfied: <clauses>) | **escalated**: the merge and any tag are yours; the block is at
the end. One sentence on why.

### What ships
Three to five bullets: what the repo can now do or refuses to claim, in the README's voice.

### What the passes found
Pass 1's findings, then Pass 2's dispositions, then this pass's corroboration, one line each. Anything still contested: the two
positions and the evidence each has.

### Verification as re-run
Tests on each Python, compileall, `verify`, mutations, regenerated files, UI cells. Numbers from this pass only. What could not
be re-run, and why.

### In sample, or held out
Which every reported result is, and the next step that would make an in-sample result trustworthy.

### Risks and accepted costs
Restated for a reader who will not open the spec.

### Questions for the owner
Each answerable in one word. A ruling a vendor recorded second-hand is confirmed here.

### Handoff block (when escalated)
The paste-ready block from SKILL.md section 7 step 6.
```
