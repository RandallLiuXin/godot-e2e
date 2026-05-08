# Next Release

> **Contributors:** Every pull request MUST include an entry in this file describing the change.
> When a new version is released, this file will be archived as `vX.Y.Z.md` and a fresh copy will take its place.

## How to add an entry

Append your change under the appropriate category below. Use this format:

```
- Brief description of the change (#PR_NUMBER) — @author
```

If no category fits, add a new one following [Keep a Changelog](https://keepachangelog.com/) conventions.

---

## Added

- GitHub Pages documentation site built with MkDocs Material — bilingual (en + zh-CN) via `mkdocs-static-i18n`, full-text search across both languages, language switcher in the header, dedicated landing page distinct from the README. Auto-deploys to `https://randallliuxin.github.io/godot-e2e/` on every push to `main` that touches `docs/`, `mkdocs.yml`, or `requirements-docs.txt`. (#PR_NUMBER) — @LiuXin

## Changed

## Fixed

- `docs/update/release-checklist.md` step 7 — corrected the Asset Library field name (`Download Commit/URL`, not `Commit/Tag`) and clarified that it requires a full commit hash; tag names are rejected by the form. — @LiuXin

## Removed
