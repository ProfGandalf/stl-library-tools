# STL Library Tools — aplikacja

Okienkowa wersja dwóch skryptów z `Scripts - version 1`: render plansz poglądowych
(Blender) i pakowanie podfolderów do ZIP. Działa na Windows i Linuksie.

## Uruchamianie

- **Windows:** dwuklik na `STL Tools.bat`.
  Potrzebny Python 3 z [python.org](https://www.python.org/downloads/) (tkinter jest w standardzie).
- **Linux:** `./stl_tools.sh`.
  Potrzebny `python3-tk` (Ubuntu/Debian: `sudo apt install python3-tk`).

Aplikację można trzymać gdziekolwiek. Nie trzeba jej kopiować do folderu z modelami.

## Jak używać

1. **Folder z modelami**: folder nadrzędny, w którym każdy podfolder to jeden zestaw
   (tak jak wcześniej przy `.bat`).
2. **Blender** jest wyszukiwany automatycznie. Jeśli go nie znajdzie, wskaż plik ręcznie.
3. Na liście zaznacz podfoldery do przerobienia. Szybkie przyciski:
   *Wszystkie*, *Żaden*, *Bez PNG* (tylko te bez planszy), *Bez ZIP*.
   Domyślnie nie są zaznaczone `Stare`, `Robocze` i `Do sprawdzenia`, a foldery
   zaczynające się od `_` są zawsze pomijane.
4. Wybierz, co zrobić: render, ZIP albo oba. Najpierw leci render wszystkich
   zaznaczonych folderów, potem pakowanie.
5. **Start.** Górny pasek pokazuje postęp etapu i szacowany czas, dolny pokazuje bieżący
   folder (import, strona A, strona B, a przy ZIP megabajty).
   **Stop** przerywa pracę. Niedokończony ZIP jest usuwany.

Pełne komunikaty Blendera są w zakładce **Log**.
Ustawienia (ścieżki, opcje) zapisują się same:
`%APPDATA%\stl-library-tools\config.json` / `~/.config/stl-library-tools/config.json`.

## Pliki

| plik | rola |
|---|---|
| `stl_tools.py` | aplikacja (tkinter, tylko biblioteka standardowa) |
| `render_grid.py` | skrypt Blendera: ten sam co w wersji 1, plus argumenty i linie postępu `@@` |
| `STL Tools.bat` / `stl_tools.sh` | uruchamianie |

Wszystkie ustawienia renderu poza rozdzielczością, jakością i A/B (orientacja,
`ROTATIONS`, kolory itd.) nadal są na górze `render_grid.py`.
