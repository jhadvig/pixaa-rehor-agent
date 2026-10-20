OTA persona — Over-The-Air updates family: cluster-version-operator (CVO), cincinnati (OSUS, **Rust**), cincinnati-operator (OSUS operator), oc (the OpenShift CLI), oc-mirror. Every Go repo here ships an `AGENTS.md` (CVO and oc also a `CLAUDE.md`) — read it first; it is the highest-signal source and corroborates the commands below.

## Repos, languages & versions

- **openshift/cluster-version-operator** — Go 1.25.7, vendored.
- **openshift/cincinnati** — ⚠️ **Rust**, not Go. Cargo workspace driven by a `Justfile` (no Makefile / go.mod). The image ships a Rust toolchain (installed at build time by the repo-root `setup.sh`): `cargo`, `rustc`, and `just` are on PATH. Use those, never Go tooling, for this repo.
- **openshift/cincinnati-operator** — Go **1.22.0** (older than the rest — match the toolchain), Operator-SDK, vendored.
- **openshift/oc** — Go 1.26 (tracks k8s v1.36.2), large & vendored, build-machinery.
- **openshift/oc-mirror** — Go 1.26.3, **NOT vendored** (`-mod=readonly`); current code is v2 in `internal/pkg/` (legacy v1 under `v1/`).

## Commands (per repo — targets differ)

**cluster-version-operator** (vendored):
- Unit: `make test` (gotestsum over all pkgs except `test/`). Build: `make build` (`hack/build-go.sh`).
- Format: `make format` (`go fmt`) + `make imports` (`gci` with custom ordering: std, default, `k8s.io`, `github.com/openshift`, local). Gate: `make verify` (verify-yaml + verify-update — checks generated files current). `make update` regenerates. No golangci-lint.
- Integration: `make integration-test` (`TEST_INTEGRATION=1`, needs admin KUBECONFIG on a disposable cluster) — rely on CI.
- Note: `lib/resourcebuilder`, `lib/resourceread` are auto-generated (`hack/generate-lib-resources.py`) — don't hand-edit.

**cincinnati (Rust):** `just test` (fmt check + `cargo test --all`); `just commit` runs fmt first; `just run-e2e` spins the full local stack (~180s) — rely on CI. Network tests gated behind cargo features `test-net`/`test-net-private`.

**cincinnati-operator** (vendored, `-mod=vendor`):
- Unit: `make unit-test` (`go test ./controllers/...`). Build: `make build`.
- `make fmt` / `make vet` (no golangci-lint). Codegen: `make manifests` + `make generate` (controller-gen); `make verify-generate` (= manifests generate fmt vet); `make bundle`.
- Functional: `make func-test` (needs a cluster + `GRAPH_DATA_IMAGE`) — rely on CI.

**oc** (vendored, build-machinery; build tags `include_gcs include_oss containers_image_openpgp gssapi`):
- Unit: `make test` (= `test-unit`, `go test -race`). Build: `make build` (or `make oc` for just the CLI); `make cross-build` for all platforms.
- Gate: `make verify` (verify-gofmt, verify-govet, verify-golang-versions, verify-cli-conventions, verify-generated-completions, verify-kube-version). `make update` (regenerates completions). Lint = gofmt + go vet (no golangci-lint).
- Flags use hyphens, not underscores; follow Kubernetes code conventions.

**oc-mirror** (NOT vendored, `-mod=readonly`; build tags `json1 btrfs libdm libsubid`):
- Unit: `make test-unit` (`go test -short -race ./internal/pkg/...`). Build: `make build`.
- Gate: `make verify` (**golangci-lint** `-c .golangci.yaml` — the only OTA repo with a real golangci config). `make sanity` (tidy+format+vet), `make tidy`.
- Integration: `make test-integration` / `make test-integration-cli`; e2e in `tests/e2e/` (own go.mod/Makefile) needs a cluster — CI-only.

## Style / conventions

- **PR title & Jira (Prow jira plugin, org-wide):** prefix with the Jira key `<PROJECT>-<NUM>: <summary>`, or `NO-JIRA:` when there is genuinely no ticket. Projects by area: **OCPBUGS** for bugs (all repos); **OTA** for CVO/Cincinnati/OSUS feature work; **CNTRLPLANE** (or OCPBUGS) for `oc`. Use the bare key form — the legacy `Bug OCPBUGS-XXXXX:` / `Bug 1234567:` forms are deprecated.
- **CVO commit body:** `<subsystem>: <what>` subject (≤70 chars) + blank line + why + footer; coordinate reviews in `#forum-ocp-updates` (no auto reviewer assignment).
- **DCO sign-off:** oc-mirror requires signed commits (`git commit -s`); apply it there.
- **Codegen is load-bearing** (CVO `make update`, cincinnati-operator `make manifests generate`, oc `make update`) — run it before committing; verify does diff checks that fail on stale output.
- Keep vendor/generated churn in its own commit. Merge via OpenShift Prow / `OWNERS` — do not self-merge.
- **Domain:** CVO reconciles the release payload → `ClusterVersion` status and fetches the upgrade graph via `pkg/cincinnati/`; the actual channel/edge data lives in a separate repo `openshift/cincinnati-graph-data`. cincinnati-operator reconciles the `UpdateService` CR (supports disconnected/air-gapped). oc-mirror mirrors release/operator content for disconnected installs.
