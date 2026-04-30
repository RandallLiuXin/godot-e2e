# Release Checklist

Steps to follow when publishing a new version of godot-e2e.

## Pre-release

1. **Finalize `docs/update/next.md`**
   - Review all entries, fix typos, group by category
   - Rename `next.md` to `vX.Y.Z.md` (e.g., `v0.2.0.md`) as a permanent archive
   - Create a new empty `next.md` by copying `docs/update/next.template.md`

2. **Update version numbers**
   - `pyproject.toml` — update `version = "X.Y.Z"`
   - `addons/godot_e2e/plugin.cfg` — update `version="X.Y.Z"`
   - `CHANGELOG.md` — move entries from `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
   - `SECURITY.md` — update the supported versions table if needed

3. **Run all tests locally**
   ```bash
   godot-e2e tests/ -v
   godot-e2e examples/minimal/tests/e2e/ -v
   godot-e2e examples/platformer/tests/e2e/ -v
   godot-e2e examples/ui_testing/tests/e2e/ -v
   ```

4. **Verify the package builds**
   ```bash
   pip install build
   python -m build
   pip install dist/godot_e2e-X.Y.Z-py3-none-any.whl
   ```

## Publish to PyPI

5. **Create a git tag and push**
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
   This triggers the `publish.yml` GitHub Actions workflow, which builds and uploads to PyPI via Trusted Publisher.

6. **Verify on PyPI**
   - Check https://pypi.org/project/godot-e2e/ for the new version
   - Test installation: `pip install godot-e2e==X.Y.Z`

## Publish to Godot Asset Library

7. **Update the asset on https://godotengine.org/asset-library/asset**
   - Log in and edit the existing asset (or submit a new one for the first release)
   - Update the **Commit/Tag** field to `vX.Y.Z`
   - Update the description if needed
   - Wait for moderator approval

## Post-release

8. **Create a GitHub Release**
   - Go to the repository's Releases page
   - Select the `vX.Y.Z` tag
   - Title: `vX.Y.Z`
   - Body: copy from `CHANGELOG.md` for this version
   - Attach the built `.whl` and `.tar.gz` from the workflow artifacts if desired

9. **Announce** (optional)
   - Post on relevant communities (Godot forums, Reddit, etc.)
