# Intelligent README Generator — Architecture & Spec (Python, Local LLM)

## 1) Purpose & Scope

Build a Python-based system that **analyzes a Git repository** (structure, code, dependencies), then **generates and maintains a high-quality README.md** using a **local LLM**. It initializes repos with no docs and **keeps docs up to date** on commits/PRs. Supports **multiple languages/project types** via analyzers.

Non-goals (for the POC): multi-repo orchestration, full website docs, API reference extraction (beyond README summaries), cloud LLMs.

---

## 2) High-Level Architecture (at a glance)

```
             ┌────────────────────┐
 Git Events  │  Event Sources      │  CLI commands, Git hooks, Webhooks/CI
 (commit/PR) └─────────┬───────────┘
                       │
                  ┌────▼─────┐
                  │ Orchestr │  (Async task graph)
                  └────┬─────┘
       ┌────────────────┼────────────────┐
       │                │                │
┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
│ Repo Scanner│  │ Analyzers    │  │ Doc Store   │
│ + Indexer   │  │ (Language,   │  │ (Artifacts, │
│ (Git, FS)   │  │ Build, Deps) │  │ Cache,     │
└──────┬──────┘  └──────┬──────┘  │ Versions)   │
       │                 │         └──────┬──────┘
       │        ┌────────▼────────┐       │
       │        │ Knowledge Graph │       │
       │        │  & Embeddings   │<──────┘
       │        └────────┬────────┘
       │                 │
       │        ┌────────▼──────────┐
       │        │ Prompt Builder     │ (Templates + RAG)
       │        └────────┬──────────┘
       │                 │
       │        ┌────────▼──────────┐
       │        │ Local LLM Runner   │ (llama.cpp/Ollama)
       │        └────────┬──────────┘
       │                 │
       │        ┌────────▼──────────┐
       └───────▶│ Post-Processor     │ (lint, ToC, badges, links)
                └────────┬──────────┘
                         │
                 ┌───────▼───────┐
                 │ Git Publisher │ (branch/PR/commit)
                 └───────────────┘
```

---

## 3) Components & Responsibilities

### 3.1 Orchestrator

* Coordinates end-to-end pipelines (init, update, regenerate).
* Computes *change impact* from Git diff; decides whether to regenerate full README or patch sections.
* Schedules tasks and caches intermediate results.
* Emits structured logs (info by default, debug with `--verbose`), respects `.docgen.yml` `ci.watched_globs` to skip unrelated diffs, and substitutes fail-safe stubs when generation fails.
* Supports dry-run previews (`docgen update --dry-run`) and records scorecards for each run under `.docgen/`.

### 3.2 Repo Scanner & Indexer

* Walks repo; builds normalized manifest:

  * Files, sizes, language tags, path roles (src/test/docs/examples).
  * Build files & dependency manifests (e.g., `pom.xml`, `build.gradle`, `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `composer.json`).
  * Entrypoints (CLIs, services), test coverage artifacts if available.
* Stores a per-repo index (JSON) to speed future runs.

### 3.3 Analyzers (Plugin-based)

* **Language analyzers** (detect idioms, entrypoints, frameworks: Spring Boot, FastAPI, Node/Express, React, Next.js, Go HTTP, Rust bin/lib).
* **Build analyzers** (Maven/Gradle, setuptools/Poetry, npm/pnpm/yarn, Go, Cargo).
* **Dependency analyzers** (extract top-level libs & notable transitive categories).
* **Entrypoint analyzers** (infer run commands for FastAPI, Django, Spring Boot, Node scripts).
* **Pattern analyzers** (monorepo layout, CI/CD, containerization/K8s heuristics).
* **Structure analyzer** (module topology, detected entities/DTOs, API endpoint sequences, service interactions).
* Each analyzer returns **Signals** (key facts) to the knowledge graph.

### 3.4 Knowledge Graph & Embeddings (RAG)

* Graph of Repo entities: modules, packages, services, scripts, configs, tests, docs.
* Lightweight embedding store (e.g., `faiss`/in-memory) of **chunks**: code comments, README fragments, `docs/`, `CHANGELOG`, issues (optional), commit messages.
* Provides **context retrieval** for prompt building (top-k by section) and persists embeddings under `.docgen/`, refreshing only the files whose hashes changed.

### 3.5 Prompt Builder

* **Section-aware** Jinja2 templates with **guardrails**:

  * Project intro, key features, architecture overview, quick start, configuration, build/test, deployment, troubleshooting, FAQ, roadmap, contribution, license, badges.
* Dynamically injects repo signals and retrieved context per section.
* Produces **LLM-ready structured prompts** (system + user messages) with token budgets and honours `readme.style` presets (`concise` trims list-heavy sections, `comprehensive` keeps full detail).
* Injects detected entrypoints and infrastructure patterns into Quick Start guidance (e.g., `uvicorn ...`, `docker compose up`).
* Generates Mermaid sequence diagrams highlighting request flow across services when API endpoints are detected.

### 3.6 Local LLM Runner

* Pluggable runtime that prefers the Docker Model Runner HTTP endpoint (host `http://localhost:12434/engines/v1`, container `http://model-runner.docker.internal/engines/v1`) with environment overrides and an `ollama` CLI fallback.
* Defaults to `ai/smollm2:360M-Q4_K_M` but respects `.docgen.yml` and OpenAI-compatible env vars for alternate weights and API keys.
* Supports **function calling style** for structured outputs when available.
* Streaming decode with stop tokens; **section-by-section** generation to stay within context limits.
* Validates configuration to ensure runners stay local (loopback/`*.internal` hosts only).

### 3.7 Post-Processor

* Lints Markdown, builds ToC, adds shields/badges, normalizes heading hierarchy.
* Enforces internal style guide and **README contract** (required sections).
* Validates links (relative/absolute), code block languages, and line length.
* Computes **diff-aware updates**: only modifies sections impacted by changes.
* Persists a README scorecard (`.docgen/scorecard.json`) capturing coverage, quick start health, and link results.
* Adds build/coverage/license badges with safe defaults and reports link warnings during post-processing.

### 3.8 Validation Layer

* Runs after section rendering and before linting/publishing to ensure generated claims are grounded.
* Normalizes analyzer signals, section metadata, and retrieved context into an **Evidence Index** used for token overlap checks.
* Default `NoHallucinationValidator` rejects sentences lacking supporting evidence, replaces offending sections with fail-safe stubs, and raises actionable errors.
* Writes `.docgen/validation.json` capturing validator status, issues, and evidence summaries for auditability.
* Respects `.docgen.yml` `validation.no_hallucination` toggle, `DOCGEN_VALIDATION_NO_HALLUCINATION` environment override, and CLI `--skip-validation` flag for one-off bypasses.

### 3.9 Doc Store (Artifacts & Versions)

* Keeps generated drafts, logs, prompts, inputs/outputs, and diffs under `.docgen/` per repo.
* Supports rollback and regression testing via “golden” READMEs.
* Stores embedding cache (`embeddings.json`) and scorecards so subsequent runs are incremental.

### 3.10 Git Publisher

* Creates a branch (e.g., `docgen/readme-update-YYYYMMDD`) and a PR.
* PR body explains detected changes and what sections were updated.
* Can commit directly (configurable) on init for empty repos.
* Applies labels (e.g., `docs:auto`) and updates existing PRs when configured.

---

## 4) Data Model (Python `pydantic`/`dataclasses`)

```python
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class FileMeta:
    path: str
    size: int
    language: Optional[str]
    role: str  # src|test|docs|config|build|script|infra|other
    hash: str

@dataclass
class RepoManifest:
    root: str
    files: List[FileMeta]
    detectors: Dict[str, str]     # {"build_system": "maven", "framework":"spring-boot", ...}
    dependency_files: Dict[str, str]  # {"pom.xml": "...", "requirements.txt": "..."}

@dataclass
class Signal:
    kind: str           # "framework","service","cli","db","queue","dep","entrypoint","test"
    name: str
    detail: Dict[str, str]

@dataclass
class AnalysisResult:
    manifest: RepoManifest
    signals: List[Signal]
    embedding_index_path: str

@dataclass
class SectionSpec:
    key: str            # "intro","features","arch","quickstart",...
    required: bool
    sources: List[str]  # preferred retrieval tags
    template_name: str

@dataclass
class ReadmeDraft:
    sections: Dict[str, str]
    full_markdown: str

@dataclass
class UpdatePlan:
    strategy: str       # "full"|"patch"
    changed_sections: List[str]
    reasons: Dict[str, str]  # section->why
```

---

## 5) Configuration (`.docgen.yml` at repo root)

```yaml
llm:
  runner: "ollama"            # or "llama.cpp"
  model: "llama3:8b-instruct" # example; local only
  max_tokens: 2048
  temperature: 0.2

readme:
  style: "concise"            # or "comprehensive"
  template_pack: "enterprise"  # optional bundle shipped with docgen
  required_sections:
    - intro
    - features
    - architecture
    - quickstart
    - configuration
    - build_and_test
    - deployment
    - troubleshooting
    - faq
    - license

validation:
  no_hallucination: true  # set to false or use DOCGEN_VALIDATION_NO_HALLUCINATION=0 to disable

publish:
  mode: "pr"                  # "commit" | "pr" | "dry-run"
  branch_prefix: "docgen/"
  labels:
    - "docs:auto"
  update_existing: true        # refresh an existing PR instead of opening a new one

analyzers:
  enabled:
    - language
    - build
    - dependencies
    - patterns
  exclude_paths:
    - ".git/"
    - "node_modules/"
    - "dist/"

ci:
  # Only update README if these paths change
  watched_globs:
    - "src/**"
    - "app/**"
    - "cmd/**"
    - "pom.xml"
    - "build.gradle*"
    - "package.json"
    - "requirements.txt"
    - "pyproject.toml"
    - "Dockerfile"
```

> If no `readme.templates_dir` is provided, docgen automatically picks up `docs/templates/` bundles in the repository root and supports built-in template packs via `readme.template_pack`.

---

## 6) Workflows

### 6.1 Initialization (Repo without README)

1. **Scan & Analyze** → Manifest + Signals + Embeddings.
2. **Prompt Build** with default templates, include “getting started” suggestions.
3. **Generate Sections** sequentially (streaming).
4. **Post-process** → ToC, badges (build status placeholder), lint.
5. **Publish**: direct commit `README.md` + `.docgen/` artifacts.

### 6.2 Update on Commit/PR

1. **Detect changes** via Git diff; map files to sections using a rules matrix:

   * `pom.xml`/`build.gradle` → *Build & Test*, *Quick Start*.
   * `Dockerfile`/`k8s` → *Deployment*.
   * `src/**` entrypoints → *Architecture*, *Features*.
2. **Decide UpdatePlan**: patch impacted sections; regenerate only those.
3. **Skip** if no changed file matches `.docgen.yml` `ci.watched_globs` (allows CI to avoid unnecessary runs).
4. **RAG retrieval**: fetch top-k chunks relevant to each section.
5. **Generate** → **Post-process** → **Open PR** with summary of deltas.
6. Dry-run support: `docgen update --dry-run` computes diffs and scorecards without writing or publishing.

### 6.3 Regenerate (Manual)

* `docgen regenerate --full` or `--sections intro,arch`.

---

## 7) Section Contract (README)

* **Intro**: what, why, who it’s for
* **Key Features**: bullets grounded in real repo signals
* **Architecture**: overview diagram (ASCII) + components
* **Quick Start**: minimal commands (per build system)
* **Configuration**: env vars, files, examples
* **Build & Test**: commands, coverage hint
* **Deployment**: container/K8s instructions if detected
* **Troubleshooting**: common failures
* **FAQ**: 5–10 concise Q\&A
* **Contributing** (if `CONTRIBUTING.md` absent)
* **License** (detected or templated)

> Each section must be independently regenerable and self-contained.

---

## 8) Prompting Strategy (Local LLM)

* **System message (fixed guardrails)**:

  * “You are a senior dev doc writer. Be precise. Cite repo facts only. No speculation.”
  * “Never invent commands. Prefer commands detected by analyzers.”
* **User message per section**:

  * Section objective + constraints (tone, length).
  * Inject **Signals** + **Top-k chunks** (RAG).
  * Provide **style tokens** (headings, code blocks, tables).
* **Post-filters**: refuse if insufficient evidence; fall back to template stubs.

---

## 9) Language & Project Support (POC targets)

* **Tier-1 (POC)**: Python (Poetry/Setuptools), Java (Maven/Gradle, Spring Boot), Node.js (npm/pnpm, Express/Next).
* **Tier-2 (soon)**: Go (modules), Rust (Cargo), Ruby (Bundler), PHP (Composer).
* Detection via:

  * File heuristics + optional tree-sitter for function/class extraction (pluggable).
  * Entry points: `main()`; Spring `@SpringBootApplication`; FastAPI app; `bin/`, `cmd/`.

---

## 10) Interfaces (Code Skeleton)

```
docgen/
  __init__.py
  cli.py                  # click/typer CLI
  failsafe.py             # fail-safe README stubs
  logging.py              # logging configuration helpers
  orchestrator.py
  repo_scanner.py
  analyzers/
    base.py               # Analyzer ABC
    language.py
    build.py
    dependencies.py
    entrypoints.py
    patterns.py
  rag/
    embedder.py           # local embedding model
    store.py
  prompting/
    builder.py            # Jinja2 templates, token mgmt
    constants.py
    templates/           # *.j2 per section
  llm/
    runner.py             # adapter for ollama/llama.cpp
  postproc/
    lint.py
    links.py
    markers.py
    toc.py
  git/
    diff.py
    publisher.py
  config.py
  models.py
```

**Analyzer ABC**

```python
from abc import ABC, abstractmethod
from .models import RepoManifest, Signal

class Analyzer(ABC):
    @abstractmethod
    def supports(self, manifest: RepoManifest) -> bool: ...
    @abstractmethod
    def analyze(self, manifest: RepoManifest) -> list[Signal]: ...
```

**CLI (Typer)**

```python
@app.command()
def init(path: str = ".", publish: bool = True): ...
@app.command()
def update(path: str = ".", event: str = "commit", diff_base: str = "origin/main"): ...
@app.command()
def regenerate(sections: str = "", full: bool = False): ...
```

**FastAPI (optional service mode)**

* `POST /analyze`
* `POST /generate?sections=arch,quickstart`
* `POST /publish`
* `GET /status/{run_id}`

---

## 11) Change Impact Matrix (examples)

| Changed Path Pattern                 | Sections to Rebuild          | Notes                                   |
| ------------------------------------ | ---------------------------- | --------------------------------------- |
| `pom.xml`, `build.gradle*`           | build\_and\_test, quickstart | Recompute build commands                |
| `requirements.txt`, `pyproject.toml` | build\_and\_test, quickstart | Update install steps                    |
| `Dockerfile`, `k8s/**`               | deployment                   | Publish container changes               |
| `src/**`, `app/**`, `cmd/**`         | features, architecture       | If entrypoint changed, update intro too |
| `docs/**`                            | all (patch)                  | Prefer doc-driven                       |
| `README.md`                          | none (unless empty)          | Prevent loops                           |

---

## 12) Post-Processing Rules

* Headings start at `#` for title then `##` for sections.
* Add **auto ToC** (<= level 3).
* Validate code blocks (` ```bash`, ` ```python`).
* Convert absolute GitHub links to relative where possible.
* Ensure **idempotency**: only edit between managed markers:

  * `<!-- docgen:begin:architecture -->` … `<!-- docgen:end:architecture -->`

---

## 13) Git & CI Integration

### Local

* **pre-commit**: forbid direct README edits outside markers (optional).
* **post-merge / post-checkout**: remind to run `docgen update` (optional).

### CI (GitHub/GitLab/Bitbucket)

* On push/PR:

  1. Checkout repo.
  2. `docgen update --event pr --diff-base $BASE_SHA`
  3. If changes → open/update PR with labeled `docs:auto`.
* Tokenless mode possible if PR created from a GitHub App/bot account.

---

## 14) Quality Gates & Evaluation

* **Consistency checks**: commands exist in repo; ports/env vars match configs.
* **No hallucinations**: reject new facts not found in signals/RAG.
* **Style**: concise paragraphs, actionable commands, no filler marketing.
* **Scorecard** (0–100):

  * Coverage of required sections (30)
  * Buildability of quick start (20)
  * Link validity (10)
  * Diff alignment w/ change set (20)
  * Lint (10)
  * Reviewer feedback loop (10)

---

## 15) Security & Privacy

* **Local only** LLM and embedding models.
* Respect `.gitignore` + configurable `exclude_paths`.
* Never index large binaries/secret files.
* Optional simple **secret scan**; block if found.

---

## 16) MVP Plan (2 weeks suggested breakdown)

1. **Core path**: CLI, Scanner, Language+Build analyzers (Python/Java/Node), Prompt Builder, Local LLM runner (Ollama adapter), Post-processor, Git Publisher (PR).
2. **RAG Lite**: embed only `/docs`, existing `README`, top 20 largest source files’ heads.
3. **Triggers**: single “commit” mode; PR mode as stretch.
4. **Templates**: 8 sections, Jinja2; managed markers.
5. **Config**: `.docgen.yml` minimal.

---

## 17) Example Templates

### 17.1 Section Template (Jinja2 — architecture.j2)

```jinja2
## Architecture

{{ project_name }} is structured as:

```

{{ ascii\_architecture }}

```

**Key components**
{% for comp in components %}
- **{{ comp.name }}** — {{ comp.summary }}
{% endfor %}

**Data flow**
{{ data_flow }}

> Generated from detected signals: {{ signals_summary }}
```

### 17.2 README Frame (composed)

```jinja2
# {{ project_name }}

{{ intro }}

## Features
{{ features }}

{% include "architecture.j2" %}

## Quick Start
{{ quickstart }}

## Configuration
{{ configuration }}

## Build & Test
{{ build_and_test }}

## Deployment
{{ deployment }}

## Troubleshooting
{{ troubleshooting }}

## FAQ
{{ faq }}

## License
{{ license }}
```

---

## 18) Minimal Python Snippets

**Change impact heuristic**

```python
SECTION_RULES = [
  ("build_and_test", ["pom.xml","build.gradle","requirements.txt","pyproject.toml","package.json"]),
  ("deployment",     ["Dockerfile","k8s/"]),
  ("architecture",   ["src/","app/","cmd/"]),
  ("features",       ["src/","app/","cmd/"]),
]

def sections_from_diff(paths: list[str]) -> set[str]:
    out = set()
    for section, patterns in SECTION_RULES:
        if any(p for p in paths for pat in patterns if p.startswith(pat)):
            out.add(section)
    return out or {"intro"}  # fall back to intro if uncertain
```

**Managed markers (patch)**

```python
def replace_block(md: str, key: str, new: str) -> str:
    start = f"<!-- docgen:begin:{key} -->"
    end   = f"<!-- docgen:end:{key} -->"
    if start in md and end in md:
        pre, rest = md.split(start, 1)
        _, post = rest.split(end, 1)
        return f"{pre}{start}\n{new}\n{end}{post}"
    return md  # or insert markers if missing
```

---

## 19) Open Questions / Trade-offs

* **Embeddings**: Use a tiny local model vs. rule-based retrieval for MVP?
* **Tree-sitter**: Adds power but increases footprint—gate behind a flag.
* **PR author**: Bot account vs. developer token—decide per environment.
* **Markdown diffs**: Keep sections atomic to minimize noisy PRs.

---

## 20) Example `.docgen.yml` for a Mixed Repo

```yaml
llm:
  runner: "ollama"
  model: "llama3:8b-instruct"
  temperature: 0.15
readme:
  style: "comprehensive"
publish:
  mode: "pr"
  branch_prefix: "docgen/"
analyzers:
  enabled: [language, build, dependencies, patterns]
  exclude_paths: [".git/", "node_modules/", "dist/", "target/"]
ci:
  watched_globs:
    - "src/**"
    - "app/**"
    - "cmd/**"
    - "pom.xml"
    - "build.gradle*"
    - "package.json"
    - "requirements.txt"
    - "Dockerfile"
```

---

## 21) Success Criteria (POC)

* For 3 diverse repos (Python CLI, Spring Boot API, Node webapp):

  * `docgen init` produces a working, linted README with runnable Quick Start.
  * On changing `pom.xml` or `requirements.txt`, PR updates only relevant sections.
  * No hallucinated commands; links and badges validate; style consistent.

---

If you want, I can spin up a **starter repo layout** (CLI, analyzers, templates, and a simple Ollama adapter) so you can drop it into your environment and run `docgen init` right away.
