"""
widgets.py -- tkinter pieces shared by every MatrixLab tab:

  MatrixEditor   an m x n grid of entry cells with row/column spinboxes
  VectorEditor   a single row of entry cells
  LibraryPanel   the saved-matrix list: preview, load, save/update, delete
"""

import random
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

from core import parse_number, fmt, fmt_mat, fmt_vec

MAX_DIM = 8
CELL_WIDTH = 6


def _make_cells(parent, count, row, values, on_key, col0=1):
    cells = []
    for j in range(count):
        e = ttk.Entry(parent, width=CELL_WIDTH, justify="center")
        e.grid(row=row, column=col0 + j, padx=1, pady=1)
        e.insert(0, fmt(values[j]) if values is not None and j < len(values) else "0")
        e.bind("<KeyRelease>", on_key)
        cells.append(e)
    return cells


def _read(entry, where):
    try:
        return parse_number(entry.get())
    except ValueError:
        raise ValueError(f"Can't read '{entry.get()}' in {where}.")


def fit_len(v, n, fill=0.0):
    """Pad with `fill` or truncate a sequence to length n (for vectors that
    arrive from another module or a library entry of a different size)."""
    v = list(v)
    return (v + [fill] * n)[:n]


def _keep(text):
    try:
        return parse_number(text)
    except ValueError:
        return 0.0


class MatrixEditor(ttk.LabelFrame):
    """Grid of cells for one matrix. on_change() fires after any edit or
    resize; the owning tab decides when to recompute."""

    def __init__(self, master, name, on_change, rows=2, cols=2,
                 lock_rows=None, lock_cols=None, max_dim=MAX_DIM):
        super().__init__(master, text=name, padding=6)
        self.name = name
        self.on_change = on_change
        self.rows_var = tk.IntVar(value=rows)
        self.cols_var = tk.IntVar(value=cols)
        self.cells = []

        dims = ttk.Frame(self)
        dims.pack(fill=tk.X)
        ttk.Label(dims, text="rows:").pack(side=tk.LEFT)
        self.rows_spin = ttk.Spinbox(dims, from_=1, to=max_dim, width=4,
                                     textvariable=self.rows_var,
                                     command=self.resize)
        self.rows_spin.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(dims, text="columns:").pack(side=tk.LEFT)
        self.cols_spin = ttk.Spinbox(dims, from_=1, to=max_dim, width=4,
                                     textvariable=self.cols_var,
                                     command=self.resize)
        self.cols_spin.pack(side=tk.LEFT, padx=2)
        ttk.Button(dims, text="Resize", command=self.resize).pack(side=tk.LEFT, padx=(10, 0))
        self.lock_cols = bool(lock_cols)
        if lock_rows:
            self.rows_spin.state(["disabled"])
            ttk.Label(dims, text=lock_rows, foreground="gray").pack(side=tk.LEFT, padx=(8, 0))
        if lock_cols:
            self.cols_spin.state(["disabled"])
            ttk.Label(dims, text=lock_cols, foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        self.grid_frame = ttk.Frame(self)
        self.grid_frame.pack(fill=tk.X, pady=(6, 0))
        self.set(np.zeros((rows, cols)))

    # -- shape / values -------------------------------------------------
    def shape(self):
        return len(self.cells), len(self.cells[0])

    def set(self, M):
        M = [list(r) for r in M]
        m, n = len(M), len(M[0])
        self.rows_var.set(m); self.cols_var.set(n)
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.cells = []
        for i in range(m):
            ttk.Label(self.grid_frame, text=f"row {i + 1}").grid(row=i, column=0, sticky="e", padx=(0, 6))
            self.cells.append(_make_cells(self.grid_frame, n, i, M[i], self._on_key))
        self.config(text=f"{self.name}  ({m} x {n})")

    def get(self):
        return np.array([[_read(e, f"{self.name} row {i + 1}, column {j + 1}")
                          for j, e in enumerate(row)]
                         for i, row in enumerate(self.cells)])

    def values_or_zero(self):
        return [[_keep(e.get()) for e in row] for row in self.cells]

    def resize(self, rows=None, cols=None):
        """Change shape, keeping whatever cells overlap the old grid."""
        try:
            m = int(rows if rows is not None else self.rows_var.get())
            n = int(cols if cols is not None else self.cols_var.get())
        except (tk.TclError, ValueError):
            return
        m, n = max(1, min(MAX_DIM, m)), max(1, min(MAX_DIM, n))
        if getattr(self, "lock_cols", False):
            n = m                      # square matrices: columns follow rows
        old = self.values_or_zero()
        M = [[old[i][j] if i < len(old) and j < len(old[i]) else 0.0
              for j in range(n)] for i in range(m)]
        self.set(M)
        self.on_change()

    def random_fill(self):
        m, n = self.shape()
        self.set([[random.randint(-3, 3) for _ in range(n)] for _ in range(m)])

    def _on_key(self, event=None):
        self.on_change()


class VectorEditor(ttk.Frame):
    """One labelled row of cells."""

    def __init__(self, master, label, on_change, size=2):
        super().__init__(master)
        self.label_text = label
        self.on_change = on_change
        self.label = ttk.Label(self, text=label)
        self.label.grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.cells = []
        self.set(np.zeros(size))

    def set(self, v, label=None):
        if label is not None:
            self.label_text = label
        for e in self.cells:
            e.destroy()
        self.cells = _make_cells(self, len(v), 0, list(v), lambda e: self.on_change())
        self.label.config(text=self.label_text)

    def get(self):
        return np.array([_read(e, f"{self.label_text} entry {j + 1}")
                         for j, e in enumerate(self.cells)])

    def resize(self, n, label=None):
        old = [_keep(e.get()) for e in self.cells]
        self.set([old[j] if j < len(old) else 0.0 for j in range(n)], label)

    def random_fill(self):
        v = [random.randint(-3, 3) for _ in self.cells]
        if not any(v):
            v[0] = 1
        self.set(v)


class LibraryPanel(ttk.LabelFrame):
    """Shared saved-matrix list. Each tab makes one; they all show the same
    files and refresh together. get_fields() returns the dict to save;
    on_load(fields) pushes a loaded dict into the tab."""

    instances = []

    def __init__(self, master, library, get_fields, on_load):
        super().__init__(master, text="Saved matrices", padding=6)
        self.library = library
        self.get_fields = get_fields
        self.on_load = on_load
        self.loaded_name = None
        self.modified = False
        LibraryPanel.instances.append(self)

        row = ttk.Frame(self); row.pack(fill=tk.X)
        self.listbox = tk.Listbox(row, height=5, exportselection=False)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self.load_selected())
        self.listbox.bind("<<ListboxSelect>>", lambda e: self.preview_selected())
        sb = ttk.Scrollbar(row, command=self.listbox.yview)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.config(yscrollcommand=sb.set)

        self.preview = tk.Label(self, text="(select a matrix to preview it)",
                                font=("Menlo", 10), justify=tk.LEFT, anchor="w",
                                foreground="gray")
        self.preview.pack(fill=tk.X, pady=(4, 0))

        btns = ttk.Frame(self); btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text="Load", command=self.load_selected).pack(side=tk.LEFT)
        ttk.Button(btns, text="Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="↻", width=3, command=self.rescan).pack(side=tk.RIGHT)

        save_row = ttk.Frame(self); save_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(save_row, text="Name:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        ttk.Entry(save_row, textvariable=self.name_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(save_row, text="Save / Update", command=self.save_current).pack(side=tk.LEFT)

        self.working = ttk.Label(self, text="", foreground="#b25a00")
        self.working.pack(fill=tk.X, pady=(6, 0))
        self.refresh()

    # -- state ------------------------------------------------------------
    def mark_modified(self, flag=True):
        self.modified = flag
        if self.loaded_name is None:
            text = "Working on: unsaved matrix" if flag else ""
        else:
            text = f"Working on: {self.loaded_name}" + (
                "   (edited, not saved)" if flag else "   (saved)")
        self.working.config(text=text)

    def rescan(self):
        """Re-read the folder (for files added or removed outside the app)."""
        self.library.names(force=True)
        LibraryPanel.refresh_all()

    @classmethod
    def refresh_all(cls):
        for p in cls.instances:
            if p.winfo_exists():
                p.refresh(select=p.loaded_name)

    def refresh(self, select=None):
        names = self.library.names()
        self.listbox.delete(0, tk.END)
        for name in names:
            self.listbox.insert(tk.END, name)
        if select in names:
            idx = names.index(select)
            self.listbox.selection_set(idx); self.listbox.see(idx)
            self.preview_selected()

    def _selected_name(self):
        sel = self.listbox.curselection()
        return self.listbox.get(sel[0]) if sel else None

    # -- actions ----------------------------------------------------------
    def preview_selected(self):
        name = self._selected_name()
        if name is None:
            return
        try:
            f = self.library.load(name)
        except (OSError, KeyError, ValueError):
            self.preview.config(text=f"{name}: can't read file")
            return
        lines = [name]
        if "A" in f:
            A = f["A"]
            lines = [f"{name}   A ({len(A)}x{len(A[0])})", fmt_mat(A, indent="")]
        if "x" in f or "y" in f:
            lines.append("   ".join(f"{k} = {fmt_vec(f[k])}" for k in ("x", "y") if k in f))
        if "B" in f:
            B = f["B"]
            lines += [f"B ({len(B)}x{len(B[0])})", fmt_mat(B, indent="")]
        if "b" in f:
            lines.append(f"b = {fmt_vec(f['b'])}")
        if "V" in f:
            V = f["V"]
            lines += [f"vectors V ({len(V)} in R^{len(V[0])})", fmt_mat(V, indent="")]
        if "u" in f or "v" in f:
            lines.append("   ".join(f"{k} = {fmt_vec(f[k])}" for k in ("u", "v") if k in f))
        if "w" in f:
            lines.append(f"w = {fmt_vec(f['w'])}")
        if "k" in f:
            lines.append(f"k = {fmt(np.asarray(f['k']).ravel()[0])}")
        if "D" in f:
            D = f["D"]
            lines += [f"data: {len(D)} points (x, y)", fmt_mat(D[:4], indent="") + ("\n..." if len(D) > 4 else "")]
        self.preview.config(text="\n".join(lines))

    def load_selected(self):
        name = self._selected_name()
        if name is None:
            return
        try:
            fields = self.library.load(name)
        except (OSError, KeyError, ValueError) as err:
            messagebox.showerror("Can't load", f"{name}: {err}")
            return
        try:
            self.on_load(fields)
        except KeyError as err:
            messagebox.showinfo("Nothing to load",
                                f"'{name}' has no {err.args[0]} saved, which this tab needs.")
            return
        self.name_var.set(name)
        self.loaded_name = name
        self.mark_modified(False)

    def save_current(self):
        try:
            fields = self.get_fields()
        except ValueError as err:
            messagebox.showerror("Bad entry", str(err))
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showinfo("Name needed", "Type a name for this matrix first.")
            return
        if (name != self.loaded_name and name in self.library.names()
                and not messagebox.askyesno(
                    "Replace?", f"'{name}' already exists. Replace it?")):
            return
        self.library.save(name, **fields)
        self.loaded_name = name
        self.mark_modified(False)
        LibraryPanel.refresh_all()
        self.refresh(select=name)

    def delete_selected(self):
        name = self._selected_name()
        if name is None:
            return
        if messagebox.askyesno("Delete?", f"Delete '{name}' from the library?"):
            self.library.delete(name)
            for p in LibraryPanel.instances:
                if p.loaded_name == name:
                    p.loaded_name = None
                    p.mark_modified(p.modified)
                p.preview.config(text="(select a matrix to preview it)")
            LibraryPanel.refresh_all()
