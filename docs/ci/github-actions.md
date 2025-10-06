# GitHub Actions Integration

The workflow below runs `docgen update` for every pull request using a
GitHub-hosted runner plus the Docker Model Runner service. The service
container downloads the requested weights (`ai/smollm2:latest`) the first
time it starts and exposes the inference endpoint on port `12434`.

```yaml
name: docgen-update

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: write

jobs:
  refresh-readme:
    runs-on: ubuntu-latest
    services:
      model-runner:
        image: ghcr.io/sourcegraph/model-runner:latest
        env:
          MODEL_RUNNER_MODEL: ai/smollm2:latest
        ports:
          - 12434:12434
        options: >-
          --health-cmd "curl --fail http://localhost:12434/engines/v1/models || exit 1"
          --health-interval 30s
          --health-retries 10
          --health-start-period 60s
    env:
      DOCGEN_LLM_BASE_URL: http://model-runner:12434/engines/v1
      DOCGEN_LLM_MODEL: ai/smollm2:360M-Q4_K_M
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Wait for model runner
        run: |
          for attempt in {1..20}; do
            if curl --fail "$DOCGEN_LLM_BASE_URL/models"; then
              exit 0
            fi
            sleep 15
          done
          exit 1

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements/**', 'pyproject.toml') }}
          restore-keys: ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements/dev.txt

      - name: Run docgen update
        env:
          DIFF_BASE: ${{ github.event.pull_request.base.sha }}
        run: python -m docgen.cli update --diff-base "$DIFF_BASE"

      - name: Commit README updates
        if: ${{ github.event.pull_request.head.repo.full_name == github.repository }}
        run: |
          set -e
          git config user.name "github-actions"
          git config user.email "github-actions@users.noreply.github.com"
          git add README.md README_after_changes.md readme_generation_progress.md
          if git diff --cached --quiet; then
            exit 0
          fi
          git commit -m "docs: refresh README via docgen"
          git push

      - name: Upload README artifact
        if: ${{ github.event.pull_request.head.repo.full_name != github.repository }}
        uses: actions/upload-artifact@v4
        with:
          name: docgen-readme
          path: README*.md
```

> **Note:** commits back to forks are skipped to avoid permission errors; the
> generated README artifacts are attached instead so contributors can apply the
> diff locally. Adjust `MODEL_RUNNER_MODEL` and `DOCGEN_LLM_MODEL` if you change
> the default weights.
```
