# docgen
<!-- docgen:begin:badges -->
[![Build Status](https://img.shields.io/badge/build-pending-lightgrey.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-review--needed-lightgrey.svg)](#)
[![License](https://img.shields.io/badge/license-tbd-lightgrey.svg)](#)
<!-- docgen:end:badges -->

<!-- docgen:begin:toc -->
## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
  - [High-Level Flow](#high-level-flow)
  - [Component Responsibilities](#component-responsibilities)
  - [Pipeline Sequence (docgen init)](#pipeline-sequence-docgen-init)
  - [Patch Sequence (docgen update)](#patch-sequence-docgen-update)
  - [API Signal Extraction](#api-signal-extraction)
  - [Detected Entities](#detected-entities)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Build & Test](#build-test)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [License](#license)
<!-- docgen:end:toc -->

<!-- docgen:begin:intro -->
docgen is a local-first README generator for polyglot repositories built primarily with Python and YAML. It scans every tracked file, emits analyzer signals, retrieves grounded context, and drives a local LLM through templated sections to keep documentation accurate. The overview below captures the full pipeline so contributors understand the moving pieces before running `docgen init`. Refer to `spec/spec.md` for detailed architecture contracts and responsibilities.
<!-- docgen:end:intro -->

## Features

<!-- docgen:begin:features -->
- **Repository manifest & caching** - `docgen/repo_scanner.py` walks the tree, respects ignore rules, and persists hashes for incremental runs.
- **Analyzer plugin system** - `docgen/analyzers/*` emit language, build, dependency, entrypoint, and structure signals for downstream prompting.
- **Template-driven prompting** - `docgen/prompting/builder.py` merges signals with Jinja templates and enforces markdown style presets.
- **Lightweight RAG index** - `docgen/rag/indexer.py` embeds repo snippets into `.docgen/embeddings.json` for section-scoped retrieval.
- **Local LLM enforcement** - `docgen/llm/runner.py` targets loopback runtimes (Model Runner, Ollama, llama.cpp) with token and temperature guards.
- **Post-processing contract** - `docgen/postproc/*` rebuild badges, ToC, lint markdown, validate links, and compute scorecards.
- **Git-aware publishing** - `docgen/git/publisher.py` and `docgen/git/diff.py` map repo changes to sections and push commits or PRs.
- **Resilient CLI UX** - `docgen/cli.py` exposes `init`/`update` commands with verbose logging, dry-run previews, and validation toggles.
- Primary stack: Python, YAML
- Supported build tooling: generic
- Ready for continuous README generation via docgen.
<!-- docgen:end:features -->

## Architecture

<!-- docgen:begin:architecture -->

### High-Level Flow

The orchestrator coordinates the repo scanner, analyzer plugins, retrieval indexer, prompt builder, local LLM runner, and post-processing/publishing services so README updates remain grounded in repository facts.

### Component Responsibilities

| Module | Roles | Files |
| --- | --- | --- |
| AGENTS.md | docs | 1 |
| docgen | src | 61 |
| docs | docs | 2 |
| spec | docs | 5 |
| tests | test | 24 |

### Pipeline Sequence (docgen init)

`mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as docgen CLI
    participant Orc as Orchestrator
    participant Scan as RepoScanner
    participant Ana as Analyzer plugins
    participant RAG as RAGIndexer
    participant Prompt as PromptBuilder
    participant LLM as LLMRunner
    participant Post as Post-processing
    participant FS as Filesystem
    Dev->>CLI: docgen init .
    CLI->>Orc: run_init(path)
    Orc->>Scan: scan()
    Scan-->>Orc: RepoManifest
    Orc->>Ana: analyze(manifest)
    Ana-->>Orc: Signal[]
    Orc->>RAG: build(manifest)
    RAG-->>Orc: contexts per section
    Orc->>Prompt: build(...)
    Prompt->>LLM: invoke prompts
    LLM-->>Prompt: section drafts
    Prompt-->>Orc: README draft
    Orc->>Post: lint + toc + badges + links + scorecard
    Post-->>Orc: polished markdown
    Orc->>FS: write README.md
`

### Patch Sequence (docgen update)

`mermaid
sequenceDiagram
    participant Dev as Developer/CI
    participant CLI as docgen CLI
    participant Orc as Orchestrator
    participant Diff as DiffAnalyzer
    participant Scan as RepoScanner
    participant Ana as Analyzer plugins
    participant RAG as RAGIndexer
    participant Prompt as PromptBuilder
    participant Mark as MarkerManager
    participant Post as Post-processing
    Dev->>CLI: docgen update --diff-base <ref>
    CLI->>Orc: run_update(path, base)
    Orc->>Diff: compute()
    Diff-->>Orc: sections to refresh
    Orc->>Scan: scan()
    Scan-->>Orc: RepoManifest
    Orc->>Ana: analyze(manifest)
    Ana-->>Orc: Signal[]
    Orc->>RAG: build(manifest, sections)
    RAG-->>Orc: context snippets
    Orc->>Prompt: render_sections(sections)
    Prompt-->>Orc: refreshed markdown
    Orc->>Mark: splice into README
    Mark-->>Orc: patched markdown
    Orc->>Post: lint + toc + badges + links + scorecard
    Post-->>Orc: final README
`

### API Signal Extraction

`mermaid
sequenceDiagram
    participant Client
    participant FastAPI endpoint
    Client ->> FastAPI endpoint: GET /health
    FastAPI endpoint -->> Client: Response
    Client ->> FastAPI endpoint: POST /init
    FastAPI endpoint -->> Client: Response
    Client ->> FastAPI endpoint: POST /update
    FastAPI endpoint -->> Client: Response
`

### Detected Entities

- InitRequest (BaseModel) - docgen/service/app.py- InitResponse (BaseModel) - docgen/service/app.py- UpdateRequest (BaseModel) - docgen/service/app.py- UpdateResponse (BaseModel) - docgen/service/app.py- HealthResponse (BaseModel) - docgen/service/app.py
<!-- docgen:end:architecture -->

## Quick Start

<!-- docgen:begin:quickstart -->
Follow the steps below to get started:

`ash
uvicorn docgen.service.app:app --reload
uvicorn tests.analyzers.test_entrypoints:napp --reload
uvicorn tests.analyzers.test_structure:app --reload
python docgen/cli.py

# Document build steps here.
`
<!-- docgen:end:quickstart -->

## Configuration

<!-- docgen:begin:configuration -->
List configuration files or environment variables required to run the project.
<!-- docgen:end:configuration -->

## Build & Test

<!-- docgen:begin:build_and_test -->
**Generic**
- # Document build steps here.
<!-- docgen:end:build_and_test -->

## Deployment

<!-- docgen:begin:deployment -->
Outline deployment strategies or hosting targets here.
<!-- docgen:end:deployment -->

## Troubleshooting

<!-- docgen:begin:troubleshooting -->
- Confirm dependencies are installed before running commands.
- Use `docgen update` after code changes to refresh sections automatically.
- Open an issue when docgen requires additional diagnostics in this section.
<!-- docgen:end:troubleshooting -->

## FAQ

<!-- docgen:begin:faq -->
**Q: How is this README maintained?**
A: Generated with `docgen init` and updated via `docgen update`.

**Q: Where do I report issues?**
A: File an issue or start a discussion in this repository.
<!-- docgen:end:faq -->

## License

<!-- docgen:begin:license -->
Add licensing information once the project selects a license.
<!-- docgen:end:license -->
