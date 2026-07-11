# Publishing to PyPI

This repo can publish **ai-guider** to [PyPI](https://pypi.org) when you create a GitHub Release. The workflow lives at `.github/workflows/publish.yml`.

You only need this if you want others to install with:

```bash
pip install ai-guider
```

Until then, install from the clone as in [installation.md](installation.md).

---

## One-time setup (do this once)

### 1. Create the PyPI project (first release only)

- Create an account on [pypi.org](https://pypi.org)
- Prefer **Trusted Publishing** (no API token in GitHub secrets)

On PyPI: **Publishing → Trusted publishers → Add a new pending publisher**

| Field | Value |
|-------|--------|
| PyPI project name | `ai-guider` |
| Owner | `odaneky` |
| Repository | `ai-guider` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

### 2. Create a GitHub Environment

In the GitHub repo: **Settings → Environments → New environment**

- Name: `pypi` (must match the workflow)
- Optional: add required reviewers so publishing needs a human click

### 3. Align the version

Before you release, set the same version in:

- `pyproject.toml` → `version = "..."`  
- `CHANGELOG.md` → matching section  

Local smoke check:

```bash
python -m build
ls dist/
```

---

## How to publish a release

1. Commit and push your changes to `main`
2. On GitHub: **Releases → Draft a new release**
3. Tag like `v0.2.4` (match `pyproject.toml`)
4. Publish the release

GitHub Actions will:

1. Build the wheel and source archive  
2. Upload them to PyPI  

Check progress under the repo **Actions** tab.

---

## If publish fails

| Symptom | Likely fix |
|---------|------------|
| Trusted publisher not found | Pending publisher on PyPI must match owner/repo/workflow/environment exactly |
| Environment protection blocked | Approve the deployment in GitHub Environments |
| File already exists | That version is already on PyPI — bump the version and release again |
| Build error | Run `python -m build` locally and fix packaging |

---

## TestPyPI (optional)

For a dry run, add a second workflow or temporarily point publishing at TestPyPI. Most people skip this and publish a low version (e.g. `0.2.0`) once trusted publishing is confirmed.
