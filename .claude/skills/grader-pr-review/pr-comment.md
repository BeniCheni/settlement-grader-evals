# The one PR comment: shape

One comment per review pass. Verdict first; everything else is evidence for it. Written for a reader who did not watch the
session, and for a public repo: no private path, no amount that was not already published, never the scale constant.

```markdown
## Review (Pass <1|2>): <verdict in one sentence: mergeable / mergeable after fixes / not mergeable, and why>

Reviewed at `<tip sha>` on <date, `TZ=America/New_York`>; verified after fixes at `<post-fix sha>`.
Seat and model: <agent, model, effort>. Fresh clone without `private/`: <yes, path-free>.
Baseline at the tip: tests <N> in <M> files on Python <3.9.x> and <3.14.x>; compileall <clean|errors>; stdlib only <yes|names>.
Diff against `origin/main`: <F> files, +<A> / −<B>. `verify`: <run id and result | no workflow yet>.

### Findings

| # | Severity | Finding | How verified (command, SHA, number) | Fix |
|---|---|---|---|---|
| 1 | high / medium / low | one sentence, file:line | the command that reproduced it, and what it printed | `<sha>` or "not fixed: <why>" |

### Killed as unreproducible
- <lead>: <what was tried, what was observed instead>.

### Mutations run
- <mutation>: <suite result, and whether it went red for the right reason>. A surviving mutant is a finding.

### Privacy sweep
- <pattern class>: <hit count>. No hit printed.

### Human-review resolutions
- <Beni's item>: <what changed on the branch, where it is recorded>.

### Deliberately not done
- <thing>: <reason and rough size>.

### As run
- Commands and counts, each with how a count is made. Not verified: <what, and why>.
```

Severity: **high** is a confident lie to a reader, a leak of anything private or of the scale constant, a trust claim the
numbers do not back (a bar called met that is not), a test that cannot fail, a red build, a crash, or an AA failure on a new
surface. **medium** is a wrong or stale claim, a missed edge, a layout defect, a surviving mutant that is not a high.
**low** is tidiness or a comment that overclaims. A high finding without a fix commit makes the verdict "not mergeable".
