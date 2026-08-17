# pixaa-backport-agent — Instance Context

## Target Repos

- **console**: upstream `https://github.com/openshift/console` (default branch: `main`)
- **console-operator**: upstream `https://github.com/openshift/console-operator` (default branch: `main`)

## Bot Fork URLs

- console fork: `https://github.com/platex-rehor-bot/console.git`
- console-operator fork: `https://github.com/platex-rehor-bot/console-operator.git`

## Release Branch Convention

Both repos use `release-X.Y` branch naming (e.g. `release-5.0`, `release-4.22`, `release-4.21`).

## Jira Project

All bugs are in the `OCPBUGS` project.
- Both console and console-operator bugs use component: `Management Console`
- Target Backport Versions field: `customfield_10878` (multi-version picker)

## Team Conventions

- PR title MUST start with `OCPBUGS-XXXXX:` followed by the bug summary
- Commit messages: `Bug OCPBUGS-XXXXX: <description>`
- Backport PRs target the `release-X.Y` branch on the upstream repo
- Use `/jira cherrypick OCPBUGS-XXXXX` in PR body to trigger automatic bug linking by Prow
- Do NOT apply `backport-risk-assessed`, `cherry-pick-approved`, or `lgtm` labels
- Do NOT approve or merge PRs — leave for human z-stream approver review
