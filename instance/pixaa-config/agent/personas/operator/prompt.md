Operator persona for **openshift/console-operator** — a Kubernetes/OpenShift operator in Go.

## Stack

- Go 1.25, vendored dependencies (`GOFLAGS=-mod=vendor`), built with `-tags ocp`
- library-go controllers (`factory.New()...ToController(...)`), incremental `sync_v400` reconcile loops
- CRDs/manifests under `manifests/`; generated bindata + profile-manifests
- No golangci-lint — static analysis is `gofmt` + `go vet`

## Conventions

- **Unit tests + static analysis**: `make test-unit` runs `go test` on `./pkg/... ./cmd/...` and enforces `gofmt -l` and `go vet` (gated here, not in `make verify`). Fix all failures before committing. Use table-driven tests.
- **Verify generated content**: `make verify` checks bindata and profile-manifests are in sync; if it fails, run the matching `make update-*` target and commit the result.
- **Combined gate**: prefer `make check` (`make verify` + `make test-unit`) as the pre-PR check.
- **Build**: `make build`.
- **e2e**: `make test-e2e` needs a live cluster — leave to CI, don't run locally.
- **Vendoring**: on dependency changes run `go mod tidy && go mod vendor`, verify with `make verify-deps`, and keep vendor changes in a **separate commit**.
- **Commits**: keep commits atomic (vendor changes separate, per above).
- **Go style** (per `CONVENTIONS.md`): grouped imports (stdlib, third-party, kube, openshift, internal); status conditions via `status.Handle*` with `*Degraded`/`*Progressing`/`*Available`/`*Upgradeable` suffixes; wrap errors with context.
