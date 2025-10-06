# DocGen Jira Stories (Remaining)

> Stories are ordered by the recommended completion sequence and formatted per the prompt template guidance. All prior milestones are complete; only the work listed below remains.

---

## Story S-032 — No-Hallucination Validation
- **Status:** ✔ Done
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
- **Implementation Plan:**
  - Create a dedicated `docgen.validators` package with a lightweight `ValidationIssue` dataclass, a `Validator` protocol, and a `NoHallucinationValidator` concrete implementation. The orchestrator registers validators after section rendering and executes them before post-processing or IO.
  - Add a shared `EvidenceIndex` builder that normalizes analyzer signals (names, kinds, key attributes) and retrieved RAG chunks (path, heading, snippet). Persist the normalized evidence in the run context so validators and verbose logging receive the same data.
  - Extend the prompt builder to annotate each section render with `SectionEvidence` metadata describing which signals and chunk IDs were injected. This metadata is stored alongside the rendered markdown to avoid re-parsing prompts.
  - Implement lexical matching heuristics: split rendered sections into sentences, ignore boilerplate phrases, and require each remaining sentence that introduces facts (numbers, detected entities, verbs with direct objects) to have at least one overlapping n-gram (len ≥3) with the normalized evidence. Flag unmatched sentences as hallucinations.
  - When hallucinations are detected, short-circuit the pipeline, emit fail-safe stubs for the offending sections (reuse existing stub generator), and bubble a `ValidationError` back to the CLI with actionable hints.
- **`.docgen.yml` & CLI Updates:**
  - Introduce a `validation` map with a `no_hallucination` boolean (default `true`). Respect repo-level overrides while allowing `DOCGEN_VALIDATION_NO_HALLUCINATION=false` to disable the check in CI emergencies.
  - Add a `--skip-validation` flag for `docgen init|update|regenerate` that flips the toggle for the current execution only and is surfaced in the run summary to encourage re-enabling.
- **Logging & UX:**
  - CLI errors show one-line summaries per section (`quickstart: references docker compose without supporting analyzer signal`). `--verbose` prints the offending sentence, the missing tokens, and a short list of nearby evidence.
  - Persist a `validation.json` report under `.docgen/` capturing the validator status, issues, and selected evidence for forensic review.
- **Testing Strategy:**
  - Unit tests cover positive/negative cases for the `NoHallucinationValidator`, including edge cases such as citations using synonyms or pluralization, bullet lists, and code blocks.
  - Integration tests run the full CLI on synthetic repos stored in `tests/data/validation/` to confirm grounded READMEs pass and tampered outputs fail fast with stub replacements.
  - Add regression fixtures asserting that disabling validation via config/CLI leaves runs untouched and that verbose logging enumerates flagged sentences.

## Story S-033 — Analyzer Artifact Persistence
- **Status:** ✔ Done
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
- **Status:** ✔ Done
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
