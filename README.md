# stp-tree-diff

STEP assembly comparison tool built for the Fwdays Agentic Engineering greenfield assignment.

The project compares two STEP files at the assembly-tree level, computes volume and center of mass for each node, and produces a visual diff with per-part previews and a 3D STL viewer.

## What Is Implemented

- CLI comparison of two `.stp` / `.step` files.
- Web interface for uploading file A and file B.
- Three-column result view: tree A, diff, tree B.
- Diff statuses: `match`, `changed`, `added`, `removed`.
- Per-node STL export and PNG preview generation.
- Interactive 3D viewer for the selected element.
- Multilingual UI: Ukrainian, English, Danish.
- Regression tests for geometry and assembly placement.

## Why This Exists

When a CAD assembly changes, the useful question is not only whether the file changed, but which exact part changed, which part moved, and which part was added or removed. This tool makes that visible without opening both revisions manually in a CAD system.

## Install

```bash
pip install -r requirements.txt --break-system-packages
```

Python 3.10+ is required. Geometry parsing is done through OpenCASCADE bindings pulled by `cadquery` / `cadquery-ocp`.

## CLI Usage

```bash
python cli.py file_a.stp file_b.stp -o report.html
```

Useful options:

- `--volume-tol 0.5` sets the allowed volume delta percentage.
- `--com-tol 0.1` sets the allowed center-of-mass delta in mm.
- `--lang en` switches report language to `uk`, `en`, or `da`.
- `--json` also prints the diff tree as JSON.

Example:

```bash
python cli.py tests/fixtures/sample_a.stp tests/fixtures/sample_b.stp -o report.html --lang en
```

## Web Usage

```bash
python app.py
```

Then open `http://127.0.0.1:5000` locally, or `http://<server-ip>:5000` from another machine if port 5000 is forwarded and allowed by the firewall.

The Flask app binds to `0.0.0.0:5000` by default so it can be reached through NAT/router forwarding.

The web UI lets the user:

- upload two STEP files,
- tune geometry tolerances,
- switch UI language,
- inspect both trees side by side,
- click any element to open its STL and PNG preview.

## Run As Service-Like Task On Windows

If you want the app to start in the background automatically on Windows, use the provided Scheduled Task installer:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_service.ps1
```

This registers the task `STPTreeDiffWebApp`, which launches the Flask app through the project `.venv`.

To remove it later:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_service.ps1
```

Note: this is a Windows Scheduled Task, not a native Windows Service wrapper. For this Python/Flask app it is the most reliable built-in option without adding extra service-manager dependencies.

## Verification

Run the automated checks:

```bash
pytest tests/ -v
```

Run a smoke comparison:

```bash
python cli.py tests/fixtures/sample_a.stp tests/fixtures/sample_b.stp -o report.html
```

The tests validate geometry against independent analytical references:

- box volume: $V = a \cdot b \cdot c$
- cylinder volume: $V = \pi r^2 h$

There is also a regression test that protects the assembly-placement bug where center of mass could be computed from the referred label instead of the placed instance shape.

## Agentic Engineering Artifacts

This repository includes explicit process artifacts used during development:

- `AGENTS.md` for stable project context and technical traps.
- `docs/current-state.md` for the current system snapshot.
- `docs/spec-template.md` for pre-implementation feature specs.
- `.github/workflows/tests.yml` for automated verification.

Development slices followed this loop:

`context -> requirements -> specification -> small slice -> tests -> implementation -> verification -> review -> summary`

## Project Structure

```text
cli.py                 CLI entry point
app.py                 Flask web app
src/step_tree.py       STEP -> tree parsing, volume/COM, STL/PNG export
src/compare.py         tree diff logic
src/report.py          HTML report generation
src/i18n.py            translations
tests/test_geometry.py geometry and regression tests
```

## Current Limitations

- Node matching is name-based, so renamed parts appear as removed plus added.
- Large assemblies can make STL and PNG generation slower.
- Session asset storage is temporary and FIFO-limited in the Flask app.

## Submission Notes

For the assignment submission, the most relevant evidence in this repository is:

- working product with CLI and web UI,
- explicit agentic workflow artifacts,
- independent verification via tests,
- maker/checker separation captured through documented review flow.
