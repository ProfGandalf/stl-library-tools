# STL Library Tools — app

Desktop version of the two scripts in `Scripts - version 1`: rendering preview sheets
(Blender) and packing subfolders into ZIP archives. Works on Windows and Linux.

## Running it

### Easiest: one file, no Python

In the repository open **Releases → “STL Tools (latest version)”** and download:
- **Windows:** `STL-Tools.exe`, then double-click it.
- **Linux:** `STL-Tools-linux.tar.gz`, extract it and double-click `STL-Tools` in the
  extracted folder. The archive keeps the run permission. On start the app adds itself to
  the applications menu with its icon (`~/.local/share/applications/stl-tools.desktop`).

The file is built automatically (GitHub Actions, `.github/workflows/build-app.yml`) after
every change in `app/` on `main`, with the Blender script bundled inside. On first launch
Windows may show a SmartScreen warning because the file is not signed. In that case click
“More info → Run anyway”.

### From the source files (needs Python)

- **Windows:** double-click `STL Tools.bat`.
  Needs Python 3 from [python.org](https://www.python.org/downloads/) (tkinter is included).
- **Linux:** `./stl_tools.sh`.
  Needs `python3-tk` (Ubuntu/Debian: `sudo apt install python3-tk`).

The app can live anywhere. It does not need to be copied into the models folder.

## How to use

1. **Models folder**: the parent folder in which every subfolder is one set
   (same as with the old `.bat` files).
2. **Blender** is detected automatically. If it is not found, select the file by hand.
3. Tick the subfolders to process. Quick buttons:
   *All*, *None*, *Without PNG* (only those without a sheet), *Without ZIP*.
   `Stare`, `Robocze` and `Do sprawdzenia` are unticked by default.

   Folder name prefixes:
   - **`_` = work-in-progress group** (e.g. `_Vehicles`). Shown as a collapsible row;
     the group itself is never rendered or zipped, but the sets inside it can be ticked.
     Clicking the group ticks / unticks all its sets (☑ all, ▣ some, ☐ none). Sets
     inside groups start unticked. A `_` folder inside a group is a sub-group.
     The sheet and the ZIP of a set inside a group go next to it, e.g.
     `_Vehicles/Rhino_A.png` and `_Vehicles/Rhino.zip`.
   - **`__` = hidden completely**, at any depth.

   Inside a set folder (e.g. `Dreadnought/Arms`) every subfolder is part of that set,
   whatever its name.
4. Choose what to do: render, ZIP or both. The render has two modes:
   - **full sheets**: `name_A.png` + `name_B.png` (resolution and A/B apply here), with
     an **engine** choice:
     - *Cycles (realistic)*: real light, ambient occlusion and shadows; slow (samples apply);
     - *Workbench (fast)*: the viewport look of the quick preview (studio light, edges
       and recesses outlined, no shadows) at full resolution; crisp and seconds per sheet.
   - **quick preview**, to recognise a set at a glance:
     - `name_preview_A.png`: the same layout, rendered with Blender's fast Workbench
       engine at 1500 px, one side (seconds instead of minutes);
     - `name_preview_B.png`: the largest picture found in the set folder, usually the
       vendor's promo render, converted to PNG if needed. No picture, no `_preview_B`.

   The *Preview* column shows which sets already have `name_preview_A.png`.
   Both "overwrite" options are ticked by default: Both "overwrite" options are ticked by default:
   - **overwrite existing PNGs** off: a folder that already has its sheet(s)
     (`name_A.png` + `name_B.png`, or `name.png` for one side) is not sent to Blender
     at all, so there is no import and no render. It is still zipped.
   - **overwrite existing ZIPs** on: the new archive is written next to the old one and
     replaces it only once it is complete. Off: folders that already have a ZIP are skipped.

   Folders go one by one: Blender renders
   folder 1, and when it is done, folder 1 is zipped while Blender already renders
   folder 2, and so on. Folders without models are zipped right away.
5. **Start.** The top bar shows overall progress and the estimated time left. Below it
   are two bars side by side: Blender (import, side A, side B) and ZIP (megabytes).
   **Pause** freezes everything in place: Blender is suspended mid-render (it keeps its
   memory, also on the GPU) and zipping waits; **Resume** continues exactly where it
   stopped. Paused time is not counted in the elapsed / remaining time.
   **Stop** stops the work, and an unfinished ZIP is deleted.

Full Blender output is in the **Log** tab.
Settings (paths, options) are saved automatically:
`%APPDATA%\stl-library-tools\config.json` / `~/.config/stl-library-tools/config.json`.

## Files

| file | role |
|---|---|
| `stl_tools.py` | the app (tkinter, standard library only) |
| `render_grid.py` | Blender script: same as version 1, plus arguments and `@@` progress lines |
| `STL Tools.bat` / `stl_tools.sh` | launchers |
| `icon/` | app icon (`icon.png`, `icon.ico`) and `make_icon.py`, which draws it (needs Pillow) |

All render settings other than resolution, quality and A/B (orientation, `ROTATIONS`,
colours, etc.) are still at the top of `render_grid.py`.
