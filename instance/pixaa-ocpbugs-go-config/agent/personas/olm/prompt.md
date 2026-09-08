OLM persona — Operator Lifecycle Manager / operator-framework family. Go 1.26.x across the family. Read the in-repo `AGENTS.md` (present in operator-controller and the OLM monorepo) first — it is authoritative.

## Repos & where work happens

- **openshift/operator-framework-operator-controller** — active OpenShift downstream (OLMv1). Now also hosts catalogd code (under `catalogd/`). Vendored.
- **openshift/operator-framework-olm** — active OpenShift downstream **monorepo**. Contains `staging/{api,operator-lifecycle-manager,operator-registry}` synced from upstreams via `scripts/sync_pop_candidate.sh`; each staging dir has its own nested go.mod/vendor. Changes usually land upstream first, then are "popped" downstream. Vendored (+ nested).
- **operator-framework/operator-registry**, **operator-framework/operator-marketplace**, **operator-framework/operator-sdk** — community upstreams (the `openshift/` variants are 404 / empty stubs — do not target them). registry & sdk are NOT vendored; marketplace is vendored.
- Do **not** target `openshift/operator-framework-catalogd` (stale/dead — catalogd lives in operator-controller).

## Commands (quote the repo's real targets; they differ)

**operator-controller** (vendored, `-mod=vendor`):
- Unit: `make test-unit` (uses envtest — run `make envtest-k8s-bins` / setup-envtest first; `CGO_ENABLED=1`).
- Lint: `make lint` (golangci-lint + custom linter + kube-api-linter; `make fix-lint` to autofix).
- Codegen: `make manifests` + `make generate` (controller-gen + mockgen). `make verify` (tidy, fmt, generate, manifests, tls-profiles, crd-ref-docs, bingo).
- e2e: `make test-e2e` (spins its own **kind** cluster; needs `fs.inotify.max_user_instances` raised) — rely on CI.
- ⚠️ Do NOT run `make test` for the pre-PR gate — it runs the full chain including `test-e2e`/`test-regression` (kind cluster). Use `make test-unit` for the gate.

**operator-framework-olm** (monorepo, vendored + nested):
- Unit: `make unit` (`scripts/unit.sh`). Build: `make build` (opm + olm binaries).
- Gate: `make verify` = verify-vendor + verify-manifests + verify-nested-vendor + **verify-commits** (`scripts/verify_commits.sh` — commit form is enforced in-tree here).
- Codegen: `make generate-manifests`; keep nested staging vendor in sync (`make vendor`, `check-staging-vendor.sh`).
- e2e: `make e2e` (`scripts/e2e.sh`; `e2e/olm`, `e2e/operator-registry`) — needs a real cluster (`oc`), `E2E_TIMEOUT=135m`.

**operator-registry** (NOT vendored): `make unit`, `make lint` (golangci-lint), `make verify` (tidy + codegen + `git diff --exit-code`), `make generate-fakes`. `make e2e` (ginkgo) needs a cluster — CI-only.
**operator-marketplace** (vendored): `make unit` / `make unit-test`, `make vendor`, `make manifests`. `make e2e` / `make e2e-job` need a cluster — CI-only.
**operator-sdk** (NOT vendored): `make test-unit`, `make test-static` (sanity+unit+docs), `make lint`, `make generate`. `make test-e2e*` (kind + kuttl scorecard) needs a cluster — CI-only. Uses changelog fragments (`changelog/fragments/*.yaml`) — add one for user-facing changes.

## Style / conventions

- **PR title & Jira depend on the target repo:**
  - OpenShift downstream (operator-controller, operator-framework-olm) → prefix `OCPBUGS-XXXX: <title>` (Prow `jira` plugin enforces valid-bug; legacy `Bug OCPBUGS-XXXXX:` is deprecated). operator-framework-olm also runs `make verify-commits`.
  - operator-framework upstream (registry, marketplace, sdk) → community style, **no Jira prefix**; follow the repo's `.github/PULL_REQUEST_TEMPLATE.md`, reference `Closes #<issue>`, and **DCO sign-off is required** (`git commit -s`).
- **Codegen is load-bearing everywhere** — run the repo's generate/manifests/fakes target before committing; `verify` does `git diff --exit-code`, so stale generated files fail CI.
- Keep vendor/nested-vendor and generated-code churn in their own commits.
- golangci-lint is the linter for operator-controller, registry, sdk; operator-framework-olm & marketplace rely on gofmt/go vet in their scripts.
- Merge is via OpenShift Prow / community reviewers per `OWNERS` — do not self-merge.
