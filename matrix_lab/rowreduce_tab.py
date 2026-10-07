"""
rowreduce_tab.py -- the "Row Reduce" tab of MatrixLab.

Edit A (m x n) and watch Gauss-Jordan elimination run in exact fractions:
every elementary row operation with the matrix after it, the moment row
echelon form is reached, then reduced row echelon form, and finally the
pivots, rank, free variables and a basis for the null space. Ticking
"LU factorization" adds PA = LU: the downward pass without scaling, with
each multiplier written into L.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

from core import (DEFAULT_EXAMPLE, rref_text, rref_steps, null_space_from_rref,
                  lu_text, lu_steps, perm_matrix)
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

# A 3x4 with one free column: shows a swap, scalings, and a null vector.
ROWREDUCE_EXAMPLE = {"A": [[2, 4, -2, 2], [4, 9, -3, 8], [-2, -3, 7, 10]]}


class RowReduceTab(ttk.Frame):
    ACCEPTS = {"A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.lu_var = tk.BooleanVar(value=False)
        self._build()
        self.load_fields(ROWREDUCE_EXAMPLE)
        self.after(50, self._place_divider)
        self.bind("<Map>", lambda e: self._place_divider())   # tab shown

    # ------------------------------------------------------------------
    def _build(self):
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(self.paned, padding=8)
        right = ttk.Frame(self.paned, padding=8)
        self.paned.add(left, weight=0)
        self.paned.add(right, weight=1)

        self.lib = LibraryPanel(left, self.library, self.get_fields, self.load_fields)
        self.lib.pack(fill=tk.X)

        self.A = MatrixEditor(left, "A", self.on_edit, rows=3, cols=4)
        self.A.pack(fill=tk.X, pady=(8, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="LU factorization", variable=self.lu_var,
                        command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(12, 0))

        note = ttk.Label(left, foreground="gray", wraplength=520, justify=tk.LEFT, text=(
            "Arithmetic is exact: entries such as 0.5 are treated as 1/2.\n"
            "Forward phase: for each column, swap a nonzero entry into the pivot row, "
            "scale the pivot to 1, clear below it.  Backward phase: clear above each pivot.\n"
            "LU factorization: the forward phase again, but without scaling; each "
            "multiplier goes into L, giving PA = LU."))
        note.pack(fill=tk.X, pady=(10, 0))

        self.status = ttk.Label(left, text="", foreground="gray")
        self.status.pack(fill=tk.X, pady=(8, 0))

        res = ttk.LabelFrame(right, text="Row reduction, step by step", padding=4)
        res.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(res, font=("Menlo", 14), wrap="none")
        vsb = ttk.Scrollbar(res, command=self.text.yview)
        hsb = ttk.Scrollbar(res, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text.tag_configure("milestone", foreground="#b25a00", font=("Menlo", 14, "bold"))
        self.text.tag_configure("step", font=("Menlo", 14, "bold"))
        self.text.tag_configure("heading", foreground="#2a5db0", font=("Menlo", 14, "bold"))

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
        self.text.delete("1.0", tk.END)
        text = rref_text(A)
        if self.lu_var.get():
            text += "\n\n" + lu_text(A)
        for line in text.splitlines():
            if line.startswith("Step "):
                self.text.insert(tk.END, line + "\n", "step")
            elif "FORM reached" in line or line.startswith("Check: L U"):
                self.text.insert(tk.END, line + "\n", "milestone")
            elif line.startswith(("ROW REDUCTION OF", "READING OFF", "LU FACTORIZATION", "THE FACTORS")):
                self.text.insert(tk.END, line + "\n", "heading")
            else:
                self.text.insert(tk.END, line + "\n")
        R, piv, _ = rref_steps(A)
        _, basis = null_space_from_rref(R, piv, A.shape[1])
        self.results = {"RREF(A)": np.array([[float(q) for q in v] for v in R]), "rank": np.float64(len(piv))}
        if basis:
            self.results["null space basis (rows)"] = np.array([[float(q) for q in v] for v in basis])
        if self.lu_var.get():
            L, U, perm, _ = lu_steps(A)
            to_np = lambda M: np.array([[float(q) for q in row] for row in M])
            self.results["L (PA = LU)"] = to_np(L)
            self.results["U (PA = LU)"] = to_np(U)
            if perm != list(range(len(perm))):
                self.results["P (PA = LU)"] = to_np(perm_matrix(perm))
        self.status.config(text="")
