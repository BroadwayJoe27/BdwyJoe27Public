"""
det_tab.py -- the "Determinant · Inverse" tab of MatrixLab.

Edit a square A. The determinant is computed two ways (cofactor expansion
written out, and elimination to triangular form where only swaps change
the sign), then the inverse by Gauss-Jordan on [A | I] with a check, plus
the adjugate formula for 2x2 and 3x3. Singular matrices show the zero
row of RREF and a null vector as the witness. For n = 2 or 3 the unit
square or cube and its image are drawn.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import det_inverse_text
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

DET_EXAMPLE = {"A": [[2, 1, -1], [-3, -1, 2], [-2, 1, 2]]}


class DetTab(ttk.Frame):
    ACCEPTS = {"A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.steps_var = tk.BooleanVar(value=False)
        self._build()
        self.load_fields(DET_EXAMPLE)
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

        self.A = MatrixEditor(left, "A (square)", self.on_edit, rows=3, cols=3,
                              lock_cols="columns = rows")
        self.A.pack(fill=tk.X, pady=(8, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Show row operations", variable=self.steps_var,
                        command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Determinant and inverse", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("method", font=bold)
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
        return {"A": self.A.get()}

    def load_fields(self, f):
        A = f["A"]
        m, n = len(A), len(A[0])
        if m != n:                              # pad or crop to square
            k = max(m, n)
            A = [[A[i][j] if i < m and j < n else 0.0 for j in range(k)] for i in range(k)]
            self.status.config(text=f"Loaded {m}x{n} matrix padded to {k}x{k} with zeros.")
        self.A.set(A)
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
        text, d = det_inverse_text(A, show_steps=self.steps_var.get())
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if "INVERTIBLE" in line or line.endswith("= I  ✓"):
                tag = "good"
            elif "SINGULAR" in line or "NO inverse" in line:
                tag = "bad"
            elif line.startswith(("DETERMINANT OF", "INVERSE", "det A = ")):
                tag = "heading"
            elif line.startswith("METHOD"):
                tag = "method"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {"det A": np.float64(float(d["det"]))}
        if d["inverse"] is not None:
            self.results["A⁻¹"] = np.array([[float(q) for q in v] for v in d["inverse"]])
        plots.build_det(self.fig, A, d["det"])
        self.canvas.draw_idle()
        if not self.status.cget("text").startswith("Loaded"):
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="determinant.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
