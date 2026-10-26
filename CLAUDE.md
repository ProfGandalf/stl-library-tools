# Project context

Batch tools for a 3D model library (Warhammer miniatures, STL files from vendors).
Two versions:

- **`app/`**: the current desktop app (tkinter, Windows + Linux). Folder selection,
  pipeline: Blender renders folder N while a separate thread zips folder N-1.
  Progress bars. Described in `app/README.md`.
  - `app/stl_tools.py`: GUI. Standard library only, no dependencies.
  - `app/render_grid.py`: Blender script the app runs as
    `blender --background --python render_grid.py -- --folder X --only name ...`.
    Render logic is identical to version 1. The only additions are the arguments after
    `--` and the `@@ ...` progress lines (TOTAL / FOLDER / IMPORT / RENDER / DONE), which
    the GUI parses together with Cycles `Sample X/Y` lines. **Changing the `@@` format
    requires a matching change in `stl_tools.py`.** The GUI also marks log lines
    containing `ERROR` / `Error` / `!!!` as errors.
- **`Scripts - version 1/`**: the original scripts, run by double-click inside the
  parent folder, kept as an archive. Make new heuristic changes in `app/render_grid.py`.
  - `__RENDER.bat` + `__render_grid.py`: renders model folders as preview sheets
  - `__ZIP.bat`: packs subfolders into ZIP archives
- **Release:** `.github/workflows/build-app.yml` builds `STL-Tools.exe` and
  `STL-Tools-linux` with PyInstaller (render script bundled) and updates the
  `app-latest` release in place, only from `main`. The README links to
  `releases/latest/download/<file>`, so asset names must not change.

The decisions below apply to the render script in both versions.

**Everything in English.** Conversation, code, comments, UI text, console messages,
commit messages, PR titles and descriptions, documentation — all in English. Keep code
comments ASCII-only (no special characters): the script runs through
`blender --background` in the Windows console, which garbles non-ASCII characters.

**Every message starts with the user's name: "Marcin".** The first word of every
reply is always "Marcin", no exceptions.

---

## How it works

The render script goes into a folder containing model subfolders. For every subfolder it
produces two PNG files: `name_A.png` and `name_B.png` — the same layout, but on B every
model is rotated 180° around the X axis. That way every part is visible from both sides,
without guessing which side is "better".

Key property: a 180° rotation around X **does not change the footprint dimensions**
(X the same, Y mirrored, Z the same), so packing is computed once and the parts sit in
exactly the same places on both sheets. They are easy to compare by switching between
the images.

Settings are at the top of `render_grid.py`, split into 7 categories. In addition,
a `_settings.json` dropped into a specific folder overrides them for that folder only.

> Note: `_settings.json`, `ORIENT_METHOD`, `ORIENT_BIAS` and `VIEW_MODE = "auto"`
> described in this file are **not** in the code in this repository (only `FLIP_METHOD`
> `"density"` / `"depth"` and `VIEW_MODE` `"top"` / `"iso"` exist). They may live in a
> local copy that was never committed — ask the user before assuming either way.

---

## Decisions NOT to reverse

Each of these is a fixed bug or a deliberate choice after testing on real files.
Ask the user before changing any of them.

### 1. Rotations only through `rotate_world()`, never `rotation_euler[i] +=`

Blender composes Euler angles in XYZ order (`R = Rz @ Ry @ Rx`), so the X component
acts **first**. If a model was previously laid down by a rotation around Y, adding
180° to the X component **will not flip it over** — it rotates it in-plane, because
the Y rotation remapped the X axis.

This caused a real bug: version B showed the model rotated sideways instead of from
below, and `AUTO_FLIP` and `ROTATIONS` did something other than what they claimed.

`rotate_world()` composes the world matrix (`R @ matrix_world`) and is immune to the
order of earlier rotations.

### 2. Packing uses the real bbox, not percentiles

`robust_bounds()` (1–99% percentiles of vertex positions) exists so that a stray
vertex does not blow up the frame. But **packing needs the real dimensions**.

With large flat plates (walls, panels) geometry is dense in the middle and sparse at
the edges — percentiles then cut off real edges, understating dimensions by up to 40%.
Result: slots too small, neighbouring parts overlapping.

Now `dims` comes from `world_bbox()`, and percentiles are only a safety net: if the
real bbox is more than 3× larger than the trimmed one, the trimmed one is used and the
file name is printed to the console.

**Centring in the slot must use the same measure as the slot dimensions** — otherwise
the part shifts relative to its place and runs into its neighbour.

### 3. The camera has `clip_start` / `clip_end` set explicitly

Without this Blender clips at its default range and the render comes out **empty** —
only the world background, no models and no floor. Models have footprints of 100+
units, and the camera is placed `grid_diag * 3` away, i.e. hundreds or thousands of
units for larger sets.

Symptom: a plain grey square for large folders, everything fine for small ones.
The console now prints `Camera: distance X, range Y - Z` for diagnosis.

### 4. Orientation — 5 methods tested, we stay with `"flat"`

**Do not propose new orientation heuristics unless explicitly asked.** We went through:

| `ORIENT_METHOD` | principle | result |
|---|---|---|
| `"flat"` | shortest axis up + `AUTO_FLIP` | **in use** |
| `"detail"` | 6 faces, mesh density | worse |
| `"normals"` | 6 faces, area-weighted normal spread | worse |
| `"raster"` | 6 directions, depth map with occlusion | worse |
| `"entropy"` | viewpoint entropy (Vázquez) | worse |

`AUTO_FLIP` itself has two variants (`FLIP_METHOD`): `"density"` (in use) and `"depth"`.
The `"depth"` variant was reworked three times — the first version measured height
spread and consistently picked **hollow backs**, because a big smooth bowl has a larger
amplitude than fine relief. Fix: local gradient (frequency of change), not amplitude.
Then a concavity penalty was added.

All methods stay in the code as options — **do not delete anything**.

**The user's conclusion, more accurate than my hypotheses:** the orientation saved in
the file is a deliberate decision by the sculptor, and "front" is a semantic concept,
not a geometric one. No measure computed from geometry can guess it. With organic
parts (Nurgle, rounded sculpts, no flat faces) automation clearly does harm.

That is why `ORIENT_BIAS` exists (default 1.25) — a model is rotated only when another
face is that many times better than the current top. Simulation: with `BIAS = 1.0`
the script broke 35 of 80 correctly placed models; with 1.15+ it broke none, while
still fixing all the ones that were actually wrong.

For parts sculpted on both sides the choice is inherently arbitrary — which is exactly
why we render A and B.

Exceptions are fixed by hand through `ROTATIONS` (key = file name, including the
subfolder path when `RECURSIVE = True`, e.g. `"Arms/left.stl"`). Use
`SHOW_LABELS = True` to read the names.

### 5. `VIEW_MODE = "top"` is the default, but has a known limitation

Looking at a **standing miniature** from above you see the top of its head — which is
why folders of finished miniatures look bad, while folders of loose parts look good.

An `"auto"` mode (detects by median height/width, threshold `AUTO_ISO_RATIO = 1.2`)
and `"iso"` (camera from a corner at an angle) are implemented. The user deliberately
went back to a fixed `"top"`. **Do not enable `"auto"` without asking.**

### 6. One import, two renders

`main()` imports the models and packs the layout once, renders A, flips everything,
renders B. Do not split this back into two passes — it was a time optimisation
(the second import and the second `AUTO_FLIP` computation went away).

---

## Things the user has already asked about

- **3MF** is not supported (Blender does not import it natively). Files are skipped and
  their names printed to the console. Workaround: export to STL from the slicer.
  Supported: STL, OBJ, PLY, FBX, GLB/GLTF.
- **Parallel Blender instances** give only ~1.2–1.4×, not 2× — one GPU handles renders
  one after another, and the gain comes only from overlapping the CPU phase (import,
  packing, denoising) of one instance with the GPU phase of the other.
  Card: RTX 4070 Ti Super, 16 GB.
- **Model scale** — `NORMALIZE = False` is a deliberate choice, the user wants real
  proportions. Do not turn normalisation on as a "fix" for anything.
- **`ALLOW_ROTATE`** rotates parts by 90° when packing — tighter, but swords and axes
  lie horizontally instead of vertically. Measured trade-off: frame fill 39% → 72%,
  layout area 45% smaller.
- **Colours** live in `make_clay_material()` and in the floor code (search for
  `Base Color`), not in the settings section. Currently: dark background
  `(0.10, 0.11, 0.13)` + light bone `(0.72, 0.70, 0.66)`. The model colour appears in
  **two** places (BSDF and the RGB node feeding the AO mix) — change both, otherwise
  they drift apart with AO enabled.
- **Lights** are `SUN`, not `AREA` — they do not depend on scene scale, which is crucial
  with `NORMALIZE = False`. A steep tilt (70°+) shortens shadows so they do not spill
  onto neighbours in a tight layout.

---

## Working style

- Before changing a heuristic — check it numerically on a simulation and **show the
  result**. In this project's history several "theoretically better" methods turned out
  worse in practice.
- **A simulation confirming your own hypothesis is weak evidence.** The user's renders
  are decisive. Several times my simulations confirmed a method that worked badly on
  real files.
- After changing `app/render_grid.py` or `app/stl_tools.py`, check the syntax:
  `python3 -m py_compile app/render_grid.py app/stl_tools.py`
- The script runs through `blender --background --python`, so it has no access to the
  Blender UI nor (in normal mode) to `bpy.context.space_data`.
- Blender 5.2 LTS prints `DeprecationWarning: 'Material.use_nodes'` — informational only,
  it breaks nothing.
