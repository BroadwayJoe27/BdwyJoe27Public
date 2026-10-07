"""
eigen_tab.py -- the "Eigen" tab of MatrixLab.

Square A. The characteristic polynomial det(λI - A) is built exactly,
rational eigenvalues are found exactly (rational root test) and the rest
numerically; for each real eigenvalue (A - λI) v = 0 is solved with the
reduction shown and A v = λ v checked; multiplicities decide whether A
diagonalizes as P D P^-1. For 2x2 / 3x3 the eigen-directions are drawn,
and for 2x2 a Play button sweeps a unit vector x around the circle next
to A x so the eigenvectors appear as the moments they line up.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure
from matplotlib import animation

from core import eigen_text
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

EIGEN_PRESETS = {
    "symmetric 2x2 (real, orthogonal eigenvectors)": [[2, 1], [1, 2]],
    "shear 2x2 (defective: one eigenvector)": [[1, 1], [0, 1]],
    "rotation 2x2 (complex eigenvalues)": [[0, -1], [1, 0]],
    "reflection 2x2 (λ = 1 and -1)": [[0, 1], [1, 0]],
    "projection 2x2 (λ = 1 and 0)": [[0.5, 0.5], [0.5, 0.5]],
    "stretch 2x2 with irrational eigenvalues": [[1, 2], [3, 4]],
    "diagonal 3x3": [[2, 0, 0], [0, -1, 0], [0, 0, 3]],
    "symmetric 3x3": [[2, 0, 0], [0, 3, 4], [0, 4, 9]],
    "general 3x3 (integer eigenvalues)": [[4, 1, 2], [0, 2, 0], [1, 1, 3]],
    "rotation 3x3 about z (one real eigenvector)": [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
}


class EigenTab(ttk.Frame):
    ACCEPTS = {"A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.anim = None
        self.sweep = None
        self.live_var = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar()
        self._build()
        self.load_fields({"A": EIGEN_PRESETS["symmetric 2x2 (real, orthogonal eigenvectors)"]})
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

        self.A = MatrixEditor(left, "A (square)", self.on_edit, rows=2, cols=2,
                              lock_cols="columns = rows", max_dim=6)
        self.A.pack(fill=tk.X, pady=(8, 0))

        pre = ttk.Frame(left); pre.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(pre, text="Examples:").pack(side=tk.LEFT)
        box = ttk.Combobox(pre, textvariable=self.preset_var, state="readonly", width=40,
                           values=list(EIGEN_PRESETS))
        box.pack(side=tk.LEFT, padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Play sweep (2x2)", command=self.play).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(act, text="Stop", command=self.stop_animation).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Eigenvalues and eigenvectors", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("section", font=bold)
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

    def apply_preset(self):
        A = EIGEN_PRESETS.get(self.preset_var.get())
        if A is None:
            return
        self.A.set(A)
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        return {"A": self.A.get()}

    def load_fields(self, f):
        A = np.asarray(f["A"], dtype=float)
        m, n = A.shape
        if m != n:
            k = min(6, max(m, n))
            B = np.zeros((k, k)); B[:min(m, k), :min(n, k)] = A[:k, :k]
            A = B
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
        self.stop_animation()
        text, d = eigen_text(A)
        self.d = d
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("EIGENVALUES AND", "EIGENVECTORS FOR", "DIAGONALIZATION")):
                tag = "heading"
            elif line.startswith(("CHARACTERISTIC", "EIGENVALUES  (")):
                tag = "section"
            elif "DEFECTIVE" in line or "NOT diagonalizable" in line or "Not diagonalizable" in line:
                tag = "bad"
            elif line.startswith(("A has", "A is SYMMETRIC")) or line.strip().startswith("λ = "):
                tag = "good"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        vecs = [v for e in d["eigs"] if e["real"] for v in e["vectors"]]
        lams = [float(e["value"]) for e in d["eigs"] if e["real"] for _ in e["vectors"]]
        if vecs:
            self.results["eigenvectors (rows)"] = np.array([[float(q) for q in v] for v in vecs])
        real_vals = [float(e["value"]) for e in d["eigs"] if e["real"] for _ in range(e["alg"])]
        if real_vals:
            self.results["eigenvalues (real, with multiplicity)"] = np.array(real_vals)
        self.results["trace A"] = np.float64(float(d["trace"])); self.results["det A"] = np.float64(float(d["det"]))
        if d["diagonalizable"]:
            self.results["P (eigenvectors as columns)"] = np.array([[float(q) for q in v] for v in vecs]).T
            self.results["D (eigenvalues)"] = np.diag(lams)
        plots.build_eigen(self.fig, A, d)
        self.canvas.draw_idle()
        if not self.status.cget("text").startswith("Loaded"):
            self.status.config(text="")

    def play(self):
        try:
            A = self.A.get()
        except ValueError:
            return
        if A.shape[0] != 2:
            messagebox.showinfo("2x2 only", "The sweep animation is for 2x2 matrices.")
            return
        self.stop_animation()
        self.sweep = plots.EigenSweep(self.fig, A, self.d)
        self.anim = animation.FuncAnimation(self.fig, self.sweep.update, frames=len(self.sweep.theta),
                                            interval=40, blit=False, repeat=True)
        self.canvas.draw_idle()
        self.status.config(text="Sweeping x around the unit circle. Eigenvectors: where x and A x line up.")

    def stop_animation(self):
        if self.anim is not None:
            self.anim.event_source.stop()
            self.anim = None
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="eigen.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
