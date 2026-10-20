Hive persona — OpenShift Hive (`openshift/hive`), the operator that provisions and manages OpenShift clusters as a service.

## Stack

- Go 1.26, controller-runtime / kubebuilder operator. Default branch is `master` (not `main`).
- Vendored (`vendor/` committed; build/test run with `-mod=vendor`).
- **Nested module:** `apis/` is a *separate* Go module (`github.com/openshift/hive/apis`) wired via `replace`. Vendor, vet, and modcheck all treat it as a submodule — changes to API types must be synced there too.
- The repo ships its own `AGENTS.md` at the root written for AI agents — read it and follow it; it is the authoritative in-repo guidance.

## Commands

Run from the repo root. Vendored, so `GOFLAGS=-mod=vendor` is implied by the Makefile.
- **Unit tests:** `make test` (alias `test-unit`; `go test -race` over `./pkg/... ./cmd/... ./contrib/...` plus the `apis/` submodule). Excludes e2e.
- **Pre-PR gate:** `make verify` — the real gate. Runs `verify-gofmt`, `verify-govet` (+ submodule), `verify-golang-versions`, `verify-lint` (golint), `verify-crd`, `verify-codegen`, `verify-vendor`, `verify-app-sre-template`. Several sub-checks do `git diff --exit-code`, so stale generated/vendored files fail it.
- **Codegen (after ANY API change):** `make update` — regenerates CRDs (`make crd`/`manifests` via controller-gen into `config/crds`) and deepcopy/client codegen (`hack/update-codegen.sh`), plus operator go-bindata under `pkg/operator/assets/bindata.go`. Run this, then `make verify`, whenever you touch `apis/hive/v1` or `apis/hiveinternal/v1alpha1` or anything under `config/**`.
- **Vendoring:** `make vendor` (`go mod tidy && go mod vendor` for root + `apis/`); `make modcheck` / `make modfix` keep the two modules' versions aligned. Vendor churn goes in its own commit.
- **Lint (optional):** `make lint` — `golangci-lint run -c ./golangci.yml`. Deliberately NOT part of `verify` (CI cache-permission issue), but run it locally when practical.
- **Build:** `make build` (binaries into `bin/`). `make all` = `vendor update test build`.
- **e2e:** `make test-e2e` (and `test-e2e-pool`, `-postdeploy`, etc.) — REQUIRE a live cluster + cloud creds (provision→destroy real ClusterDeployments). Do not run in-container; rely on CI.

## Style / conventions

- **PR title & Jira:** Hive tracks work in the Jira **HIVE** project, NOT OCPBUGS. Title format is `<Subsystem>: <Title>`, in practice `HIVE-<number>: <summary>` (e.g. `HIVE-2980: Refresh ClusterPool cloud creds`). Do **not** use `OCPBUGS-XXXX:` or the legacy `Bug OCPBUGS-XXXXX:` form here.
- **AI attribution:** when AI assisted the change, add a commit footer `Assisted-by: <AI model name>`.
- No `.github/PULL_REQUEST_TEMPLATE.md`; merge is standard OpenShift Prow (`/lgtm` + `/approve`) — do not self-approve/merge.
- Follow controller-runtime reconciler patterns. Controllers live under `pkg/controller/<name>`; the core `ClusterDeployment` lifecycle spans clusterprovision/clusterdeprovision, clusterpool/clusterclaim, hibernation, machinepool, clustersync (SyncSet), dnszone, and more. Cloud clients are in `pkg/{awsclient,azureclient,gcpclient,ibmclient}`.
- Provisioning drives `openshift-install` via `pkg/install` / `pkg/installmanager`.
