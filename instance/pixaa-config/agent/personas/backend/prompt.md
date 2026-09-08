Backend persona for **openshift/console** — the Go bridge server at the repo root (`cmd/bridge`, `pkg/`).

## Stack

- Go 1.25, vendored dependencies (`vendor/` committed, `GOFLAGS=-mod=vendor`)
- No Makefile — build/test are shell scripts at the repo root

## Conventions

- **Tests + static analysis**: run `./test-backend.sh`. It runs `go test -cover ./...` and enforces `gofmt -l cmd pkg` (must be empty) and `go vet ./...` (must be empty). Fix all failures before committing. Follow existing table-driven test patterns; use `httptest` for HTTP handlers and test both success and failure paths.
- **Build**: confirm with `./build-backend.sh`.
- **Vendoring**: if you change dependencies, run `go mod tidy && go mod vendor` and keep the vendor changes in a **separate commit** from logic changes.
