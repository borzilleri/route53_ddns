---
name: Default GitHub repo
overview: Add the canonical GitHub URL to `pyproject.toml` under PEP 621 `[project.urls]`, resolve `owner/repo` at runtime as the default for update checks while keeping `GITHUB_REPOSITORY` as the override (empty string disables).
todos:
  - id: pyproject-urls
    content: Add [project.urls] Repository to pyproject.toml
    status: completed
  - id: resolve-slug
    content: Implement metadata URL→owner/repo helper + Settings default
    status: completed
  - id: tests-conftest
    content: Set GITHUB_REPOSITORY empty in tests/conftest autouse; adjust docs if needed
    status: completed
  - id: docs-env-readme
    content: Update .env.example and README for default/override/disable
    status: completed
isProject: false
---

# Default GitHub repository from pyproject

## Goals

- Record **`borzilleri/route53_ddns`** in [`pyproject.toml`](pyproject.toml) in a standard way (PEP 621 `[project.urls]`).
- Use that as the **default** `owner/repo` for GitHub Releases / version checking when **`GITHUB_REPOSITORY` is unset**.
- **Override**: any non-empty `GITHUB_REPOSITORY` still wins (pydantic-settings env priority).
- **Disable**: keep current behavior where **`GITHUB_REPOSITORY=`** (empty) normalizes to `None` via [`empty_github_repo`](src/route53_ddns/config.py) so operators can opt out of the upstream check.

## 1. pyproject metadata

Add:

```toml
[project.urls]
Repository = "https://github.com/borzilleri/route53_ddns"
```

This appears in wheel/sdist metadata as `Project-URL` and can be read with `importlib.metadata`.

## 2. Resolve default `owner/repo` in code

Add a small helper (e.g. in [`src/route53_ddns/config.py`](src/route53_ddns/config.py) or a tiny [`src/route53_ddns/package_meta.py`](src/route53_ddns/package_meta.py)) that:

1. Uses `importlib.metadata.metadata("route53-ddns")` and `get_all("Project-URL")` to find the entry whose label is **`Repository`**, parses the URL (handle `https://github.com/{owner}/{repo}` with optional `.git` / trailing slash).
2. If metadata is missing or parsing fails (e.g. dev edge case), **fallback** to the literal string **`borzilleri/route53_ddns`** so behavior stays predictable.

Set `Settings.github_repository` **default** to the result of that helper (not `None`). Pydantic Settings will still apply **`GITHUB_REPOSITORY` from the environment when set**; empty string continues to map to `None` via existing validators.

## 3. Tests

- **[`tests/conftest.py`](tests/conftest.py)** autouse `env_config`: add `monkeypatch.setenv("GITHUB_REPOSITORY", "")` **before** `clear_settings_cache()` so the suite does not call the real GitHub API by default (same pattern as other env isolation).
- **[`tests/test_update_check.py`](tests/test_update_check.py)**: `test_update_check_without_github_repo` remains valid (configured `false` with empty env). Optionally add a **unit test** for the URL→slug helper (mocked `Project-URL` or direct call to fallback).

## 4. Docs

- **[`.env.example`](.env.example)**: Comment that `GITHUB_REPOSITORY` is optional and defaults to the upstream repo; set empty to disable the check.
- **[`README.md`](README.md)**: Update the `GITHUB_REPOSITORY` row and `GET /api/update-check` blurb to describe default + override + disable.

## Behavior summary

| `GITHUB_REPOSITORY` | Effective repo |
|----------------------|----------------|
| (unset) | `borzilleri/route53_ddns` from metadata (fallback) |
| `myfork/route53_ddns` | `myfork/route53_ddns` |
| `` (empty) | `None` — no GitHub API call, footer shows version only |
