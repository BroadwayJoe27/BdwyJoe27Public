"""
subspaces_tab.py -- the "Subspaces" tab of MatrixLab.

Edit A (m x n) and see its four fundamental subspaces with exact bases:
row space and null space in R^n, column space and left null space in R^m,
the dimension counts r + (n - r) = n and r + (m - r) = m, and the
orthogonality between each pair. For m, n <= 3 the two spaces are drawn.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import subspaces_text
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

# Rank 2 in R^3 -> R^2: row space is a plane, null space a line.
SUBSPACES_EXAMPLE = {"A": [[1, 0, 1], [0, 1, 2]]}


class SubspacesTab(ttk.Frame):
    ACCEPTS = {"A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self._build()
        self.load_fields(SUBSPACES_EXAMPLE)
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

        self.A = MatrixEditor(left, "A", self.on_edit, rows=2, cols=3)
        self.A.pack(fill=tk.X, pady=(8, 0))
        self.dim_note = ttk.Label(left, text="", foreground="gray")
        self.dim_note.pack(fill=tk.X)

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="The four subspaces", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("space", font=bold)

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
        return {"A": self.A.get()}

    def load_fields(self, f):
        self.A.set(f["A"])
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
        self.A.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            A = self.A.get()
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        text, d = subspaces_text(A)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("THE FOUR", "IN THE DOMAIN", "IN THE CODOMAIN", "WHAT IT MEANS")):
                tag = "heading"
            elif line.startswith(("ROW SPACE", "NULL SPACE", "COLUMN SPACE", "LEFT NULL SPACE")):
                tag = "space"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        m, n = A.shape
        self.dim_note.config(text="" if plots.can_plot(A) else
                             f"Plots need m, n ≤ {plots.MAX_PLOT_DIM}; bases still shown.")
        self.results = {"rank": np.float64(d["rank"])}
        for key, label in (("row", "row space basis (rows)"), ("null", "null space basis (rows)"), ("col", "column space basis (rows)"), ("left", "left null space basis (rows)")):
            if d[key]:
                self.results[label] = np.array([[float(q) for q in v] for v in d[key]])
        plots.build_subspaces(self.fig, A, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="subspaces.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
