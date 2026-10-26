# Kontekst projektu

Narzędzia wsadowe do biblioteki modeli 3D (figurki Warhammer, STL-e od sprzedawców).
Dwie wersje:

- **`app/`**: aktualna, okienkowa aplikacja (tkinter, Windows + Linux). Wybór folderów,
  render, potem ZIP, paski postępu. Opis jest w `app/README.md`.
  - `app/stl_tools.py`: GUI. Tylko biblioteka standardowa, bez zależności.
  - `app/render_grid.py`: skrypt Blendera, który aplikacja uruchamia przez
    `blender --background --python render_grid.py -- --folder X --only nazwa ...`.
    Logika renderu jest identyczna z wersją 1. Doszły tylko argumenty po `--` i linie
    postępu `@@ ...` (TOTAL / FOLDER / IMPORT / RENDER / DONE), które GUI parsuje razem
    z liniami Cycles `Sample X/Y`. **Zmiana formatu `@@` wymaga zmiany w `stl_tools.py`.**
- **`Scripts - version 1/`**: pierwotne skrypty uruchamiane dwuklikiem w folderze
  nadrzędnym, zostawione jako archiwum. Nowe zmiany heurystyk wprowadzaj w
  `app/render_grid.py`.
  - `__RENDER.bat` + `__render_grid.py`: render folderów modeli jako plansze poglądowe
  - `__ZIP.bat`: pakowanie podfolderów do archiwów ZIP

Poniższe decyzje dotyczą skryptu renderującego w obu wersjach.

**Rozmowa po polsku.** Komentarze w kodzie też po polsku, ale **bez polskich znaków
diakrytycznych** — skrypt leci przez `blender --background` w konsoli Windows i ogonki
się tam sypią.

**Każda wiadomość zaczyna się od imienia użytkownika: „Marcin".** Zawsze pierwsze słowo
odpowiedzi to „Marcin", bez wyjątków.

---

## Jak to działa

Skrypt renderujący wrzuca się do folderu zawierającego podfoldery modeli. Dla każdego
podfolderu generuje dwa pliki PNG: `nazwa_A.png` i `nazwa_B.png` — ten sam układ, ale
na B wszystkie modele obrócone o 180° wokół osi X. Dzięki temu każdą część widać
z obu stron, bez zgadywania, która strona jest „lepsza".

Kluczowa własność: obrót o 180° wokół X **nie zmienia wymiarów obrysu** (X ten sam,
Y lustrzany, Z ten sam), więc pakowanie liczy się raz i części są dokładnie w tych
samych miejscach na obu planszach. Łatwo je porównywać przełączając podgląd.

Ustawienia są na górze `__render_grid.py`, podzielone na 7 kategorii. Dodatkowo
`_settings.json` wrzucony do konkretnego folderu nadpisuje je tylko dla niego.

---

## Decyzje, których NIE cofać

Każda z poniższych to naprawiony błąd albo świadomy wybór po testach na realnych
plikach. Przed zmianą którejkolwiek — zapytaj użytkownika.

### 1. Obroty tylko przez `rotate_world()`, nigdy `rotation_euler[i] +=`

Blender składa kąty Eulera w kolejności XYZ (`R = Rz @ Ry @ Rx`), więc składowa X
działa **pierwsza**. Jeśli model został wcześniej położony obrotem wokół Y, to dodanie
180° do składowej X **nie odwróci go na drugą stronę** — obróci go w płaszczyźnie,
bo obrót Y przemapował oś X.

To powodowało realny błąd: wersja B pokazywała model obrócony bokiem zamiast spodem,
a `AUTO_FLIP` i `ROTATIONS` robiły co innego, niż deklarowały.

`rotate_world()` składa macierz świata (`R @ matrix_world`) i jest odporna na kolejność
wcześniejszych obrotów.

### 2. Pakowanie używa prawdziwego bboxa, nie percentyli

`robust_bounds()` (percentyle 1–99% położenia wierzchołków) istnieje po to, żeby
zabłąkany wierzchołek nie rozdmuchiwał kadru. Ale **do pakowania trzeba prawdziwych
wymiarów**.

Przy dużych płaskich płytach (ściany, panele) geometria jest gęsta w środku i rzadka
na krawędziach — percentyle obcinały wtedy realne brzegi, zaniżając wymiary nawet
o 40%. Efekt: sloty za małe, sąsiednie części nachodziły na siebie.

Teraz `dims` liczy się z `world_bbox()`, a percentyle są tylko bezpiecznikiem: jeśli
prawdziwy bbox jest ponad 3× większy od przyciętego, bierzemy przycięty i wypisujemy
nazwę pliku w konsoli.

**Środkowanie w slocie musi używać tej samej miary co wymiary slotu** — inaczej część
przesunie się względem swojego miejsca i wejdzie na sąsiada.

### 3. Kamera ma jawnie ustawiany `clip_start` / `clip_end`

Bez tego Blender obcina domyślnym zasięgiem i render wychodzi **pusty** — widać samo
tło świata, bez modeli i bez podłogi. Modele mają footprinty rzędu 100+ jednostek,
a kamerę stawiamy w odległości `grid_diag * 3`, czyli przy większych zestawach setki
albo tysiące jednostek.

Objaw: jednolity szary kwadrat przy dużych folderach, przy małych wszystko OK.
Konsola wypisuje teraz `Kamera: odleglosc X, zasieg Y - Z` do diagnozy.

### 4. Orientacja — przetestowano 5 metod, zostajemy przy `"flat"`

**Nie proponuj nowych heurystyk orientacji bez wyraźnej prośby.** Przerobiliśmy:

| `ORIENT_METHOD` | zasada | wynik |
|---|---|---|
| `"flat"` | najkrótsza oś do góry + `AUTO_FLIP` | **używana** |
| `"detail"` | 6 ścian, gęstość siatki | gorzej |
| `"normals"` | 6 ścian, rozrzut normalnych ważony polem | gorzej |
| `"raster"` | 6 kierunków, mapa głębi z zasłanianiem | gorzej |
| `"entropy"` | entropia widoku (Vázquez) | gorzej |

Sam `AUTO_FLIP` ma dwa warianty (`FLIP_METHOD`): `"density"` (używany) i `"depth"`.
Wariant `"depth"` był przerabiany trzykrotnie — pierwsza wersja mierzyła rozrzut
wysokości i konsekwentnie wybierała **wydrążone tyły**, bo wielka gładka misa ma
większą amplitudę niż drobny relief. Poprawka: lokalny gradient (częstotliwość zmian),
nie amplituda. Potem doszła kara za wklęsłość.

Wszystkie metody zostały w kodzie jako opcje — **nic nie usuwać**.

**Wniosek użytkownika, trafniejszy od moich hipotez:** orientacja zapisana w pliku to
świadoma decyzja rzeźbiarza, a „przód" to pojęcie znaczeniowe, nie geometryczne. Żadna
miara liczona z geometrii tego nie odgadnie. Przy organicznych częściach (Nurgle, obła
rzeźba, brak płaskich ścian) automatyka wyraźnie szkodzi.

Dlatego istnieje `ORIENT_BIAS` (domyślnie 1.25) — model jest obracany dopiero, gdy inna
ściana jest o tyle razy lepsza od obecnej góry. Symulacja: przy `BIAS = 1.0` skrypt
psuł 35 na 80 dobrze ustawionych modeli; przy 1.15+ psuł zero, naprawiając nadal
wszystkie faktycznie złe.

Przy częściach rzeźbionych z obu stron wybór jest z natury arbitralny — i właśnie
dlatego renderujemy A i B.

Wyjątki poprawia się ręcznie przez `ROTATIONS` (klucz = nazwa pliku, ze ścieżką
podfolderu gdy `RECURSIVE = True`, np. `"Arms/lewa.stl"`). Do odczytania nazw służy
`SHOW_LABELS = True`.

### 5. `VIEW_MODE = "top"` jest domyślny, ale ma znane ograniczenie

Na **stojącą figurkę** patrząc z góry widzisz czubek głowy — dlatego foldery z gotowymi
miniaturkami wyglądają źle, a foldery z luźnymi częściami dobrze.

Jest zaimplementowany tryb `"auto"` (wykrywa po medianie wysokość/szerokość, próg
`AUTO_ISO_RATIO = 1.2`) oraz `"iso"` (kamera z rogu pod kątem). Użytkownik świadomie
wrócił do sztywnego `"top"`. **Nie włączaj `"auto"` bez pytania.**

### 6. Jeden import, dwa rendery

`main()` importuje modele i pakuje układ raz, renderuje A, obraca wszystko, renderuje B.
Nie rozdzielać tego z powrotem na dwa przebiegi — to była optymalizacja czasu
(znikł drugi import i drugie liczenie `AUTO_FLIP`).

---

## Rzeczy, o które użytkownik już pytał

- **3MF** nie jest obsługiwany (Blender nie importuje natywnie). Pliki są pomijane,
  nazwy wypisywane w konsoli. Obejście: eksport do STL ze slicera.
  Obsługiwane: STL, OBJ, PLY, FBX, GLB/GLTF.
- **Równoległe instancje Blendera** dają tylko ~1,2–1,4×, nie 2× — jedno GPU obsługuje
  rendery po kolei, zysk bierze się wyłącznie z nakładania fazy CPU (import, pakowanie,
  denoising) jednej instancji na fazę GPU drugiej. Karta: RTX 4070 Ti Super, 16 GB.
- **Skala modeli** — `NORMALIZE = False` to świadomy wybór, użytkownik chce prawdziwych
  proporcji. Nie włączać normalizacji jako „naprawy" czegokolwiek.
- **`ALLOW_ROTATE`** obraca części o 90° przy pakowaniu — ciaśniej, ale miecze i topory
  leżą poziomo zamiast pionowo. Zmierzony kompromis: wypełnienie kadru 39% → 72%,
  pole układu mniejsze o 45%.
- **Kolory** siedzą w `make_clay_material()` i w funkcji podłogi (szukaj `Base Color`),
  nie w sekcji ustawień. Obecnie: ciemne tło `(0.10, 0.11, 0.13)` + jasna kość
  `(0.72, 0.70, 0.66)`. Kolor modelu występuje w **dwóch** miejscach (BSDF i węzeł RGB
  zasilający miks AO) — zmieniać oba, inaczej się rozjedzie przy włączonym AO.
- **Światła** to `SUN`, nie `AREA` — są niezależne od skali sceny, co jest kluczowe przy
  `NORMALIZE = False`. Wysokie nachylenie (70°+) skraca cienie, żeby nie rozlewały się
  na sąsiadów przy ciasnym upakowaniu.

---

## Styl pracy

- Przed zmianą heurystyki — sprawdź ją liczbowo na symulacji i **pokaż wynik**.
  W historii tego projektu kilka „teoretycznie lepszych" metod wypadło w praktyce
  gorzej.
- **Symulacja potwierdzająca własną hipotezę to słaby dowód.** Rozstrzygające są
  rendery użytkownika. Kilkakrotnie moje symulacje potwierdzały metodę, która na
  realnych plikach działała źle.
- Po zmianie w `app/render_grid.py` lub `app/stl_tools.py` sprawdź składnię:
  `python3 -m py_compile app/render_grid.py app/stl_tools.py`
- Skrypt uruchamia się przez `blender --background --python`, więc nie ma dostępu do
  interfejsu Blendera ani (w normalnym trybie) do `bpy.context.space_data`.
- Blender 5.2 LTS wypisuje `DeprecationWarning: 'Material.use_nodes'` — to tylko
  informacja, nic nie psuje.
