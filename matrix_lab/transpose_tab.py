"""
transpose_tab.py -- the "Transpose · Dot" tab of MatrixLab.

Edit A (m x n), x in R^n and y in R^m; see  (A x) . y = x . (A^T y)
worked step by step, the two-panel figure, and the sweeping animation.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure
from matplotlib import animation

from core import DEFAULT_EXAMPLE, steps_text
import plots
from widgets import MatrixEditor, VectorEditor, LibraryPanel, fit_len

LIVE_DELAY_MS = 350


class TransposeDotTab(ttk.Frame):
    ACCEPTS = {"A": "matrix", "x": "vector", "y": "vector"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self.anim = None
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self._build()
        self.load_fields(DEFAULT_EXAMPLE)
        self.compute()
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

        self.A = MatrixEditor(left, "A", self.on_A_change, rows=2, cols=3)
        self.A.pack(fill=tk.X, pady=(8, 0))
        self.dim_note = ttk.Label(left, text="", foreground="gray")
        self.dim_note.pack(fill=tk.X)

        vec = ttk.LabelFrame(left, text="Vectors", padding=6)
        vec.pack(fill=tk.X, pady=(8, 0))
        self.x = VectorEditor(vec, "x ∈ R^3", self.on_edit, size=3)
        self.x.pack(anchor="w")
        self.y = VectorEditor(vec, "y ∈ R^2", self.on_edit, size=2)
        self.y.pack(anchor="w", pady=(2, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Animate", command=self.animate).pack(side=tk.LEFT, padx=4)
        ttk.Button(act, text="Stop", command=self.stop_animation).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))

        txt = ttk.LabelFrame(left, text="Step by step", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)

        self.status = ttk.Label(left, text="", foreground="gray")
        self.status.pack(fill=tk.X, pady=(4, 0))

        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        NavigationToolbar2Tk(self.canvas, right).update()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _place_divider(self):
        # ttk.PanedWindow can start with the divider at x=0 on macOS,
        # hiding the whole control column.
        self.update_idletasks()
        if self.paned.sashpos(0) < 300:
            self.paned.sashpos(0, 560)

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        A, x, y = self.read_inputs()
        return {"A": A, "x": x, "y": y}

    def load_fields(self, f):
        A = f["A"]
        m, n = len(A), len(A[0])
        self.A.set(A)
        x = fit_len(f["x"], n) if f.get("x") is not None else [0.0] * n
        y = fit_len(f["y"], m) if f.get("y") is not None else [0.0] * m
        self.x.set(x, label=f"x ∈ R^{n}")
        self.y.set(y, label=f"y ∈ R^{m}")
        self._update_dim_note()
        self.compute(quiet=True)

    def _update_dim_note(self):
        m, n = self.A.shape()
        self.dim_note.config(text="" if plots.can_plot(np.zeros((m, n))) else
                             f"Plots need m, n ≤ {plots.MAX_PLOT_DIM}; arithmetic still shown.")

    def read_inputs(self):
        return self.A.get(), self.x.get(), self.y.get()

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_A_change(self):
        m, n = self.A.shape()
        if len(self.x.cells) != n:
            self.x.resize(n, label=f"x ∈ R^{n}")
        if len(self.y.cells) != m:
            self.y.resize(m, label=f"y ∈ R^{m}")
        self._update_dim_note()
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
        self.A.random_fill(); self.x.random_fill(); self.y.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    # compute / animate / save
    # ------------------------------------------------------------------
    def _inputs(self, quiet):
        try:
            return self.read_inputs()
        except ValueError as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return None

    def compute(self, quiet=False):
        vals = self._inputs(quiet)
        if vals is None:
            return
        A, x, y = vals
        self.stop_animation()
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, steps_text(A, x, y))
        self.results = {"Aᵀ": A.T, "A x": A @ x, "Aᵀ y": A.T @ y}
        plots.build_static(self.fig, A, x, y)
        self.canvas.draw_idle()
        self.status.config(text="")

    def animate(self):
        vals = self._inputs(False)
        if vals is None:
            return
        A, x, y = vals
        self.stop_animation()
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, steps_text(A, x, y))
        self.anim = plots.build_animation(self.fig, A, x, y)
        self.canvas.draw_idle()
        self.status.config(text="Animating: y sweeps a circle; Aᵀy sweeps "
                                "the row space. Press Stop to halt.")

    def stop_animation(self):
        if self.anim is not None:
            self.anim.event_source.stop()
            self.anim = None
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="transpose_dot.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")

    def save_gif(self):
        vals = self._inputs(False)
        if vals is None:
            return
        A, x, y = vals
        if not plots.can_plot(A):
            messagebox.showinfo("No animation", f"Animation needs m, n ≤ {plots.MAX_PLOT_DIM}.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".gif",
                                            initialfile="transpose_dot_anim.gif",
                                            filetypes=[("GIF animation", "*.gif")])
        if not path:
            return
        self.stop_animation()
        self.status.config(text="Rendering GIF (144 frames)… this takes a minute.")
        self.update_idletasks()
        anim = plots.build_animation(self.fig, A, x, y)
        anim.save(path, writer=animation.PillowWriter(fps=20), dpi=80)
        self.status.config(text=f"Saved {os.path.basename(path)}")
        self.animate()
