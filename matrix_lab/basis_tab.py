"""
basis_tab.py -- the "Basis" tab of MatrixLab: change of basis.

A basis of R^n as rows, a vector x, and optionally a matrix A. The text
checks det P, finds [x]_B by reducing [P | x], shows P and P^-1 and what
each converts, expresses A in the new basis as P^-1 A P with a check on
x, and notices when that is diagonal (an eigenbasis). A button fills the
basis with the eigenvectors of A when they exist. For n = 2, 3 the basis
grid, the basis arrows, and x as a path of basis steps are drawn.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import basis_text, eigen_analysis
import plots
from widgets import MatrixEditor, VectorEditor, LibraryPanel, fit_len

LIVE_DELAY_MS = 350

BASIS_EXAMPLE = {"V": [[1, 1], [-1, 1]], "x": [3, 1], "A": [[2, 1], [1, 2]]}
BASIS_PRESETS = {
    "2D: rotated 45° (1,1), (-1,1)": [[1, 1], [-1, 1]],
    "2D: skewed (2,1), (1,2)": [[2, 1], [1, 2]],
    "2D: standard e1, e2": [[1, 0], [0, 1]],
    "2D: scaled 2e1, 3e2": [[2, 0], [0, 3]],
    "3D: staircase (1,0,0), (1,1,0), (1,1,1)": [[1, 0, 0], [1, 1, 0], [1, 1, 1]],
    "3D: standard": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
}


class BasisTab(ttk.Frame):
    ACCEPTS = {"V": "matrix", "x": "vector", "A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.use_A = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar()
        self._build()
        self.load_fields(BASIS_EXAMPLE)
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

        self.B = MatrixEditor(left, "Basis vectors (one per row)", self.on_B_change, rows=2, cols=2,
                              lock_cols="n vectors in R^n", max_dim=4)
        self.B.pack(fill=tk.X, pady=(8, 0))
        pre = ttk.Frame(left); pre.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pre, text="Presets:").pack(side=tk.LEFT)
        box = ttk.Combobox(pre, textvariable=self.preset_var, state="readonly", width=34, values=list(BASIS_PRESETS))
        box.pack(side=tk.LEFT, padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())
        ttk.Button(pre, text="Use eigenvectors of A", command=self.use_eigenbasis).pack(side=tk.LEFT, padx=(8, 0))

        xf = ttk.LabelFrame(left, text="Vector to convert", padding=6)
        xf.pack(fill=tk.X, pady=(8, 0))
        self.x = VectorEditor(xf, "x =", self.on_edit, size=2)
        self.x.pack(anchor="w")

        self.A = MatrixEditor(left, "A (optional: express it in the new basis)", self.on_edit,
                              rows=2, cols=2, lock_cols="n x n")
        self.A.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(self.A, text="include A", variable=self.use_A,
                        command=lambda: self.compute(quiet=True)).pack(anchor="w")

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Change of basis", padding=4)
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
    def _sync_sizes(self):
        n = self.B.shape()[0]
        if len(self.x.cells) != n:
            self.x.resize(n)
        if self.A.shape()[0] != n:
            self.A.resize(rows=n)

    def apply_preset(self):
        B = BASIS_PRESETS.get(self.preset_var.get())
        if B is None:
            return
        self.B.set(B)
        self._sync_sizes()
        self.lib.mark_modified()
        self.compute()

    def use_eigenbasis(self):
        try:
            A = self.A.get()
        except ValueError as err:
            messagebox.showerror("Bad entry", str(err)); return
        d = eigen_analysis(A)
        vecs = [v for e in d["eigs"] if e["real"] for v in e["vectors"]]
        if len(vecs) < A.shape[0]:
            messagebox.showinfo("No eigenbasis",
                                "A does not have enough real eigenvectors to form a basis "
                                "(complex eigenvalues or a defective matrix).")
            return
        B = [[float(q) for q in v] for v in vecs]
        self.B.set(np.round(np.array(B), 6))
        self.use_A.set(True)
        self.lib.mark_modified()
        self.compute()
        self.status.config(text="Basis = eigenvectors of A, so [A]_B should come out diagonal.")

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        f = {"V": self.B.get(), "x": self.x.get()}
        if self.use_A.get():
            f["A"] = self.A.get()
        return f

    def load_fields(self, f):
        V = f.get("V")
        if V is None and "A" in f and len(f["A"]) == len(f["A"][0]):
            V = f["A"]                    # a square matrix's rows as the basis
        if V is None:
            raise KeyError("V (basis vectors)")
        n = len(V)
        self.B.set(V)
        x = f.get("x")
        self.x.set(fit_len(x, n) if x is not None else [1.0] * n)
        A = f.get("A")
        if A is not None and len(A) == n and len(A[0]) == n:
            self.A.set(A)
        else:
            self.A.set(np.eye(n))
        self._sync_sizes()
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_B_change(self):
        self._sync_sizes()
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
        self.B.random_fill(); self.x.random_fill(); self.A.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            B, x = self.B.get(), self.x.get()
            A = self.A.get() if self.use_A.get() else None
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        text, d = basis_text(B, x, A)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("CHANGE OF BASIS", "COORDINATES OF", "A MATRIX IN")):
                tag = "heading"
            elif "form a BASIS" in line or "DIAGONAL!" in line:
                tag = "good"
            elif "NOT a basis" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        if d.get("ok"):
            self.results["P (basis as columns)"] = np.array([[float(q) for q in v] for v in d["P"]])
            self.results["P⁻¹"] = np.array([[float(q) for q in v] for v in d["Pinv"]])
            self.results["[x]_B"] = np.array(d["coords"], dtype=float)
            if "AB" in d:
                self.results["[A]_B = P⁻¹ A P"] = np.array(d["AB"], dtype=float)
        plots.build_basis(self.fig, B, x, d)
        self.canvas.draw_idle()
        if not self.status.cget("text").startswith("Basis = "):
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="basis.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
