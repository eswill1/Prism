# Contributing to Prism

Prism should not be developed directly on `main`.

## Branching

- create a feature branch for every substantive change
- keep branch names short and descriptive, for example:
  - `feature/hybrid-clustering`
  - `feature/story-brief-qc`
  - `fix/source-link-rendering`
- open a pull request back to `main`

## Expected validation

Before opening or merging a pull request, run:

```bash
npm run build:web
python3 -m py_compile tooling/*.py
python3 tooling/ci_smoke_checks.py
```

If your change touches live ingestion or connected-mode data, also run the relevant connected commands and note what you checked.

## Review standard

- product-facing changes should be reviewed against the design and doctrine docs
- data-pipeline changes should preserve auditability and rollback options
- changes that affect clustering, Perspective, notifications, or correction behavior should update doctrine docs when needed

## GitHub settings to enable

Set these in the GitHub repository:

- protect `main`
- require pull requests before merging
- require at least one review
- require status checks to pass before merging
- require branches to be up to date before merging

Suggested required checks:

- `CI / build-web`
- `CI / python-pipeline`
