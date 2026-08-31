# pixaa-rehor-agent — Additional Instructions

## Target Repos
- **console**: `https://github.com/openshift/console`
- **console-operator**: `https://github.com/openshift/console-operator`

## Detected Tech Stacks
- **openshift/console**: envs=[node, browser, go, patternfly-mcp], personas=[frontend, backend]
- **openshift/console-operator**: envs=[go], personas=[operator]

## Team Conventions

- When maintaining a PR, check if the `jira/valid-bug` or `jira/valid-reference` label is present. If missing:
  1. Comment `/jira refresh` on the PR to trigger validation
  2. Read the `openshift-ci-robot` response to identify which Jira fields are missing or incorrect
  3. Fix the missing fields on the Jira bug (e.g. Fix Version, Target Version, `is blocked by` link direction, status)
  4. Comment `/jira refresh` again to re-validate
- After a PR merges, do NOT move the bug to `Release Pending`. Leave it at `MODIFIED` (set automatically by Prow). The backport agent and Prow's `jira/valid-bug` check depend on this status.
- **Console i18n**: When making changes in `openshift/console` that add or modify user-facing strings wrapped in i18n (`t()`, `<Trans>`, etc.), run `yarn i18n` after the code changes to regenerate all translation files. Commit the regenerated files together with the code change.
- **Console linting**: After making code changes in `openshift/console` frontend (`*.js`, `*.jsx`, `*.ts`, `*.tsx`, `*.json`), run `yarn lint` from the `frontend/` directory to verify the changes pass ESLint. Fix any lint errors before committing.
- **Console Gherkin linting**: When modifying or adding `.feature` files in `openshift/console` (under `packages/*/integration-tests/features`), run `yarn gherkin-lint` from the `frontend/` directory to validate Gherkin syntax. Fix any errors before committing.
