# README Generation Revamp - Progress Log

## Objective
Establish a reproducible, high-quality README generation pipeline that works across fresh environments, small local LLMs, and fallback-only runs while keeping validation strict enough to block hallucinations.

## Phase Overview
| Phase | Focus | Status | Notes |
| --- | --- | --- | --- |
| Phase 1 | Robust baseline (deterministic templates, grounded validators, non-blocking RAG) | Done | Templates now gate docgen-only claims, quick start commands are filtered, RAG indexing is deferred, and validators support balanced evidence tiers with synonym maps. |
| Phase 2 | Quality upgrade via guarded LLM narratives | Done | Per-section LLM toggles honour generation config, validation auto-fallbacks swap in deterministic copy, and offline runs now skip the runner entirely. |
| Phase 3 | Ergonomics and operator control | In progress | Configuration surfaces generation/validation switches; logging hooks and spec updates still pending together with richer telemetry. |

## Completed Work
- Hardened prompt templates for architecture, quick start, configuration, build & test, and deployment sections to produce deterministic, repository-aware prose.
- Implemented artifact gating and runtime command filtering to avoid docgen-specific placeholders and test-only instructions in generated READMEs.
- Added balanced validation with observed vs inferred evidence tiers, synonym expansion, and analyzer-derived tokens feeding the evidence index.
- Deferred RAG index rebuilds so README generation never blocks on embeddings; contexts now reuse cached artifacts when present.
- Introduced `GenerationConfig` and expanded `ValidationConfig` parsing to expose new switches from `.docgen.yml`.
- Orchestrator honours generation config for LLM usage, disables the runner when no configuration/environment is detected, and retries validation with deterministic fallbacks on failure.
- Added async RAG refresh hooks that rebuild embeddings after init/update without delaying markdown writes.
- Updated builder, validator, config, and orchestrator unit suites plus the validation integration test (current runs pass under the new defaults).
- Extended orchestrator coverage for strict generation overrides and per-section LLM toggles.
- Refreshed failsafe stubs so fallback sections provide actionable guidance instead of placeholder warnings.

## Work In Flight
- Finalize spec updates documenting balanced validation, generation modes, and fallback behaviour (see `spec/spec.md`).
- Capture deterministic/LLM comparison snapshots in docs so contributors know when fallbacks engage.
- Harden CI smoke: add fresh-clone, offline, and double-run determinism tests once Phase 3 wiring is in place.

## Upcoming Tasks & Risks
- Extend integration coverage: fresh-clone run without caches, determinism check (double init), offline/no-runner scenario, and echo-handling regression tests.
- Document new configuration knobs and runtime expectations in `spec/spec.md` and user-facing docs once wiring lands.
- Monitor small-model behaviour; tighten validation overlap thresholds if balanced mode becomes overly permissive.
- Expose operator telemetry (per-section fallback reasons, runner latency) to surface regressions.

## Testing Snapshot
- `python -m pytest tests/test_orchestrator.py`
- `python -m pytest tests/prompting/test_builder.py tests/validators/test_no_hallucination_validator.py`
- `python -m pytest tests/integration/test_validation.py`

---
_Last updated: 2025-10-06_
