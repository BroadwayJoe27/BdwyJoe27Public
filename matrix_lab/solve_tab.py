"""
solve_tab.py -- the "Solve Ax = b" tab of MatrixLab.

Edit A (m x n) and b in R^m (b's length follows A's row count). The
augmented matrix [A | b] is row-reduced in exact fractions; the result
pane says whether the system is consistent, gives the unique solution or
the general solution (particular + null space) with checks, and for an
inconsistent system works the least-squares solution from the normal
equations, showing the residual orthogonal to the column space. "Solve by LU" factors
a square invertible A as PA = LU and solves L y = Pb, U x = y instead.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

from core import solve_text, solve_summary, lu_solve_text
from widgets import MatrixEditor, VectorEditor, LibraryPanel, fit_len

LIVE_DELAY_MS = 350

# Unique solution x = (2, 3, -1); Random fill and the library give the rest.
SOLVE_EXAMPLE = {"A": [[2, 1, -1], [-3, -1, 2], [-2, 1, 2]], "b": [8, -11, -3]}


class SolveTab(ttk.Frame):
    ACCEPTS = {"A": "matrix", "b": "vector"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.steps_var = tk.BooleanVar(value=False)
        self.lu_var = tk.BooleanVar(value=False)
        self._build()
        self.load_fields(SOLVE_EXAMPLE)
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

        self.A = MatrixEditor(left, "A", self.on_A_change, rows=3, cols=3)
        self.A.pack(fill=tk.X, pady=(8, 0))

        vec = ttk.LabelFrame(left, text="Right-hand side", padding=6)
        vec.pack(fill=tk.X, pady=(8, 0))
        self.b = VectorEditor(vec, "b ∈ R^3", self.on_edit, size=3)
        self.b.pack(anchor="w")

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Solve", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Show row operations", variable=self.steps_var,
                        command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Solve by LU", variable=self.lu_var,
                        command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(12, 0))

        note = ttk.Label(left, foreground="gray", wraplength=520, justify=tk.LEFT, text=(
            "Three outcomes: a unique solution, a family of solutions (a particular "
            "solution plus the null space of A), or no solution, in which case the "
            "least-squares x̂ from the normal equations AᵀA x̂ = Aᵀb is worked instead.\n"
            "Try: make two rows of A proportional, then change b so the system breaks."))
        note.pack(fill=tk.X, pady=(10, 0))

        self.status = ttk.Label(left, text="", foreground="gray")
        self.status.pack(fill=tk.X, pady=(8, 0))

        res = ttk.LabelFrame(right, text="Solution", padding=4)
        res.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(res, font=("Menlo", 14), wrap="none")
        vsb = ttk.Scrollbar(res, command=self.text.yview)
        hsb = ttk.Scrollbar(res, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bold = ("Menlo", 14, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("milestone", foreground="#b25a00", font=bold)
        self.text.tag_configure("step", font=bold)
        self.text.tag_configure("verdict", foreground="#1a7f37", font=bold)
        self.text.tag_configure("bad", foreground="#c0392b", font=bold)

    def _place_divider(self):
        self.update_idletasks()
        if self.paned.sashpos(0) < 300:
            self.paned.sashpos(0, 560)

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        return {"A": self.A.get(), "b": self.b.get()}

    def load_fields(self, f):
        A = f["A"]
        m = len(A)
        self.A.set(A)
        b = f.get("b")
        if b is not None:
            self.b.set(fit_len(b, m), label=f"b ∈ R^{m}")
        else:
            self.b.resize(m, label=f"b ∈ R^{m}")
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_A_change(self):
        m = self.A.shape()[0]
        if len(self.b.cells) != m:
            self.b.resize(m, label=f"b ∈ R^{m}")
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
        self.A.random_fill(); self.b.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            A, b = self.A.get(), self.b.get()
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        self.text.delete("1.0", tk.END)
        text = None
        if self.lu_var.get():
            text, why = lu_solve_text(A, b, show_steps=self.steps_var.get())
            if text is None:
                text = ("LU NOT USED: " + why + "\nSolving by row reduction instead.\n\n"
                        + solve_text(A, b, show_steps=self.steps_var.get()))
        if text is None:
            text = solve_text(A, b, show_steps=self.steps_var.get())
        for line in text.splitlines():
            if line.startswith("Step "):
                tag = "step"
            elif "FORM reached" in line:
                tag = "milestone"
            elif line.startswith("Check: L U"):
                tag = "milestone"
            elif line.startswith(("SOLVE A x", "IS THERE", "THE SOLUTION", "LEAST SQUARES",
                                  "LU FACTORIZATION", "FORWARD SUBST", "BACK SUBST")):
                tag = "heading"
            elif line.startswith(("UNIQUE SOLUTION", "INFINITELY MANY")) or "CONSISTENT." in line and "INCONSISTENT" not in line:
                tag = "verdict"
            elif "INCONSISTENT" in line or line.startswith("LU NOT USED"):
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        summ = solve_summary(A, b)
        if summ["x"] is not None:
            self.results[summ["label"]] = summ["x"]
        if summ["null"] is not None:
            self.results["null space basis (rows)"] = summ["null"]
        if summ["x"] is not None:
            self.results["A x (fitted / reached b)"] = A @ summ["x"]
            self.results["residual b − A x"] = b - A @ summ["x"]
            self.results["|residual|"] = np.float64(np.linalg.norm(b - A @ summ["x"]))
        self.status.config(text="")
