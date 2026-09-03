# pixaa-rehor-agent — Additional Instructions

## Target Repos
- **console**: `https://github.com/openshift/console`
- **console-operator**: `https://github.com/openshift/console-operator`

## Detected Tech Stacks
- **openshift/console**: envs=[node, browser, go, patternfly-mcp], personas=[frontend, backend]
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

### openshift/console
All commands below run from the `frontend/` directory.
- **i18n**: When adding or modifying user-facing strings wrapped in i18n (`t()`, `<Trans>`, etc.), run `yarn i18n` to regenerate translation files. Commit the regenerated files together with the code change.
- **Linting**: After modifying frontend source files (`*.js`, `*.jsx`, `*.ts`, `*.tsx`), run `yarn lint`. Fix any lint errors before committing.
- **Gherkin linting**: When modifying or adding `.feature` files (under `packages/*/integration-tests/features`), run `yarn gherkin-lint`. Fix any errors before committing.
- **Unit tests**: After modifying frontend code, run `yarn test --findRelatedTests path/to/changed/File.tsx` (space-separated relative paths for each changed file). Fix any failing tests before committing.

### openshift/console-operator
- **Verify**: After making code changes, run `make verify` to execute static analysis checks. Fix any issues before committing.
- **Unit tests**: After making code changes, run `make test` to execute unit tests. Fix any failures before committing.
