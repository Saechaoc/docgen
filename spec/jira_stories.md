# DocGen Jira Stories (Remaining)

> Stories are ordered by the recommended completion sequence and formatted per the prompt template guidance. All prior milestones are complete; only the work listed below remains.

---

## Story S-032 — No-Hallucination Validation
- **Status:** ☐ Not started
- **Story Text:** Introduce a validation layer that rejects README content containing facts not backed by analyzer signals or RAG context, surfacing actionable errors to users.
- **Dependencies already completed:** S-031 (guardrailed execution), S-011 (RAG contexts)
- **Constraints:**
  - Validation must run after section rendering but before writing files or publishing PRs.
  - Provide clear remediation logs referencing the missing signals and affected sections.
  - Allow an opt-out toggle in `.docgen.yml` for edge cases.
- **Non-Goals:** External API calls or complex semantic similarity checks.
- **Acceptance Criteria:**
  - Validator cross-references generated claims against available signals/context; disallowed content triggers a failure path with stub fallback.
  - Unit tests cover acceptance of grounded content and rejection of injected hallucinations.
  - CLI surfaces concise error messages and `--verbose` logs list offending sections and missing evidence.

## Story S-033 — Analyzer Artifact Persistence
- **Status:** ☐ Not started
- **Story Text:** Persist analyzer outputs alongside embeddings so repeated runs can reuse structured signals without reprocessing unchanged files.
- **Dependencies already completed:** S-003 (Repo scanner), S-020 (embedding cache groundwork)
- **Constraints:**
  - Store artifacts under `.docgen/` with versioning to handle schema changes.
  - Refresh analyzer results incrementally based on file hashes and invalidate when analyzers change.
  - Keep storage format JSON-serializable and human-auditable.
- **Non-Goals:** Remote cache backends or cross-repo sharing.
- **Acceptance Criteria:**
  - Analyzer outputs saved and reloaded during orchestrator runs, skipping recomputation when inputs unchanged.
  - Integration tests demonstrate speed-up by reusing cached signals and correct invalidation when files mutate.
  - Documentation in `spec/spec.md` updated to reflect artifact caching behavior.

## Story S-034 — Service Mode & Extended Runtimes
- **Status:** ☐ Not started
- **Story Text:** Deliver FastAPI-based service mode, llama.cpp runtime adapter, and tree-sitter powered symbol extraction to round out stretch goals.
- **Dependencies already completed:** S-010 (Git publishing infrastructure), S-017 (entrypoint detection groundwork)
- **Constraints:**
  - FastAPI service must expose endpoints for init/update/dry-run with authentication disabled by default but ready for future hardening hooks.
  - llama.cpp adapter should mirror `LLMRunner` interface and enforce local execution paths.
  - Tree-sitter integration limited to supported languages (Python/Java/TypeScript) with graceful degradation when parsers unavailable.
- **Non-Goals:** Production deployment tooling or advanced queueing.
- **Acceptance Criteria:**
  - Service mode passes end-to-end tests invoking FastAPI routes and reusing orchestrator logic.
  - llama.cpp adapter covered by unit tests simulating CLI and shared configuration.
  - Tree-sitter analyzer enriches signals with symbol metadata and associated tests validate extraction on fixtures.
  - Updated documentation for service usage and extended runtimes in `docs/` and `spec/spec.md`.

---

**Next Actions:** Execute the stories above sequentially; upon completion reassess remaining stretch goals (knowledge graph, secret scanning) if still in scope.
