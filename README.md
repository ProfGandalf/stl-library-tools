# STL Library Tools

Narzędzia do biblioteki modeli 3D (figurki, STL-e). Aplikacja z okienkiem, która:

- **renderuje plansze poglądowe** przez Blendera: każdy podfolder z modelami daje dwa
  obrazy PNG (`nazwa_A.png` i `nazwa_B.png`), na których te same części są pokazane z obu stron;
- **pakuje podfoldery do ZIP**: folder pakuje się w tle, gdy Blender robi już następny.

## ⬇️ Pobierz

**[Najnowsza wersja (Releases)](https://github.com/ProfGandalf/stl-library-tools/releases/latest)**

Bezpośrednie linki:

| system | plik |
|---|---|
| **Windows** | [**STL-Tools.exe**](https://github.com/ProfGandalf/stl-library-tools/releases/latest/download/STL-Tools.exe) |
| Linux | [STL-Tools-linux](https://github.com/ProfGandalf/stl-library-tools/releases/latest/download/STL-Tools-linux) (po pobraniu `chmod +x`) |

To jeden plik, bez instalacji i bez Pythona. Potrzebny jest tylko
[Blender](https://www.blender.org/download/).

> Windows może przy pierwszym uruchomieniu pokazać ostrzeżenie SmartScreen, bo plik nie
> jest podpisany. Kliknij **„Więcej informacji” → „Uruchom mimo to”**.

## Jak używać

1. Uruchom `STL-Tools.exe`.
2. **Folder z modelami**: wskaż folder nadrzędny, w którym każdy podfolder to jeden zestaw.
3. **Blender** jest wyszukiwany automatycznie. Jeśli go nie znajdzie, wskaż `blender.exe` ręcznie.
4. Zaznacz podfoldery, wybierz render i/lub ZIP, kliknij **Start**.

Szczegóły są w [app/README.md](app/README.md).

## Zawartość repozytorium

| folder | co to jest |
|---|---|
| [`app/`](app) | aktualna aplikacja: źródła (`stl_tools.py`, `render_grid.py`) |
| [`Scripts - version 1/`](Scripts%20-%20version%201) | pierwsze wersje: `.bat` + skrypt Blendera, uruchamiane dwuklikiem w folderze z modelami |
| `.github/workflows/build-app.yml` | automatyczne budowanie `.exe` i plików wydania po każdej zmianie w `app/` na `main` |
