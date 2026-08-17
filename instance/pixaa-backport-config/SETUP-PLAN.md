# Backport Agent Setup Plan

## Goal

Create a Rehor agent that autonomously handles backports for console and console-operator. The agent watches Jira for bugs that have been fixed on master and need backporting, then cherry-picks the fix to each target release branch and opens properly formatted backport PRs. Clean cherry-picks are handled directly by the backport agent. Conflicted cherry-picks are delegated to the dev agent.

## Separation of Concerns

| Actor | Responsibility |
|-------|---------------|
| **Human (triage)** | Decides *what* needs backporting — sets Target Backport Versions on the Jira bug |
| **Prow** | Moves bug to MODIFIED automatically when the fix PR merges |
| **Backport agent** | Detects MODIFIED bugs with Target Backport Versions, attempts cherry-pick. If clean → opens PR directly. If conflicts → delegates to dev agent |
| **Dev agent** | Handles conflict resolution when delegated — cherry-picks, resolves conflicts, opens PR |

## End-to-End Flow

```
TRIAGE (human)
━━━━━━━━━━━━━━
Bug: OCPBUGS-9999 "Console crashes on node list"
  Target Version:           5.1
  Target Backport Versions: 5.0, 4.22, 4.21
  Component:                console


DEV AGENT (pixaa-config)
━━━━━━━━━━━━━━━━━━━━━━━━
  Picks up OCPBUGS-9999
  Implements fix on master
  Opens PR #200: "OCPBUGS-9999: Fix console crash on node list"
  PR #200 merges ✓
  Prow moves OCPBUGS-9999 → MODIFIED

  (dev agent moves on to next bug, doesn't care about backports)


BACKPORT AGENT CYCLE 1 (pixaa-backport-config)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Preflight scans:
    - Jira: OCPBUGS bugs, status=MODIFIED, Target Backport Versions set
    - Finds OCPBUGS-9999, linked to merged PR #200
    - Target Backport Versions: [5.0, 4.22, 4.21]
    - Checks what's done: nothing yet
    - Next target: release-5.0 (newest first)

  Dry-run cherry-pick:
    git fetch upstream release-5.0
    git checkout release-5.0
    git cherry-pick --no-commit <sha(s) from PR #200>
    → exit code 0 = CLEAN ✓
    git cherry-pick --abort

  Clean → backport agent handles it directly:
    git cherry-pick <sha(s)>
    git push to bot fork
    Opens PR #201: "OCPBUGS-10001: Fix console crash on node list"
      base: release-5.0
    Clones OCPBUGS-9999 → OCPBUGS-10001 (target: 5.0.z)
    Links PR #201 to OCPBUGS-10001

  Waits for PR #201 to merge...


BACKPORT AGENT CYCLE 2
━━━━━━━━━━━━━━━━━━━━━━━
  Re-reads Target Backport Versions from OCPBUGS-9999: [5.0, 4.22, 4.21]
  Checks what's done:
    release-5.0  → PR #201 merged ✓
    release-4.22 → no PR           ✗ ← next
    release-4.21 → no PR           ✗

  Dry-run cherry-pick release-5.0 → release-4.22:
    → exit code 0 = CLEAN ✓

  Clean → handles directly:
    Opens PR #205: "OCPBUGS-10002: Fix console crash on node list"
      base: release-4.22
    Clones bug → OCPBUGS-10002

  Waits for PR #205 to merge...


BACKPORT AGENT CYCLE 3
━━━━━━━━━━━━━━━━━━━━━━━
  Re-reads Target Backport Versions from OCPBUGS-9999: [5.0, 4.22, 4.21]
  Checks what's done:
    release-5.0  → PR #201 merged ✓
    release-4.22 → PR #205 merged ✓
    release-4.21 → no PR           ✗ ← next

  Dry-run cherry-pick release-4.22 → release-4.21:
    → exit code 1 = CONFLICTS ✗

  Conflicts → hands off to dev agent:
    Clones OCPBUGS-9999 → OCPBUGS-10003 (target: 4.21.z)
    Adds labels to OCPBUGS-10003:
      - rehor-ai-pixaa
      - repo:console
    Adds comment to OCPBUGS-10003:
      "Cherry-pick from release-4.22 to release-4.21 has conflicts.
       Original fix: PR #200 (master).
       Source branch: release-4.22 (PR #205)."


DEV AGENT (picks up OCPBUGS-10003)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Reads bug context + backport agent's comment
  Cherry-picks from release-4.22 → release-4.21
  Resolves conflicts
  Runs tests
  Opens PR #210: "OCPBUGS-10003: Fix console crash on node list"
    base: release-4.21


BACKPORT AGENT CYCLE 4
━━━━━━━━━━━━━━━━━━━━━━━
  Checks what's done for OCPBUGS-9999:
    release-5.0  → ✓
    release-4.22 → ✓
    release-4.21 → PR #210 exists ✓

  All versions covered. Done. ✓
```

## Preflight Logic

The preflight runs as Python (zero AI cost) and decides whether to start a Claude session.

```
1. Query Jira: OCPBUGS bugs where:
   - status = MODIFIED
   - component in (console, console-operator)
   - Target Backport Versions is set

2. For each bug:
   a. Re-read Target Backport Versions (may have changed since last cycle)
   b. Normalize version strings (4.22.z / 4.22 / 4.22.0 → release-4.22)
   c. Sort versions newest-first (handle 4.x → 5.x transition)
   d. Find the merged PR on GitHub (from bug's PR links)
      - If no linked PR → skip, log warning
   e. Get ALL commits from the PR (gh pr view --json commits)
   f. For each target version (newest first):
      - Check: does release-X.Y branch exist? If not → skip
      - Check: does a backport PR already exist? (search by bug ID + branch)
      - Check: has this version been delegated to dev agent? (cloned bug with labels exists)
      - If no PR and not delegated → attempt dry-run cherry-pick
        - Determine source: master for first backport, previous release branch for cascade
        - Cherry-pick ALL commits in order
        - Clean (exit 0) → mark as actionable (agent handles directly)
        - Conflicts (exit != 0) → mark as actionable (delegate to dev agent)

3. If no actionable work → sleep, no Claude session
```

## Edge Cases and Handling

### Must handle (will break the flow)

| # | Edge case | Handling |
|---|-----------|----------|
| 1 | **Multi-commit PRs** | Get ALL commits via `gh pr view --json commits`, cherry-pick in order. If any commit conflicts, whole backport is delegated to dev agent |
| 2 | **Bug has no linked PR** | Skip the bug with a warning log. Optionally comment on the Jira bug: "Cannot create backport — no linked PR found" |
| 3 | **Human backporting simultaneously** | Check for existing backport PR (bug ID in title + target branch) right before creating. If found, skip that version |
| 4 | **Version string normalization** | Normalize `4.22.z` / `4.22` / `4.22.0` → `release-4.22`. Handle `4.x → 5.x` ordering explicitly (5.0 > 4.22 > 4.21) |
| 5 | **Release branch doesn't exist** | Check if branch exists before cherry-pick. If not, skip and retry next cycle |
| 6 | **Target Backport Versions updated mid-cascade** | Re-read from the original bug every cycle. If version removed, stop working on it (don't close existing PR). If version added, include it |

### Should handle (will cause stuck/stale state)

| # | Edge case | Handling |
|---|-----------|----------|
| 7 | **Backport PR fails CI** | Retry CI once. If still failing, hand off to dev agent (add labels to cloned bug). Don't block the cascade for lower versions |
| 8 | **Backport PR stuck (no `backport-risk-assessed`)** | Post reminder comment after N business days tagging z-stream approvers. Consider Slack notification |
| 9 | **PR rejected/closed by reviewers** | Detect closure → mark version skipped, move to next. Detect changes-requested → hand off to dev agent |
| 10 | **Dry-run clean but semantic conflict** | After clean cherry-pick, run basic build/compile check before opening PR. If build fails, hand off to dev agent |
| 11 | **Backport agent and dev agent race** | Track per-version state. Once delegated (cloned bug with labels exists), don't touch that version again |

### Nice to have (uncommon)

| # | Edge case | Handling |
|---|-----------|----------|
| 12 | **Merge commits** | Detect via `git cat-file -p <sha>`. Use `cherry-pick -m 1`. Rare — Prow squash-merges in OpenShift |
| 13 | **PR fixes multiple bugs** | Check ALL linked Jira bugs on the PR, not just the title bug. Clone and manage each one |
| 14 | **"No-op" bug (code rewritten in newer branch)** | If cherry-pick produces no changes or target files don't exist, create Jira bug with note for QE but don't open a PR |
| 15 | **Reviewer changes on backport PR** | Always cherry-pick from the most recently merged backport branch (not master) so reviewer modifications cascade down |
| 16 | **Bug cloning field correctness** | After cloning, verify: Target Version, component, severity, `is blocked by` link to the next-newest version's bug (required by Prow Jira plugin for `jira/valid-bug`) |

## Config Files

### `agent/instance.yaml`

```yaml
workflow: jira-kanban
source: jira
envs:
  - node
  - go
claude_md:
  strategy: append
```

Uses `jira-kanban` workflow with Jira as the source. Envs: `node` (for console frontend build checks) and `go` (for console-operator build checks). No `browser` needed — this agent doesn't test UI.

Note: `node` and `go` are only needed for the build check after clean cherry-picks (edge case #10). If we skip the build check and just open the PR (let CI catch issues), these envs can be dropped and the agent becomes even lighter.

### `agent/CLAUDE.md`

Needs to include:
- Role: "You are a backport agent. You cherry-pick merged fixes to release branches."
- Two modes of operation:
  - **Clean cherry-pick**: Open backport PR directly, clone Jira bug
  - **Conflicted cherry-pick**: Clone Jira bug, add labels, delegate to dev agent
- Backport PR formatting rules:
  - Title MUST start with `OCPBUGS-XXXXX:`
  - PR description: bug number, impact, cause, resolution (user-focused release notes)
- Cherry-pick source: master for first backport, previous release branch for cascade
- What NOT to do:
  - Never apply `backport-risk-assessed` label (z-stream approver responsibility)
  - Never approve or merge — leave for human review
  - Never decide on its own that something should be backported
- Delegation: when creating a cloned bug for the dev agent, include a comment with:
  - Which branches have conflicts
  - Link to original PR
  - Link to the source branch's backport PR

### `agent/personas/`

Focus on conflict resolution context (used by dev agent when delegated, but included here for completeness):

**frontend**:
- PatternFly version differences between branches
- React API changes across releases
- Webpack/Vite config drift
- CSS module / utility class renames

**operator**:
- Go module version differences
- API version changes (v1beta1 vs v1)
- controller-runtime breaking changes between releases
- Makefile target differences

### `agent/project-repos.json`

Same as dev agent — console and console-operator with bot fork URLs.

### `agent/mcp.json`

Same as dev agent — needs `mcp-atlassian` for Jira access.

## Key Rules from the Backport Process Doc

1. PR title MUST start with `OCPBUGS-XXXXX:`
2. Every backport needs a linked Jira bug
3. Agent must NOT apply `backport-risk-assessed` label (z-stream approver responsibility)
4. Backports go from newest release branch down to oldest
5. Bug severity and PM score matter for z-stream approval
6. PR description needs user-focused release notes: bug number, impact, cause, resolution
7. Jira bug clones must have `is blocked by` link to the next-newest version's bug
8. Use `/jira cherrypick OCPBUGS-XXXXX` in the backport PR for automatic bug cloning when possible

## Open Questions

1. **Build check on clean cherry-picks**: Should the agent run a build after clean cherry-picks before opening the PR? This catches semantic conflicts but requires `node`/`go` envs. Alternative: skip and let CI catch issues.
2. **Stuck PR timeout**: How many business days before posting a reminder for `backport-risk-assessed`?
3. **Jira field names**: Need to confirm the exact Jira field name for "Target Backport Versions" in the OCPBUGS project.
4. **Scope per cycle**: One backport version per cycle, or handle multiple versions in a single cycle?
