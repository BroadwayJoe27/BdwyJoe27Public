"""
multiply_tab.py -- the "Multiply" tab of MatrixLab.

Edit A (m x n) and B (n x p); B's row count follows A's column count so
AB is always defined. The result pane shows AB and BA in matrix form,
with each entry expanded as (row) . (column), and says when BA is
undefined or when the two products differ.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

from core import DEFAULT_EXAMPLE, multiply_text, fmt
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350


class MultiplyTab(ttk.Frame):
    ACCEPTS = {"A": "matrix", "B": "matrix", "k": "scalar"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.entries_var = tk.BooleanVar(value=True)
        self.k_var = tk.StringVar(value="1")
        self._build()
        self.load_fields(DEFAULT_EXAMPLE)
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

        self.A = MatrixEditor(left, "A", self.on_A_change, rows=2, cols=3)
        self.A.pack(fill=tk.X, pady=(8, 0))
        self.B = MatrixEditor(left, "B", self.on_edit, rows=3, cols=2,
                              lock_rows="rows = columns of A")
        self.B.pack(fill=tk.X, pady=(8, 0))

        kr = ttk.LabelFrame(left, text="Scalar multiplication", padding=6)
        kr.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(kr, text="k =").pack(side=tk.LEFT)
        ke = ttk.Entry(kr, textvariable=self.k_var, width=8, justify="center")
        ke.pack(side=tk.LEFT, padx=(4, 8))
        ke.bind("<KeyRelease>", lambda e: self.on_edit())
        ttk.Label(kr, text="shows kA, kB and (kA)B = k(AB) when k ≠ 1", foreground="gray").pack(side=tk.LEFT)

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Show entry arithmetic", variable=self.entries_var,
                        command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(12, 0))

        self.status = ttk.Label(left, text="", foreground="gray")
        self.status.pack(fill=tk.X, pady=(8, 0))

        res = ttk.LabelFrame(right, text="AB and BA", padding=4)
        res.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(res, font=("Menlo", 14), wrap="none")
        vsb = ttk.Scrollbar(res, command=self.text.yview)
        hsb = ttk.Scrollbar(res, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _place_divider(self):
        self.update_idletasks()
        if self.paned.sashpos(0) < 300:
            self.paned.sashpos(0, 560)

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        return {"A": self.A.get(), "B": self.B.get(), "k": self._k()}

    def _k(self):
        from core import parse_number
        try:
            return parse_number(self.k_var.get())
        except ValueError:
            raise ValueError(f"Can't read '{self.k_var.get()}' as the scalar k.")

    def load_fields(self, f):
        A = f["A"]
        n = len(A[0])
        self.A.set(A)
        if f.get("k") is not None:
            kv = np.asarray(f["k"], dtype=float).ravel()
            self.k_var.set(fmt(float(kv[0])))
        B = f.get("B")
        if B is not None:
            self.B.set(B)
            if len(B) != n:                # a B of another size: A's columns follow B's rows
                self.A.resize(cols=len(B))
        else:
            self.B.resize(rows=n)          # keep current B, fix its rows
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_A_change(self):
        n = self.A.shape()[1]
        if self.B.shape()[0] != n:
            self.B.resize(rows=n)          # fires on_edit
        else:
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
        self.A.random_fill(); self.B.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            A, B, k = self.A.get(), self.B.get(), self._k()
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, multiply_text(A, B, show_entries=self.entries_var.get(), k=k))
        self.results = {"AB": A @ B, "Aᵀ": A.T, "Bᵀ": B.T}
        if k != 1:
            self.results[f"k A  (k = {fmt(k)})"] = k * A
            self.results[f"k B  (k = {fmt(k)})"] = k * B
        if B.shape[1] == A.shape[0]:
            self.results["BA"] = B @ A
        self.status.config(text="")
