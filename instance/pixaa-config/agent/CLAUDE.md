# pixaa-rehor-agent — Additional Instructions

## Target Repos
- **console**: `https://github.com/openshift/console`
- **console-operator**: `https://github.com/openshift/console-operator`

## Detected Tech Stacks
- **openshift/console**: envs=[node, browser, go, patternfly-mcp], personas=[frontend, backend]
- **openshift/console-operator**: envs=[go], personas=[operator]

## Team Conventions

- After a PR merges, do NOT move the bug to `Release Pending`. Leave it at `MODIFIED` (set automatically by Prow). The backport agent and Prow's `jira/valid-bug` check depend on this status.
