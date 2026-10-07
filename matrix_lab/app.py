"""
app.py -- MatrixLab: a suite of linear-algebra demos.

Layout: a sidebar on the left lists the modules by chapter; the chosen
module fills the rest of the window. Modules are built the first time
they are opened, so launch is instant. The Overview page describes every
module. "Send to" hands the current module's matrix/vectors to another
module without going through the saved library. The last module opened
is remembered between launches.

Every module shares the same matrix editor and the same saved-matrix
library (JSON files in ~/Documents/MatrixLab Matrices/).

Run from a terminal:      python3 app.py
Build a macOS .app:       ./build_app.sh
"""

import cProfile
import io
import json
import os
import pstats
import sys
import time

# Keep matplotlib's cache (font list etc.) in a stable, writable place.
# PyInstaller's runtime hook otherwise points MPLCONFIGDIR at a fresh temp
# folder on every launch, so the font cache is rebuilt each time.
_SUPPORT_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "MatrixLab")
os.makedirs(os.path.join(_SUPPORT_DIR, "mpl"), exist_ok=True)
os.environ["MPLCONFIGDIR"] = os.path.join(_SUPPORT_DIR, "mpl")

import matplotlib
matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subprocess
import threading

from core import MatrixLibrary, fmt_mat, fmt_vec, DOCUMENTS_SHORTCUT
from widgets import LibraryPanel
from transpose_tab import TransposeDotTab
from multiply_tab import MultiplyTab
from rowreduce_tab import RowReduceTab
from solve_tab import SolveTab
from subspaces_tab import SubspacesTab
from span_tab import SpanTab
from det_tab import DetTab
from transform_tab import TransformTab
from eigen_tab import EigenTab
from vectors_tab import VectorsTab
from gs_tab import GramSchmidtTab
from basis_tab import BasisTab
from powers_tab import PowersTab
from svd_tab import SvdTab
from fit_tab import FitTab
from cplx_tab import ComplexEigenTab

# (key, label, class, one-line description) grouped by chapter, in course order
CHAPTERS = [
    ("Vectors", [
        ("vectors", "Vectors", VectorsTab,
         "dot product, angle, projection, cross product, triple product"),
        ("span", "Span", SpanTab,
         "linear independence, dependence relations, span, is w in the span?"),
    ]),
    ("Matrices as maps", [
        ("multiply", "Multiply", MultiplyTab,
         "AB and BA in matrix form, entry by entry; when BA is undefined"),
        ("transpose", "Transpose · Dot", TransposeDotTab,
         "the adjoint identity (Ax)·y = x·(Aᵀy), with plots and animation"),
        ("det", "Determinant · Inverse", DetTab,
         "det by cofactors and by elimination; inverse by [A | I] and adjugate"),
        ("transform", "Transform", TransformTab,
         "2×2 / 3×3 as a map of the plane or space; presets, shapes, morph from I to A"),
    ]),
    ("Systems and subspaces", [
        ("rowreduce", "Row Reduce", RowReduceTab,
         "Gauss-Jordan step by step in exact fractions; pivots, rank, null space; PA = LU"),
        ("solve", "Solve Ax = b", SolveTab,
         "consistency, unique or general solution, least squares; or by LU substitution"),
        ("subspaces", "Subspaces", SubspacesTab,
         "column, row, null and left null space with bases, dimensions, pictures"),
        ("basis", "Basis", BasisTab,
         "coordinates in a new basis, P and P⁻¹, a matrix as P⁻¹AP"),
        ("gs", "Orthogonalize", GramSchmidtTab,
         "Gram-Schmidt step by step and A = QR"),
        ("fit", "Fit", FitTab,
         "least-squares curve fitting: design matrix, normal equations, residuals, R²"),
    ]),
    ("Eigen and beyond", [
        ("eigen", "Eigen", EigenTab,
         "characteristic polynomial, eigenvalues and eigenvectors, PDP⁻¹"),
        ("cplx", "Complex Eigen", ComplexEigenTab,
         "a 2×2 with eigenvalues a ± bi as rotation by φ and scaling by |λ|: A = PCP⁻¹"),
        ("powers", "Powers · Markov", PowersTab,
         "Aᵏ, the sequence Aᵏx₀, why it behaves that way, Markov steady states"),
        ("svd", "SVD", SvdTab,
         "A = UΣVᵀ from AᵀA, checks, rank, the four-stage picture"),
    ]),
]
MODULES = {key: (label, cls, desc) for _, items in CHAPTERS for key, label, cls, desc in items}
ORDER = [key for _, items in CHAPTERS for key, *_ in items]


class OverviewPage(ttk.Frame):
    """The first page: what each module does, each name clickable."""

    def __init__(self, master, go):
        super().__init__(master, padding=24)
        ttk.Label(self, text="MatrixLab", font=("Helvetica", 26, "bold")).pack(anchor="w")
        ttk.Label(self, text="Linear algebra worked out step by step, with pictures. Pick a module "
                  "in the sidebar or click a name below. Every module shares one matrix editor and "
                  "one library of saved matrices. Every module also computes its characteristic results "
                  "(a cross product, an RREF, eigenvectors, Q and R, ...); 'Send…' passes any input or result "
                  "to another module, or saves it to the library, without retyping.",
                  wraplength=820, justify=tk.LEFT).pack(anchor="w", pady=(6, 14))
        for chapter, items in CHAPTERS:
            ttk.Label(self, text=chapter, font=("Helvetica", 15, "bold"),
                      foreground="#2a5db0").pack(anchor="w", pady=(10, 2))
            for key, label, _, desc in items:
                row = ttk.Frame(self); row.pack(anchor="w", fill=tk.X)
                link = tk.Label(row, text=label, fg="#1a5fb4", cursor="hand2",
                                font=("Helvetica", 13, "underline"), width=22, anchor="w")
                link.pack(side=tk.LEFT)
                link.bind("<Button-1>", lambda e, k=key: go(k))
                ttk.Label(row, text=desc, wraplength=640, justify=tk.LEFT).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(self, text="Tips: cells accept fractions like 1/2. Live update recomputes as you type. "
                  "The divider between controls and picture can be dragged. Saved matrices live in "
                  "~/Library/Application Support/MatrixLab/Matrices (File menu opens the folder or adds a "
                  "shortcut to it in Documents).",
                  wraplength=820, justify=tk.LEFT, foreground="gray").pack(anchor="w", pady=(24, 0))


def _kind(value):
    nd = np.ndim(value)
    return "scalar" if nd == 0 else "vector" if nd == 1 else "matrix"


def _coerce(value, kind):
    """Reshape a value for a slot of the given kind: a scalar becomes a
    1x1 matrix or a length-1 vector, a vector a 1-row matrix, and a
    one-row / one-column matrix a vector."""
    value = np.asarray(value, dtype=float)
    if kind == "scalar":
        return np.float64(value.reshape(-1)[0])
    if kind == "vector":
        return value.reshape(-1)
    if value.ndim == 0:
        return value.reshape(1, 1)
    return value.reshape(1, -1) if value.ndim == 1 else value


def _fits(value, kind):
    """Can this value go into a slot of this kind?"""
    v = np.asarray(value, dtype=float)
    if kind == "scalar":
        return v.size == 1
    if kind == "matrix":
        return True                                   # scalars and vectors reshape into matrices
    return v.ndim <= 1 or 1 in v.shape                # scalars, vectors, 1xn / nx1 matrices


class SendDialog(tk.Toplevel):
    """Pick something from the current module (an input or a computed
    result), a destination module, and the slot to load it into; or save
    it straight to the library."""

    def __init__(self, app, source_key):
        super().__init__(app)
        self.app = app
        self.source_key = source_key
        source = app.instances[source_key]
        src_label = MODULES[source_key][0]
        self.title(f"Send from {src_label}")
        self.resizable(False, False)
        self.transient(app)

        # what can be sent: inputs first, then results
        self.items = []                               # (label, value)
        try:
            for k, v in source.get_fields().items():
                self.items.append((f"input {k}  {self._shape(v)}", np.asarray(v, dtype=float)))
        except ValueError:
            pass
        for label, v in getattr(source, "results", {}).items():
            self.items.append((f"result: {label}  {self._shape(v)}", np.asarray(v, dtype=float)))
        self.targets = [k for k in ORDER if k != source_key]

        body = ttk.Frame(self, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text="What to send", font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="To module", font=("Helvetica", 12, "bold")).grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.what = tk.Listbox(body, height=12, width=44, exportselection=False)
        self.what.grid(row=1, column=0, sticky="nsew")
        for label, _ in self.items:
            self.what.insert(tk.END, label)
        self.where = tk.Listbox(body, height=12, width=26, exportselection=False)
        self.where.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        for k in self.targets:
            self.where.insert(tk.END, MODULES[k][0])
        self.what.bind("<<ListboxSelect>>", lambda e: self._refresh())
        self.where.bind("<<ListboxSelect>>", lambda e: self._refresh())

        self.preview = tk.Label(body, text="", font=("Menlo", 10), justify=tk.LEFT, anchor="nw",
                                height=6, width=44, foreground="#333")
        self.preview.grid(row=2, column=0, sticky="w", pady=(6, 0))

        slot = ttk.Frame(body); slot.grid(row=2, column=1, sticky="nw", padx=(12, 0), pady=(6, 0))
        ttk.Label(slot, text="Load it as:").pack(anchor="w")
        self.slot_var = tk.StringVar()
        self.slot_box = ttk.Combobox(slot, textvariable=self.slot_var, state="readonly", width=22)
        self.slot_box.pack(anchor="w", pady=(2, 0))
        self.note = ttk.Label(slot, text="", foreground="gray", wraplength=200, justify=tk.LEFT)
        self.note.pack(anchor="w", pady=(6, 0))

        btns = ttk.Frame(body); btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Save to library…", command=self.save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))
        self.send_btn = ttk.Button(btns, text="Send", command=self.send)
        self.send_btn.pack(side=tk.LEFT, padx=(8, 0))

        if self.items:
            self.what.selection_set(0)
        if self.targets:
            self.where.selection_set(0)
        self._refresh()
        self.bind("<Return>", lambda e: self.send())
        self.bind("<Escape>", lambda e: self.destroy())

    @staticmethod
    def _shape(v):
        v = np.asarray(v)
        if v.ndim == 0:
            return "(scalar)"
        return f"({v.shape[0]}x{v.shape[1]})" if v.ndim == 2 else f"(length {v.shape[0]})"

    def _selected(self):
        wi = self.what.curselection(); ti = self.where.curselection()
        if not wi or not ti:
            return None, None, None
        label, value = self.items[wi[0]]
        return label, value, self.targets[ti[0]]

    def _slots(self, target_key, value):
        cls = MODULES[target_key][1]
        accepts = getattr(cls, "ACCEPTS", {"A": "matrix"})
        return [(k, kind) for k, kind in accepts.items() if _fits(value, kind)]

    def _refresh(self):
        label, value, target_key = self._selected()
        if label is None:
            self.slot_box["values"] = []; self.slot_var.set(""); self.send_btn.state(["disabled"])
            return
        v = np.asarray(value)
        text = fmt_mat(v, indent="") if v.ndim == 2 else fmt_vec(v) if v.ndim == 1 else f"{float(v):.6g}"
        self.preview.config(text=text[:600])
        slots = self._slots(target_key, value)
        self.slot_box["values"] = [f"{k}  ({kind})" for k, kind in slots]
        if slots:
            # prefer a slot whose kind matches the value's own kind
            pref = next((i for i, (k, kind) in enumerate(slots) if kind == _kind(value)), 0)
            self.slot_var.set(self.slot_box["values"][pref])
            self.send_btn.state(["!disabled"])
            _, kind0 = self._chosen_slot()
            self.note.config(text="A scalar arrives as a 1x1 matrix or a length-1 vector."
                             if _kind(value) == "scalar" and kind0 != "scalar" else "")
        else:
            self.slot_var.set("")
            self.send_btn.state(["disabled"])
            self.note.config(text=f"{MODULES[target_key][0]} has no slot that fits this.")

    def _chosen_slot(self):
        s = self.slot_var.get()
        return (s.split("  (")[0], s.split("(")[-1].rstrip(")")) if s else (None, None)

    def send(self):
        label, value, target_key = self._selected()
        field, kind = self._chosen_slot()
        if label is None or field is None:
            return
        self.app.deliver(target_key, field, _coerce(value, kind), MODULES[self.source_key][0], label)
        self.destroy()

    def save(self):
        label, value, _ = self._selected()
        if label is None:
            return
        field, kind = self._chosen_slot()
        if field is None:                              # no target slot: save under the natural field
            field, kind = ("x", "vector") if _kind(value) == "vector" else ("A", "matrix")
        default = label.replace("input ", "").replace("result: ", "").split("  (")[0]
        default = f"{default} from {MODULES[self.source_key][0]}"
        name = simpledialog.askstring("Save to library", "Name for this entry:", initialvalue=default, parent=self)
        if not name:
            return
        self.app.library.save(name, **{field: _coerce(value, kind)})
        LibraryPanel.refresh_all()
        self.app.instances[self.source_key].status.config(text=f"Saved '{name}' ({field}) to the library.")
        self.destroy()


class MatrixLab(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MatrixLab")
        self.geometry("1480x900")
        self.minsize(1100, 700)
        self.library = MatrixLibrary()
        threading.Thread(target=self._prepare_library, daemon=True).start()
        # settings and logs live in Application Support: fast, no privacy prompts
        self.support_dir = _SUPPORT_DIR
        self.settings_path = os.path.join(self.support_dir, "settings.json")
        self.instances = {}          # key -> module frame (created on demand)
        self.current_key = None

        self._build_layout()
        self._build_menu()
        self.show("overview")
        self.selftest_path = os.path.join(self.support_dir, "selftest")
        if os.path.exists(self.selftest_path):
            self.after(800, self._selftest_tour)

    # ------------------------------------------------------------------
    # layout: sidebar + content
    # ------------------------------------------------------------------
    def _build_layout(self):
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)

        side = ttk.Frame(outer, width=210)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)
        ttk.Label(side, text="MatrixLab", font=("Helvetica", 16, "bold"), padding=(10, 10, 0, 4)).pack(anchor="w")

        self.tree = ttk.Treeview(side, show="tree", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=(6, 0))
        self.tree.tag_configure("chapter", font=("Helvetica", 12, "bold"))
        self.tree.insert("", "end", iid="overview", text="Overview", tags=("module",))
        for chapter, items in CHAPTERS:
            cid = self.tree.insert("", "end", iid="chap:" + chapter, text=chapter, open=True, tags=("chapter",))
            for key, label, _, _ in items:
                self.tree.insert(cid, "end", iid=key, text="   " + label, tags=("module",))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        ttk.Button(side, text="Send…  (inputs or results)", command=self.open_send).pack(
            fill=tk.X, padx=8, pady=(6, 2))
        send = ttk.Menubutton(side, text="Quick send inputs to…")
        send.pack(fill=tk.X, padx=8, pady=(0, 10))
        self.send_menu = tk.Menu(send, tearoff=0)
        send["menu"] = self.send_menu
        self._fill_send_menu(self.send_menu)

        self.content = ttk.Frame(outer)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # pages are stacked in one grid cell and raised, never unmapped:
        # on macOS, Tk can leave a re-mapped page unpainted until the next
        # event, which showed up as a blank Overview for several seconds.
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.instances["overview"] = OverviewPage(self.content, self.show)
        self.instances["overview"].grid(row=0, column=0, sticky="nsew")

    def _fill_send_menu(self, menu):
        for chapter, items in CHAPTERS:
            menu.add_separator() if menu.index("end") is not None else None
            menu.add_command(label=chapter, state="disabled")
            for key, label, _, _ in items:
                menu.add_command(label="   " + label, command=lambda k=key: self.send_to(k))

    def _build_menu(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Save Figure as PNG…", command=self.save_png, accelerator="Cmd+S")
        filemenu.add_command(label="Save Animation as GIF…  (Transpose · Dot)", command=self.save_gif)
        filemenu.add_separator()
        filemenu.add_command(label="Open Library Folder in Finder", command=self.open_library_folder)
        filemenu.add_command(label="Add a Shortcut to the Library in Documents…", command=self.add_documents_shortcut)
        filemenu.add_command(label="Import Matrices from the Old Documents Folder…", command=self.import_from_documents)
        menubar.add_cascade(label="File", menu=filemenu)

        modmenu = tk.Menu(menubar, tearoff=0)
        modmenu.add_command(label="Overview", command=lambda: self.show("overview"), accelerator="Cmd+0")
        for chapter, items in CHAPTERS:
            modmenu.add_separator()
            modmenu.add_command(label=chapter, state="disabled")
            for key, label, _, _ in items:
                modmenu.add_command(label="   " + label, command=lambda k=key: self.show(k))
        modmenu.add_separator()
        last = self._load_settings().get("last")
        if last in MODULES:
            modmenu.add_command(label=f"Reopen last module  ({MODULES[last][0]})", command=lambda k=last: self.show(k))
        modmenu.add_command(label="Previous module", command=lambda: self.step(-1), accelerator="Cmd+[")
        modmenu.add_command(label="Next module", command=lambda: self.step(1), accelerator="Cmd+]")
        modmenu.add_separator()
        modmenu.add_command(label="Send…  (inputs or results)", command=self.open_send, accelerator="Cmd+Shift+S")
        sendmenu = tk.Menu(modmenu, tearoff=0)
        self._fill_send_menu(sendmenu)
        modmenu.add_cascade(label="Quick send inputs to", menu=sendmenu)
        menubar.add_cascade(label="Modules", menu=modmenu)
        self.config(menu=menubar)

        self.bind_all("<Command-s>", lambda e: self.save_png())
        self.bind_all("<Command-Shift-S>", lambda e: self.open_send())
        self.bind_all("<Command-0>", lambda e: self.show("overview"))
        self.bind_all("<Command-bracketleft>", lambda e: self.step(-1))
        self.bind_all("<Command-bracketright>", lambda e: self.step(1))

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    def module(self, key):
        """The module frame for key, built on first use."""
        if key not in self.instances:
            label, cls, _ = MODULES[key]
            self.instances[key] = cls(self.content, self.library)
            self.instances[key].grid(row=0, column=0, sticky="nsew")
        return self.instances[key]

    def show(self, key):
        if key not in MODULES and key != "overview":
            key = "overview"
        frame = self.module(key) if key != "overview" else self.instances["overview"]
        frame.tkraise()
        self.current_key = key
        self.update_idletasks()                     # paint now, not at the next event
        label = "Overview" if key == "overview" else MODULES[key][0]
        self.title(f"MatrixLab — {label}")
        if self.tree.exists(key) and (not self.tree.selection() or self.tree.selection()[0] != key):
            self.tree.selection_set(key)
            self.tree.see(key)
        if key != "overview":
            settings = self._load_settings(); settings["last"] = key
            self._save_settings(settings)

    def step(self, delta):
        keys = ["overview"] + ORDER
        i = keys.index(self.current_key) if self.current_key in keys else 0
        self.show(keys[(i + delta) % len(keys)])

    def _on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        if key.startswith("chap:"):
            self.show("overview")
        elif key != self.current_key:
            self.show(key)

    # ------------------------------------------------------------------
    # hand-off between modules
    # ------------------------------------------------------------------
    def open_send(self):
        if self.current_key in (None, "overview"):
            messagebox.showinfo("Nothing to send", "Open a module first; then you can send its inputs or results onward.")
            return
        SendDialog(self, self.current_key)

    def deliver(self, target_key, field, value, src_label, what):
        """Load `value` into slot `field` of the target module, keeping the
        target's other inputs, then show it."""
        target = self.module(target_key)
        try:
            base = target.get_fields()
        except ValueError:
            base = {}
        base[field] = value
        if field == "A":
            base.pop("B", None)               # the sent A wins; a dependent B is re-fitted to it
        try:
            target.load_fields(base)
        except KeyError as err:
            messagebox.showinfo("Can't send", f"{MODULES[target_key][0]} needs {err.args[0]}.")
            return
        except ValueError as err:
            messagebox.showinfo("Can't send", str(err))
            return
        target.lib.loaded_name = None
        target.lib.mark_modified(True)
        self.show(target_key)
        target.status.config(text=f"Received {what.split('  (')[0]} from {src_label} as {field}.")

    def send_to(self, target_key):
        if self.current_key in (None, "overview"):
            messagebox.showinfo("Nothing to send", "Open a module first, then send its matrix onward.")
            return
        if target_key == self.current_key:
            return
        source = self.instances[self.current_key]
        try:
            fields = source.get_fields()
        except ValueError as err:
            messagebox.showerror("Bad entry", str(err))
            return
        target = self.module(target_key)
        try:
            target.load_fields(fields)
        except KeyError as err:
            messagebox.showinfo("Can't send",
                                f"{MODULES[target_key][0]} needs {err.args[0]}, which "
                                f"{MODULES[self.current_key][0]} does not provide.")
            return
        except ValueError as err:
            messagebox.showinfo("Can't send", str(err))
            return
        src_label = MODULES[self.current_key][0]
        target.lib.loaded_name = None
        target.lib.mark_modified(True)
        self.show(target_key)
        target.status.config(text=f"Received from {src_label}.")

    # ------------------------------------------------------------------
    # library folder
    # ------------------------------------------------------------------
    def _prepare_library(self):
        """Background: warm the listing cache. The app never looks at
        ~/Documents on its own (that needs a macOS consent dialog);
        importing from the old Documents folders is a File-menu action."""
        self.library.names()

    def import_from_documents(self):
        """Move matrices saved by earlier versions in ~/Documents into the
        library. macOS may ask for permission to access Documents."""
        try:
            moved = self.library.migrate_from_documents()
        except OSError as err:
            messagebox.showerror("Import failed", str(err))
            return
        LibraryPanel.refresh_all()
        messagebox.showinfo("Import from Documents",
                            f"{moved} file(s) moved into the library." if moved else
                            "No saved matrices were found in the old Documents folders.")

    def open_library_folder(self):
        self.library.names()                       # make sure the folder exists
        subprocess.Popen(["open", self.library.directory])

    def add_documents_shortcut(self):
        """A symlink in ~/Documents pointing at the library, for browsing.
        Creating it needs Documents access once; macOS may ask."""
        self.library.names()
        if os.path.lexists(DOCUMENTS_SHORTCUT):
            messagebox.showinfo("Shortcut exists", f"{DOCUMENTS_SHORTCUT} already exists.")
            return
        try:
            os.symlink(self.library.directory, DOCUMENTS_SHORTCUT)
            messagebox.showinfo("Shortcut added", f"Created {DOCUMENTS_SHORTCUT}\npointing at the library folder.")
        except OSError as err:
            messagebox.showerror("Couldn't add shortcut", str(err))

    # ------------------------------------------------------------------
    # file actions delegate to the current module
    # ------------------------------------------------------------------
    def save_png(self):
        cur = self.instances.get(self.current_key)
        if cur is not None and hasattr(cur, "save_png"):
            cur.save_png()
        else:
            messagebox.showinfo("No figure", "This page has no figure to save.")

    def save_gif(self):
        self.show("transpose")
        self.instances["transpose"].save_gif()

    # ------------------------------------------------------------------
    # self-test: when ~/Documents/MatrixLab Matrices/.selftest exists, tour
    # the modules, time each switch, profile it, log, and quit.
    # ------------------------------------------------------------------
    def _selftest_tour(self):
        log_path = os.path.join(self.support_dir, "timing.log")
        tour = ["multiply", "overview", "det", "vectors", "overview", "eigen", "vectors", "svd", "multiply",
                "@save", "@delete", "@refresh", "rowreduce", "overview", "det", "@watch:overview", "vectors", "@watch:overview"]
        lines = [f"MatrixLab self-test {time.ctime()}  frozen={getattr(sys, 'frozen', False)}"]
        for key in tour:
            prof = cProfile.Profile()
            t0 = time.perf_counter()
            if not key.startswith("@watch:"):
                prof.enable()
            if key.startswith("@watch:"):
                # switch, then keep pumping the event loop and log any heavy turn
                target = key.split(":", 1)[1]
                self.show(target)
                t_start = time.perf_counter(); heavy = []
                while time.perf_counter() - t_start < 8.0:
                    p2 = cProfile.Profile(); t1 = time.perf_counter(); p2.enable()
                    self.update()
                    p2.disable(); d1 = time.perf_counter() - t1
                    if d1 > 0.05:
                        buf = io.StringIO()
                        pstats.Stats(p2, stream=buf).sort_stats("cumulative").print_stats(10)
                        heavy.append((time.perf_counter() - t_start, d1, buf.getvalue()))
                    else:
                        time.sleep(0.02)
                lines.append(f"{key}: watched 8 s after switching; heavy loop turns: {len(heavy)}")
                for at, d1, txt in heavy[:4]:
                    lines.append(f"   at +{at:.2f}s a loop turn took {d1:.2f}s:\n{txt}")
                continue
            if key == "@save":
                self.library.save("selftest entry", A=[[1, 2], [3, 4]]); LibraryPanel.refresh_all()
            elif key == "@delete":
                self.library.delete("selftest entry"); LibraryPanel.refresh_all()
            elif key == "@refresh":
                self.library.names(force=True)
            else:
                self.show(key)
            self.update()
            prof.disable()
            dt = time.perf_counter() - t0
            lines.append(f"{key}: {dt:.2f}s")
            if dt > 0.8:
                buf = io.StringIO()
                pstats.Stats(prof, stream=buf).sort_stats("cumulative").print_stats(14)
                lines.append(buf.getvalue())
        with open(log_path, "w") as f:
            f.write("\n".join(lines))
        try:
            os.remove(self.selftest_path)
        except OSError:
            pass
        self.destroy()

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(self.settings_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_settings(self, data):
        try:
            with open(self.settings_path, "w") as f:
                json.dump(data, f)
        except OSError:
            pass


def main():
    MatrixLab().mainloop()


if __name__ == "__main__":
    main()
