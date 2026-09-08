# pixaa-rehor-agent — Additional Instructions

## Target Repos
- **console**: `https://github.com/openshift/console`
- **console-operator**: `https://github.com/openshift/console-operator`

## Detected Tech Stacks
- **openshift/console**: envs=[node, browser, go], personas=[frontend, backend] (patternfly-mcp scoped to the frontend persona)
- **openshift/console-operator**: envs=[go], personas=[operator]

## Team Conventions

### General
- When maintaining a PR, check if the `jira/valid-bug` or `jira/valid-reference` label is present. If missing:
  1. Comment `/jira refresh` on the PR to trigger validation
  2. Read the `openshift-ci-robot` response to identify which Jira fields are missing or incorrect
  3. Fix the missing fields on the Jira bug (e.g. Fix Version, Target Version, `is blocked by` link direction, status)
  4. Comment `/jira refresh` again to re-validate
- After a PR merges, do NOT move the bug to `Release Pending`. Leave it at `MODIFIED` (set automatically by Prow). The backport agent and Prow's `jira/valid-bug` check depend on this status.
- If a test fails, `@openshift-ci` will comment that "The following test failed". If the test fails, read the failure details and analyze them. Determine whether they are valid, and fix issues to pass the test if the issue is valid and not a flake.

### Version Management
Match the toolchain to the repo **and the branch** before building or testing — this matters most on `release-X.Y` branches (backports), where the pinned versions differ from `main`. Wrong versions cause spurious build/test failures.
- **Go**: read the `go` directive in the repo's `go.mod` and switch to it before running `make` / `go test` (`main` is Go 1.25; older release branches pin older Go). Use `goenv` / `use-go <version>` where available.
- **Node**: read `engines.node` (and `.nvmrc` if present) in `frontend/package.json` and `nvm use` the matching version (console needs Node >= 22). Enable Corepack (`corepack enable`) so the pinned Yarn 4 is used.

Per-stack build, test, lint, and i18n commands live in the active persona
(`personas/{frontend,backend,operator}/prompt.md`) — the persona for the
component being worked on is loaded alongside this file. Keep stack-specific
commands there, not here.

## Definition of Done

Before the bot opens a PR, **all** of the following must be true. Do not open (or take out of draft) a PR until every applicable item passes. Run the concrete build/test/lint/i18n commands from the active persona.

### Code quality
- [ ] All relevant **unit** tests pass (run the active persona's unit-test command). **Do not run e2e or cluster-dependent integration suites as part of this gate** — they require a live cluster and are left to CI (`@openshift-ci`).
- [ ] Linting and formatting are clean (eslint/prettier for frontend, `gofmt`/`go vet` for Go) with no new warnings.
- [ ] i18n keys are extracted where applicable and the regenerated locale files are committed (no CI diff).
- [ ] PatternFly components are used correctly — prefer PatternFly components over raw HTML for standard UI patterns.
- [ ] The diff contains **no unrelated changes** — no stray formatting, debug output, or vendored-dep churn mixed with logic. Vendor bumps go in their own commit.

### Jira & PR hygiene
- [ ] Commit message: subject describes *what* changed prefixed with the Jira key, body explains *why* — e.g. `OCPBUGS-XXXX: <description>`.
- [ ] PR title is prefixed with the Jira key: `OCPBUGS-XXXX: <summary>` for bugs (or `CONSOLE-XXXX: <summary>` for stories). This is a hard merge requirement enforced by Prow.
- [ ] PR description follows the repo template: root-cause/analysis, solution description, test setup/cases, and for console UI changes the browser-conformance checklist. Include a link to the Jira bug and a change summary.
- [ ] Jira fields validate: the PR carries `jira/valid-bug` (or `jira/valid-reference`). If missing, comment `/jira refresh`, fix the fields the `openshift-ci-robot` flags, and re-run (see the General section above).
- [ ] Branch is named for the Jira id (`OCPBUGS-####` / `CONSOLE-####`), based on `main`.
