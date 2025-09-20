# Intelligent README Generator — Feature Checklist

> Status legend: ☐ Not started · ◐ In progress · ✔ Done  
> Scope tags: **[MVP]** required for proof‑of‑concept, **[NEXT]** nice‑to‑have soon, **[STRETCH]** later

## 1) Core Workflows
- [x] **docgen init** — Initialize README for repos without docs **[MVP]**
- [ ] **docgen update** — Detect changes on commit/PR and patch affected sections **[MVP]**
- [ ] **docgen regenerate** — Manual full/partial regeneration **[MVP]**
- [ ] Dry‑run mode (`--dry-run`) to preview diffs without writing **[NEXT]**
- [ ] Service mode (FastAPI) endpoints for CI/bots **[STRETCH]**

## 2) Repository Scanning & Indexing
- [x] Walk filesystem with ignore rules (`.gitignore`, `.docgen.yml`) **[MVP]**
- [x] Build normalized manifest of files, roles (src/test/docs/config/infra) **[MVP]**
- [x] Hash & cache file metadata to speed subsequent runs **[MVP]**
- [x] Entrypoint detection (e.g., `main()`, `@SpringBootApplication`, FastAPI app) **[NEXT]**
- [ ] Monorepo module detection **[NEXT]**

## 3) Analyzers (Plugin‑based)
- [x] Language analyzers: Python, Java, Node.js (Tier‑1) **[MVP]**
- [x] Build analyzers: Poetry/Setuptools, Maven/Gradle, npm/pnpm/yarn **[MVP]**
- [x] Dependency analyzers from manifest files **[MVP]**
- [x] Pattern analyzers: Docker/K8s, CI config, monorepo layout **[NEXT]**
- [ ] Tree‑sitter powered symbol/entrypoint extraction (flagged) **[STRETCH]**

## 4) Knowledge Store (RAG)
- [ ] Local embedding model + chunking strategy **[MVP]**
- [ ] Index `README`, `/docs`, top N source headers & comments **[MVP]**
- [ ] Section‑scoped retrieval (top‑k per section) **[MVP]**
- [ ] Lightweight knowledge graph of modules/services/signals **[NEXT]**

## 5) Prompting & Templates
- [x] Jinja2 templates per section (intro, features, architecture, quickstart, config, build/test, deployment, troubleshooting, FAQ, license) **[MVP]**
- [x] Guardrailed system prompt (“no speculation; cite repo facts only”) **[MVP]**
- [x] Token budgeting & streaming section-by-section generation **[MVP]**
- [ ] Template override mechanism (`docs/templates/*.j2`) **[NEXT]**
- [x] Style presets: concise vs comprehensive **[NEXT]**
- [ ] Mermaid.js diagrams for architecture/flow sections where appropriate **[NEXT]**

## 6) Local LLM Runner
- [x] Model Runner HTTP adapter (host/container defaults, env/API key overrides) **[MVP]**
- [ ] llama.cpp adapter **[NEXT]**
- [ ] Structured outputs / tool‑use compatibility **[STRETCH]**

## 7) Post‑Processing
- [x] Markdown lint: heading hierarchy, code fences, line length **[MVP]**
- [x] Auto ToC (≤ level 3) **[MVP]**
- [ ] Badges (build, coverage, license) with safe defaults **[NEXT]**
- [ ] Link validator (relative/absolute) **[NEXT]**
- [x] Managed markers for idempotent patching (`<!-- docgen:begin:end -->`) **[MVP]**

## 8) Git Integration
- [ ] Diff detection (map changed files → impacted sections) **[MVP]**
- [ ] Branch + PR creation with summary of README deltas **[MVP]**
- [x] Commit mode for init or small changes (configurable) **[NEXT]**
- [ ] Prevent loops on README‑only changes **[MVP]**

## 9) Configuration
- [x] Parse `.docgen.yml` (LLM, readme style, analyzers, publish) **[MVP]**
- [x] Path exclusions & `watched_globs` for CI triggers **[MVP]**
- [ ] Per-section on/off toggles and titles **[NEXT]**

## 10) CI Integration
- [x] GitHub Actions example workflow **[MVP]**
- [ ] GitLab CI and Bitbucket Pipelines samples **[NEXT]**
- [ ] Labeling (`docs:auto`) and PR update behavior **[NEXT]**

## 11) Security & Privacy
- [x] Local-only models; never exfiltrate code **[MVP]**
- [ ] Respect `.gitignore`; exclude large binaries/secrets **[MVP]**
- [ ] Optional simple secret scanner gate **[NEXT]**

## 12) Multi‑Language & Project Types
- [ ] Tier‑1: Python (Poetry/Setuptools), Java (Maven/Gradle/Spring Boot), Node.js (npm/pnpm/Express/Next) **[MVP]**
- [ ] Tier‑2: Go, Rust, Ruby, PHP **[STRETCH]**
- [ ] Framework‑aware quickstart commands per build system **[MVP]**

## 13) Quality Gates & Evaluation
- [ ] Command validation (existence checks) **[MVP]**
- [ ] No‑hallucination checks: reject facts not in signals/RAG **[MVP]**
- [ ] README scorecard (coverage, buildability, link validity, diff alignment, lint) **[NEXT]**

## 14) Performance & Caching
- [ ] Persist analyzer outputs & embeddings under `.docgen/` **[MVP]**
- [ ] Incremental RAG refresh (changed files only) **[NEXT]**

## 15) Error Handling & UX
- [x] Fail-safe stub generation when evidence is insufficient **[MVP]**
- [ ] Clear run logs + PR body with rationale (“sections updated because…”) **[MVP]**
- [x] Helpful CLI errors and `--verbose` flag (works pre/post subcommand) **[MVP]**

## 16) Extensibility
- [x] Analyzer ABC and plugin discovery **[MVP]**
- [ ] Template packs (org‑style) **[NEXT]**

---

### Definition of Done (per section)
- [ ] Passing unit & integration tests for core logic
- [ ] Golden README regression test(s)
- [ ] Meets lint/style requirements
