"""
==========================================================================
 RENDER GRID - podglad kolekcji modeli 3D na jednej planszy (Blender 4.x)
==========================================================================
 Importuje wszystkie modele z folderu, ustawia je w rowna siatke,
 nadaje jednolity matowy material (clay), ustawia miekkie swiatlo
 i kamere izometryczna, po czym renderuje jeden duzy obraz w wysokiej
 rozdzielczosci. Dobre do pokazania duzej ilosci czesci figurek.

 WERSJA DLA APLIKACJI (app/stl_tools.py). Aplikacja uruchamia ten plik:
   blender --background --python render_grid.py -- --folder X [--only nazwa]...
   i czyta z konsoli linie zaczynajace sie od "@@" (postep). Recznie da sie
   go odpalic tak samo jak wersje 1 - bez argumentow dziala identycznie.

 JAK UZYWAC (recznie, z Blendera):
   1. Otworz Blendera (najlepiej 4.x). Zamknij domyslna scene nie trzeba -
      skrypt sam ja czysci.
   2. Zakladka "Scripting" -> New -> wklej ten plik (albo Open i wskaz go).
   3. Zmien ponizej FOLDER na sciezke do swojego folderu z modelami.
   4. Nacisnij "Run Script" (Alt+P). Gotowy obraz zapisze sie do OUTPUT.

 Obsluguje: STL, OBJ, PLY, FBX, GLB/GLTF.
 UWAGA 3MF: Blender nie importuje 3MF natywnie. Najprosciej wyeksportuj
 te pliki do STL ze slicera (Bambu/Prusa/Chitubox). Skrypt pominie 3MF
 i wypisze liste pominietych plikow w konsoli.
==========================================================================
"""

import bpy
import os
import sys
import math
from mathutils import Vector, Matrix

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

# ========================== USTAWIENIA ==================================

# Zostaw FOLDER = "" -> skrypt uzyje folderu, w ktorym sam lezy.
# (dzieki temu wystarczy wrzucic skrypt + .bat do folderu z modelami)
FOLDER        = ""
OUTPUT        = ""          # puste -> ___png.png w tym samym folderze

BATCH         = True        # True: TRYB WSADOWY. Zamiast czytac modele wprost
                            # z FOLDER, wchodzi do kazdego PODFOLDERU i robi
                            # osobny render nazwany jak folder:
                            #   Modele\xyz\*.stl    ->  Modele\xyz.png
                            #   Modele\abc\*.stl    ->  Modele\abc.png
                            # Foldery bez plikow 3D sa pomijane.

RECURSIVE     = True        # True: modele zbierane sa TAKZE z podfolderow.
                            # Przyklad - folder z czesciami w podkatalogach:
                            #   Dreadnought\Arms\*.stl
                            #   Dreadnought\Body\*.stl
                            #   Dreadnought\Head\*.stl
                            # -> wszystko trafia na jedna plansze Dreadnought.png
                            # False: tylko pliki lezace wprost w folderze.


def _script_dir():
    """Folder, w ktorym lezy ten skrypt (dziala tez z blender --background)."""
    p = None
    try:
        p = os.path.abspath(__file__)
    except NameError:
        pass
    if not p or not os.path.isfile(p):
        # uruchomiony z edytora tekstu w Blenderze
        txt = bpy.context.space_data.text if hasattr(bpy.context, 'space_data') else None
        if txt and txt.filepath:
            p = bpy.path.abspath(txt.filepath)
    if not p:
        # ostatnia deska ratunku: argument --python z linii polecen
        for i, a in enumerate(sys.argv):
            if a == '--python' and i + 1 < len(sys.argv):
                p = os.path.abspath(sys.argv[i + 1])
                break
    return os.path.dirname(p) if p else os.getcwd()


ONLY = None    # lista nazw podfolderow do zrobienia (None = wszystkie)


def _parse_args():
    """Argumenty po '--' w linii polecen Blendera (podaje je aplikacja):
         --folder SCIEZKA   folder nadrzedny z podfolderami modeli
         --only NAZWA       zrob tylko ten podfolder (mozna powtarzac)
         --res PX           rozdzielczosc (kwadrat)
         --samples N        jakosc renderu
         --one-side         tylko plansza A (bez obroconej B)
    """
    global FOLDER, ONLY, RES_X, RES_Y, SAMPLES, RENDER_BOTH_SIDES
    if '--' not in sys.argv:
        return
    args = sys.argv[sys.argv.index('--') + 1:]
    i = 0
    while i < len(args):
        a = args[i]
        val = args[i + 1] if i + 1 < len(args) else None
        if a == '--folder' and val is not None:
            FOLDER = val
            i += 1
        elif a == '--only' and val is not None:
            ONLY = (ONLY or []) + [val]
            i += 1
        elif a == '--res' and val is not None:
            RES_X = RES_Y = int(val)
            i += 1
        elif a == '--samples' and val is not None:
            SAMPLES = int(val)
            i += 1
        elif a == '--one-side':
            RENDER_BOTH_SIDES = False
        i += 1


def progress(*parts):
    """Linia postepu dla aplikacji - zaczyna sie od '@@', flush od razu,
    bo przy przekierowanym wyjsciu Python buforuje cale bloki."""
    print("@@ " + " ".join(str(p) for p in parts), flush=True)


if not FOLDER:
    FOLDER = _script_dir()
if not OUTPUT:
    OUTPUT = os.path.join(FOLDER, "___png.png")

RES_X         = 4000        # rozdzielczosc pozioma (px)
RES_Y         = 4000        # rozdzielczosc pionowa (px)

RENDER_BOTH_SIDES = True    # True: dla kazdego folderu powstaja DWA pliki:
                            #   nazwa_A.png - modele jak ustawil je skrypt
                            #   nazwa_B.png - te same modele odwrocone na
                            #                 druga strone (widzisz ich spod)
                            # Uklad jest identyczny na obu, wiec latwo porownac
                            # i wybrac lepsza strone. False = tylko jeden plik.
SAMPLES       = 128         # jakosc renderu (wiecej = ladniej + wolniej)

# Proporcja ukladu modeli (szerokosc:wysokosc). 1.0 = kwadrat.
# None -> dopasuj automatycznie do proporcji obrazu (RES_X / RES_Y).
TARGET_ASPECT = 1.0

NORMALIZE     = False       # False: zachowaj prawdziwe proporcje/skale modeli
                            #        (OK gdy pliki sa w tych samych jednostkach)
                            # True: przeskaluj kazdy do tej samej wysokosci (ponizej)
TARGET_HEIGHT = 2.0         # docelowa wysokosc modelu (uzywane tylko gdy True)
SPACING       = 0.15        # odstep miedzy czesciami (mnoznik, 0.15 = 15%)

ALLOW_ROTATE  = True        # przy pakowaniu obroc czesc o 90 st. tak, by jej
                            # dluzszy bok byl poziomo -> nizsze polki, ciasniej.
                            # False = zachowaj oryginalna orientacje w plaszczyznie.

AO_STRENGTH   = 0.8         # sila ambient occlusion (0 = wylaczone, 1 = mocne)
                            # przyciemnia szczeliny i osadza czesci na podlodze
                            # mniej = ciasniej, mniej pustej podlogi miedzy modelami

ONE_PER_FILE  = True        # True: jeden plik = jedna komorka (czesci zlaczone)
                            # False: kazdy osobny obiekt dostaje wlasna komorke

VIEW_MODE     = "top"       # "top" = rzut z gory (modele plasko, ciasna siatka)
                            # "iso" = rzut z rogu (modele stojace, izometryczny)

AUTO_UPRIGHT  = True        # automatyczna orientacja modeli:
                            #  - w trybie "iso": stawia je do pionu (najdluzsza os w gore)
                            #  - w trybie "top": klodzie je plasko (najkrotsza os w gore,
                            #    czyli najwieksza sylwetka widoczna z gory)

AUTO_FLIP     = True        # True: automatycznie wybierz strone pokazywana do gory
                            # (dziala w trybie "top"). Wyjatki nadpiszesz w ROTATIONS.

FLIP_METHOD   = "density"   # "density" - ocenia po gestosci siatki (szybkie,
                            #             dawalo lepszy efekt na Twoich czesciach)
                            # "depth"   - test mapa glebi: detal + wypuklosc
                            #             (wolniejsze, teoretycznie dokladniejsze)

# Reczna korekta orientacji dla konkretnych plikow. Klucz = nazwa pliku,
# wartosc = obrot (X, Y, Z) w stopniach. Nadpisuje AUTO_UPRIGHT dla tego pliku.
# Przyklad:
#   ROTATIONS = {
#       "kapitan.stl":  (90, 0, 0),
#       "czolg.obj":    (0, 0, 180),
#   }
ROTATIONS = {
}

SHOW_LABELS   = False       # True: podpisz kazdy model nazwa pliku (do rozpoznania
                            # co obrocic w ROTATIONS). Wylacz do finalnego renderu.

TRANSPARENT_BG = False      # True: przezroczyste tlo (PNG z alpha), bez podlogi,
                            # ale z zachowanymi miekkimi cieniami pod modelami

USE_GPU       = True        # sprobuj renderowac na karcie graficznej

# Katy kamery - uzywane TYLKO w trybie "iso"
CAM_AZIMUTH   = 45          # obrot wokol pionu (stopnie)
CAM_ELEVATION = 32          # wysokosc kamery nad pozioma (stopnie)

# ========================================================================


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras):
        for b in list(block):
            block.remove(b)


def import_file(path):
    """Importuje plik i zwraca liste nowych obiektow typu MESH (albo None)."""
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    try:
        if ext == '.stl':
            try:    bpy.ops.wm.stl_import(filepath=path)
            except AttributeError: bpy.ops.import_mesh.stl(filepath=path)
        elif ext == '.obj':
            try:    bpy.ops.wm.obj_import(filepath=path)
            except AttributeError: bpy.ops.import_scene.obj(filepath=path)
        elif ext == '.ply':
            try:    bpy.ops.wm.ply_import(filepath=path)
            except AttributeError: bpy.ops.import_mesh.ply(filepath=path)
        elif ext == '.fbx':
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            return None
    except Exception as e:
        print(f"  BLAD importu {os.path.basename(path)}: {e}")
        return []
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    return new


def join_objects(objs):
    """Laczy liste obiektow w jeden i go zwraca."""
    if not objs:
        return None
    if len(objs) == 1:
        return objs[0]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    return objs[0]


def world_bbox(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return (Vector((min(xs), min(ys), min(zs))),
            Vector((max(xs), max(ys), max(zs))))


def robust_bounds(obj, lo=1.0, hi=99.0):
    """Zwraca (min, max) w swiecie liczone z percentyli wierzcholkow -
    ignoruje zablakane wierzcholki. Fallback do world_bbox bez numpy."""
    me = getattr(obj, "data", None)
    if not HAS_NUMPY or me is None or len(me.vertices) == 0:
        return world_bbox(obj)
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    world = co @ m[:3, :3].T + m[:3, 3]
    lo_p = np.percentile(world, lo, axis=0)
    hi_p = np.percentile(world, hi, axis=0)
    return (Vector((lo_p[0], lo_p[1], lo_p[2])),
            Vector((hi_p[0], hi_p[1], hi_p[2])))


MODEL_EXTS = ('.stl', '.obj', '.ply', '.fbx', '.glb', '.gltf')


def collect_models(folder, recursive=True):
    """Zwraca liste (nazwa_do_pokazania, pelna_sciezka) posortowana.

    recursive=True -> wchodzi tez do podfolderow, np.
        Dreadnought/Arms/a.stl
        Dreadnought/Body/b.stl
      wszystko trafia na JEDNA plansze "Dreadnought".
    Nazwa do pokazania zawiera podfolder (Arms/a.stl), zeby bylo wiadomo
    skad czesc pochodzi i zeby te same nazwy plikow sie nie mylily.
    """
    out = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for f in sorted(files):
                if f.lower().endswith(MODEL_EXTS + ('.3mf',)):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, folder).replace('\\', '/')
                    out.append((rel, full))
    else:
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith(MODEL_EXTS + ('.3mf',)):
                out.append((f, os.path.join(folder, f)))
    return sorted(out, key=lambda t: t[0].lower())


def rotate_world(obj, axis, deg):
    """Obraca obiekt o zadany kat wokol osi SWIATA.

    UWAGA - to nie to samo co obj.rotation_euler[i] += kat!
    Blender sklada katy Eulera w kolejnosci XYZ (R = Rz @ Ry @ Rx), wiec
    skladowa X dziala PIERWSZA. Jesli model zostal wczesniej polozony
    obrotem wokol Y, to dodanie 180 do skladowej X NIE odwroci go na
    druga strone - obroci go w plaszczyznie, bo obrot Y przemapowuje os X.
    Skladanie macierzy swiata (R @ matrix_world) jest odporne na kolejnosc.
    """
    R = Matrix.Rotation(math.radians(deg), 4, axis)
    obj.matrix_world = R @ obj.matrix_world
    bpy.context.view_layer.update()


def apply_manual_rotation(obj, name):
    """Reczna korekta z ROTATIONS. Zwraca True jesli cos zastosowano."""
    rot = ROTATIONS.get(name)
    if not rot:
        return False
    for axis, ang in (('X', rot[0]), ('Y', rot[1]), ('Z', rot[2])):
        if ang:
            rotate_world(obj, axis, ang)
    return True


def orient_upright(obj):
    """Obraca obiekt tak, by jego najdluzsza os byla pionowa (Z)."""
    mn, mx = robust_bounds(obj)
    dx, dy, dz = (mx.x - mn.x), (mx.y - mn.y), (mx.z - mn.z)
    longest = max(dx, dy, dz)
    if longest <= dz:
        return                                    # juz stoi
    if longest == dx:
        rotate_world(obj, 'Y', 90)   # X -> Z
    else:
        rotate_world(obj, 'X', 90)   # Y -> Z


def orient_flat(obj):
    """Kladzie obiekt plasko - najkrotsza os pionowo (najwieksza sylwetka z gory)."""
    mn, mx = robust_bounds(obj)
    dx, dy, dz = (mx.x - mn.x), (mx.y - mn.y), (mx.z - mn.z)
    shortest = min(dx, dy, dz)
    if shortest >= dz:
        return                                    # juz lezy plasko
    if shortest == dx:
        rotate_world(obj, 'Y', 90)   # X -> Z
    else:
        rotate_world(obj, 'X', 90)   # Y -> Z


def _visible_relief(obj, grid=40):
    """Ocenia, jak dobrze wyglada ta strona czesci widziana z gory.
    Kryterium jak przy rendere probnym, ale liczone mapa glebi (raycast):
    szybciej i bez renderowania. Sklada sie z dwoch miar:

    1. DETAL = lokalny gradient mapy glebi (nie globalny rozrzut!). Wydrazony
       tyl to jedna wielka gladka misa - ogromny rozrzut, ale zmiana lagodna.
       Rzezbiony przod to gestwina drobnych skokow. Liczy sie czestotliwosc
       zmian, nie ich amplituda.

    2. WYPUKLOSC = jak wysoko lezy material w bryle czesci. Skorupa wnetrzem
       do gory ma wysoka tylko krawedz. Bez tej miary skorupy z zeberkami
       w srodku wygrywaja sama gestoscia detalu.
    """
    me = getattr(obj, "data", None)
    if not HAS_NUMPY or me is None or len(me.vertices) == 0:
        return 0.0
    try:
        from mathutils.bvhtree import BVHTree
        me.calc_loop_triangles()
    except Exception:
        return 0.0
    ntri = len(me.loop_triangles)
    if ntri == 0:
        return 0.0

    # wierzcholki -> swiat
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(nv, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    world = co @ m[:3, :3].T + m[:3, 3]

    tri = np.empty(ntri * 3, dtype=np.int32)
    me.loop_triangles.foreach_get('vertices', tri)
    tri = tri.reshape(ntri, 3)

    try:
        bvh = BVHTree.FromPolygons([tuple(v) for v in world],
                                   [tuple(t) for t in tri],
                                   all_triangles=True)
    except Exception:
        return 0.0

    mn = world.min(axis=0)
    mx = world.max(axis=0)
    if mx[0] - mn[0] <= 0 or mx[1] - mn[1] <= 0:
        return 0.0
    zext = float(mx[2] - mn[2])
    if zext <= 0:
        return 0.0
    z_start = float(mx[2]) + zext * 0.5
    down = Vector((0.0, 0.0, -1.0))

    # mapa glebi: NaN = promien w powietrze (poza sylwetka)
    dm = np.full((grid, grid), np.nan, dtype=np.float64)
    hits = 0
    for gx in range(grid):
        x = mn[0] + (mx[0] - mn[0]) * (gx + 0.5) / grid
        for gy in range(grid):
            y = mn[1] + (mx[1] - mn[1]) * (gy + 0.5) / grid
            hit = bvh.ray_cast(Vector((x, y, z_start)), down)
            if hit and hit[0] is not None:
                dm[gx, gy] = hit[0].z
                hits += 1
    if hits < 16:
        return 0.0

    # lokalny gradient: srednia |roznica| miedzy sasiednimi probkami.
    # Liczymy tylko pary, gdzie oba promienie trafily w model.
    diffs = []
    for a, b in ((dm[1:, :], dm[:-1, :]), (dm[:, 1:], dm[:, :-1])):
        d = np.abs(a - b)
        d = d[~np.isnan(d)]
        if d.size:
            diffs.append(d)
    if not diffs:
        return 0.0
    grad = np.concatenate(diffs)
    # przycinamy skrajne 2% - pojedyncze urwiska na krawedzi sylwetki
    # nie moga przewazyc nad ogolna gestoscia detalu
    hi = np.percentile(grad, 98.0)
    grad = np.clip(grad, 0.0, hi)
    detail = float(grad.mean()) / zext

    # WYPUKLOSC: jak wysoko lezy material wzgledem bryly czesci.
    # Skorupa wnetrzem do gory ma wysoka tylko krawedz, a cala reszte
    # powierzchni gleboko pod nia -> niskie meanh. Strona wypukla ma
    # material tuz pod szczytem -> wysokie meanh. Bez tego skorupy z
    # zeberkami w srodku wygrywaja sama gestoscia detalu.
    vals = dm[~np.isnan(dm)]
    meanh = float(((vals - float(mn[2])) / zext).mean())

    coverage = hits / float(grid * grid)
    return detail * (0.5 + 0.5 * coverage) * (0.25 + 1.2 * meanh)


def _flip_by_density(obj):
    """Metoda 'density' - ocenia strone po gestosci siatki.
    Zaklada, ze rzezbiony przod ma duzo drobnych trojkatow, a gladki/plaski
    tyl malo. Szybka, nie liczy zadnych promieni. Zwraca True jesli obrocono.
    """
    me = getattr(obj, "data", None)
    if not HAS_NUMPY or me is None or len(me.vertices) == 0:
        return False
    try:
        me.calc_loop_triangles()
    except Exception:
        return False
    ntri = len(me.loop_triangles)
    if ntri == 0:
        return False

    nor = np.empty(ntri * 3, dtype=np.float64)
    me.loop_triangles.foreach_get('normal', nor)
    nor = nor.reshape(ntri, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    nor_w = nor @ m[:3, :3].T

    area = np.empty(ntri, dtype=np.float64)
    me.loop_triangles.foreach_get('area', area)

    up = nor_w[:, 2] > 0.2
    dn = nor_w[:, 2] < -0.2
    n_up, n_dn = int(np.count_nonzero(up)), int(np.count_nonzero(dn))
    if n_up == 0 or n_dn == 0:
        return False

    a_up, a_dn = float(area[up].sum()), float(area[dn].sum())
    if a_up <= 0 or a_dn <= 0:
        return False
    dens_up, dens_dn = n_up / a_up, n_dn / a_dn

    if dens_dn > dens_up * 1.15:       # detal wyraznie pod spodem -> obroc
        rotate_world(obj, 'X', 180)
        return True
    return False


def auto_flip_detail(obj):
    """Wybiera strone pokazywana do gory. Metoda wg FLIP_METHOD."""
    if FLIP_METHOD == "density":
        return _flip_by_density(obj)
    # "depth": testuje obie strony mapa glebi i zostawia lepsza
    a = _visible_relief(obj)
    rotate_world(obj, 'X', 180)
    b = _visible_relief(obj)
    if b > a * 1.05:                 # obrocona strona wyraznie ciekawsza
        return True
    rotate_world(obj, 'X', -180)   # wracamy do oryginalu
    return False


def make_clay_material():
    mat = bpy.data.materials.new("Clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.72, 0.70, 0.66, 1.0)   # jasna kosc
        bsdf.inputs["Roughness"].default_value = 0.6
        for name in ("Specular IOR Level", "Specular"):
            if name in bsdf.inputs:
                bsdf.inputs[name].default_value = 0.2

    # (5) Ambient occlusion - przyciemnia szczeliny i miejsca styku,
    # przez co rzezba jest czytelniejsza a czesci "siedza" na podlodze.
    if AO_STRENGTH > 0 and bsdf:
        nt = mat.node_tree
        ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
        ao.samples = 16
        ao.inputs['Distance'].default_value = 1.0   # ustawiane pozniej wg skali
        ao.name = "ClayAO"
        base = nt.nodes.new('ShaderNodeRGB')
        base.outputs[0].default_value = (0.72, 0.70, 0.66, 1.0)   # musi byc == Base Color wyzej
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MULTIPLY'
        mix.inputs['Fac'].default_value = min(1.0, max(0.0, AO_STRENGTH))
        nt.links.new(base.outputs[0], mix.inputs['Color1'])
        nt.links.new(ao.outputs['Color'], mix.inputs['Color2'])
        nt.links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
    return mat


def setup_lighting():
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.80, 0.83, 0.88, 1.0)   # chlodne otoczenie
        bg.inputs[1].default_value = 0.4                        # sila wypelnienia

    # Swiatla SUN sa niezalezne od skali sceny - oswietlaja rowno
    # niezaleznie od tego, jak duze sa modele (kluczowe przy NORMALIZE=False).
    def sun(name, rot_deg, energy):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(4)        # rozmiar tarczy = miekkosc cieni
        o = bpy.data.objects.new(name, ld)
        o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        bpy.context.collection.objects.link(o)
        return o

    # (obrot X = nachylenie, obrot Z = kierunek/azymut)
    # wysokie nachylenie -> krotkie cienie, ktore nie rozlewaja sie na sasiadow
    sun("Key",  (70, 0, 35),   1.6)    # glowne, prawie z gory
    sun("Fill", (72, 0, -110), 0.6)    # wypelnienie z drugiej strony
    sun("Rim",  (75, 0, 180),  0.9)    # kontra od tylu, odcina od tla


def main(FOLDER, OUTPUT):
    if not os.path.isdir(FOLDER):
        print(f"!!! Folder nie istnieje: {FOLDER}")
        return

    clear_scene()

    files = collect_models(FOLDER, RECURSIVE)

    clay = make_clay_material()
    cells = []          # gotowe obiekty do rozlozenia
    cell_names = []     # nazwa pliku dla kazdej komorki (do podpisow)
    skipped = []
    flipped = []        # pliki obrocone przez AUTO_FLIP (raport w konsoli)

    for k, (f, path) in enumerate(files, 1):
        progress("IMPORT", k, len(files))
        if f.lower().endswith('.3mf'):
            skipped.append(f)
            continue
        objs = import_file(path)
        if not objs:
            continue
        group = [join_objects(objs)] if ONE_PER_FILE else objs
        for obj in group:
            if obj is None:
                continue
            # material
            obj.data.materials.clear()
            obj.data.materials.append(clay)
            # orientacja: reczna korekta ma pierwszenstwo nad auto
            if not apply_manual_rotation(obj, f) and AUTO_UPRIGHT:
                if VIEW_MODE == "top":
                    orient_flat(obj)
                    if AUTO_FLIP and auto_flip_detail(obj):
                        flipped.append(f)
                else:
                    orient_upright(obj)
            # normalizacja wysokosci
            if NORMALIZE:
                mn, mx = robust_bounds(obj)
                h = mx.z - mn.z
                if h > 1e-6:
                    s = TARGET_HEIGHT / h
                    obj.scale = (obj.scale[0]*s, obj.scale[1]*s, obj.scale[2]*s)
                    bpy.context.view_layer.update()
            cells.append(obj)
            cell_names.append(f)

    if not cells:
        print("!!! Nie zaimportowano zadnych modeli.")
        return

    # rozmiar komorki: MEDIANA footprintow - odporna nawet gdy polowa modeli
    # to outliery. Normalne modele wypelnia kadr, odmiency wyjda poza komorke
    # (ale beda widoczni), zamiast rozdmuchac cala siatke do niewidocznosci.
    foots = []
    heights = []
    for obj in cells:
        mn, mx = robust_bounds(obj)
        foots.append(max(mx.x - mn.x, mx.y - mn.y))
        heights.append(mx.z - mn.z)
    foots_sorted = sorted(foots)
    heights_sorted = sorted(heights)
    med = foots_sorted[len(foots_sorted) // 2]
    cell = med * (1.0 + SPACING)
    if cell <= 0:
        cell = 1.0
    rep_height = heights_sorted[len(heights_sorted) // 2]
    if rep_height <= 0:
        rep_height = cell

    # DIAGNOSTYKA - rozpietosc rozmiarow modeli (sprawdz w konsoli!)
    print("  --- rozmiary modeli (footprint) ---")
    print("      min: %.3f   mediana: %.3f   max: %.3f"
          % (foots_sorted[0], med, foots_sorted[-1]))
    if med > 0 and foots_sorted[-1] > med * 4:
        outliers = sorted(set(cell_names[i] for i, fp in enumerate(foots)
                              if fp > med * 4))
        print("  UWAGA - te pliki sa >4x wieksze od mediany (zla skala lub"
              " zablakany wierzcholek): " + ", ".join(outliers))
        print("      -> rozwiazanie: napraw te pliki albo ustaw NORMALIZE = True")

    # dystans AO musi pasowac do skali modeli (inaczej efekt zniknie albo
    # zaczerni wszystko) - ustawiamy go dopiero teraz, gdy znamy mediane
    if AO_STRENGTH > 0:
        ao_node = clay.node_tree.nodes.get("ClayAO")
        if ao_node:
            ao_node.inputs['Distance'].default_value = max(1e-4, med * 0.15)

    n = len(cells)

    label_mat = None
    if SHOW_LABELS:
        label_mat = bpy.data.materials.new("Label")
        label_mat.use_nodes = True
        lb = label_mat.node_tree.nodes.get("Principled BSDF")
        if lb:
            lb.inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1.0)
            lb.inputs["Roughness"].default_value = 0.9

    # --- PAKOWANIE POLKOWE (shelf packing) -----------------------------
    # Kazdy model dostaje slot swojego realnego rozmiaru (footprint), modele
    # ukladane polka po polce. Brak nachodzenia mimo roznych rozmiarow -
    # i BEZ ruszania skali modeli.
    #  * ALLOW_ROTATE: dluzszy bok w poziomie -> nizsze polki, ciasniej
    #  * sortowanie wg wysokosci malejaco -> podobne wysokosci na jednej polce
    #  * srodkowanie w pionie polki -> schludniej, mniej dziur
    gap = med * SPACING                       # absolutny odstep miedzy modelami

    # WYMIARY DO PAKOWANIA: bierzemy PRAWDZIWY bounding box, nie percentyle.
    # Powod: robust_bounds obcina 1% skrajnych wierzcholkow. Przy duzych
    # plaskich plytach (sciany, panele) geometria jest gesta w srodku, a rzadka
    # na krawedziach - obciete zostaja wtedy REALNE brzegi, slot wychodzi za
    # maly i sasiednie czesci na siebie nachodza.
    # Percentyle zostaja tylko jako bezpiecznik: jesli prawdziwy bbox jest
    # absurdalnie wiekszy (zablakany wierzcholek), uzywamy wersji przycietej.
    dims = []
    huge = []
    for i, obj in enumerate(cells):
        tmn, tmx = world_bbox(obj)                 # prawdziwe wymiary
        rmn, rmx = robust_bounds(obj)              # przyciete percentylami
        tw, th = tmx.x - tmn.x, tmx.y - tmn.y
        rw, rh = rmx.x - rmn.x, rmx.y - rmn.y
        if rw > 0 and rh > 0 and (tw > rw * 3.0 or th > rh * 3.0):
            dims.append([rw, rh])                  # patologia - bierz przyciete
            huge.append(cell_names[i])
        else:
            dims.append([tw, th])
    if huge:
        print("  [i] Zablakana geometria w: " + ", ".join(sorted(set(huge))))

    # (3) obrot 90 st. w plaszczyznie: ustaw dluzszy bok poziomo
    rotated = []
    if ALLOW_ROTATE:
        for i, obj in enumerate(cells):
            w, h = dims[i]
            if h > w:
                rotate_world(obj, 'Z', 90)
                dims[i] = [h, w]
                rotated.append(cell_names[i])

    # (1) sortowanie wg wysokosci malejaco - klasyczna poprawka shelf packingu
    order = sorted(range(n), key=lambda i: -dims[i][1])

    def pack(row_width):
        """Uklada modele polkami przy zadanej szerokosci rzedu.
        Zwraca (pozycje wg indeksu, szerokosc, wysokosc, granice)."""
        shelves = []                          # [[indeksy], ...]
        cur, x_cur = [], 0.0
        for i in order:
            w = dims[i][0]
            if cur and x_cur + w > row_width:
                shelves.append(cur)
                cur, x_cur = [], 0.0
            cur.append(i)
            x_cur += w + gap
        if cur:
            shelves.append(cur)

        # szerokosc kazdej polki (do wysrodkowania w poziomie)
        shelf_w = []
        for items in shelves:
            shelf_w.append(sum(dims[i][0] for i in items) + gap * (len(items) - 1))
        max_w = max(shelf_w) if shelf_w else 0.0

        pos = [None] * n
        y_top = 0.0
        for si, items in enumerate(shelves):
            sh = max(dims[i][1] for i in items)    # wysokosc polki
            # wysrodkowanie polki w poziomie - niepelny rzad nie "ucieka" w lewo
            x_cur = (max_w - shelf_w[si]) * 0.5
            for i in items:
                w, h = dims[i]
                # (2) srodkowanie w pionie polki
                pos[i] = (x_cur + w * 0.5, y_top - sh * 0.5)
                x_cur += w + gap
            y_top -= (sh + gap)

        xs_min = min(pos[i][0] - dims[i][0] * 0.5 for i in range(n))
        xs_max = max(pos[i][0] + dims[i][0] * 0.5 for i in range(n))
        ys_min = min(pos[i][1] - dims[i][1] * 0.5 for i in range(n))
        ys_max = max(pos[i][1] + dims[i][1] * 0.5 for i in range(n))
        return pos, (xs_max - xs_min), (ys_max - ys_min), (xs_min, xs_max, ys_min, ys_max)

    # Szukamy szerokosci rzedu dajacej uklad o proporcji TARGET_ASPECT.
    # Prosty wzor (sqrt z sumy pol) nie wystarcza, bo polki maja rozne
    # wysokosci i zostaja w nich luki - wiec testujemy wiele wariantow.
    widest = max(d[0] for d in dims)
    total_area = sum((d[0] + gap) * (d[1] + gap) for d in dims)
    base = math.sqrt(total_area) if total_area > 0 else 1.0
    aspect_goal = TARGET_ASPECT if TARGET_ASPECT else (RES_X / float(RES_Y))
    best = None
    for k in range(1, 241):
        rw = max(widest, base * (0.35 + k * 0.02))
        pos, lw, lh, bounds = pack(rw)
        if lh <= 0 or lw <= 0:
            continue
        err = abs(math.log((lw / lh) / aspect_goal))   # log -> symetrycznie
        if best is None or err < best[0]:
            best = (err, pos, lw, lh, bounds)
    positions = best[1]
    lay_min_x, lay_max_x, lay_min_y, lay_max_y = best[4]
    print("  Proporcja ukladu: %.2f:1 (cel %.2f:1)" % (best[2] / best[3], aspect_goal))
    if rotated:
        print("  Obrocono 90 st. przy pakowaniu: %d czesci" % len(rotated))

    # ustaw modele w slotach: baza na z=0, footprint wysrodkowany w slocie
    # WAZNE: srodek liczymy z tej samej miary, co wymiary slotu (prawdziwy
    # bbox) - inaczej czesc przesunie sie wzgledem swojego slotu i wejdzie
    # na sasiada.
    for i, obj in enumerate(cells):
        cx, cy = positions[i]
        mn, mx = world_bbox(obj)
        center = (mn + mx) * 0.5
        obj.location.x += cx - center.x
        obj.location.y += cy - center.y
        obj.location.z += -mn.z            # postaw na "podlodze"
        bpy.context.view_layer.update()

        if SHOW_LABELS:
            if VIEW_MODE == "top":
                offset = Vector((0, -dims[i][1] * 0.5 - gap * 0.5, 0))
                lbl_rot = (0, 0, 0)
            else:
                az = math.radians(CAM_AZIMUTH)
                offset = Vector((math.cos(az), math.sin(az), 0)) * cell * 0.42
                lbl_rot = (0, 0, az + math.radians(90))
            cur = bpy.data.curves.new("lbl", type='FONT')
            cur.body = cell_names[i]
            cur.align_x = 'CENTER'
            cur.align_y = 'CENTER'
            lbl = bpy.data.objects.new("lbl_" + cell_names[i], cur)
            lbl.location = Vector((cx, cy, 0.02)) + offset
            lbl.rotation_euler = lbl_rot
            s = cell * 0.10
            lbl.scale = (s, s, s)
            lbl.data.materials.append(label_mat)
            bpy.context.collection.objects.link(lbl)

    grid_diag = math.hypot(lay_max_x - lay_min_x, lay_max_y - lay_min_y)

    setup_lighting()

    # kamera izometryczna (ortho)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = 'ORTHO'
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)

    # srodek i kadr liczone z granic UKLADU (pakowanie polkowe) - odporne
    # na outliery: kazdy model zajmuje slot swojego rozmiaru
    gx_min, gx_max = lay_min_x, lay_max_x
    gy_min, gy_max = lay_min_y, lay_max_y
    gz_min, gz_max = 0.0, rep_height
    target = Vector(((gx_min + gx_max) * 0.5,
                     (gy_min + gy_max) * 0.5,
                     (gz_min + gz_max) * 0.5))

    if VIEW_MODE == "top":
        # prosto z gory, patrzy w dol, gora kadru = +Y
        cam.location = target + Vector((0, 0, 1)) * grid_diag * 3
    else:
        az = math.radians(CAM_AZIMUTH)
        el = math.radians(CAM_ELEVATION)
        direction = Vector((math.cos(el) * math.cos(az),
                            math.cos(el) * math.sin(az),
                            math.sin(el)))
        cam.location = target + direction * grid_diag * 3
    look = target - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    # ZASIEG WIDZENIA KAMERY (clip). Blender domyslnie obcina wszystko dalej
    # niz 100 jednostek. Modele bywaja duze (footprint rzedu 100+ jednostek),
    # a kamere stawiamy w odleglosci grid_diag*3 - przy wiekszych zestawach
    # to setki/tysiace jednostek. Bez tego render wychodzi PUSTY (widac samo
    # tlo swiata, bez modeli i bez podlogi). Skalujemy zasieg do sceny.
    cam_dist = (target - cam.location).length
    cam_data.clip_start = max(1e-4, grid_diag * 0.001)
    cam_data.clip_end = (cam_dist + grid_diag * 4.0) * 2.0 + 1000.0
    print("  Kamera: odleglosc %.1f, zasieg %.1f - %.1f"
          % (cam_dist, cam_data.clip_start, cam_data.clip_end))

    # dopasuj ortho_scale do 8 naroznikow bryly SIATKI w ukladzie kamery
    bpy.context.view_layer.update()
    minv = cam.matrix_world.inverted()
    ext_x = ext_y = 0.0
    for cx in (gx_min, gx_max):
        for cy in (gy_min, gy_max):
            for cz in (gz_min, gz_max):
                p = minv @ Vector((cx, cy, cz))
                ext_x = max(ext_x, abs(p.x))
                ext_y = max(ext_y, abs(p.y))
    cam_data.ortho_scale = 2.0 * max(ext_x, ext_y) * 1.06   # 6% marginesu

    # podloga: tworzona PO dopasowaniu kamery, rozmiar wzgledem kadru
    # (a nie 4x siatki), wysrodkowana na modelach. W izo musi byc wieksza,
    # bo grunt "ucieka" w glab kadru.
    floor_span = cam_data.ortho_scale * (4.0 if VIEW_MODE == "iso" else 1.6)
    bpy.ops.mesh.primitive_plane_add(
        size=floor_span, location=(target.x, target.y, 0))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("Floor")
    fmat.use_nodes = True
    fb = fmat.node_tree.nodes.get("Principled BSDF")
    if fb:
        fb.inputs["Base Color"].default_value = (0.10, 0.11, 0.13, 1.0)   # ciemne tlo
        fb.inputs["Roughness"].default_value = 0.9
    floor.data.materials.append(fmat)
    if TRANSPARENT_BG:
        floor.is_shadow_catcher = True   # widoczne tylko cienie, reszta przezroczysta

    # render
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.filepath = OUTPUT
    scene.render.image_settings.file_format = 'PNG'
    if TRANSPARENT_BG:
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = 'RGBA'
    else:
        scene.render.film_transparent = False
        scene.render.image_settings.color_mode = 'RGB'
    # AgX lagodnie wygasza jasne obszary (nie przepala do bieli)
    try:
        scene.view_settings.view_transform = 'AgX'
    except Exception:
        pass

    if USE_GPU:
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.get_devices()
            for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
                try:
                    prefs.compute_device_type = backend
                    if any(d.type == backend for d in prefs.devices):
                        for d in prefs.devices:
                            d.use = True
                        scene.cycles.device = 'GPU'
                        print(f"  Render na GPU ({backend})")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"  GPU niedostepne, licze na CPU: {e}")

    print(f"\n  Modeli w ukladzie: {n}")
    if flipped:
        print(f"  AUTO_FLIP obrocil {len(flipped)} czesci (detal patrzyl w dol):")
        print("      " + ", ".join(sorted(set(flipped))))
    if skipped:
        print(f"  Pominieto 3MF (wyeksportuj do STL): {', '.join(skipped)}")

    def _render_to(path):
        progress("RENDER", os.path.basename(path))
        scene.render.filepath = path
        print(f"  Renderuje -> {path}")
        bpy.ops.render.render(write_still=True)

    if not RENDER_BOTH_SIDES:
        _render_to(OUTPUT)
        print("  GOTOWE.")
        return

    # A i B z JEDNEJ sceny - import, orientacja i pakowanie liczone raz.
    _render_to(_with_suffix(OUTPUT, "_A"))

    # odwroc kazdy model na druga strone i posadz z powrotem w jego slocie.
    # Obrot o 180 st. wokol X nie zmienia wymiarow obrysu (X ten sam,
    # Y lustrzany, Z ten sam), wiec pozycje slotow zostaja te same -
    # czesci beda dokladnie tam, gdzie na A.
    for i, obj in enumerate(cells):
        rotate_world(obj, 'X', 180)
        cx, cy = positions[i]
        mn, mx = world_bbox(obj)
        center = (mn + mx) * 0.5
        obj.location.x += cx - center.x
        obj.location.y += cy - center.y
        obj.location.z += -mn.z
    bpy.context.view_layer.update()

    _render_to(_with_suffix(OUTPUT, "_B"))
    print("  GOTOWE.")


def _with_suffix(path, suffix):
    """wstawia sufiks przed rozszerzeniem: plansza.png -> plansza_A.png"""
    root, ext = os.path.splitext(path)
    return root + suffix + ext


def run_all():
    """Tryb pojedynczy albo wsadowy - zaleznie od BATCH."""
    if not BATCH:
        main(FOLDER, OUTPUT)
        return

    subs = []
    pominiete = []
    for name in sorted(os.listdir(FOLDER)):
        d = os.path.join(FOLDER, name)
        if not os.path.isdir(d):
            continue
        # foldery zaczynajace sie od _ sa pomijane (tak jak przy zipowaniu)
        if ONLY is not None and name not in ONLY:
            continue
        if name.startswith('_'):
            pominiete.append(name)
            continue
        # tylko foldery, ktore zawieraja modele - takze w podfolderach
        # (np. Dreadnought\\Arms\\*.stl), jesli RECURSIVE = True
        try:
            if collect_models(d, RECURSIVE):
                subs.append((name, d))
        except Exception:
            continue

    if pominiete:
        print("  Pominieto foldery z _ : " + ", ".join(pominiete))

    if not subs:
        print(f"!!! Brak podfolderow z modelami w: {FOLDER}")
        print("    (BATCH = True oczekuje folderow, w kazdym pliki 3D)")
        return

    print("\n" + "=" * 60)
    print(f"  TRYB WSADOWY - folderow do zrobienia: {len(subs)}")
    print("=" * 60)

    progress("TOTAL", len(subs))
    done, failed = [], []
    for i, (name, d) in enumerate(subs, 1):
        progress("FOLDER", i, name)
        out = os.path.join(FOLDER, name + ".png")
        sides = " (_A + _B)" if RENDER_BOTH_SIDES else ""
        print("\n" + "-" * 60)
        print(f"  [{i}/{len(subs)}] {name}  ->  {name}{sides}.png")
        print("-" * 60)
        try:
            main(d, out)
            done.append(name)
            progress("DONE", "ok", name)
        except Exception as e:
            print(f"  !!! BLAD przy '{name}': {e}")
            failed.append(name)
            progress("DONE", "fail", name)

    print("\n" + "=" * 60)
    print(f"  KONIEC: gotowe {len(done)} / {len(subs)}")
    if failed:
        print("  Nie udalo sie: " + ", ".join(failed))
    print("=" * 60 + "\n")


_parse_args()
run_all()
