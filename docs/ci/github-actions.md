# GitHub Actions Integration

The workflow below runs `docgen update` on pushes and pull requests. It assumes a
self-hosted runner (or GitHub-hosted runner with network access to your local
model runtime). The job skips early when no files match `.docgen.yml`'s
`ci.watched_globs` entries so that purely documentation-only changes do not
trigger the generator.

```yaml
name: docgen-update

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  update-readme:
    runs-on: self-hosted  # requires local LLM access
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}
          restore-keys: ${{ runner.os }}-pip-

      - name: Install docgen in editable mode
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]

      - name: Determine diff base
        id: diff
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            echo "base=${{ github.event.pull_request.base.sha }}" >> "$GITHUB_OUTPUT"
          else
            echo "base=origin/main" >> "$GITHUB_OUTPUT"
          fi

      - name: Run docgen update
        env:
          DOCGEN_LLM_BASE_URL: http://localhost:12434/engines/v1
        run: |
          python -m docgen.cli update --diff-base ${{ steps.diff.outputs.base }}

      - name: Commit README updates (if any)
        run: |
          if git status --short | grep -q README.md; then
            git config user.name "github-actions"
            git config user.email "github-actions@users.noreply.github.com"
            git commit -am "docs: update README via docgen"
          fi

      - name: Upload README artifact
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: generated-readme
          path: README.md
```

> **Note:** the workflow relies on `DOCGEN_LLM_BASE_URL` pointing to a local or
> private inference endpoint. For GitHub-hosted runners you will need to expose
> the runner within your private network or switch to the `ollama` CLI with
> appropriate caching.
```
