# Backport Workflow

Cherry-pick merged fixes from main to release branches. One backport action per cycle.

## Input Data

Preflight provides structured data for each actionable bug:

- Bug key, summary, status, component, repo
- Original merged PR number, URL, commit SHAs (in merge order)
- Target backport version and corresponding release branch
- Cherry-pick source branch (main for first backport, previous release branch for cascade)
- Cherry-pick classification: CLEAN or CONFLICTS
- Conflicting files list (if CONFLICTS)
- Status of all target versions (done, pending, delegated, etc.)

Do NOT re-query Jira or GitHub for data already in the preflight output. Use MCP tools only for write actions (creating bugs, adding comments, linking issues).

## Cycle Loop

Read preflight data. It contains one actionable backport item. Process it according to its classification.

### Action: Clean Cherry-Pick

When preflight says cherry-pick is CLEAN:

1. **Clone the Jira bug**
   - Use `jira_create_issue` to create a clone of the original bug for this release version.
   - Fields to set:
     - Project: OCPBUGS
     - Issue type: Bug
     - Summary: `[<release-branch>] <original bug summary>`
     - Description: `Backport of <ORIGINAL-KEY> to <version>.\n\nOriginal fix: <PR-URL>`
     - Component: same as original
     - Target Version: the z-stream version (e.g. `4.22.z`)
     - Labels: copy from original, KEEPING `rehor-ai-pixaa` and `repo:*` labels (so the dev agent maintains the PR)
   - Use `jira_create_issue_link` to add `is blocked by` link (the CLONE is blocked by the upstream bug, NOT the other way around):
     - `link_type="Blocks"`, `inward_issue_key=<UPSTREAM-BUG>`, `outward_issue_key=<CLONE-BUG>`
     - For the highest version: the upstream bug is the ORIGINAL bug
     - For cascade versions: the upstream bug is the next-newest version's clone bug (use `clone_keys` from preflight data to resolve the key; if not available, search Jira for the clone)
     - Prow requires this direction for `jira/valid-bug` validation

2. **Prepare repo**
   - Clone if not present: `git clone <fork-url> ./repos/<name>/`
   - Add upstream remote: `git remote add upstream <upstream-url>` (if not present)
   - Configure git identity:
     - `git config user.name "$GH_USER_NAME"`
     - `git config user.email "$GH_USER_EMAIL"`
   - Fetch the target release branch: `git fetch upstream <release-branch>`
   - Fetch the source branch: `git fetch upstream <source-branch>`
   - Create working branch: `git checkout -b bot/<clone-bug-key> upstream/<release-branch>`

3. **Cherry-pick commits**
   - Cherry-pick ALL commits from the original PR in order: `git cherry-pick <sha1> <sha2> ...`
   - If cherry-pick fails unexpectedly (race with new commits on branch), switch to delegation flow.

4. **Push and create PR**
   - Push branch to fork: `git push origin bot/<clone-bug-key>`
   - Create PR via `gh pr create`:
     - `--repo <upstream-org/repo>` (target the upstream repo, not the fork)
     - `--head <fork-org>:bot/<clone-bug-key>` (e.g. `platex-rehor-bot:bot/OCPBUGS-10001`)
     - `--base <release-branch>`
     - Title: `[<release-branch>] <CLONE-BUG-KEY>: <bug summary>` (e.g. `[release-5.0] OCPBUGS-112009: Fix flaky TestAsyncCache backend test`). This exact format is required.
     - Body:
       ```
       ## Bug
       [<CLONE-BUG-KEY>](https://issues.redhat.com/browse/<CLONE-BUG-KEY>)

       Backport of <ORIGINAL-KEY> to <release-branch>.
       Original fix: <ORIGINAL-PR-URL>

       ## Changes
       Cherry-picked from <source-branch> (<N> commits).
       ```

5. **Post-PR bookkeeping**
   - If this is the first backport for this bug (no `cascade_task_key` in preflight data), create the cascade task:
     ```
     task_add:
       external_key: "backport:<ORIGINAL-BUG-KEY>"
       status: "in_progress"
       source_type: "jira"
       repo: <repo>
       metadata:
         original_bug: <ORIGINAL-BUG-KEY>
         bug_summary: <summary>
         bug_labels: [<labels>]
         bug_component: <component>
         target_versions: [<all target versions from preflight>]
         completed: [<this version>]
         delegated: []
         clone_keys: {"<this version>": "<CLONE-BUG-KEY>"}
     ```
   - If cascade task already exists (`cascade_task_key` in preflight data):
     - Read the current task via `task_get`
     - Append this version to `metadata.completed`
     - Add this version's clone key to `metadata.clone_keys`
     - If `metadata_healed` is true in preflight data, also update `repo`, `bug_summary`, `bug_labels`, `bug_component` from the preflight values
     - Write back the full metadata via `task_update`
   - If all versions are now completed or delegated, remove the cascade task:
     ```
     task_rm:
       external_key: "backport:<ORIGINAL-BUG-KEY>"
     ```
   - Add Jira comment on clone bug with the PR link.
   - Add Jira comment on the ORIGINAL bug: `Backport PR for <version> opened: <PR-URL> (<CLONE-KEY>)`

### Action: Conflicted Cherry-Pick (Delegation)

When preflight says cherry-pick has CONFLICTS:

1. **Clone the Jira bug** (same as clean flow step 1)
   - Same fields as clean flow (labels already include `rehor-ai-pixaa` and `repo:*` for dev agent maintenance).

2. **Add delegation comment on the clone bug**
   ```
   Cherry-pick from <source-branch> to <release-branch> has merge conflicts.

   Original fix: <ORIGINAL-PR-URL> (main)
   Source for cherry-pick: <source-branch>
   Commits to cherry-pick: <sha1>, <sha2>, ...

   Conflicting files: <file1>, <file2>, ...

   Please resolve the conflicts and open a PR targeting <release-branch>.
   ```

3. **Comment on the ORIGINAL bug**
   - `Backport to <version> has conflicts. Delegated to dev agent: <CLONE-KEY>`

4. **Link bugs** (same direction as clean flow step 1 — clone is blocked by upstream bug)

5. **Track delegation**
   - If first backport (no `cascade_task_key`), create cascade task (same as clean flow step 5), with this version in `delegated` instead of `completed`, and its clone key in `clone_keys`.
   - If cascade task exists:
     - Read the current task via `task_get`
     - Append this version to `metadata.delegated`
     - Add this version's clone key to `metadata.clone_keys`
     - Write back the full metadata via `task_update`
   - If all versions are now completed or delegated, remove the cascade task:
     ```
     task_rm:
       external_key: "backport:<ORIGINAL-BUG-KEY>"
     ```

## Rules

### One action per cycle
Process exactly one backport version for one bug per cycle. This keeps cycles short and lets preflight re-evaluate state each time.

### Ordering
Always process the newest unhandled version first. Preflight enforces this ordering.

### Cherry-pick source
- First backport (highest version): cherry-pick from main
- Cascade (lower versions): cherry-pick from the most recently completed release branch
- This ensures reviewer modifications on higher-version backport PRs cascade down

### Bug cloning field correctness
After cloning a bug, verify these fields are set:
- Target Version matches the z-stream version (e.g. 4.22.z, NOT 4.22)
- Component matches the original bug
- `is blocked by` link points to the next-newest version's bug (or original bug for the highest version)

### What NOT to do
- NEVER apply `backport-risk-assessed`, `cherry-pick-approved`, or `lgtm` labels
- NEVER approve or merge PRs
- NEVER decide what should be backported — humans set Target Backport Versions during triage
- NEVER modify existing backport PRs opened by humans
- NEVER touch versions that already have a backport PR or delegated bug

### Duplicate PR detection
Before creating a PR, check if one already exists: `gh pr list --repo <upstream> --base <release-branch> --search <bug-key>`
If found, skip and move on.

### Error handling
- Cherry-pick failed unexpectedly: switch to delegation flow
- Push failed: log error, stop cycle
- Jira API error: retry once, then stop cycle
- Duplicate PR detected: skip version, move on
