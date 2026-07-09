# Current State

Last updated: 2026-07-09

## Product Snapshot

- Project: STEP tree comparison (volume, center of mass, diff statuses).
- Main interfaces:
  - CLI: compare two STEP files and generate HTML.
  - Web: upload 2 STEP files, render tree A/B plus diff.
- Visualization:
  - PNG previews for each tree element.
  - Embedded STL viewer for the currently selected element with rotate/pan/zoom.

## Architecture State

- cli.py: CLI execution, volume/com tolerances, HTML/JSON output.
- app.py: Flask UI, upload, compare, session-based STL/PNG routing.
- src/step_tree.py: STEP -> Node, per-node STL export (`stl_id`), correct instance COM.
- src/compare.py: Node -> DiffNode, `volume_tol_pct` / `com_tol_mm` tolerances.
- src/report.py: three panels (A | diff | B), PNG thumbnails, inline STL viewer.

## Verified Behaviors

- The instance COM regression is covered by `test_cylinder_center_of_mass_reflects_assembly_location`.
- Tests: `pytest tests/ -v` -> pass.
- Smoke: `cli.py` on `sample_a`/`sample_b` generates `report.html`.

## Risks / Open Points

- Node matching by name can lose precision when parts are renamed.
- In large assemblies, PNG preview generation can increase page load time.
- The session STL cache is limited; older sessions are removed FIFO.

## Next Slice Ideas

1. Optimize thumbnail generation (queue + lazy loading by visibility).
2. Add a stable node path ID, not just name.
3. Add optional export of the report and STL artifacts to a user directory.
