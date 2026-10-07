"""
gs_tab.py -- the "Orthogonalize" tab of MatrixLab: Gram-Schmidt and QR.

Enter k vectors in R^d as rows. Each is orthogonalized against the ones
before it in exact fractions with every subtracted projection shown,
then normalized; the result is assembled into A = Q R (and the exact
A = U C before normalizing). Dependent vectors are dropped with a note.
For d <= 3 the originals (thin) and the orthogonalized set (bold) are
drawn with the removed projections dotted.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import gram_schmidt_text
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

GS_EXAMPLE = {"V": [[1, 1, 0], [1, 0, 1], [0, 1, 1]]}


class GramSchmidtTab(ttk.Frame):
    ACCEPTS = {"V": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self._build()
        self.load_fields(GS_EXAMPLE)
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

        self.V = MatrixEditor(left, "Vectors (one per row)", self.on_edit, rows=3, cols=3, max_dim=6)
        self.V.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(left, text="rows = number of vectors k,   columns = dimension d   (order matters: "
                  "v1 is kept as is)", foreground="gray", wraplength=520, justify=tk.LEFT).pack(fill=tk.X)

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Gram-Schmidt and QR", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("step", font=bold)
        self.text.tag_configure("bad", foreground="#c0392b", font=bold)

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

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        return {"V": self.V.get()}

    def load_fields(self, f):
        V = f.get("V")
        if V is None and "A" in f:
            V = f["A"]
        if V is None:
            raise KeyError("V or A")
        self.V.set(V)
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
        self.V.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            V = self.V.get()
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        text, d = gram_schmidt_text(V)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("GRAM-SCHMIDT ON", "NORMALIZE", "QR FACTORIZATION", "EXACT VERSION", "WHY BOTHER")):
                tag = "heading"
            elif line.startswith("STEP "):
                tag = "step"
            elif "dropped" in line or "dependent" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        kept = [u for u in d["us"] if u is not None]
        if kept:
            self.results["orthogonal vectors u_i (rows)"] = np.array([[float(q) for q in v] for v in kept])
            self.results["orthonormal vectors q_i (rows)"] = np.array(d["qs"], dtype=float)
        if "Q" in d:
            self.results["Q"] = d["Q"]; self.results["R"] = d["R"]
        plots.build_gram_schmidt(self.fig, V, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="gram_schmidt.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
