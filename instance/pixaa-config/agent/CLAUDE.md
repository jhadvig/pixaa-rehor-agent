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
