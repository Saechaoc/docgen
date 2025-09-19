# DocGen Development Roadmap

## Phase 0 — Bootstrap the skeleton

1. **Project skeleton + CLI (`docgen`) + config loader (`.docgen.yml`) + models**
   * Covers: 1 (commands scaffolding), 9 (parse config), 16 (Analyzer ABC)

2. **Analyzer plugin ABC & discovery**
   * Covers: 16 (plugin discovery)

## Phase 1 — "Init" happy-path (single repo, local)

1. **Repo scanner & manifest (roles, hashing, ignores)**
   * Covers: 2 (walk FS, manifest, cache, ignores)

2. **Tier-1 analyzers (Python, Java, Node) + build analyzers + dependency analyzers**
   * Covers: 3 (language/build/deps)

3. **Templates + prompt builder (section-by-section) + guardrailed system prompt**
   * Covers: 5 (Jinja2 templates, guardrails, token budget)

4. **Local LLM runner (Ollama adapter)**
   * Covers: 6 (Ollama)

5. **Post-processor: managed markers, ToC, markdown lint**
   * Covers: 7 (markers, ToC, lint)

6. **Git publisher: commit mode (for init only)**
   * Covers: 8 (commit mode), 1 (`docgen init` end-to-end)

✅ **Milestone**: `docgen init` generates a clean README for a repo with no docs.

## Phase 2 — Update-on-change (PR workflow)

1. **Diff detection + change→section mapping + patching inside markers**
   * Covers: 8 (diff mapping, prevent loops), 1 (`docgen update`)

2. **Git publisher: branch + PR with delta summary**
   * Covers: 8 (branch/PR), 10 (labeling later)

✅ **Milestone**: `docgen update` opens a PR updating only impacted sections.

## Phase 3 — Minimal RAG & accuracy

1. **RAG Lite: embed README/docs/top N source headers; section-scoped retrieval**
   * Covers: 4 (local embedding, index sources, per-section retrieval)

2. **No-hallucination & command existence checks**
   * Covers: 13 (command validation, no-hallucination)

✅ **Milestone**: outputs grounded in repo facts with targeted context.

## Phase 4 — Hardening & DX

1. **Error handling, clear logs, `--verbose`, fail-safe stubs**
   * Covers: 15 (fail-safe, logs, CLI UX)

2. **Security: .gitignore respect, path excludes, local-only enforcement**
   * Covers: 11 (privacy, excludes)

## Phase 5 — CI integration & config polish

1. **GitHub Actions sample (push/PR trigger calling `docgen update`)**
   * Covers: 10 (GH Actions)

2. **Config refinements: watched globs, style preset (concise/comprehensive)**
   * Covers: 9 (watched_globs), 5 (style presets)

## Phase 6 — Multi-language breadth & framework smarts

1. **Entrypoint detection (main, Spring Boot, FastAPI) + framework-aware Quick Start**
   * Covers: 2 (entrypoints), 12 (framework-aware commands)

2. **Pattern analyzers (Docker/K8s, CI config, monorepo layout)**
   * Covers: 3 (pattern analyzers)

## Phase 7 — Quality gates & performance

1. **README scorecard + link validator + badges**
   * Covers: 13 (scorecard), 7 (link validator), 7 (badges)

2. **Artifact & embedding caching in `.docgen/` + incremental RAG refresh**
   * Covers: 14 (persist outputs, incremental refresh)

## Phase 8 — "Nice to have" & stretch

1. **Dry-run mode, PR labeling/updates, commit/PR policy tuning**
   * Covers: 1 (dry-run), 10 (labeling/PR updates)

2. **Template overrides (`docs/templates/*.j2`) & org template packs**
   * Covers: 5 (override), 16 (template packs)

3. **Service mode (FastAPI), llama.cpp adapter, tree-sitter extraction**
   * Covers: 1 (service mode), 6 (llama.cpp), 3 (tree-sitter)

## Why this order

* **Fastest path to value**: get `docgen init` producing a solid README before adding diffing/RAG.
* **Contain risk early**: section markers, lint, and commit publishing ensure safe/idempotent edits.
* **Accuracy next**: add RAG + validation to avoid hallucinations once the pipeline works.
* **Scale breadth later**: only after the core loop is robust do we widen language/framework coverage.
* **Polish last**: CI, caching, and quality gates refine dev experience and performance.