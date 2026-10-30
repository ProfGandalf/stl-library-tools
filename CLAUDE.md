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
    `--` (`--only` takes a path relative to `--folder` with "/", e.g. `_Vehicles/Rhino`,
    and the sheet is saved next to that folder) and the `@@ ...` progress lines (TOTAL / FOLDER / IMPORT / RENDER / DONE), which
    the GUI parses together with Cycles `Sample X/Y` lines. **Changing the `@@` format
    requires a matching change in `stl_tools.py`.** The GUI also marks log lines
    containing `ERROR` / `Error` / `!!!` as errors.
- **Quick preview mode** (`--preview`, radio "quick preview" in the app): Workbench render
  of the same layout at `PREVIEW_RES` 1500 px, one side -> `name_preview_A.png`
  (`setup_workbench()` only overrides settings after the Cycles setup; full sheets untouched),
  plus the largest image in the set folder saved as PNG -> `name_preview_B.png`
  (`find_vendor_image()`, `save_as_png()`), reported with `@@ IMAGE ok|none|fail <rel>`.
- **Full sheets engine** (`ENGINE` / `--engine cycles|workbench`, "engine" combobox in the app):
  `"workbench"` runs the same `setup_workbench()` at `RES_X` with both sides A/B. Added after
  the user compared a Cycles sheet with a quick preview and found the Workbench one more
  readable (no shadows over neighbours, cavity edges). Cycles stays the default.
- **Pause:** `suspend_process()` freezes Blender (SIGSTOP/SIGCONT, Windows
  NtSuspendProcess/NtResumeProcess); the ZIP thread waits on the `self.running` event
  between 1 MB chunks. Stop while paused must thaw the process first, otherwise it never
  handles the terminate. Elapsed / ETA use `_active_time()` (paused time excluded).
- **Blender must never outlive a run:** `_run_render` ends it in a `finally`
  (`end_process`: thaw, terminate, kill after 5 s). Stop kills after 5 s if the polite
  terminate is ignored; closing the window waits for Blender and the ZIP thread. If the app
  itself dies, `ChildGuard` takes Blender with it (Windows job object with
  KILL_ON_JOB_CLOSE, Linux PR_SET_PDEATHSIG). A garbled `@@` line is logged, not fatal.
- **Folder prefixes in the app:** `_` = work-in-progress group (collapsible, never a set
  itself, its sets selectable and unticked by default, nesting allowed), `__` = hidden
  completely. Sets are keyed by their relative path everywhere in the GUI (tree iids,
  `self.rows`, `@@` lines). Inside a set all subfolders belong to the set.
- **`Scripts - version 1/`**: the original scripts, run by double-click inside the
  parent folder, kept as an archive. Make new heuristic changes in `app/render_grid.py`.
  - `__RENDER.bat` + `__render_grid.py`: renders model folders as preview sheets
  - `__ZIP.bat`: packs subfolders into ZIP archives
- **Release:** `.github/workflows/build-app.yml` builds `STL-Tools.exe` (with the icon),
  `STL-Tools-linux.tar.gz` (folder with the binary, icon, README; keeps the executable
  bit) and the bare `STL-Tools-linux` with PyInstaller (render script and `app/icon/`
  bundled), and updates the `app-latest` release in place, only from `main`. The README
  links to `releases/latest/download/<file>`, so asset names must not change.
- **Icon:** `app/icon/make_icon.py` draws `icon.png` / `icon.ico` (contact sheet + zipper,
  simpler drawing at <= 48 px). The app sets it as the window icon; on Linux the
  single-file build writes `~/.local/share/applications/stl-tools.desktop` and the icon
  on every start (only if changed), and `className="stl-tools"` matches `StartupWMClass`.

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
  with `NORMALIZE = False`.
  **Correction (tested):** the X rotation of 70–75° does *not* give short shadows. A sun
  with X = 0 points straight down, so X = 70° is a sun only 20° above the horizon:
  shadows are ~2.75× the part height (70° → 2.75×, 45° → 1×, 25° → 0.47×) and they do
  spill onto neighbours. A test with real Blender (Cycles, same scene, tilts 70–75 vs
  45–55 vs 25–45) showed the trade-off: steeper suns give compact shadows but flatten the
  surface relief (raking light is what shows it) and brighten the background (corner
  63 → 96 → 105 of 255). The user found a Workbench sheet more readable than both, which
  is why `ENGINE = "workbench"` exists. The Cycles tilts were left unchanged - change them
  only if the user asks.

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
