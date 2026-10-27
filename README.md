# <img src="app/icon/icon.png" width="40" align="top"> STL Library Tools

Tools for a 3D model library (miniatures, STL files). A desktop app that:

- **renders preview sheets** with Blender: every subfolder of models produces two
  PNG images (`name_A.png` and `name_B.png`) showing the same parts from both sides;
- **packs subfolders into ZIP archives**: a folder is zipped in the background while
  Blender is already rendering the next one.

## ⬇️ Download

**[Latest version (Releases)](https://github.com/ProfGandalf/stl-library-tools/releases/latest)**

Direct links:

| system | file |
|---|---|
| **Windows** | [**STL-Tools.exe**](https://github.com/ProfGandalf/stl-library-tools/releases/latest/download/STL-Tools.exe) |
| Linux | [STL-Tools-linux.tar.gz](https://github.com/ProfGandalf/stl-library-tools/releases/latest/download/STL-Tools-linux.tar.gz): extract it, double-click `STL-Tools` in the extracted folder |

It is one download, with no installation and no Python needed. The only requirement is
[Blender](https://www.blender.org/download/).

> On first launch Windows may show a SmartScreen warning because the file is not signed.
> Click **“More info” → “Run anyway”**.
>
> On Linux the app adds itself to the applications menu, with its icon, every time it
> starts. The bare [STL-Tools-linux](https://github.com/ProfGandalf/stl-library-tools/releases/latest/download/STL-Tools-linux)
> file is still available, but a downloaded bare file needs `chmod +x` (or Properties →
> Permissions → “Allow executing file as program”) before it runs.

## How to use

1. Run `STL-Tools.exe`.
2. **Models folder**: select the parent folder in which every subfolder is one set.
3. **Blender** is detected automatically. If it is not found, select `blender.exe` by hand.
4. Tick the subfolders, choose render and/or ZIP, click **Start**.
   Folders starting with `_` are work-in-progress groups whose sets you can tick one by
   one. Folders starting with `__` are hidden.

Details are in [app/README.md](app/README.md).

## Repository contents

| folder | what it is |
|---|---|
| [`app/`](app) | the current app: sources (`stl_tools.py`, `render_grid.py`) |
| [`Scripts - version 1/`](Scripts%20-%20version%201) | first versions: `.bat` + Blender script, run by double-click inside the models folder |
| `.github/workflows/build-app.yml` | builds the `.exe` and the release files automatically after every change in `app/` on `main` |
