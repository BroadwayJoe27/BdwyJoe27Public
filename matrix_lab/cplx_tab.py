"""
cplx_tab.py -- the "Complex Eigen" module of MatrixLab.

A real 2x2 with complex eigenvalues a ± bi is a rotation-scaling in
disguise: A = P C P^-1 with C = [[a, -b], [b, a]] = |λ| x (rotation by
φ) and P = [Re v  Im v]. The text derives and checks this, then follows
x_j = A^j x0 in both coordinate systems. The figure shows the skewed
spiral on an ellipse (standard coordinates) beside the true spiral in
P-coordinates; Play reveals the points step by step.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure
from matplotlib import animation

from core import complex_eigen_text
import plots
from widgets import MatrixEditor, VectorEditor, LibraryPanel, fit_len

LIVE_DELAY_MS = 350

CPLX_PRESETS = {
    "Lay's example [[0.5,-0.6],[0.75,1.1]]  (|λ| ≈ 1.02)": ([[0.5, -0.6], [0.75, 1.1]], [1, 0], 12),
    "pure rotation by 90°: [[0,-1],[1,0]]": ([[0, -1], [1, 0]], [1, 0], 8),
    "rotate 45° and scale √2: [[1,-1],[1,1]]": ([[1, -1], [1, 1]], [1, 0], 8),
    "spiral in: [[0.8,-0.6],[0.6,0.8]] x 0.9": ([[0.72, -0.54], [0.54, 0.72]], [1, 0], 20),
    "skewed circle: [[1,-2],[1,-1]]  (|λ| = 1)": ([[1, -2], [1, -1]], [1, 0], 12),
    "hidden rotation: [[2,-5],[1,-2]]": ([[2, -5], [1, -2]], [1, 0], 8),
    "real eigenvalues (no rotation): [[2,1],[1,2]]": ([[2, 1], [1, 2]], [1, 0], 6),
}


class ComplexEigenTab(ttk.Frame):
    ACCEPTS = {"A": "matrix", "x": "vector"}

    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.anim = None
        self.d = None
        self.live_var = tk.BooleanVar(value=True)
        self.k_var = tk.IntVar(value=12)
        self.preset_var = tk.StringVar()
        self._build()
        A, x0, k = CPLX_PRESETS["Lay's example [[0.5,-0.6],[0.75,1.1]]  (|λ| ≈ 1.02)"]
        self.k_var.set(k)
        self.load_fields({"A": A, "x": x0})
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

        self.A = MatrixEditor(left, "A (2x2)", self.on_edit, rows=2, cols=2, lock_cols="2x2 only", max_dim=2)
        self.A.pack(fill=tk.X, pady=(8, 0))
        self.A.rows_spin.state(["disabled"])

        pre = ttk.Frame(left); pre.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pre, text="Examples:").pack(side=tk.LEFT)
        box = ttk.Combobox(pre, textvariable=self.preset_var, state="readonly", width=44, values=list(CPLX_PRESETS))
        box.pack(side=tk.LEFT, padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())

        xf = ttk.LabelFrame(left, text="Start vector and steps", padding=6)
        xf.pack(fill=tk.X, pady=(8, 0))
        self.x = VectorEditor(xf, "x0 =", self.on_edit, size=2)
        self.x.pack(anchor="w")
        kr = ttk.Frame(xf); kr.pack(anchor="w", pady=(6, 0))
        ttk.Label(kr, text="steps k:").pack(side=tk.LEFT)
        ttk.Spinbox(kr, from_=1, to=60, width=5, textvariable=self.k_var,
                    command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(4, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Play", command=self.play).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(act, text="Stop", command=self.stop_animation).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="A = P C P⁻¹, C = rotation-scaling", padding=4)
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
        item = CPLX_PRESETS.get(self.preset_var.get())
        if item is None:
            return
        A, x0, k = item
        self.k_var.set(k)
        self.A.set(A); self.x.set(x0)
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def get_fields(self):
        return {"A": self.A.get(), "x": self.x.get()}

    def load_fields(self, f):
        A = np.asarray(f["A"], dtype=float)
        if A.shape != (2, 2):
            raise ValueError("Complex Eigen needs a 2x2 matrix.")
        self.A.set(A)
        x = f.get("x")
        self.x.set(fit_len(x, 2) if x is not None else [1.0, 0.0])
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

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            A, x0 = self.A.get(), self.x.get()
            k = max(1, min(60, int(self.k_var.get())))
        except (ValueError, tk.TclError) as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        self.stop_animation()
        text, d = complex_eigen_text(A, x0, k)
        self.d = d
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith("COMPLEX EIGENVALUES OF"):
                tag = "heading"
            elif line.startswith(("CHARACTERISTIC", "WHAT A COMPLEX", "AN EIGENVECTOR", "THE FACTORIZATION", "READING C", "THE TRAJECTORY", "POWERS")):
                tag = "section"
            elif "COMPLEX CONJUGATE PAIR" in line or "rotation by" in line and "C = |λ|" in line:
                tag = "good"
            elif "REAL." in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {}
        if d.get("ok"):
            self.results = {"P = [Re v  Im v]": d["P"], "C (rotation-scaling)": d["C"], "Re v": d["Re"], "Im v": d["Im"],
                            f"x_{k}": d["traj"][-1]}
        plots.build_complex_eigen(self.fig, A, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def play(self):
        if not (self.d and self.d.get("ok")):
            return
        self.stop_animation()
        k = self.d["traj"].shape[0] - 1
        A = self.A.get()

        def frame(i):
            plots.build_complex_eigen(self.fig, A, self.d, upto=i)
            return []

        self.anim = animation.FuncAnimation(self.fig, frame, frames=k + 1, interval=350, blit=False, repeat=True)
        self.canvas.draw_idle()
        self.status.config(text="Playing: one step of A per frame, in both coordinate systems.")

    def stop_animation(self):
        if self.anim is not None:
            self.anim.event_source.stop()
            self.anim = None
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", initialfile="complex_eigen.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
