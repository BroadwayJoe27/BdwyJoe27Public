"""
svd_tab.py -- the "SVD" tab of MatrixLab.

Any m x n A. The text derives A = U Σ V^T from the eigen-decomposition
of A^T A (exact where possible), checks A v_i = σ_i u_i and U Σ V^T = A,
and reads off rank, column/null space bases, the ellipse/ellipsoid
picture, condition number, Frobenius norm, and the best rank-1
approximation. For square 2x2 / 3x3 the figure shows the four stages:
unit shape, after V^T, after Σ V^T, after U Σ V^T = A. Other shapes up
to 3x3 get a domain/codomain pair.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import svd_text
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

SVD_PRESETS = {
    "2x2: [[3,0],[4,5]]  (σ = 3√5, √5)": [[3, 0], [4, 5]],
    "2x2 symmetric: [[2,1],[1,2]]  (σ = |λ|)": [[2, 1], [1, 2]],
    "2x2 shear: [[1,1],[0,1]]": [[1, 1], [0, 1]],
    "2x2 rotation 45° (σ = 1, 1)": [[np.cos(np.pi / 4), -np.sin(np.pi / 4)], [np.sin(np.pi / 4), np.cos(np.pi / 4)]],
    "2x2 rank 1: [[1,2],[2,4]]": [[1, 2], [2, 4]],
    "2x2 nearly singular: [[1,1],[1,1.01]]": [[1, 1], [1, 1.01]],
    "3x3: stretch + twist": [[2, 0, 0], [0, 1, 1], [0, -1, 1]],
    "2x3 (wide): [[1,0,1],[0,1,2]]": [[1, 0, 1], [0, 1, 2]],
    "3x2 (tall): [[1,1],[1,2],[1,3]]": [[1, 1], [1, 2], [1, 3]],
}


class SvdTab(ttk.Frame):
    ACCEPTS = {"A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar()
        self._build()
        self.load_fields({"A": [[3, 0], [4, 5]]})
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

        self.A = MatrixEditor(left, "A (any shape)", self.on_edit, rows=2, cols=2, max_dim=6)
        self.A.pack(fill=tk.X, pady=(8, 0))

        pre = ttk.Frame(left); pre.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pre, text="Examples:").pack(side=tk.LEFT)
        box = ttk.Combobox(pre, textvariable=self.preset_var, state="readonly", width=40, values=list(SVD_PRESETS))
        box.pack(side=tk.LEFT, padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="A = U Σ Vᵀ", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("section", font=bold)
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

    def apply_preset(self):
        A = SVD_PRESETS.get(self.preset_var.get())
        if A is None:
            return
        self.A.set(np.round(np.array(A, dtype=float), 6))
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def get_fields(self):
        return {"A": self.A.get()}

    def load_fields(self, f):
        self.A.set(f["A"])
        self.compute(quiet=True)

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
        text, d = svd_text(A)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("SINGULAR VALUE", "WHAT THE SVD")):
                tag = "heading"
            elif line.startswith(("HOW TO FIND IT", "CHECKS", "LOW-RANK", "THE PICTURE")):
                tag = "section"
            elif "nearly singular" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        S = np.zeros(A.shape); S[:len(d["s"]), :len(d["s"])] = np.diag(d["s"])
        self.results = {"U": d["U"], "Σ": S, "Vᵀ": d["Vt"], "V": d["Vt"].T, "singular values σ": d["s"],
                        "rank": np.float64(d["r"])}
        if d["r"] and d["s"][d["r"] - 1] > 0:
            self.results["condition number σ1/σr"] = np.float64(d["s"][0] / d["s"][d["r"] - 1])
        if d["r"] >= 1:
            self.results["A₁ (rank-1 approximation)"] = d["s"][0] * np.outer(d["U"][:, 0], d["Vt"][0])
        plots.build_svd(self.fig, A, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="svd.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
