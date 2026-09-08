# pixaa-ocpbugs-go — Additional Instructions

A Rehor dev-bot instance covering the OCPBUGS Go component families: **OLM /
operator-framework**, **Hive**, **CCO**, and **OTA**. One persona is loaded per
task, selected by the repo being worked — per-stack build/test/lint/codegen
commands live in that persona (`personas/{olm,hive,cco,ota}/prompt.md`), not here.

## Target Repos → persona

- **olm**: `openshift/operator-framework-operator-controller`, `openshift/operator-framework-olm` (monorepo: `staging/{api,operator-lifecycle-manager,operator-registry}`), `operator-framework/operator-registry`, `operator-framework/operator-marketplace`, `operator-framework/operator-sdk`
- **hive**: `openshift/hive` (default branch `master`)
- **cco**: `openshift/cloud-credential-operator`, `openshift/azure-workload-identity`
- **ota**: `openshift/cluster-version-operator`, `openshift/cincinnati` (**Rust**), `openshift/cincinnati-operator`, `openshift/oc`, `openshift/oc-mirror`

Notes:
- The OLM community upstreams (`operator-framework/*` — registry, marketplace, sdk) follow a *different* contribution flow than the openshift downstream repos: no Jira prefix, **DCO sign-off required**, GitHub issues. The `olm` persona spells out the split.
- `openshift/cincinnati` is Rust (Cargo + `Justfile`); the Rust toolchain (`cargo`/`just`) is installed at image-build time via the repo-root `setup.sh`, not an env preset. Everything else is Go.
- Most repos ship an in-repo `AGENTS.md` (some also `CLAUDE.md`) — read it first for the repo; it is authoritative and generally corroborates the persona.

## Team Conventions

### General
- When maintaining a PR, check if the `jira/valid-bug` or `jira/valid-reference` label is present. If missing:
  1. Comment `/jira refresh` on the PR to trigger validation
  2. Read the `openshift-ci-robot` response to identify which Jira fields are missing or incorrect
  3. Fix the missing fields on the Jira issue (e.g. Fix Version, Target Version, `is blocked by` link direction, status)
  4. Comment `/jira refresh` again to re-validate
- After a PR merges, do NOT move the bug to `Release Pending`. Leave it at `MODIFIED` (set automatically by Prow). The backport agent and Prow's `jira/valid-bug` check depend on this status.
- If a test fails, `@openshift-ci` will comment that "The following test failed". Read the failure details and analyze them. Determine whether they are valid, and fix issues to pass the test if the issue is valid and not a flake.
- Merge is via OpenShift Prow / community reviewers per each repo's `OWNERS` — never self-approve or self-merge.

### Version Management
Match the toolchain to the repo **and the branch** before building or testing — Go versions vary across this fleet, and pinned versions differ on `release-X.Y` branches (backports). Wrong versions cause spurious build/test failures.
- **Go**: read the `go` directive in the repo's `go.mod` and switch before `make` / `go test` (`goenv` / `use-go <version>`). Versions in this fleet range from Go 1.22 (`cincinnati-operator`) through 1.25 (`cluster-version-operator`) to 1.26 (most OLM/CCO/oc/oc-mirror). Some repos carry nested modules (Hive's `apis/`, the OLM monorepo's `staging/*`) — sync those too.
- **Rust** (`cincinnati` only): use the repo's pinned toolchain (`rust-toolchain*` if present) with `cargo` / `just`.

Per-stack build, test, lint, and codegen commands live in the active persona
(`personas/{olm,hive,cco,ota}/prompt.md`) — the persona for the component being
worked is loaded alongside this file. Keep stack-specific commands there, not here.

## Definition of Done

Before the bot opens (or takes out of draft) a PR, **all** applicable items must pass. Run the concrete build/test/lint/codegen commands from the active persona.

### Code quality
- [ ] All relevant unit tests pass (e2e/integration where the change touches them — most e2e here needs a live cluster, so rely on CI for those).
- [ ] Linting/formatting clean per the repo's tooling (golangci-lint where the repo has a config; otherwise `gofmt` + `go vet`; `cargo fmt` for cincinnati). No new warnings.
- [ ] **Codegen is current.** After any API/CRD/manifest/bindata change, run the repo's generate target (e.g. Hive `make update`, CCO `make update`, operator-controller `make manifests generate`, CVO `make update`) and commit the result — `make verify` does `git diff --exit-code` and fails on stale generated files.
- [ ] The diff contains **no unrelated changes**. Vendor/dependency and generated-code churn go in their own commits (several repos are vendored; `operator-registry`, `operator-sdk`, `oc-mirror` are not).

### Jira & PR hygiene
- [ ] Commit message: subject = *what* changed, prefixed with the Jira key; body = *why*.
- [ ] PR title is prefixed with the Jira key in the **bare `PROJECT-NUM:` form** — `OCPBUGS-XXXX:` for bugs, or the area project for feature work (`HIVE-XXXX:` for Hive, `OTA-XXXX:` for CVO/Cincinnati/OSUS, `CNTRLPLANE-XXXX:` for `oc`), or `NO-JIRA:` when there is genuinely no ticket. The legacy `Bug OCPBUGS-XXXXX:` / `Bug 1234567:` forms are deprecated. This is a hard merge requirement enforced by the Prow `jira` plugin. The active persona pins the right project per repo.
- [ ] **DCO sign-off** (`git commit -s`) on repos that require it — the `operator-framework/*` community upstreams and `oc-mirror`.
- [ ] AI attribution footer `Assisted-by: <AI model name>` where the repo asks for it (Hive, CCO).
- [ ] PR description follows the repo template; links the Jira issue + change summary.
- [ ] PR carries `jira/valid-bug` (or `jira/valid-reference`); if not, `/jira refresh` (see General above).
- [ ] Branch named for the Jira id, based on the repo's default branch (note Hive uses `master`).
