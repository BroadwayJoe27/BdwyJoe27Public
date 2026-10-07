"""
vectors_tab.py -- the "Vectors" tab of MatrixLab: dot product, angle,
projection, cross product, triple product.

Two vectors u and v in R^2 or R^3, plus an optional third vector w (3D).
The text works u . v, |u|, |v|, the angle, the projection of u onto v
with its perpendicular part, the cross product by the i-j-k determinant
with area and orthogonality checks, and with w the triple product as a
volume and the projection of w onto the plane of u and v. All of it is
drawn on the right.
"""

import os
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import vectors_text
import plots
from widgets import VectorEditor, LibraryPanel

LIVE_DELAY_MS = 350

VECTORS_EXAMPLE = {"u": [1, 2, 2], "v": [3, 0, 4], "w": [1, 1, 1]}


class VectorsTab(ttk.Frame):
    ACCEPTS = {"u": "vector", "v": "vector", "w": "vector"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.use_w = tk.BooleanVar(value=True)
        self.dim_var = tk.IntVar(value=3)
        self._build()
        self.load_fields(VECTORS_EXAMPLE)
        self.after(50, self._place_divider)
        self.bind("<Map>", lambda e: self._place_divider())   # tab shown

    # ------------------------------------------------------------------
    def _build(self):
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(self.paned, padding=8)
        right = ttk.Frame(self.paned)
        self.paned.add(left, weight=0)
        self.paned.add(right, weight=1)

        self.lib = LibraryPanel(left, self.library, self.get_fields, self.load_fields)
        self.lib.pack(fill=tk.X)

        box = ttk.LabelFrame(left, text="Vectors", padding=6)
        box.pack(fill=tk.X, pady=(8, 0))
        dims = ttk.Frame(box); dims.pack(anchor="w")
        ttk.Label(dims, text="dimension:").pack(side=tk.LEFT)
        ttk.Radiobutton(dims, text="R²", variable=self.dim_var, value=2, command=self.set_dim).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Radiobutton(dims, text="R³", variable=self.dim_var, value=3, command=self.set_dim).pack(side=tk.LEFT, padx=(6, 0))
        self.u = VectorEditor(box, "u =", self.on_edit, size=3); self.u.pack(anchor="w", pady=(6, 0))
        self.v = VectorEditor(box, "v =", self.on_edit, size=3); self.v.pack(anchor="w", pady=(2, 0))
        self.w_check = ttk.Checkbutton(box, text="third vector w (triple product, projection onto the plane of u, v)",
                                       variable=self.use_w, command=lambda: self.compute(quiet=True))
        self.w_check.pack(anchor="w", pady=(8, 0))
        self.w = VectorEditor(box, "w =", self.on_edit, size=3); self.w.pack(anchor="w", pady=(2, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Dot, projection, cross", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("section", font=bold)
        self.text.tag_configure("note", foreground="#1a7f37", font=bold)

        self.status = ttk.Label(left, text="", foreground="gray")
        self.status.pack(fill=tk.X, pady=(4, 0))

        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        NavigationToolbar2Tk(self.canvas, right).update()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _place_divider(self):
        self.update_idletasks()
        if self.paned.sashpos(0) < 300:
            self.paned.sashpos(0, 560)

    def set_dim(self):
        d = self.dim_var.get()
        for ed in (self.u, self.v, self.w):
            if len(ed.cells) != d:
                ed.resize(d)
        state = ["!disabled"] if d == 3 else ["disabled"]
        self.w_check.state(state)
        self.lib.mark_modified()
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        f = {"u": self.u.get(), "v": self.v.get()}
        if self.dim_var.get() == 3:
            f["w"] = self.w.get()
        return f

    def load_fields(self, f):
        if "u" not in f or "v" not in f:
            raise KeyError("u and v")
        u, v = list(f["u"]), list(f["v"])
        d = 3 if max(len(u), len(v)) >= 3 else 2
        pad = lambda x: (x + [0.0] * d)[:d]
        self.dim_var.set(d)
        self.u.set(pad(u)); self.v.set(pad(v))
        w = f.get("w")
        self.w.set(pad(list(w)) if w is not None else [0.0] * d)
        self.w_check.state(["!disabled"] if d == 3 else ["disabled"])
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_edit(self):
        self.lib.mark_modified()
        if self._live_job is not None:
            self.after_cancel(self._live_job)
            self._live_job = None
        if self.live_var.get():
            self._live_job = self.after(LIVE_DELAY_MS, self._live_compute)

    def _live_compute(self):
        self._live_job = None
        self.compute(quiet=True)

    def random_fill(self):
        for ed in (self.u, self.v, self.w):
            ed.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            u, v = self.u.get(), self.v.get()
            w = self.w.get() if (self.use_w.get() and self.dim_var.get() == 3) else None
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        text, d = vectors_text(u, v, w)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("TWO VECTORS", "A THIRD VECTOR")):
                tag = "heading"
            elif line.startswith(("DOT PRODUCT", "PROJECTION", "CROSS PRODUCT", "SIGNED AREA", "TRIPLE PRODUCT")):
                tag = "section"
            elif "ORTHOGONAL" in line or "PARALLEL" in line or "coplanar" in line or "independent and span" in line:
                tag = "note"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        for key, label in (("cross", "u × v"), ("proj", "proj of u onto v"), ("perp", "perpendicular part of u"), ("w_plane", "proj of w onto plane of u, v")):
            if key in d:
                self.results[label] = np.array(d[key], dtype=float)
        self.results["u · v"] = np.float64(u @ v)
        self.results["|u|"] = np.float64(np.linalg.norm(u)); self.results["|v|"] = np.float64(np.linalg.norm(v))
        if "angle" in d:
            self.results["angle θ (degrees)"] = np.float64(d["angle"])
        if "cross" in d:
            self.results["|u × v| (area)"] = np.float64(np.linalg.norm(d["cross"]))
        if w is not None and "cross" in d:
            self.results["triple product w · (u × v) (volume)"] = np.float64(np.asarray(w) @ np.array(d["cross"]))
            self.results["matrix with rows u, v, w"] = np.vstack([u, v, w]).astype(float)
        elif len(u) == len(v):
            self.results["matrix with rows u, v"] = np.vstack([u, v]).astype(float)
        plots.build_vectors(self.fig, u, v, w, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="vectors.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
