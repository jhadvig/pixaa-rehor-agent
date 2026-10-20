CCO persona — Cloud Credential Operator family: `openshift/cloud-credential-operator` (the operator + `ccoctl` CLI) and `openshift/azure-workload-identity` (AWI webhook/`azwi` CLI).

## Stack

- Go operators, vendored, merged via OpenShift Prow (OWNERS-based `/lgtm` + `/approve`; do not self-merge). Treat each repo's `OWNERS` as the authoritative merge gate — for azure-workload-identity ignore the upstream GitHub-native `CODEOWNERS`.
- **cloud-credential-operator:** Go 1.26, uses vendored `openshift/build-machinery-go` make library. Multi-cloud provider implementations under `pkg/{aws,azure,gcp,ibmcloud,kubevirt,openstack,ovirt,vsphere}/` — one test suite covers all providers. Ships `ccoctl` (off-cluster STS/OIDC credential CLI, `cmd/ccoctl/`). Has `AGENTS.md` + `.ai/README.md` at root — read them first (they define the Manual/Mint/Passthrough operator modes and the commit rule).
- **azure-workload-identity:** Go 1.24 (build with 1.24 semantics even though CI build-root is golang-1.26), kubebuilder/controller-runtime, hand-written Makefile. Go module path stays `github.com/Azure/azure-workload-identity` (upstream path preserved in the fork). Binaries: `azwi` CLI (`cmd/azwi/`), `webhook`, `proxy`.

## Commands

### cloud-credential-operator (run from repo root; build-machinery, `-mod=vendor`)
- **Unit tests:** `make test` (alias `test-unit`; `./pkg/... ./cmd/...`, e2e excluded).
- **Pre-PR gate:** `make verify` — `verify-gofmt`, `verify-govet`, `verify-golang-versions`, `verify-vendored-crds`, `verify-codegen`, `verify-bindata`. Does `git diff --exit-code` on generated output, so stale generated files fail it. **No golangci-lint here** — linting is gofmt + `go vet` only.
- **Codegen (after API/manifest/bindata changes):** `make update` (`update-vendored-crds update-codegen update-bindata generate`; controller-gen pinned v0.2.5). Then re-run `make verify`.
- **Build:** `make build`. `ccoctl` builds via `go build ./cmd/ccoctl`.
- **e2e (needs a live cluster + cloud creds):** `make test-e2e-sts` (AWS STS), `make test-e2e-azident` (Azure workload identity). Tagged `//go:build e2e`; rely on CI, don't run in-container.
- **Vendoring:** `make update-go-modules*` (`go mod tidy` + `go mod vendor`); vendor churn in its own commit.

### azure-workload-identity (run from repo root)
- **Unit tests:** `make test` (runs `generate manifests` then `go test -v ./... -coverprofile cover.out`).
- **Lint:** `make lint` (`golangci-lint run`; also `make lint-full`, `make helm-lint`, `make shellcheck`). `make fmt` / `make vet` available.
- **Codegen:** `make generate` + `make manifests` (controller-gen, mockgen) — re-run and commit after API changes.
- **Build:** `make manager` / `make proxy` / `make bin/azwi`.
- **e2e (needs a cluster):** `make test-e2e-run` (Ginkgo against `$KUBECONFIG`); `make test-e2e` is the full kind-based CI flow (Docker/kind/helm) — rely on CI.

## Style / conventions

- **PR title & Jira:** these are OCPBUGS-flow repos. For a bug PR, prefix the title with `OCPBUGS-XXXX: <summary>` (current Jira form; the legacy `Bug OCPBUGS-XXXXX:` / `Bug 1234567:` forms are deprecated — do not use them). The documented in-repo style is `<Subsystem>: <Title>` (e.g. `ccoctl: Add support for new region`) — combine as `OCPBUGS-XXXX: <subsystem>: <title>` when a Jira is linked.
- **AI attribution:** add a commit footer `Assisted-by: <AI model name>` when AI assisted.
- Submission checklist (both): run codegen (`make update` / `make generate manifests`), `make test`, and (CCO) `make verify` before opening the PR.
- Keep vendored-dep and generated-code churn in separate commits from logic changes.
