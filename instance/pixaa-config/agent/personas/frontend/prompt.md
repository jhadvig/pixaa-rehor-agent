Frontend persona for **openshift/console** — the React/PatternFly console UI in `frontend/`.

## Stack

- React 18 + TypeScript (tsconfig `strict: false`, `noUnusedLocals: true`)
- PatternFly **v6** (`@patternfly/react-core`, `-react-table`, `-react-icons`, `-react-tokens`, `-react-topology` ~6.6.x; `-react-charts` v8)
- rspack bundler (type-checking runs during build via `ts-checker-rspack-plugin`)
- Jest 30 (`@swc/jest`) for unit tests; Cypress + Cucumber for existing integration tests, Playwright for new e2e (active Cypress→Playwright migration)
- **Yarn 4** (`yarn@4.14.1`, Node >= 22) — never `npm`

## Memory / resources

The build container has limited memory (rspack builds and Jest are heavy). To avoid OOM:
- Never run build, lint, and test in parallel — run one at a time.
- Run build/test tooling through `yarn` scripts, never `tsc` / `jest` (or `npx tsc`/`npx jest`) directly.
- If Jest OOMs, cap workers: `yarn test --runInBand` (or `--maxWorkers=2`).

## Conventions

- Run everything from `frontend/`.
- **Tests**: unit test files are `*.spec.{ts,tsx,js,jsx}`. Run with `yarn test <path>` (or `yarn test --findRelatedTests <changed file>`). Cypress+Cucumber integration and Playwright e2e need a running console against a live cluster — do NOT run them as part of the pre-PR gate; leave them to CI.
- **Lint/format**: `yarn lint` (ESLint runs Prettier as a rule; respect the exact `MAX_WARNINGS` baseline — no new warnings). Prettier: single quotes, trailing commas, `printWidth: 100`, `arrowParens: always`.
- **i18n**: after touching user-facing strings, run `yarn i18n` and commit regenerated `public/locales` / `packages/**/locales`. `t()` keys must be plain strings (no template literals). CI fails on any i18n diff.
- **Gherkin**: run `yarn gherkin-lint` after editing `.feature` files.
- **Import cycles / dead code**: if you add or move modules, run `yarn check-cycles` and `yarn knip` — both are CI gates.
- **PatternFly first**: use PatternFly components for standard UI patterns instead of raw HTML. Exhaust PatternFly options before custom SCSS; custom SCSS uses BEM with the `co-` prefix.
