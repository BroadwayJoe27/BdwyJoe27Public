"""
span_tab.py -- the "Span" tab of MatrixLab.

Enter k vectors in R^d as the ROWS of a grid (one vector per row) and an
optional target w. The tab puts the vectors as columns of A, row-reduces,
and reports: independent or the exact dependence relations, a basis and
dimension for the span, and whether w is in the span with the
combination that produces it. For d <= 3 the vectors, the span, and w
are drawn.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import span_text
import plots
from widgets import MatrixEditor, VectorEditor, LibraryPanel, fit_len

LIVE_DELAY_MS = 350

# Three vectors in R^3, the third the sum of the first two; w in the plane.
SPAN_EXAMPLE = {"V": [[1, 0, 1], [0, 1, 2], [1, 1, 3]], "w": [2, 1, 4]}


class SpanTab(ttk.Frame):
    ACCEPTS = {"V": "matrix", "w": "vector"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.use_w = tk.BooleanVar(value=True)
        self._build()
        self.load_fields(SPAN_EXAMPLE)
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

        self.V = MatrixEditor(left, "Vectors (one per row)", self.on_V_change, rows=3, cols=3)
        self.V.pack(fill=tk.X, pady=(8, 0))
        self.dim_note = ttk.Label(left, text="rows = number of vectors k,   columns = dimension d",
                                  foreground="gray")
        self.dim_note.pack(fill=tk.X)

        wf = ttk.LabelFrame(left, text="Target vector", padding=6)
        wf.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(wf, text="Test whether w is in the span", variable=self.use_w,
                        command=lambda: self.compute(quiet=True)).pack(anchor="w")
        self.w = VectorEditor(wf, "w ∈ R^3", self.on_edit, size=3)
        self.w.pack(anchor="w", pady=(4, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Span and independence", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("good", foreground="#1a7f37", font=bold)
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
        return {"V": self.V.get(), "w": self.w.get()}

    def load_fields(self, f):
        V = f.get("V")
        if V is None and "A" in f:          # a plain matrix: use its rows as vectors
            V = f["A"]
        if V is None:
            raise KeyError("V (vectors as rows) or A")
        self.V.set(V)
        d = len(V[0])
        w = f.get("w")
        if w is not None:
            self.w.set(fit_len(w, d), label=f"w ∈ R^{d}")
        else:
            self.w.resize(d, label=f"w ∈ R^{d}")
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_V_change(self):
        d = self.V.shape()[1]
        if len(self.w.cells) != d:
            self.w.resize(d, label=f"w ∈ R^{d}")
        self.on_edit()

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
        self.V.random_fill(); self.w.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            V = self.V.get()
            w = self.w.get() if self.use_w.get() else None
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        text, d = span_text(V, w)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("SPAN AND", "LINEARLY", "THE SPAN", "IS w")):
                tag = "heading"
            elif "INDEPENDENT." in line or line.startswith("YES.") or "ALL of R" in line:
                tag = "good"
            elif "DEPENDENT." in line or "NOT in the span" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        if d["pivot"]:
            self.results["basis of the span (rows)"] = np.asarray(V, dtype=float)[d["pivot"]]
        plots.build_span(self.fig, V, w, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="span.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
