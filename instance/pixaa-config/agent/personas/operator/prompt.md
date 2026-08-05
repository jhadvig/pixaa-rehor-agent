Operator persona for Kubernetes/OpenShift operators.

## Stack

- Go + controller-runtime / operator-sdk
- CRDs and reconciliation loops

## Conventions

- `make test` for unit tests, `make e2e` for integration
- Follow controller-runtime patterns for reconcile logic
- Conventional commits: `fix(scope): description`
