# PIXAA Rehor Instance Authoring Playbook

A reusable reference for building and refining a PIXAA Rehor bot instance. Written to be
portable — it makes no assumptions about whether each instance grouping lives in its own
repo or as another `instance/<name>-config` directory in a shared repo.

Derived from building the Console instance (CONSOLE-5492) and reviewing four peer Rehor
instances (see [Peer reference instances](#peer-reference-instances)).

---

## 1. How the bot reads config (context-assembly model)

Understanding this is the whole game — it dictates where each piece of guidance belongs.

- The runbook the bot runs on is assembled as **`core/CLAUDE.md` + `workflow/CLAUDE.md` + instance `CLAUDE.md`**. The instance file is combined per `claude_md.strategy` in `instance.yaml`:
  - `append` (what we use) — instance CLAUDE.md is appended after the workflow's
  - `replace` — instance CLAUDE.md replaces the workflow's
  - `ignore` (default) — instance CLAUDE.md is not used
- **One persona is selected per task**, by the component/repo being worked. Personas
  *extend* CLAUDE.md with tech-stack specifics — they are a separate per-task layer, not
  part of the assembled CLAUDE.md.
- **MCP servers layer**: instance `mcp.json` + the active persona's `mcp.json`.

### The layering rule (one source of truth per fact)

| Tier | Content | Home |
|------|---------|------|
| **1 — Generic** | DoD skeleton, PR-title/commit format, version management, OOM rules, Jira/PR workflow | Ideally the **shared base engine** (`OpenShift-Fleet/rehor`) so every instance inherits it via `append`. Until then, the instance CLAUDE.md. |
| **2 — Instance cross-cutting** | Target repos, general workflow deltas, DoD checklist, one copy of commit/PR conventions | Instance **CLAUDE.md** (thin) |
| **3 — Per-stack** | Build/test/lint/i18n commands, stack description, memory/OOM guardrails, stack-scoped MCP | The matching **persona** |

**Do not duplicate a fact across tiers.** Because CLAUDE.md and the active persona co-load,
restating commands in both bloats context and drifts. Keep per-stack commands in personas;
keep the DoD checklist intent-level (reference "the active persona's commands", don't
re-spell flags).

---

## 2. Instance anatomy

```
instance/<name>-config/agent/
├── instance.yaml            # workflow, source, envs, claude_md strategy
├── CLAUDE.md                # cross-cutting instructions (thin — see §1)
├── mcp.json                 # instance-wide MCP servers (usually just Jira)
├── project-repos.json       # fork → upstream map for every managed repo
├── personas/
│   └── <persona>/
│       ├── prompt.md        # per-stack playbook (commands live here)
│       └── mcp.json         # persona-scoped MCP servers
└── skills/                  # custom skills (often empty; shared skills come from engine)
```

Supporting files at repo root: `.gitmodules` (dev-bot submodule → the shared Rehor engine),
`deploy/template.yaml` (OpenShift deploy), `.tekton/` (Konflux build), `setup.sh`
(build-time hook), `README.md`.

---

## 3. `instance.yaml`

```yaml
workflow: jira-kanban        # or jira-sprint; or a custom ./workflows/<name> for scheduled bots
source: jira                 # or scheduled (for triage/quality/manager bots)
envs:                        # enabled stacks/tooling presets provided by the engine
  - node
  - browser
  - go
claude_md:
  strategy: append           # append instance deltas over base — do not fork the base CLAUDE.md
```

Notes:
- Prefer `append` and keep the instance CLAUDE.md as deltas. Reserve `replace` for a bot
  that genuinely needs a different runbook.
- Scope MCP tooling that only one stack needs (e.g. PatternFly, chrome-devtools) to the
  **persona**, not to instance-wide `envs`. See §7.

---

## 4. Instance `CLAUDE.md` — what belongs

Keep it thin. Recommended sections:

1. **Target Repos** and **Detected Tech Stacks** (repo → envs/personas map).
2. **General workflow** — the OpenShift/Jira mechanics that apply to every stack:
   - `jira/valid-bug` / `jira/valid-reference` handling: comment `/jira refresh`, read the
     `openshift-ci-robot` response, fix the missing Jira fields, re-run.
   - Post-merge bug status handling (e.g. leave at `MODIFIED`, set by Prow).
   - Test-failure triage (read `@openshift-ci` failure, decide valid vs. flake, fix).
3. **Version Management** — see snippet in §8.
4. **Definition of Done** — the pre-PR gate; see §5.
5. A one-line pointer that per-stack commands live in the active persona.

Do **not** put per-stack build/test/lint commands here — they belong in personas.

---

## 5. Definition of Done (template)

A pre-PR gate. Keep items intent-level; the concrete commands live in the active persona.

```markdown
## Definition of Done
Before opening (or un-drafting) a PR, all applicable items must pass. Run the concrete
build/test/lint/i18n commands from the active persona.

### Code quality
- [ ] All relevant tests pass — unit, plus integration/e2e where the change touches them.
- [ ] Linting and formatting clean (per-stack linters), no new warnings.
- [ ] i18n keys extracted where applicable; regenerated locale files committed (no CI diff).
- [ ] UI: framework components used correctly (prefer the design system over raw HTML).
- [ ] No unrelated changes in the diff; vendor/dependency bumps in their own commit.

### Jira & PR hygiene
- [ ] Commit message: subject = what (Jira-prefixed, e.g. `OCPBUGS-XXXX: ...`), body = why.
- [ ] PR title prefixed with the Jira key (`OCPBUGS-XXXX:` bug / `CONSOLE-XXXX:` story) —
      hard merge requirement enforced by Prow.
- [ ] PR description follows the repo template; links the Jira issue + change summary.
- [ ] PR carries `jira/valid-bug` (or `jira/valid-reference`); if not, `/jira refresh`.
- [ ] Branch named for the Jira id, based on the repo's default branch.
```

---

## 6. Personas

- **Key personas by task/repo type** (e.g. `frontend`, `backend`, `operator`, and where
  relevant `config`, `cve`, `tooling`), not by individual app. One loads per task.
- Each persona owns: a short **Stack** description, the **per-stack commands**
  (build/test/lint/i18n, with real script/target names and versions), any **memory/OOM
  guardrails**, and stack-specific **style** rules.
- **No overlap with CLAUDE.md.** Conventions that apply to all stacks (commit/PR format)
  live once in the DoD, not repeated per persona.
- Give a persona its own `mcp.json` when it needs stack-specific tools (§7).

Reference the ground truth: derive commands from the target repo's actual
`package.json`/`Makefile`/scripts and CONTRIBUTING docs, not from generic assumptions.

---

## 7. Per-persona MCP scoping

Load stack-specific MCP servers only for the persona that needs them, instead of enabling
them instance-wide. Example — PatternFly docs only for the frontend persona:

`personas/frontend/mcp.json`
```json
{
  "mcpServers": {
    "patternfly-mcp": {
      "command": "npx",
      "args": ["-y", "@patternfly/patternfly-mcp@latest"],
      "description": "PatternFly rules and documentation"
    }
  }
}
```

For visual verification, peers also scope a `chrome-devtools` MCP to the frontend persona
(`command: chrome-devtools-mcp`, `--browserUrl http://127.0.0.1:9222`).

The instance-wide `mcp.json` typically holds only Jira:
```json
{ "mcpServers": { "mcp-atlassian": { "type": "http", "url": "${JIRA_MCP_URL}" } } }
```

---

## 8. Reusable snippets

### Version Management (instance CLAUDE.md)

```markdown
### Version Management
Match the toolchain to the repo AND the branch before building or testing — this matters
most on `release-X.Y` branches (backports), where pinned versions differ from the default
branch. Wrong versions cause spurious build/test failures.
- Go: read the `go` directive in the repo's `go.mod` and switch before `make` / `go test`
  (`goenv` / `use-go <version>`).
- Node: read `engines.node` (and `.nvmrc` if present) and `nvm use` the match; enable
  Corepack (`corepack enable`) so the pinned package manager (e.g. Yarn 4) is used.
```

### Memory / OOM guardrails (persona, esp. frontend)

```markdown
## Memory / resources
The build container has limited memory (bundler builds and Jest are heavy). To avoid OOM:
- Never run build, lint, and test in parallel — run one at a time.
- Run build/test tooling through package-manager scripts, never `tsc` / `jest` directly.
- If Jest OOMs, cap workers: `--runInBand` (or `--maxWorkers=2`).
```

### `project-repos.json` fork/upstream convention

```json
{
  "<repo>": {
    "url": "https://github.com/platex-rehor-bot/<repo>.git",
    "upstream": "https://github.com/<org>/<repo>.git"
  },
  "<gitlab-repo>": {
    "host": "gitlab",
    "url": "https://gitlab.example/<bot>/<repo>.git",
    "upstream": "https://gitlab.example/<org>/<repo>.git"
  }
}
```

The bot pushes to its fork and opens PRs to upstream. Add `"host": "gitlab"` per repo where
needed. Include QE/test-plugin repos alongside services so the bot can update tests in
lockstep with code.

---

## 9. Deploy hardening checklist (`deploy/template.yaml`)

From the peer instances — reuse these:

- **Egress-locked NetworkPolicy** — the bot pod can only reach the shared `devbot-proxy`
  (LLM/Jira/GitHub all brokered through it), the memory server, and DNS. Strong blast-radius
  control for an autonomous agent.
- **KEDA cron ScaledObject** — scale 0→1 only during business hours (weekdays); idle to 0
  otherwise. Cost control + "only act during working hours."
- **Secrets from Vault** (`devbot-secrets`); Vertex/Claude auth brokered by the proxy
  (`CLAUDE_CODE_SKIP_VERTEX_AUTH=true`).
- **Hardened `securityContext`** (runAsNonRoot, drop ALL caps, seccomp RuntimeDefault) and
  modest resource limits.

---

## 10. Scheduled / triage & quality bots (Phase 2)

For non-dev bots (`source: scheduled` + a custom `./workflows/<name>`), reuse these proven
patterns (see hcc-framework's `manager-tasks` and `quality-monitor`):

- **Deterministic Python preflight, LLM only for judgment.** A `00-cycle-sleep.py` time-slot
  pacing table and a `01-*.py` task-dispatch state machine gather GitHub/Jira state and
  inject it into the prompt — zero AI tokens spent deciding whether/what to run, and the
  agent never re-fetches what preflight already provided.
- **Memory-keyed idempotency.** Use `external_key` conventions (e.g.
  `merge-violation:{repo}:{pr}`) via the memory server to prevent duplicate tickets/pings
  across cycles; cap tasks per cycle.
- **`anti-patterns.yaml` catalog.** One entry per anti-pattern with severity, bad/good
  examples, a preventive ESLint rule, and a remediation template — doubles as agent
  detection config and human docs.
- **Security-scan-aware CI gating.** Don't treat vulnerability-scanner job failures as merge
  violations; only flag genuine test/build failures. Ship it with a fixture test suite.
- **Shadow mode first** — validate findings before enabling auto-labeling/ticketing.

---

## 11. Peer reference instances

| Repo | Best for |
|------|----------|
| [RedHatInsights/hcc-framework-agent-dev](https://github.com/RedHatInsights/hcc-framework-agent-dev) | The richest example: multi-instance (dev + scheduled), 8 deep personas, Python preflight, `anti-patterns.yaml`, security-scan gating |
| [RedHatInsights/hcc-ui-agent-dev](https://github.com/RedHatInsights/hcc-ui-agent-dev) | Frontend visual-verification persona (Caddy proxy + SSO + chrome-devtools MCP + screenshot-to-`gh release` + Playwright-in-container) |
| [RedHatInsights/consoledot-integrations-bot](https://github.com/RedHatInsights/consoledot-integrations-bot) | Thin overlay pattern, large GitHub+GitLab fork map incl. IQE test repos, version-management CLAUDE.md |
| [patternfly/react-component-groups-agent-dev](https://github.com/patternfly/react-component-groups-agent-dev) | Minimal starter + a clean deploy/isolation blueprint |

---

## 12. New-instance checklist

- [ ] Scaffold `instance/<name>-config/agent/` with `instance.yaml`, `CLAUDE.md`, `mcp.json`,
      `project-repos.json`, `personas/`, `skills/`.
- [ ] `project-repos.json`: fork → upstream for every managed repo (`host: gitlab` where needed).
- [ ] Pick `workflow`/`source`; set `envs`; `claude_md.strategy: append`.
- [ ] CLAUDE.md: target repos, general workflow, Version Management, DoD, persona pointer — thin.
- [ ] One persona per stack, with real commands derived from each repo's ground truth.
- [ ] Scope stack-specific MCP to personas; keep instance `mcp.json` to Jira.
- [ ] Deploy: egress NetworkPolicy, KEDA business-hours scaler, Vault secrets, hardened securityContext.
- [ ] Verify no fact is duplicated between CLAUDE.md and personas.
- [ ] (Scheduled bots) preflight scripts, memory-keyed idempotency, shadow mode first.
