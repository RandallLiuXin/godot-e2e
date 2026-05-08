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
   - **If minimum Godot version changed in this release** (see "Bumping the minimum Godot version" below for the full procedure):
     - Add a new row to the **Compatibility matrix** in `README.md` and `README.zh-CN.md`, and close out the previous row's version range
     - Bump `config/features=PackedStringArray("X.Y")` in `tests/godot_project/project.godot` and every `examples/*/godot_project/project.godot`
     - Update the Godot badge in both READMEs (e.g. `Godot-4.x` → `Godot-4.5%2B`)
     - Update the "works with standard Godot 4.x binaries" line in both READMEs to name the new minimum

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
   - Update the **Godot version** field to the current minimum (e.g. `4.5`) — Asset Library uses this to filter the listing for users on older engines
   - Update the description if needed
   - Wait for moderator approval

## Post-release

8. **Create a GitHub Release**
   - Go to the repository's Releases page
   - Select the `vX.Y.Z` tag
   - Title: `vX.Y.Z`
   - Body: copy from `CHANGELOG.md` for this version
   - **If minimum Godot version changed in this release**, prepend a callout to the body: `> **Note:** this release requires Godot X.Y+.`
   - Attach the built `.whl` and `.tar.gz` from the workflow artifacts if desired

9. **Announce** (optional)
   - Post on relevant communities (Godot forums, Reddit, etc.)

---

## Bumping the minimum Godot version

When a release raises the minimum supported Godot version, **all of the following must change in the same release PR** (not in the release commit on `main`). Per `docs/versioning.md`, this is a MINOR bump — the API contract is unchanged for users on supported engine versions.

Files to touch:

- `README.md` and `README.zh-CN.md`
  - Compatibility matrix: add a new row for `X.Y.x → Godot A.B+`, and close out the previous row's range (e.g. `1.0.x – 1.1.x → Godot 4.x`)
  - Top-of-file Godot badge: bump the version label
  - Any `4.x` mentions in feature bullets / descriptive text
  - CI install snippets and `GODOT_PATH` examples (Linux / Windows / macOS sections — easy to miss)
- `.github/workflows/ci.yml` — every Godot download URL, every `Godot_v4.X-stable_*` filename, every `GODOT_PATH=...` env value, and every step name like "Download Godot 4.X stable". CI runs against the version listed here, not `project.godot`'s features array, so missing this lands the merged PR on a red main.
- `tests/godot_project/project.godot` — `config/features=PackedStringArray("A.B")`
- `examples/*/godot_project/project.godot` — same field, every example
- `docs/update/next.md` — call out the bump under a `### Compatibility` heading so it propagates into the changelog

Then on the Asset Library and GitHub Release sides, set the **Godot version** field and the release-body callout as described in steps 7 and 8.
