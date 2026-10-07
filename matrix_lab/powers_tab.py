"""
powers_tab.py -- the "Powers · Markov" tab of MatrixLab.

A square A, a start vector x0 and a number of steps k. The text shows
A^2, A^3, ..., A^k, the sequence x_j = A^j x0, the eigenvalue explanation
of its long-run behaviour (A^j = P D^j P^-1, dominant eigenvalue,
direction settling on its eigenvector, spirals for complex pairs), and
for a column-stochastic A the Markov reading with its steady state. The
figure shows the trajectory in state space (n = 2, 3) and every
component against j.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import powers_text
import plots
from widgets import MatrixEditor, VectorEditor, LibraryPanel, fit_len

LIVE_DELAY_MS = 350

_c, _s = 0.9 * np.cos(np.radians(30)), 0.9 * np.sin(np.radians(30))
POWERS_PRESETS = {
    "Markov: weather (sunny/rainy), columns sum to 1": ([[0.9, 0.5], [0.1, 0.5]], [1, 0], 12),
    "Markov: 3 states (rental cars between cities)": ([[0.8, 0.1, 0.2], [0.1, 0.7, 0.3], [0.1, 0.2, 0.5]], [1, 0, 0], 15),
    "Markov: absorbing state": ([[1, 0.3], [0, 0.7]], [0, 1], 12),
    "Fibonacci: [[1,1],[1,0]] from (1, 0)": ([[1, 1], [1, 0]], [1, 0], 10),
    "spiral in: rotation by 30° scaled by 0.9": ([[_c, -_s], [_s, _c]], [1, 0], 24),
    "growth vs decay: diag(1.5, 0.6)": ([[1.5, 0], [0, 0.6]], [1, 1], 10),
    "shear: [[1,1],[0,1]] (defective, linear growth)": ([[1, 1], [0, 1]], [1, 1], 8),
    "reflection: [[0,1],[1,0]] (oscillates)": ([[0, 1], [1, 0]], [2, 1], 6),
    "3D: rotation about z scaled by 0.95": ([[0.95 * np.cos(0.5), -0.95 * np.sin(0.5), 0], [0.95 * np.sin(0.5), 0.95 * np.cos(0.5), 0], [0, 0, 0.8]], [1, 0, 1], 30),
}


class PowersTab(ttk.Frame):
    ACCEPTS = {"A": "matrix", "x": "vector"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.k_var = tk.IntVar(value=12)
        self.preset_var = tk.StringVar()
        self._build()
        A, x0, k = POWERS_PRESETS["Markov: weather (sunny/rainy), columns sum to 1"]
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

        self.A = MatrixEditor(left, "A (square)", self.on_A_change, rows=2, cols=2,
                              lock_cols="columns = rows", max_dim=6)
        self.A.pack(fill=tk.X, pady=(8, 0))

        pre = ttk.Frame(left); pre.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pre, text="Examples:").pack(side=tk.LEFT)
        box = ttk.Combobox(pre, textvariable=self.preset_var, state="readonly", width=44, values=list(POWERS_PRESETS))
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
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Powers, sequence, long-run behaviour", padding=4)
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
        item = POWERS_PRESETS.get(self.preset_var.get())
        if item is None:
            return
        A, x0, k = item
        self.k_var.set(k)
        self.A.set(np.round(np.array(A, dtype=float), 6))
        self.x.set(x0)
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        return {"A": self.A.get(), "x": self.x.get()}

    def load_fields(self, f):
        A = np.asarray(f["A"], dtype=float)
        m, n = A.shape
        if m != n:
            kk = min(6, max(m, n))
            B = np.zeros((kk, kk)); B[:min(m, kk), :min(n, kk)] = A[:kk, :kk]
            A = B
            self.status.config(text=f"Loaded {m}x{n} matrix padded to {kk}x{kk} with zeros.")
        self.A.set(A)
        n = A.shape[0]
        x = f.get("x")
        self.x.set(fit_len(x, n) if x is not None else [1.0] + [0.0] * (n - 1))
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_A_change(self):
        n = self.A.shape()[0]
        if len(self.x.cells) != n:
            self.x.resize(n)
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
        self.A.random_fill(); self.x.random_fill()
        self.lib.mark_modified()
        self.compute()

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
        text, d = powers_text(A, x0, k)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("POWERS OF A", "MARKOV CHAIN", "WHY IT BEHAVES")):
                tag = "heading"
            elif line.startswith(("THE POWERS", "THE SEQUENCE", "Steady state")):
                tag = "section"
            elif "REGULAR" in line or "Dominant eigenvalue" in line or "stochastic matrix" in line:
                tag = "good"
            elif "blows up" in line or "not regular" in line or "defective" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {f"A^{k}": np.linalg.matrix_power(A, k), f"x_{k}": d["traj"][-1]}
        if "steady" in d:
            self.results["steady state"] = d["steady"]
        plots.build_powers(self.fig, A, d)
        self.canvas.draw_idle()
        if not self.status.cget("text").startswith("Loaded"):
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="powers.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
