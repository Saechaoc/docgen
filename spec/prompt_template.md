Below is a **drop‑in prompt template** you can reuse for **each single story (S‑001 → S‑044)**, followed by **two filled examples** (for S‑001 and S‑016).

---

## 🔧 One‑Story‑At‑A‑Time Implementation Prompt (Template)

> **Use this exact structure for every story.** Replace `{{…}}` placeholders with your specifics before sending.

---

**SYSTEM / ROLE**

You are a **Principal Python engineer** implementing a single, tightly scoped story in an existing repository.
You must:

* Implement **only the story below** (no scope drift, no future stories).
* Produce production‑grade, cross‑platform code (Windows/macOS), Python 3.11.
* Follow repo conventions: Poetry, ruff, black, mypy (strict), pytest.
* Use logging (no prints) in library code, and type hints everywhere.
* Keep audio callbacks non‑blocking; prefer ring buffers and preallocated arrays.
* Avoid OS‑specific imports at module top level.
* When something is ambiguous, **make the smallest reasonable assumption**, state it in the *Assumptions* section, and proceed.

---

### Story Context

* **Story ID:** {{STORY_ID}}
* **Story Title:** {{STORY_TITLE}}
* **Story Text:**
  {{STORY_TEXT}}
* **Dependencies already completed:** {{DEPENDENCIES_LIST_OR_NONE}}
* **Constraints from PRD/backlog:** {{KEY_CONSTRAINTS}}
* **Non‑Goals for this story:** {{NON_GOALS}}

### Environment & Tooling (fixed)

* **Python:** 3.11
* **Package manager:** Poetry
* **Linters/formatters:** ruff, black
* **Static typing:** mypy (strict)
* **Tests:** pytest + pytest‑cov
* **UI:** PySide6 (if relevant to story)
* **Audio I/O:** sounddevice/PortAudio (if relevant)
* **ML runtime:** onnxruntime (if relevant)

### Current Repository Snapshot

> Paste fresh snapshots so the model does not hallucinate. Keep these short but sufficient.

* **Root tree (`tree -a -I .git` or `git ls-files`):**

  ```
  {{REPO_TREE}}
  ```
* **Key files (paste only relevant sections):**

  * `{{PATH/TO/FILE1}}`

    ```python
    {{FILE1_RELEVANT_SNIPPET}}
    ```
  * `{{PATH/TO/FILE2}}`

    ```python
    {{FILE2_RELEVANT_SNIPPET}}
    ```
* **Pinned pyproject.toml (relevant parts):**

  ```toml
  {{PYPROJECT_SNIPPET}}
  ```

### Acceptance Criteria (Definition of Done)

* Functional: {{FUNCTIONAL_DOC}}
* Quality: **ruff/black/mypy** pass; **pytest** passes with **≥ 90%** coverage for new code.
* Cross‑platform: No OS‑specific breakage; guarded imports where needed.
* Performance (if applicable): {{PERF_REQUIREMENTS}}
* Docs: Inline docstrings; README or module‑level docs updated if user‑facing.
* No unrelated refactors; minimal diff outside touched scope.

### Deliverables — **Output Contract**

Return the following sections **in order**, with exact headings:

1. **Assumptions & Decisions** – bullet list of any reasonable assumptions you made.
2. **Planned Changes (TL;DR)** – short summary of what files you will add/modify and why. 
3. **Tests** – full test files covering success, edge cases, and error paths.
4. **Validation Steps (Local)** – exact commands to run (Poetry install, lint, type, test) and expected outputs.
5. **Conventional Commit Message** – a single commit with the story and a description, ex: "S-001: Implemented the GET customers endpoint"

### Implementation Hints (if helpful)

* Keep per‑frame allocations near zero in audio callbacks.
* Use dependency inversion: define clear interfaces in `core/` or `ml/` where specified in the backlog.
* If an external binary or model is out of scope for this story, provide a deterministic stub with TODO and a feature flag.

### Important Guardrails

* **Do not** implement future stories.
* **Do not** introduce new dependencies without updating `pyproject.toml` and justifying them.
* **Do not** change licensing, repo name, or CI workflows unless explicitly requested in this story.
* If output would exceed message limits, **split the Patch and File Contents by directory** but still include all required files.

---

## ✅ Example Instantiation #1 — S‑001 (Initialize repository & core metadata)

> Copy, adjust, and paste the following as a real prompt to your LLM.

**Story ID:** S‑001
**Story Title:** Initialize repository & core metadata
**Story Text:** Create Poetry project `voice-xform`; add LICENSE (Apache‑2.0), README with purpose/install/quickstart, CONTRIBUTING, .editorconfig, .gitattributes, .gitignore, pyproject.toml (Python 3.11).
**Dependencies already completed:** none
**Constraints:** Use Poetry; repo name `voice-xform`; Python 3.11; keep docs concise but actionable.
**Non‑Goals:** No code beyond scaffolding; no CI; no package layout yet.

**Current Repository Snapshot**
*(empty directory)*

```
(Empty)
```

**Acceptance Criteria (Definition of Done)**

* `poetry install` succeeds on macOS & Windows.
* `README.md` includes purpose, install instructions, and placeholder quickstart.
* Running `poetry run python -V` prints Python 3.11.x.

**Deliverables — Output Contract**
(then paste the **Deliverables** list from the template)

**Implementation Hints**

* Use standard `.gitignore` for Python + macOS + Windows.
* Include project metadata (name, version `0.1.0`, authors) in `pyproject.toml`.

**Important Guardrails**

* Do not add CI or tests yet.
* Keep README succinct; add section headers as placeholders.

---

## ✅ Example Instantiation #2 — S‑016 (Model registry & provider detection)

**Story ID:** S‑016
**Story Title:** Model registry & provider detection
**Story Text:** Implement `ml/runtime/onnx_loader.py` that chooses the best ONNX Runtime EP at runtime (TensorRT > DirectML > CPU; MPS/CoreML on macOS). Implement `ml/registry.py` for model paths/versioning. Provide tests that monkeypatch provider availability.
**Dependencies already completed:** S‑004 (package layout), S‑002 (tooling), S‑003 (CI)
**Constraints:** No GPU‑specific imports at module top level. Log chosen EP and fallbacks.
**Non‑Goals:** No real model files yet; no inference calls.

**Current Repository Snapshot**

```
voice-xform/
  app/
  core/
    version.py
  ml/
    __init__.py
    runtime/
      __init__.py
    registry.py        # (empty placeholder)
  tests/
  pyproject.toml
```

**Key files:**
`pyproject.toml` (relevant parts)

```toml
[tool.poetry]
name = "voice-xform"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.11"
onnxruntime = "^1.18.0"
```

**Acceptance Criteria (Definition of Done)**

* `onnx_loader.select_providers()` returns an ordered provider list based on platform and availability.
* Logs contain the selected EP and reason for fallback.
* Tests simulate availability (monkeypatch `onnxruntime.get_available_providers`) and assert selection order across Windows/macOS/Linux.
* mypy/ruff/pytest pass.

**Deliverables — Output Contract**
(then paste the **Deliverables** list from the template)

**Implementation Hints**

* Detect OS with `platform.system()`.
* Prefer `"TensorrtExecutionProvider"` on NVIDIA, `"DmlExecutionProvider"` on Windows, `"CoreMLExecutionProvider"` or `"MPSExecutionProvider"` on macOS, else CPU.
* Expose a helper `create_session(path: str, preferred: list[str] | None) -> InferenceSession`.

**Important Guardrails**

* No actual model downloads.
* No global provider checks at import time; run checks inside functions.

---

## 🧪 Verification Checklist (You run this after each story)

Run locally and produce these commands in the **Validation Steps** section:

```bash
make all
```

* Confirm tests pass and coverage for new code ≥ 95%.
* On Windows/macOS, spot‑check for platform‑specific issues if the story touches system features.
* Run the command /review and do a PR review of the diff. Fix any issues you find.

---

## 📝 Tips for Working With the Template

* Always **update the “Current Repository Snapshot”** before each story so the LLM is grounded in reality.
* Keep **Acceptance Criteria** crisp and testable.
* The **Output Contract** ensures you get a `git apply`‑able patch, full file contents, tests, and a commit message — every time.
* If a story is UI‑heavy, add screenshots or UI state diagrams to the **Story Context** section to steer layout and naming.
* If a story is performance‑sensitive, put explicit budgets into **Acceptance Criteria** and ask the LLM to print measured timings in test logs.

---

Use this template verbatim for S‑001 through S‑044 by swapping in the relevant **Story Context**, **Snapshot**, and **Acceptance Criteria**.
