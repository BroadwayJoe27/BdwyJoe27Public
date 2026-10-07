"""
fit_tab.py -- the "Fit" module of MatrixLab: least-squares curve fitting.

Data points (x, y) one per row, and a polynomial degree. The text sets
up the design matrix A and A c = y, forms and solves the normal
equations exactly, tabulates fitted values and residuals, checks
A^T r = 0, gives SSE and R^2, cross-checks with the QR route, and
explains the projection picture. The figure shows the data, the curve,
and every residual.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

from core import fit_text
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350

FIT_PRESETS = {
    "4 points, nearly a line": ([[0, 1], [1, 2], [2, 2], [3, 4]], 1),
    "5 points on a parabola + noise": ([[-1, 1.2], [0, -0.1], [1, 1.1], [2, 3.9], [3, 9.2]], 2),
    "exact: 3 points, degree 2 (passes through all)": ([[0, 1], [1, 3], [2, 7]], 2),
    "overfit: 4 points, degree 3": ([[0, 1], [1, 2], [2, 2], [3, 4]], 3),
    "singular: repeated x": ([[1, 1], [1, 2], [2, 3]], 2),
    "temperature-like: 6 points, degree 1": ([[1, 30], [2, 34], [3, 43], [4, 55], [5, 64], [6, 73]], 1),
}


class FitTab(ttk.Frame):
    ACCEPTS = {"D": "matrix"}

    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.live_var = tk.BooleanVar(value=True)
        self.degree_var = tk.IntVar(value=1)
        self.preset_var = tk.StringVar()
        self._build()
        D, deg = FIT_PRESETS["4 points, nearly a line"]
        self.degree_var.set(deg)
        self.load_fields({"D": D})
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

        self.D = MatrixEditor(left, "Data points (x, y), one per row", self.on_edit, rows=4, cols=2,
                              lock_cols="columns = x, y", max_dim=8)
        self.D.pack(fill=tk.X, pady=(8, 0))
        self.D.cols_spin.state(["disabled"])
        self.D.lock_cols = False                  # rows may change freely, columns stay 2
        self.D.resize = self._resize_rows_only

        opts = ttk.Frame(left); opts.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(opts, text="polynomial degree:").pack(side=tk.LEFT)
        ttk.Spinbox(opts, from_=0, to=5, width=4, textvariable=self.degree_var,
                    command=lambda: self.compute(quiet=True)).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(opts, text="Examples:").pack(side=tk.LEFT)
        box = ttk.Combobox(opts, textvariable=self.preset_var, state="readonly", width=36, values=list(FIT_PRESETS))
        box.pack(side=tk.LEFT, padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Fit", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random points", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="Least squares, step by step", padding=4)
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

    def _resize_rows_only(self, rows=None, cols=None):
        MatrixEditor.resize(self.D, rows=rows, cols=2)

    def _place_divider(self):
        self.update_idletasks()
        if self.paned.sashpos(0) < 300:
            self.paned.sashpos(0, 560)

    def apply_preset(self):
        item = FIT_PRESETS.get(self.preset_var.get())
        if item is None:
            return
        D, deg = item
        self.degree_var.set(deg)
        self.D.set(D)
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    # fields (library interface)
    # ------------------------------------------------------------------
    def get_fields(self):
        return {"D": self.D.get()}

    def load_fields(self, f):
        D = f.get("D")
        if D is None:
            for k in ("A", "V"):
                if k in f and len(f[k][0]) == 2:
                    D = f[k]; break
        if D is None:
            raise KeyError("D (data points as rows of x, y)")
        D = np.asarray(D, dtype=float)
        if D.ndim != 2 or D.shape[1] != 2:
            raise ValueError("Data needs exactly two columns: x and y.")
        self.D.set(D)
        self.compute(quiet=True)

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
        k = self.D.shape()[0]
        xs = np.arange(k, dtype=float)
        ys = np.round(1 + 0.8 * xs + np.random.default_rng().normal(0, 0.6, k), 1)
        self.D.set(np.column_stack([xs, ys]))
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    def compute(self, quiet=False):
        try:
            D = self.D.get()
            deg = max(0, min(5, int(self.degree_var.get())))
        except (ValueError, tk.TclError) as err:
            if quiet:
                self.status.config(text=str(err))
            else:
                messagebox.showerror("Bad entry", str(err))
            return
        text, d = fit_text(D, deg)
        self.text.delete("1.0", tk.END)
        for line in text.splitlines():
            if line.startswith(("LEAST-SQUARES FIT", "GEOMETRY")):
                tag = "heading"
            elif line.startswith(("NORMAL EQUATIONS", "FITTED CURVE", "THE SAME ANSWER")):
                tag = "section"
            elif "singular" in line or "NO exact solution" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {"coefficients c": d["c"]}
        if "yhat" in d:
            self.results["fitted values"] = d["yhat"]; self.results["residuals"] = d["res"]
            self.results["SSE (sum of squared residuals)"] = np.float64(d["sse"])
            sst = float(np.sum((d["ys"] - d["ys"].mean()) ** 2))
            if sst > 0:
                self.results["R²"] = np.float64(1 - d["sse"] / sst)
        self.results["design matrix A"] = np.array([[x ** j for j in range(deg + 1)] for x in d["xs"]])
        plots.build_fit(self.fig, d)
        self.canvas.draw_idle()
        self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="fit.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
