"""
==========================================================================
 STL LIBRARY TOOLS - desktop app (Windows + Linux)
==========================================================================
 Combines the two scripts from "Scripts - version 1" in one window:
   1. RENDER - preview sheets via Blender (render_grid.py next to it)
   2. ZIP    - packing subfolders into archives

 Pick the parent folder, tick the subfolders, click Start.
 Folders go through a pipeline: Blender renders folder 1, then folder 1
 gets zipped while Blender is already rendering folder 2 - and so on.

 Needs only Python 3.8+ with tkinter (bundled on Windows, on Linux:
 the python3-tk package) and Blender for rendering.
 Launch: "STL Tools.bat" (Windows) or stl_tools.sh (Linux), or the
 single-file build STL-Tools.exe from the GitHub releases.
==========================================================================
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

# packed into one file (PyInstaller): render_grid.py is extracted
# to the temporary folder sys._MEIPASS while the program runs
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
RENDER_SCRIPT = os.path.join(APP_DIR, "render_grid.py")

# same extensions as in render_grid.py
MODEL_EXTS = ('.stl', '.obj', '.ply', '.fbx', '.glb', '.gltf')

# folders NOT ticked by default (like SKIP in __ZIP.bat) - these are the
# user's real folder names, so they stay as they are
DEFAULT_SKIP = {"stare", "robocze", "do sprawdzenia"}

# colours - same mood as the sheets: dark background + light bone
C_BG = "#1a1c21"
C_PANEL = "#23262d"
C_FIELD = "#2b2f37"
C_TEXT = "#e6e3dc"
C_DIM = "#8b8f98"
C_BONE = "#b8b3a8"
C_ACCENT = "#e0a14a"
C_OK = "#6fbf73"
C_ERR = "#e06c5a"

IS_WIN = sys.platform.startswith("win")


def ui_font(size, bold=False):
    """system font in the given size (works only after the window is created)"""
    fam = tkfont.nametofont("TkDefaultFont").actual()["family"]
    return (fam, size, "bold") if bold else (fam, size)


# ============================ configuration =============================

def config_path():
    if IS_WIN:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "stl-library-tools", "config.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(config_path()), exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# =========================== finding Blender ============================

def _newest_in(folder, exe):
    """folder with version subfolders (e.g. Blender Foundation\\Blender 4.2) -
    returns the exe from the newest name, like :scan in __RENDER.bat"""
    try:
        subs = sorted(os.listdir(folder), reverse=True)
    except OSError:
        return None
    for s in subs:
        p = os.path.join(folder, s, exe)
        if os.path.isfile(p):
            return p
    return None


def find_blender():
    found = shutil.which("blender")
    if found:
        return found
    if IS_WIN:
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        lap = os.environ.get("LOCALAPPDATA", "")
        for base in (os.path.join(pf, "Blender Foundation"),
                     os.path.join(pf86, "Blender Foundation"),
                     os.path.join(lap, "Programs", "Blender Foundation"),
                     r"D:\Blender Foundation", r"E:\Blender Foundation"):
            p = _newest_in(base, "blender.exe")
            if p:
                return p
        candidates = [os.path.join(pf86, r"Steam\steamapps\common\Blender\blender.exe"),
                      os.path.join(pf, r"Steam\steamapps\common\Blender\blender.exe")]
        candidates += [d + r":\SteamLibrary\steamapps\common\Blender\blender.exe"
                       for d in "CDEFGX"]
    elif sys.platform == "darwin":
        candidates = ["/Applications/Blender.app/Contents/MacOS/Blender"]
    else:
        home = os.path.expanduser("~")
        candidates = ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender",
                      os.path.join(home, ".steam/steam/steamapps/common/Blender/blender"),
                      os.path.join(home, ".local/share/Steam/steamapps/common/Blender/blender")]
        p = _newest_in(os.path.join(home, "blender"), "blender")
        if p:
            candidates.insert(0, p)
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


# ============================ folder scan ===============================

def scan_folder(parent):
    """Returns a list of dicts describing every subfolder."""
    out = []
    try:
        names = sorted(os.listdir(parent), key=str.lower)
    except OSError:
        return out
    for name in names:
        d = os.path.join(parent, name)
        if not os.path.isdir(d):
            continue
        models = mf3 = 0
        for root, _dirs, files in os.walk(d):
            for f in files:
                fl = f.lower()
                if fl.endswith(MODEL_EXTS):
                    models += 1
                elif fl.endswith(".3mf"):
                    mf3 += 1
        png = (os.path.isfile(os.path.join(parent, name + "_A.png"))
               or os.path.isfile(os.path.join(parent, name + ".png")))
        out.append({
            "name": name,
            "models": models,
            "mf3": mf3,
            "png": png,
            "zip": os.path.isfile(os.path.join(parent, name + ".zip")),
            "underscore": name.startswith("_"),
        })
    return out


# ====================== fancy progress bar (Canvas) =====================

def _mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class FancyBar(tk.Canvas):
    """Rounded bar with the percentage inside and a moving shine while
    working. The colour shifts from amber to green."""

    def __init__(self, master, height=26, **kw):
        super().__init__(master, height=height, bg=C_PANEL,
                         highlightthickness=0, bd=0, **kw)
        self.h = height
        self.value = 0.0
        self.text = ""
        self.running = False
        self.error = False
        self._shine = 0.0
        self.bind("<Configure>", lambda e: self._draw())
        self._tick()

    def set(self, value, text=None):
        self.value = max(0.0, min(1.0, value))
        if text is not None:
            self.text = text
        self._draw()

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.h
        if w < 10:
            return
        r = h / 2
        self._rrect(1, 1, w - 1, h - 1, r, fill=C_FIELD, outline="#383c46")
        fw = (w - 4) * self.value
        if fw >= 2:
            if self.error:
                col = C_ERR
            else:
                col = _mix(C_ACCENT, C_OK, self.value ** 3)
            self._rrect(2, 2, 2 + fw, h - 2, r - 1, fill=col, outline="")
            # gloss on the upper half
            self._rrect(4, 3, 2 + fw - 2, h / 2, r / 2,
                        fill=_mix(col, "#ffffff", 0.25), outline="")
            if self.running and fw > 30:
                sw = min(60, fw / 3)
                sx = 2 + (fw + sw) * self._shine - sw
                x1, x2 = max(2 + r / 2, sx), min(2 + fw - r / 2, sx + sw)
                if x2 > x1:
                    self._rrect(x1, 3, x2, h - 3, 4,
                                fill=_mix(col, "#ffffff", 0.35), outline="")
        label = self.text or ("%d%%" % round(self.value * 100))
        self.create_text(w / 2 + 1, h / 2 + 1, text=label, fill="#000000",
                         font=ui_font(10, True))
        self.create_text(w / 2, h / 2, text=label, fill=C_TEXT,
                         font=ui_font(10, True))

    def _tick(self):
        if self.running:
            self._shine = (self._shine + 0.02) % 1.0
            self._draw()
        self.after(40, self._tick)


# ============================== the app =================================

SAMPLE_RE = re.compile(r"Sample (\d+)/(\d+)")
# Cycles renders large images in tiles: "Rendered 1/4 Tiles, Sample 64/128"
TILES_RE = re.compile(r"(\d+)/(\d+) Tiles")


def fmt_time(sec):
    sec = int(sec)
    if sec >= 3600:
        return "%d h %d min" % (sec // 3600, (sec % 3600) // 60)
    if sec >= 60:
        return "%d min %d s" % (sec // 60, sec % 60)
    return "%d s" % sec


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("STL Library Tools")
        # tall, so the folder list is long - but not taller than the screen
        self.geometry("1000x%d" % min(900, self.winfo_screenheight() - 80))
        self.minsize(820, 640)
        self.configure(bg=C_BG)

        self.cfg = load_config()
        self.events = queue.Queue()
        self.worker = None
        self.proc = None
        self.cancel = threading.Event()
        self.rows = {}          # name -> dict from the scan
        self.checked = set()

        self.var_folder = tk.StringVar(value=self.cfg.get("folder", ""))
        self.var_blender = tk.StringVar(value=self.cfg.get("blender") or find_blender() or "")
        self.var_render = tk.BooleanVar(value=self.cfg.get("do_render", True))
        self.var_zip = tk.BooleanVar(value=self.cfg.get("do_zip", True))
        self.var_overwrite_png = tk.BooleanVar(value=self.cfg.get("overwrite_png", True))
        self.var_overwrite_zip = tk.BooleanVar(value=self.cfg.get("overwrite_zip", True))
        self.var_both = tk.BooleanVar(value=self.cfg.get("both_sides", True))
        self.var_res = tk.StringVar(value=str(self.cfg.get("res", 4000)))
        self.var_samples = tk.StringVar(value=str(self.cfg.get("samples", 128)))

        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self._poll)
        if self.var_folder.get():
            self.refresh()

    # ---------------------------------------------------------- styling
    def _style(self):
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont"):
            try:
                f = tkfont.nametofont(name)
                f.configure(size=10)
                if IS_WIN:
                    f.configure(family="Segoe UI")
            except tk.TclError:
                pass
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=C_PANEL, foreground=C_TEXT,
                     fieldbackground=C_FIELD, bordercolor="#383c46",
                     lightcolor=C_PANEL, darkcolor=C_PANEL, troughcolor=C_FIELD)
        st.configure("Bg.TFrame", background=C_BG)
        st.configure("TFrame", background=C_PANEL)
        st.configure("TLabel", background=C_PANEL, foreground=C_TEXT)
        st.configure("Bg.TLabel", background=C_BG, foreground=C_TEXT)
        st.configure("Dim.TLabel", background=C_PANEL, foreground=C_DIM)
        st.configure("Title.TLabel", background=C_BG, foreground=C_BONE,
                     font=ui_font(16, True))
        st.configure("Head.TLabel", background=C_PANEL, foreground=C_BONE,
                     font=ui_font(11, True))
        st.configure("TCheckbutton", background=C_PANEL, foreground=C_TEXT,
                     indicatorbackground=C_FIELD, indicatorforeground=C_ACCENT)
        st.map("TCheckbutton", background=[("active", C_PANEL)],
               indicatorbackground=[("pressed", "#383c46"), ("active", "#383c46")])
        st.configure("TNotebook", background=C_BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        st.configure("TNotebook.Tab", background=C_BG, foreground=C_DIM,
                     padding=(10, 5), font=ui_font(11, True), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", C_PANEL), ("active", C_FIELD)],
               foreground=[("selected", C_BONE), ("active", C_TEXT)])
        st.configure("TButton", background=C_FIELD, foreground=C_TEXT, padding=(10, 4))
        st.map("TButton", background=[("active", "#383c46"), ("disabled", C_PANEL)],
               foreground=[("disabled", C_DIM)])
        st.configure("Start.TButton", background=C_ACCENT, foreground="#1a1c21",
                     font=ui_font(11, True), padding=(18, 6))
        st.map("Start.TButton", background=[("active", "#f0b560"), ("disabled", C_FIELD)],
               foreground=[("disabled", C_DIM)])
        st.configure("TEntry", foreground=C_TEXT, insertcolor=C_TEXT)
        st.configure("TCombobox", foreground=C_TEXT, arrowcolor=C_TEXT)
        st.map("TCombobox", fieldbackground=[("readonly", C_FIELD)],
               foreground=[("readonly", C_TEXT)])
        st.configure("Treeview", background=C_FIELD, fieldbackground=C_FIELD,
                     foreground=C_TEXT, rowheight=24, borderwidth=0)
        st.map("Treeview", background=[("selected", "#3a3f4a")])
        st.configure("Treeview.Heading", background=C_PANEL, foreground=C_BONE,
                     font=ui_font(10, True), relief="flat")
        st.map("Treeview.Heading", background=[("active", C_FIELD)])
        st.configure("Vertical.TScrollbar", background=C_FIELD, arrowcolor=C_DIM)
        self.option_add("*TCombobox*Listbox.background", C_FIELD)
        self.option_add("*TCombobox*Listbox.foreground", C_TEXT)

    def _panel(self, parent, title):
        outer = ttk.Frame(parent, padding=(12, 8))
        ttk.Label(outer, text=title, style="Head.TLabel").pack(anchor="w", pady=(0, 6))
        return outer

    def _build(self):
        root = ttk.Frame(self, style="Bg.TFrame", padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="STL Library Tools", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Render preview sheets and pack folders into ZIP archives",
                  style="Bg.TLabel", foreground=C_DIM).pack(anchor="w", pady=(0, 8))

        # --- paths
        p = self._panel(root, "Paths")
        p.pack(fill="x", pady=(0, 8))
        g = ttk.Frame(p)
        g.pack(fill="x")
        g.columnconfigure(1, weight=1)
        ttk.Label(g, text="Models folder:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(g, textvariable=self.var_folder).grid(row=0, column=1, sticky="ew")
        ttk.Button(g, text="Browse…", command=self.pick_folder).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(g, text="Refresh", command=self.refresh).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(g, text="Blender:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Entry(g, textvariable=self.var_blender).grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Button(g, text="Browse…", command=self.pick_blender).grid(row=1, column=2, padx=(6, 0), pady=(6, 0))
        ttk.Button(g, text="Detect", command=self.detect_blender).grid(row=1, column=3, padx=(6, 0), pady=(6, 0))

        # --- folder list and log as two tabs (saves window height)
        self.tabs = ttk.Notebook(root)

        p = ttk.Frame(self.tabs, padding=(12, 8))
        self.tabs.add(p, text="  Subfolders  ")
        ttk.Label(p, text="Click a row to tick / untick it.",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 6))
        bar = ttk.Frame(p)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="All", command=lambda: self.select("all")).pack(side="left")
        ttk.Button(bar, text="None", command=lambda: self.select("none")).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Without PNG", command=lambda: self.select("nopng")).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Without ZIP", command=lambda: self.select("nozip")).pack(side="left", padx=(6, 0))
        self.lbl_count = ttk.Label(bar, text="", style="Dim.TLabel")
        self.lbl_count.pack(side="right")

        tf = ttk.Frame(p)
        tf.pack(fill="both", expand=True)
        cols = ("chk", "name", "models", "png", "zip", "st_render", "st_zip")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="none", height=6)
        for c, txt, w, anchor, stretch in (
                ("chk", "", 34, "center", False),
                ("name", "Folder", 260, "w", True),
                ("models", "Models", 80, "center", False),
                ("png", "PNG", 50, "center", False),
                ("zip", "ZIP", 50, "center", False),
                ("st_render", "Render", 170, "w", True),
                ("st_zip", "Zip", 150, "w", True)):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor=anchor, stretch=stretch)
        self.tree.tag_configure("off", foreground=C_DIM)
        self.tree.tag_configure("ok", foreground=C_OK)
        self.tree.tag_configure("err", foreground=C_ERR)
        self.tree.tag_configure("busy", foreground=C_ACCENT)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_click)

        # --- tasks
        p = self._panel(root, "What to do — folder by folder: render, then ZIP "
                            "(zips in the background while Blender renders the next one)")
        p.pack(side="bottom", fill="x", pady=(0, 8))
        tasks_panel = p
        r1 = ttk.Frame(p)
        r1.pack(fill="x")
        ttk.Checkbutton(r1, text="Render sheets (Blender)", variable=self.var_render).pack(side="left")
        ttk.Label(r1, text="   resolution:").pack(side="left")
        ttk.Combobox(r1, textvariable=self.var_res, width=6, state="readonly",
                     values=("1000", "2000", "3000", "4000", "6000", "8000")).pack(side="left", padx=(4, 0))
        ttk.Label(r1, text="  quality (samples):").pack(side="left")
        ttk.Combobox(r1, textvariable=self.var_samples, width=5, state="readonly",
                     values=("16", "32", "64", "128", "256", "512")).pack(side="left", padx=(4, 0))
        ttk.Checkbutton(r1, text="both sides (A + B)", variable=self.var_both).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(r1, text="overwrite existing PNGs",
                        variable=self.var_overwrite_png).pack(side="left", padx=(12, 0))
        r2 = ttk.Frame(p)
        r2.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(r2, text="Pack into ZIP", variable=self.var_zip).pack(side="left")
        ttk.Checkbutton(r2, text="overwrite existing ZIPs", variable=self.var_overwrite_zip).pack(side="left", padx=(12, 0))

        # --- progress
        p = self._panel(root, "Progress")
        p.pack(side="bottom", fill="x", before=tasks_panel)
        self.lbl_stage = ttk.Label(p, text="Ready.", style="Dim.TLabel")
        self.lbl_stage.pack(anchor="w")
        self.bar_total = FancyBar(p, height=28)
        self.bar_total.pack(fill="x", pady=(4, 8))
        # two bars side by side - Blender and ZIP work at the same time
        two = ttk.Frame(p)
        two.pack(fill="x")
        two.columnconfigure(0, weight=1, uniform="b")
        two.columnconfigure(1, weight=1, uniform="b")
        self.lbl_render = ttk.Label(two, text="Blender: —", style="Dim.TLabel")
        self.lbl_render.grid(row=0, column=0, sticky="w")
        self.bar_render = FancyBar(two, height=20)
        self.bar_render.grid(row=1, column=0, sticky="ew", pady=(4, 0), padx=(0, 6))
        self.lbl_zip = ttk.Label(two, text="ZIP: —", style="Dim.TLabel")
        self.lbl_zip.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.bar_zip = FancyBar(two, height=20)
        self.bar_zip.grid(row=1, column=1, sticky="ew", pady=(4, 0), padx=(6, 0))
        self.bars = (self.bar_total, self.bar_render, self.bar_zip)

        btns = ttk.Frame(p)
        btns.pack(fill="x", pady=(10, 0))
        self.btn_start = ttk.Button(btns, text="▶  Start", style="Start.TButton", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(btns, text="■  Stop", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(8, 0))

        # --- log in the second tab
        self.log_frame = ttk.Frame(self.tabs, padding=(12, 8))
        self.tabs.add(self.log_frame, text="  Log  ")
        self.log = tk.Text(self.log_frame, height=6, bg="#121317", fg=C_DIM,
                           insertbackground=C_TEXT, relief="flat", wrap="word",
                           font=("Consolas" if IS_WIN else "TkFixedFont", 9))
        lsb = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=lsb.set, state="disabled")
        self.log.tag_configure("err", foreground=C_ERR)
        self.log.tag_configure("ok", foreground=C_OK)
        self.log.tag_configure("head", foreground=C_ACCENT)
        self.log.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")

        # tabs are packed last - they only get the space that is left,
        # so in a small window the list shrinks, not the progress bars
        self.tabs.pack(fill="both", expand=True, pady=(0, 8))

    # ------------------------------------------------------- UI actions

    def pick_folder(self):
        d = filedialog.askdirectory(initialdir=self.var_folder.get() or os.path.expanduser("~"),
                                    title="Folder with model subfolders")
        if d:
            self.var_folder.set(os.path.normpath(d))
            self.refresh()

    def pick_blender(self):
        types = [("Blender", "blender.exe"), ("All files", "*.*")] if IS_WIN else [("All files", "*")]
        f = filedialog.askopenfilename(title="Select the Blender executable", filetypes=types)
        if f:
            self.var_blender.set(os.path.normpath(f))

    def detect_blender(self):
        b = find_blender()
        if b:
            self.var_blender.set(b)
        else:
            messagebox.showwarning("Blender", "Could not find Blender automatically.\n"
                                   "Select the file manually with the “Browse…” button.")

    def refresh(self):
        folder = self.var_folder.get().strip()
        # ticks are remembered only within the same folder
        same = os.path.normcase(folder) == getattr(self, "_scanned", None)
        keep = set(self.checked) if same else None
        self._scanned = os.path.normcase(folder)
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.checked.clear()
        if not os.path.isdir(folder):
            self.lbl_count.configure(text="")
            return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            items = scan_folder(folder)
        finally:
            self.configure(cursor="")
        for it in items:
            name = it["name"]
            self.rows[name] = it
            if it["underscore"]:
                status = "skipped (name starts with _)"
            elif it["models"] == 0:
                status = "3MF only" if it["mf3"] else "no models"
            else:
                status = ""
            selectable = not it["underscore"]
            if selectable:
                if keep is None:
                    on = name.lower() not in DEFAULT_SKIP
                else:
                    on = name in keep
                if on:
                    self.checked.add(name)
            models = str(it["models"]) + (" +%d 3MF" % it["mf3"] if it["mf3"] else "")
            self.tree.insert("", "end", iid=name, values=(
                "", name, models, "✔" if it["png"] else "—", "✔" if it["zip"] else "—", status, ""),
                tags=() if selectable else ("off",))
            self._draw_check(name)
        self._update_count()

    def _draw_check(self, name):
        if self.tree.exists(name):
            self.tree.set(name, "chk", "☑" if name in self.checked else "☐")

    def _update_count(self):
        self.lbl_count.configure(text="ticked: %d / %d" % (len(self.checked), len(self.rows)))

    def on_click(self, event):
        if self.worker:
            return "break"
        if self.tree.identify_region(event.x, event.y) == "heading":
            return None
        name = self.tree.identify_row(event.y)
        if not name or self.rows.get(name, {}).get("underscore"):
            return "break"
        if name in self.checked:
            self.checked.discard(name)
        else:
            self.checked.add(name)
        self._draw_check(name)
        self._update_count()
        return "break"

    def select(self, mode):
        if self.worker:
            return
        self.checked.clear()
        for name, it in self.rows.items():
            if it["underscore"] or mode == "none":
                continue
            if mode == "nopng" and (it["png"] or it["models"] == 0):
                continue
            if mode == "nozip" and it["zip"]:
                continue
            self.checked.add(name)
        for name in self.rows:
            self._draw_check(name)
        self._update_count()

    def set_status(self, name, col, text):
        """col: "st_render" or "st_zip"; the row colour follows both columns"""
        if not self.tree.exists(name):
            return
        self.tree.set(name, col, text)
        both = self.tree.set(name, "st_render") + " " + self.tree.set(name, "st_zip")
        if "✖" in both:
            tag = "err"
        elif "…" in both:
            tag = "busy"
            if col == "st_render":
                self.tree.see(name)
        elif "✔" in both or "already exists" in both:
            tag = "ok"
        else:
            tag = None
        self.tree.item(name, tags=(tag,) if tag else ())

    def log_line(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        # cap the log length
        if int(self.log.index("end-1c").split(".")[0]) > 5000:
            self.log.delete("1.0", "1000.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _save(self):
        self.cfg.update({
            "folder": self.var_folder.get(),
            "blender": self.var_blender.get(),
            "do_render": self.var_render.get(),
            "do_zip": self.var_zip.get(),
            "overwrite_png": self.var_overwrite_png.get(),
            "overwrite_zip": self.var_overwrite_zip.get(),
            "both_sides": self.var_both.get(),
            "res": int(self.var_res.get()),
            "samples": int(self.var_samples.get()),
        })
        save_config(self.cfg)

    # -------------------------------------------------------- start/stop
    def start(self):
        if self.worker:
            return
        folder = self.var_folder.get().strip()
        if not os.path.isdir(folder):
            messagebox.showerror("Folder", "Select an existing models folder.")
            return
        do_render, do_zip = self.var_render.get(), self.var_zip.get()
        if not (do_render or do_zip):
            messagebox.showinfo("Nothing to do", "Tick render, ZIP or both.")
            return
        names = [n for n in self.rows if n in self.checked]  # same order as the list
        if not names:
            messagebox.showinfo("Nothing to do", "Tick at least one folder.")
            return
        render_names = [n for n in names if self.rows[n]["models"] > 0]
        # without "overwrite existing PNGs" a folder that already has its sheet(s)
        # is not sent to Blender at all - no import, no render (it is still zipped)
        png_kept = []
        if do_render and not self.var_overwrite_png.get():
            both = self.var_both.get()
            png_kept = [n for n in render_names if self._has_png(folder, n, both)]
            render_names = [n for n in render_names if n not in png_kept]
        blender = self.var_blender.get().strip()
        if do_render and render_names and not os.path.isfile(blender):
            messagebox.showerror("Blender", "Blender is not at the given path.\n"
                                 "Select it manually or click “Detect”.")
            return
        if do_render and not os.path.isfile(RENDER_SCRIPT):
            messagebox.showerror("Missing file", "Could not find render_grid.py next to the app:\n"
                                 + RENDER_SCRIPT)
            return
        self._save()

        job = {
            "folder": folder,
            "blender": blender,
            "render": render_names if do_render else [],
            "zip": names if do_zip else [],
            "overwrite_zip": self.var_overwrite_zip.get(),
            "res": self.var_res.get(),
            "samples": self.var_samples.get(),
            "both": self.var_both.get(),
        }
        for n in names:
            if n in job["render"]:
                self.set_status(n, "st_render", "queued")
            elif n in png_kept:
                self.set_status(n, "st_render", "already exists")
            elif do_render:
                self.set_status(n, "st_render", "—")
            self.set_status(n, "st_zip", "queued" if do_zip else "")
        # overall progress: each folder is the sum of its parts (render weighs more)
        self.parts = {}
        for n in names:
            r, z = n in job["render"], n in job["zip"]
            w_r = (0.85 if z else 1.0) if r else 0.0
            self.parts[n] = {"w_r": w_r, "w_z": 1.0 - w_r if z else 0.0, "r": 0.0, "z": 0.0}
        self.png_kept = len(png_kept)
        self.t0 = time.time()
        self.cancel.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        for b in self.bars:
            b.error = False
            b.running = True
            b.set(0, "")
        if job["render"]:
            self.lbl_render.configure(text="Blender: —")
        else:
            self.lbl_render.configure(text="Blender: nothing to render" if do_render else "Blender: off")
        self.lbl_zip.configure(text="ZIP: —" if job["zip"] else "ZIP: off")
        self.worker = threading.Thread(target=self._run, args=(job,), daemon=True)
        self.worker.start()

    def stop(self):
        if not self.worker:
            return
        self.cancel.set()
        p = self.proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        self.lbl_stage.configure(text="Stopping…")

    def on_close(self):
        if self.worker:
            if not messagebox.askyesno("Work in progress", "Work is still running. Stop and close?"):
                return
            self.stop()
        self._save()
        self.destroy()

    # ------------------------------------------ worker threads (background)
    def emit(self, *ev):
        self.events.put(ev)

    def _run(self, job):
        """Pipeline: Blender renders folders one by one, and every finished
        folder goes straight to the ZIP queue. Zipping runs in a separate
        thread, so folder 1 is zipped while Blender already renders folder 2."""
        results = {"render": [0, 0], "zip": [0, 0, 0]}
        t0 = time.time()
        zip_q = queue.Queue()
        zipper = None
        sent = set()

        def to_zip(name):
            if name in job["zip"] and name not in sent:
                sent.add(name)
                zip_q.put(name)

        if job["zip"]:
            zipper = threading.Thread(target=self._zip_worker,
                                      args=(job, zip_q, results["zip"]), daemon=True)
            zipper.start()
        try:
            # folders Blender does not render (no models / render off)
            # have nothing to wait for - straight to zipping
            for n in job["zip"]:
                if n not in job["render"]:
                    to_zip(n)
            if job["render"]:
                self._run_render(job, results["render"], to_zip)
            # Blender finished (or crashed) - the rest goes to ZIP anyway
            if not self.cancel.is_set():
                for n in job["zip"]:
                    to_zip(n)
        except Exception as e:
            self.emit("log", "!!! Error: %s" % e, "err")
        if zipper:
            zip_q.put(None)         # end of queue
            zipper.join()
        self.emit("finished", results, time.time() - t0, self.cancel.is_set(),
                  bool(job["render"]), bool(job["zip"]))

    def _run_render(self, job, res, on_done):
        names = job["render"]
        cmd = [job["blender"], "--background", "--python", RENDER_SCRIPT, "--",
               "--folder", job["folder"], "--res", job["res"], "--samples", job["samples"]]
        if not job["both"]:
            cmd.append("--one-side")
        for n in names:
            cmd += ["--only", n]
        self.emit("log", "> " + " ".join('"%s"' % c if " " in c else c for c in cmd), "head")

        flags = 0x08000000 if IS_WIN else 0     # CREATE_NO_WINDOW - no black console window
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     cwd=job["folder"], creationflags=flags, env=env)

        total = len(names)
        t_start = time.time() - 2
        sides = 2 if job["both"] else 1
        idx = 0                 # which folder (1..total)
        cur = None
        imp = 0.0               # import progress 0..1
        rend = -1               # which render in the folder (0 = A, 1 = B)
        samp = 0.0

        def push():
            if not cur:
                return
            if rend < 0:
                frac = 0.2 * imp
                txt = "importing models"
            else:
                frac = 0.2 + 0.8 * (rend + samp) / sides
                side = ("side A" if rend == 0 else "side B") if sides == 2 else "render"
                txt = "%s — %d%%" % (side, samp * 100)
            self.emit("prog", "r", cur, frac, "Blender [%d/%d]: %s" % (idx, total, cur), txt)

        for raw in self.proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line.startswith("@@ "):
                parts = line[3:].split(" ", 2)
                kind = parts[0]
                if kind == "TOTAL":
                    total = int(parts[1])
                elif kind == "FOLDER":
                    idx = int(parts[1])
                    cur = parts[2] if len(parts) > 2 else "?"
                    imp, rend, samp = 0.0, -1, 0.0
                    self.emit("status", cur, "st_render", "rendering…")
                    self.emit("log", "── Blender [%d/%d] %s" % (idx, total, cur), "head")
                elif kind == "IMPORT":
                    imp = int(parts[1]) / max(1, int(parts[2]))
                elif kind == "RENDER":
                    rend += 1
                    samp = 0.0
                elif kind == "DONE":
                    name = parts[2] if len(parts) > 2 else cur
                    # "ok" from the script is not enough - main() returns without
                    # rendering when nothing was imported; a fresh PNG on disk counts
                    ok = parts[1] == "ok" and self._fresh_png(job["folder"], name, t_start)
                    res[0 if ok else 1] += 1
                    self.emit("status", name, "st_render", "✔ done" if ok else "✖ error")
                    self.emit("rowflag", name, "png", ok)
                    self.emit("prog", "r", name, 1.0, "Blender: waiting for the next one", "")
                    cur = None
                    on_done(name)
                push()
                continue
            m = SAMPLE_RE.search(line)
            if m:
                s = int(m.group(1)) / max(1, int(m.group(2)))
                t = TILES_RE.search(line)
                if t:
                    s = (int(t.group(1)) + s) / max(1, int(t.group(2)))
                # never backwards (adaptive sampling / new tile)
                samp = max(samp, min(1.0, s))
                push()
                continue
            if line.startswith("Fra:"):
                continue        # Blender noise (memory, time) - keep it out of the log
            if line.strip():
                tag = "err" if ("ERROR" in line or "Error" in line or "!!!" in line) else None
                self.emit("log", line, tag)
        code = self.proc.wait()
        self.proc = None
        if cur and not self.cancel.is_set():
            # Blender died in the middle of a folder
            res[1] += 1
            self.emit("status", cur, "st_render", "✖ Blender aborted")
        if code != 0 and not self.cancel.is_set():
            self.emit("log", "!!! Blender exited with code %s" % code, "err")
        self.emit("prog", "r", None, 1.0, "Blender: finished", "")

    @staticmethod
    def _has_png(parent, name, both):
        """True when the folder already has its sheet(s): name_A.png and
        name_B.png for A + B, or name.png for one side."""
        if both:
            return all(os.path.isfile(os.path.join(parent, name + s))
                       for s in ("_A.png", "_B.png"))
        return os.path.isfile(os.path.join(parent, name + ".png"))

    @staticmethod
    def _fresh_png(parent, name, since):
        for suf in ("_A.png", ".png"):
            p = os.path.join(parent, name + suf)
            if os.path.isfile(p) and os.path.getmtime(p) >= since:
                return True
        return False

    def _zip_worker(self, job, zip_q, res):
        """Separate thread: zips folders in the order Blender hands them over."""
        parent = job["folder"]
        total = len(job["zip"])
        k = 0
        while True:
            self.emit("prog", "z", None, 0.0, "ZIP: waiting for a folder from Blender", "")
            name = zip_q.get()
            if name is None:
                break
            k += 1
            if self.cancel.is_set():
                continue
            label = "ZIP [%d/%d]: %s" % (k, total, name)
            dst = os.path.join(parent, name + ".zip")
            if os.path.exists(dst) and not job["overwrite_zip"]:
                res[1] += 1
                self.emit("status", name, "st_zip", "already exists")
                self.emit("prog", "z", name, 1.0, label, "already exists")
                self.emit("log", "[=] ZIP already exists: %s.zip" % name)
                continue
            self.emit("status", name, "st_zip", "zipping…")
            self.emit("log", "[+] zipping: %s" % name)
            try:
                done = self._zip_one(parent, name, os.path.join(parent, name), dst, label)
            except Exception as e:
                done = False
                self.emit("log", "    [ERROR] %s: %s" % (name, e), "err")
            if done:
                res[0] += 1
                self.emit("status", name, "st_zip", "✔ done")
                self.emit("rowflag", name, "zip", True)
            elif self.cancel.is_set():
                self.emit("status", name, "st_zip", "stopped")
            else:
                res[2] += 1
                self.emit("status", name, "st_zip", "✖ error")
        self.emit("prog", "z", None, 1.0, "ZIP: finished", "")

    def _zip_one(self, parent, name, src, dst, label):
        # file list with sizes - progress is counted in bytes
        entries = []
        for root, dirs, files in os.walk(src):
            dirs.sort()
            rel_root = os.path.relpath(root, parent)
            if not files and not dirs:
                entries.append((root, rel_root + "/", 0, True))
            for f in sorted(files):
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                entries.append((full, os.path.join(rel_root, f), size, False))
        total_bytes = sum(e[2] for e in entries) or 1
        done_bytes = 0
        last = 0.0
        tmp = dst + ".part"
        try:
            # the archive holds a "name/..." folder - same as tar / 7-Zip in __ZIP.bat
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=5,
                                 allowZip64=True) as zf:
                for full, arc, size, is_dir in entries:
                    if self.cancel.is_set():
                        raise InterruptedError
                    arc = arc.replace(os.sep, "/")
                    if is_dir:
                        zf.writestr(arc, b"")
                        continue
                    zi = zipfile.ZipInfo.from_file(full, arc, strict_timestamps=False)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as fin, \
                            zf.open(zi, "w", force_zip64=size > 0x7FFFFFFF) as fout:
                        while True:
                            chunk = fin.read(1 << 20)
                            if not chunk:
                                break
                            fout.write(chunk)
                            done_bytes += len(chunk)
                            now = time.time()
                            if now - last > 0.1:
                                last = now
                                frac = done_bytes / total_bytes
                                self.emit("prog", "z", name, frac, label, "%d%% — %.0f / %.0f MB" % (
                                    frac * 100, done_bytes / 1e6, total_bytes / 1e6))
                            if self.cancel.is_set():
                                raise InterruptedError
            os.replace(tmp, dst)
            self.emit("prog", "z", name, 1.0, label, "done")
            return True
        except InterruptedError:
            return False
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ------------------------------------ receiving events in the UI thread
    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        self._update_eta()
        self.after(80, self._poll)

    def _overall(self):
        """(overall fraction, how many folders are fully done)"""
        if not self.parts:
            return 0.0, 0
        frac = done = 0
        for p in self.parts.values():
            f = p["w_r"] * p["r"] + p["w_z"] * p["z"]
            frac += f
            done += f >= 0.999
        return frac / len(self.parts), done

    def _handle(self, ev):
        kind = ev[0]
        if kind == "log":
            self.log_line(ev[1], ev[2] if len(ev) > 2 else None)
        elif kind == "prog":
            _, which, name, frac, label, txt = ev
            if which == "r":
                self.lbl_render.configure(text=label)
                self.bar_render.set(frac if name else 0, txt)
                if not name:
                    self.bar_render.running = False
            else:
                self.lbl_zip.configure(text=label)
                self.bar_zip.set(frac if name else 0, txt)
            if name in self.parts:
                self.parts[name][which] = max(self.parts[name][which], frac)
                total, done = self._overall()
                self.bar_total.set(total, "%d / %d folders done  ·  %d%%" % (
                    done, len(self.parts), round(total * 100)))
        elif kind == "status":
            self.set_status(ev[1], ev[2], ev[3])
        elif kind == "rowflag":
            _, name, col, val = ev
            if val and name in self.rows:
                self.rows[name][col] = True
                self.tree.set(name, col, "✔")
        elif kind == "finished":
            self._finished(*ev[1:])

    def _update_eta(self):
        if not self.worker:
            return
        el = time.time() - self.t0
        frac, _ = self._overall()
        txt = "Working   ·   elapsed %s" % fmt_time(el)
        if 0.02 < frac < 1.0 and el > 5:
            txt += "   ·   about %s left" % fmt_time(el * (1 - frac) / frac)
        self.lbl_stage.configure(text=txt)

    def _finished(self, results, elapsed, cancelled, did_render, did_zip):
        self.worker = None
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        for b in self.bars:
            b.running = False
        busy = ("queued", "rendering…", "zipping…")
        for n in self.rows:
            for col in ("st_render", "st_zip"):
                if self.tree.set(n, col) in busy:
                    self.set_status(n, col, "stopped")
        parts = []
        r, z = results["render"], results["zip"]
        if did_render or self.png_kept:
            parts.append("render: %d ok%s%s" % (
                r[0], ", %d skipped (PNG exists)" % self.png_kept if self.png_kept else "",
                ", %d errors" % r[1] if r[1] else ""))
        if did_zip:
            parts.append("ZIP: %d zipped, %d skipped%s" % (
                z[0], z[1], ", %d errors" % z[2] if z[2] else ""))
        summary = " · ".join(parts)
        errors = r[1] + z[2]
        if cancelled:
            head = "Stopped"
            self.bar_total.error = True
        elif errors:
            head = "Finished with errors"
            self.bar_total.error = True
        else:
            head = "Finished"
            self.bar_total.value = 1.0
        self.bar_total.set(self.bar_total.value, "%s — %s" % (head, summary))
        self.lbl_stage.configure(text="%s in %s" % (head, fmt_time(elapsed)))
        self.log_line("═══ %s (%s): %s ═══" % (head, fmt_time(elapsed), summary),
                      "err" if errors or cancelled else "ok")
        self.bell()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
