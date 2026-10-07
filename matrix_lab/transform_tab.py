"""
transform_tab.py -- the "Transform" tab of MatrixLab.

A 2x2 or 3x3 matrix as a map of the plane or of space. Pick a preset
(rotation by an angle, reflection, shear, scaling, projection, ...) or
type A; pick a shape; drag the t slider or press Play to morph the shape
from the identity to A along M(t) = (1 - t) I + t A. The text explains
where the basis vectors go, the determinant's meaning, what kind of map
A is, and its stretch factors.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure
from matplotlib import animation

from core import transform_text, transform_presets
import plots
from widgets import MatrixEditor, LibraryPanel

LIVE_DELAY_MS = 350
N_FRAMES = 70


class TransformTab(ttk.Frame):
    ACCEPTS = {"A": "matrix"}
    def __init__(self, master, library):
        super().__init__(master)
        self.library = library
        self._live_job = None
        self.anim = None
        self.scene = None
        self.live_var = tk.BooleanVar(value=True)
        self.t_var = tk.DoubleVar(value=1.0)
        self.angle_var = tk.StringVar(value="45")
        self.shape_var = tk.StringVar()
        self.preset_var = tk.StringVar()
        self._build()
        self.load_fields({"A": transform_presets(2, 45)["rotation by 45°"]})
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

        self.A = MatrixEditor(left, "A (2x2 or 3x3)", self.on_A_change, rows=2, cols=2,
                              lock_cols="columns = rows", max_dim=3)
        self.A.pack(fill=tk.X, pady=(8, 0))

        pre = ttk.LabelFrame(left, text="Presets", padding=6)
        pre.pack(fill=tk.X, pady=(8, 0))
        self.preset_box = ttk.Combobox(pre, textvariable=self.preset_var, state="readonly", width=34)
        self.preset_box.grid(row=0, column=0, sticky="w")
        self.preset_box.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())
        ttk.Label(pre, text="angle θ (deg):").grid(row=0, column=1, padx=(10, 2))
        ang = ttk.Entry(pre, textvariable=self.angle_var, width=6)
        ang.grid(row=0, column=2)
        ang.bind("<Return>", lambda e: self.apply_preset())
        ttk.Button(pre, text="Apply", command=self.apply_preset).grid(row=0, column=3, padx=(6, 0))

        shp = ttk.Frame(left); shp.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(shp, text="Shape:").pack(side=tk.LEFT)
        self.shape_box = ttk.Combobox(shp, textvariable=self.shape_var, state="readonly", width=24)
        self.shape_box.pack(side=tk.LEFT, padx=(4, 0))
        self.shape_box.bind("<<ComboboxSelected>>", lambda e: self.rebuild_scene())

        sl = ttk.LabelFrame(left, text="Morph from identity (t = 0) to A (t = 1)", padding=6)
        sl.pack(fill=tk.X, pady=(8, 0))
        self.t_label = ttk.Label(sl, text="t = 1.00", width=9)
        self.t_label.pack(side=tk.LEFT)
        self.slider = ttk.Scale(sl, from_=0.0, to=1.0, variable=self.t_var, command=self.on_slide)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(sl, text="Play", command=self.play).pack(side=tk.LEFT)
        ttk.Button(sl, text="Stop", command=self.stop_animation).pack(side=tk.LEFT, padx=(4, 0))

        act = ttk.Frame(left); act.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(act, text="Compute", command=self.compute).pack(side=tk.LEFT)
        ttk.Button(act, text="Random fill", command=self.random_fill).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(act, text="Live update", variable=self.live_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(act, text="Save PNG…", command=self.save_png).pack(side=tk.RIGHT)

        txt = ttk.LabelFrame(left, text="What A does", padding=4)
        txt.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.text = tk.Text(txt, width=64, font=("Menlo", 11), wrap="none")
        tsb = ttk.Scrollbar(txt, command=self.text.yview)
        self.text.config(yscrollcommand=tsb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.LEFT, fill=tk.Y)
        bold = ("Menlo", 11, "bold")
        self.text.tag_configure("heading", foreground="#2a5db0", font=bold)
        self.text.tag_configure("kind", foreground="#1a7f37", font=bold)
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
    # dimension-dependent choices
    # ------------------------------------------------------------------
    def _dim(self):
        return self.A.shape()[0]

    def _angle(self):
        try:
            return float(self.angle_var.get())
        except ValueError:
            return 45.0

    def _refresh_choices(self):
        n = self._dim()
        presets = list(transform_presets(n, self._angle()).keys()) if n in (2, 3) else []
        self.preset_box["values"] = presets
        if self.preset_var.get() not in presets:
            self.preset_var.set("")
        shapes = plots.SHAPES_2D if n == 2 else plots.SHAPES_3D if n == 3 else []
        self.shape_box["values"] = shapes
        if self.shape_var.get() not in shapes and shapes:
            self.shape_var.set(shapes[0])

    def apply_preset(self):
        name = self.preset_var.get()
        n = self._dim()
        presets = transform_presets(n, self._angle())
        # the angle may have changed the preset's name: match by prefix
        key = next((k for k in presets if k.split(" by ")[0].split(" at ")[0] ==
                    name.split(" by ")[0].split(" at ")[0]), None)
        if key is None:
            return
        self._refresh_choices()
        self.preset_var.set(key)
        self.A.set(np.round(np.array(presets[key], dtype=float), 6))
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
        k = min(3, max(2, max(m, n)))
        if (m, n) != (k, k):
            B = np.eye(k)
            B[:min(m, k), :min(n, k)] = A[:k, :k]
            A = B
            self.status.config(text=f"Loaded {m}x{n} matrix fitted to {k}x{k}.")
        self.A.set(A)
        self._refresh_choices()
        self.compute(quiet=True)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------
    def on_A_change(self):
        self._refresh_choices()
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
        self.A.random_fill()
        self.lib.mark_modified()
        self.compute()

    # ------------------------------------------------------------------
    # compute / scene / animation
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
        n = A.shape[0]
        if n not in (2, 3):
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, "This tab draws 2x2 and 3x3 matrices. Set rows to 2 or 3.")
            return
        self.text.delete("1.0", tk.END)
        for line in transform_text(A).splitlines():
            if line.startswith(("A AS A", "WHERE THE", "SIZE AND", "WHAT KIND", "STRETCH", "THE ANIMATION")):
                tag = "heading"
            elif line.strip().startswith(("ROTATION", "REFLECTION", "SCALING", "SHEAR", "ORTHOGONAL PROJECTION",
                                          "PROJECTION", "SYMMETRIC", "A general map")):
                tag = "kind"
            elif "SINGULAR" in line or "REVERSED" in line:
                tag = "bad"
            else:
                tag = ()
            self.text.insert(tk.END, line + "\n", tag)
        self.results = {"Aᵀ": A.T, "det A": np.float64(np.linalg.det(A))}
        if abs(np.linalg.det(A)) > 1e-12:
            self.results["A⁻¹"] = np.linalg.inv(A)
        self.rebuild_scene()
        if not self.status.cget("text").startswith("Loaded"):
            self.status.config(text="")

    def rebuild_scene(self):
        try:
            A = self.A.get()
        except ValueError:
            return
        n = A.shape[0]
        if n not in (2, 3):
            return
        self.stop_animation()
        self._refresh_choices()
        lines = plots.transform_shape(self.shape_var.get(), n)
        self.scene = plots.TransformScene(self.fig, A, lines, n)
        self.scene.update(self.t_var.get())
        self.canvas.draw_idle()

    def on_slide(self, value):
        t = float(value)
        self.t_label.config(text=f"t = {t:.2f}")
        if self.anim is not None:
            self.stop_animation()
        if self.scene is not None:
            self.scene.update(t)
            self.canvas.draw_idle()

    def play(self):
        if self.scene is None:
            return
        self.stop_animation()
        ts = np.concatenate([np.zeros(8), np.linspace(0, 1, N_FRAMES), np.ones(15)])
        ts = ts * ts * (3 - 2 * ts)                  # ease in/out

        def frame(i):
            t = float(ts[i])
            self.t_var.set(t)
            self.t_label.config(text=f"t = {t:.2f}")
            return self.scene.update(t)

        self.anim = animation.FuncAnimation(self.fig, frame, frames=len(ts), interval=40,
                                            blit=False, repeat=True)
        self.canvas.draw_idle()
        self.status.config(text="Playing: identity -> A, looping. Drag the slider or press Stop.")

    def stop_animation(self):
        if self.anim is not None:
            self.anim.event_source.stop()
            self.anim = None
            self.status.config(text="")

    def save_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="transform.png",
                                            filetypes=[("PNG image", "*.png")])
        if path:
            self.fig.savefig(path, dpi=130)
            self.status.config(text=f"Saved {os.path.basename(path)}")
