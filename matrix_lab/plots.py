"""
plots.py -- matplotlib figures for the TransposeDot app, generalized from
TransposeDot.py / TransposeDotAnim.py to any A with m <= 3 rows and
n <= 3 columns.  (The arithmetic works for any size; the pictures need
dimensions we can draw.)

Left panel  : R^n, the domain   -- x, A^T y, row space, null space
Right panel : R^m, the codomain -- y, A x
Animation   : y sweeps a circle in R^m; A^T y sweeps an ellipse inside
              the row space of A; both dot products are plotted together.

Panels are always 3D axes; a 2-D (or 1-D) space is shown looking straight
down at the z = 0 sheet so it reads as a flat plot.
"""

import numpy as np
from matplotlib import animation

from core import compute, subspaces, fmt, fmt_vec

MAX_PLOT_DIM = 3


def can_plot(A):
    m, n = np.asarray(A).shape
    return m <= MAX_PLOT_DIM and n <= MAX_PLOT_DIM


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def embed3(v):
    v = np.asarray(v, dtype=float).ravel()
    out = np.zeros(3)
    out[:len(v)] = v
    return out


def norm(v):
    return float(np.linalg.norm(v))


def angle_between(v1, v2):
    n1, n2 = norm(v1), norm(v2)
    if n1 == 0 or n2 == 0:
        return float("nan")
    c = np.dot(v1, v2) / (n1 * n2)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def quiver3(ax, v, color, label=None, **kw):
    v = embed3(v)
    kw.setdefault("arrow_length_ratio", 0.08)
    kw.setdefault("linewidth", 2)
    return ax.quiver(0, 0, 0, v[0], v[1], v[2], color=color, label=label, **kw)


def plot_span_plane(ax, v1, v2, scale, color="c", alpha=0.25):
    s = np.linspace(-scale, scale, 10)
    S, T = np.meshgrid(s, s)
    pts = np.outer(S.ravel(), embed3(v1)) + np.outer(T.ravel(), embed3(v2))
    ax.plot_surface(pts[:, 0].reshape(S.shape), pts[:, 1].reshape(S.shape),
                    pts[:, 2].reshape(S.shape), color=color, alpha=alpha,
                    linewidth=0)


def plot_span_line(ax, v, scale, **kw):
    v = embed3(v)
    p = np.outer([-scale, scale], v)
    return ax.plot(p[:, 0], p[:, 1], p[:, 2], **kw)


def set_equal_limits(ax, vectors, pad=1.1):
    m = pad * max([np.max(np.abs(embed3(v))) for v in vectors] + [1e-9])
    if m == 0:
        m = 1.0
    ax.set_xlim([-m, m]); ax.set_ylim([-m, m]); ax.set_zlim([-m, m])
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    return m


def flatten_view(ax, dim):
    """Look straight down so a 2-D (or 1-D) space reads as a flat plot."""
    if dim <= 2:
        ax.view_init(elev=90, azim=-90)
        ax.set_zticks([]); ax.set_zlabel("")
    if dim == 1:
        ax.set_yticks([]); ax.set_ylabel("")


def draw_flat_sheet(ax, extent):
    gx, gy = np.meshgrid(np.linspace(-extent, extent, 2),
                         np.linspace(-extent, extent, 2))
    ax.plot_surface(gx, gy, np.zeros_like(gx), color="k", alpha=0.06)


# ----------------------------------------------------------------------
# the two panels
# ----------------------------------------------------------------------

def draw_domain(ax, A, x, ATy=None, extra_paths=()):
    """R^n: x, A^T y (if given), the row space of A (cyan), the null space
    (gray), and the projection of x onto the row space (orange)."""
    A = np.asarray(A, dtype=float)
    n = A.shape[1]
    rank, row_basis, null_basis = subspaces(A)
    vecs = [x, *extra_paths] + ([ATy] if ATy is not None else [])
    ext = set_equal_limits(ax, vecs)

    if n <= 2:
        draw_flat_sheet(ax, ext)

    # Row space of A
    if rank == n:
        row_note = f"row space of A = all of R^{n}"
    elif rank == 2:
        plot_span_plane(ax, row_basis[0], row_basis[1], 1.4 * ext)
        row_note = "cyan plane = row space of A"
    elif rank == 1:
        plot_span_line(ax, row_basis[0], ext, color="c", lw=6, alpha=0.35)
        row_note = "cyan line = row space of A"
    else:
        row_note = "row space of A = {0}"

    # Null space of A (each basis direction, dotted gray)
    for k, b in enumerate(null_basis):
        plot_span_line(ax, b, ext, color="gray", linestyle=":", lw=1.5,
                       label="null space of A (dot = 0)" if k == 0 else None)

    # Projection of x onto the row space
    if len(null_basis):
        x_null = sum((x @ b) * b for b in null_basis)
        x_row = x - x_null
        if norm(x_row) > 1e-12:
            quiver3(ax, x_row, "orange", "proj of x onto row space",
                    linestyle="dashed", linewidth=1.5)

    quiver3(ax, x, "r", f"x = {fmt_vec(x)}")
    if ATy is not None:
        quiver3(ax, ATy, "b", f"A$^T$y = {fmt_vec(ATy)}")
    flatten_view(ax, n)
    ax.legend(loc="upper left", fontsize=8)
    return row_note


def draw_codomain(ax, A, Ax, y=None, extra_paths=()):
    """R^m: A x and y (if given)."""
    m = np.asarray(A).shape[0]
    vecs = [Ax, *extra_paths] + ([y] if y is not None else [])
    ext = set_equal_limits(ax, vecs)
    if m <= 2:
        draw_flat_sheet(ax, ext)
    if y is not None:
        quiver3(ax, y, "g", f"y = {fmt_vec(y)}")
    quiver3(ax, Ax, "m", f"Ax = {fmt_vec(Ax)}")
    flatten_view(ax, m)
    ax.legend(loc="upper left", fontsize=8)


def draw_unplottable(fig, A):
    m, n = np.asarray(A).shape
    fig.clear()
    fig.text(0.5, 0.55, f"A is {m}x{n}: R^{n} -> R^{m}", ha="center",
             fontsize=15)
    fig.text(0.5, 0.42,
             f"Plots need at most {MAX_PLOT_DIM} rows and {MAX_PLOT_DIM} "
             "columns.\nThe step-by-step arithmetic on the left still "
             "works for any size.", ha="center", fontsize=11, color="gray")


# ----------------------------------------------------------------------
# static figure
# ----------------------------------------------------------------------

def build_static(fig, A, x, y):
    A = np.asarray(A, dtype=float)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if not can_plot(A):
        draw_unplottable(fig, A)
        return
    m, n = A.shape
    Ax, ATy, lhs, _ = compute(A, x, y)
    fig.clear()

    ax1 = fig.add_subplot(121, projection="3d")
    row_note = draw_domain(ax1, A, x, ATy=ATy)
    ax1.set_title(f"R$^{n}$ (domain):  x . (A$^T$y) = {fmt(lhs)}\n"
                  f"angle(x, A$^T$y) = {angle_between(x, ATy):.1f}°  |  "
                  f"{row_note}", fontsize=10)

    ax2 = fig.add_subplot(122, projection="3d")
    draw_codomain(ax2, A, Ax, y=y)
    ax2.set_title(f"R$^{m}$ (codomain):  (Ax) . y = {fmt(lhs)}\n"
                  f"angle(Ax, y) = {angle_between(Ax, y):.1f}°", fontsize=10)

    fig.suptitle(r"The adjoint identity:  $(Ax)\cdot y \;=\; x\cdot(A^Ty)$"
                 f"  =  {fmt(lhs)}   -- one number, two spaces", fontsize=13)
    fig.tight_layout()


# ----------------------------------------------------------------------
# animation
# ----------------------------------------------------------------------

def rotation_frame(y):
    """Unit vectors u (along y) and v (perpendicular to y, in R^m) so that
    y(theta) = |y| (cos(theta) u + sin(theta) v) sweeps a circle through y."""
    y = np.asarray(y, dtype=float)
    m = len(y)
    r = norm(y)
    u = y / r if r > 0 else np.eye(m)[0]
    v = np.zeros(m)
    if m >= 2:
        e = np.eye(m)[int(np.argmin(np.abs(u)))]   # axis least aligned with u
        v = e - (e @ u) * u
        v /= norm(v)
    return u, v


def build_animation(fig, A, x, y, n_frames=144, interval=50):
    """Draw the animated layout into fig and return the FuncAnimation
    (keep a reference to it, or it will be garbage-collected)."""
    A = np.asarray(A, dtype=float)
    x = np.asarray(x, dtype=float)
    y0 = np.asarray(y, dtype=float)
    if not can_plot(A):
        draw_unplottable(fig, A)
        return None
    m, n = A.shape
    Ax = A @ x
    r = norm(y0) if norm(y0) > 0 else 1.0
    u, v = rotation_frame(y0)

    theta = np.linspace(0, 2 * np.pi, n_frames)
    ys = r * (np.outer(np.cos(theta), u) + np.outer(np.sin(theta), v))  # (N, m)
    ATys = ys @ A                                                        # (N, n)
    dots_R2 = ys @ Ax
    dots_R3 = ATys @ x
    deg = np.degrees(theta)

    fig.clear()
    gs = fig.add_gridspec(2, 2, height_ratios=[2.4, 1], hspace=0.3)
    ax1 = fig.add_subplot(gs[0, 0], projection="3d")
    ax2 = fig.add_subplot(gs[0, 1], projection="3d")
    ax3 = fig.add_subplot(gs[1, :])

    # LEFT: R^n
    draw_domain(ax1, A, x, extra_paths=ATys)
    P = np.array([embed3(p) for p in ATys])
    ax1.plot(P[:, 0], P[:, 1], P[:, 2], color="b", alpha=0.25, lw=1,
             label="path of A$^T$y (ellipse in row space)")
    ax1.set_title(f"R$^{n}$:  A$^T$y sweeps the row space of A", fontsize=10)
    ax1.legend(loc="upper left", fontsize=8)

    # RIGHT: R^m
    draw_codomain(ax2, A, Ax, extra_paths=ys)
    Q = np.array([embed3(p) for p in ys])
    ax2.plot(Q[:, 0], Q[:, 1], Q[:, 2], color="g", alpha=0.25, lw=1,
             label="path of y (circle)")
    ax2.set_title(f"R$^{m}$:  y sweeps a circle", fontsize=10)
    ax2.legend(loc="upper left", fontsize=8)

    moving = {"q_ATy": None, "q_y": None}   # arrows redrawn every frame

    # BOTTOM: both dot products vs angle
    ax3.axhline(0, color="k", lw=0.5)
    ax3.plot(deg, dots_R2, color="m", alpha=0.15, lw=3)
    line_R2, = ax3.plot([], [], color="m", lw=3,
                        label=rf"$(Ax)\cdot y$   [in R$^{m}$]")
    line_R3, = ax3.plot([], [], color="b", lw=1.5, linestyle="--",
                        label=rf"$x\cdot(A^Ty)$   [in R$^{n}$]")
    marker, = ax3.plot([], [], "ko", ms=6)
    ax3.set_xlim(0, 360)
    pad = 1.15 * max(np.max(np.abs(dots_R2)), 1e-9)
    ax3.set_ylim(-pad, pad)
    ax3.set_xlabel("rotation of y (degrees)")
    ax3.set_ylabel("dot product")
    ax3.legend(loc="upper right", fontsize=9)
    readout = ax3.text(0.02, 0.92, "", transform=ax3.transAxes, fontsize=10,
                       va="top")
    fig.suptitle(r"$(Ax)\cdot y = x\cdot(A^Ty)$ as y rotates -- "
                 "two spaces, one number, locked together", fontsize=13)

    def update(i):
        if moving["q_ATy"] is not None:
            moving["q_ATy"].remove()
            moving["q_y"].remove()
        moving["q_ATy"] = quiver3(ax1, ATys[i], "b")
        moving["q_y"] = quiver3(ax2, ys[i], "g")
        line_R2.set_data(deg[:i + 1], dots_R2[:i + 1])
        line_R3.set_data(deg[:i + 1], dots_R3[:i + 1])
        marker.set_data([deg[i]], [dots_R2[i]])
        readout.set_text(f"y = {fmt_vec(np.round(ys[i], 2))}    "
                         f"A$^T$y = {fmt_vec(np.round(ATys[i], 2))}    "
                         f"(Ax)·y = {dots_R2[i]:.2f} = x·(A$^T$y) = "
                         f"{dots_R3[i]:.2f}")
        return line_R2, line_R3, marker, readout

    return animation.FuncAnimation(fig, update, frames=n_frames,
                                   interval=interval, blit=False, repeat=True)


# ----------------------------------------------------------------------
# four fundamental subspaces (Subspaces tab)
# ----------------------------------------------------------------------

def _orthonormal(vectors):
    """Orthonormal basis (rows) spanning the given float vectors."""
    if not len(vectors):
        return np.zeros((0, 3))
    V = np.array([embed3(v) for v in vectors], dtype=float)
    Q, R = np.linalg.qr(V.T)
    r = int(np.sum(np.abs(np.diag(R)) > 1e-9))
    return Q[:, :r].T


def draw_subspace(ax, vectors, scale, color, label, dim):
    """Shade the span of `vectors` in a 3D axes: point, line, plane, or note."""
    B = _orthonormal(vectors)
    k = len(B)
    if k == 0:
        ax.scatter([0], [0], [0], color=color, s=40, label=f"{label} = {{0}}")
    elif k >= dim:
        ax.plot([], [], " ", label=f"{label} = all of R^{dim}")
    elif k == 1:
        plot_span_line(ax, B[0], scale, color=color, lw=6, alpha=0.35,
                       label=f"{label} (line)")
    elif k == 2:
        plot_span_plane(ax, B[0], B[1], scale * (1.3 if dim == 3 else 1.0),
                        color=color, alpha=0.22)
        ax.plot([], [], color=color, lw=8, alpha=0.4, label=f"{label} (plane)")
    return k


def _draw_basis_arrows(ax, vectors, color, name):
    for i, v in enumerate(vectors):
        quiver3(ax, v, color, f"{name}{i + 1} = {fmt_vec(v)}", linewidth=1.8)


def build_subspaces(fig, A, d):
    """Two panels: R^n (row space + null space) and R^m (column space +
    left null space). d is the dict from core.fundamental_subspaces."""
    A = np.asarray(A, dtype=float)
    if not can_plot(A):
        draw_unplottable(fig, A)
        return
    m, n, r = d["m"], d["n"], d["rank"]
    tofloat = lambda vs: [[float(q) for q in v] for v in vs]
    row, null = tofloat(d["row"]), tofloat(d["null"])
    col, left = tofloat(d["col"]), tofloat(d["left"])
    fig.clear()

    # --- domain R^n -------------------------------------------------
    ax1 = fig.add_subplot(121, projection="3d")
    ext = set_equal_limits(ax1, row + null + [np.ones(n)])
    if n <= 2:
        draw_flat_sheet(ax1, ext)
    draw_subspace(ax1, row, ext, "c", "row space C(Aᵀ)", n)
    draw_subspace(ax1, null, ext, "gray", "null space N(A)", n)
    _draw_basis_arrows(ax1, row, "b", "r")
    _draw_basis_arrows(ax1, null, "k", "k")
    flatten_view(ax1, n)
    ax1.set_title(f"Domain R$^{n}$:  row space (dim {r})  ⊥  null space (dim {n - r})",
                  fontsize=10)
    ax1.legend(loc="upper left", fontsize=7)

    # --- codomain R^m -----------------------------------------------
    ax2 = fig.add_subplot(122, projection="3d")
    ext = set_equal_limits(ax2, col + left + [np.ones(m)])
    if m <= 2:
        draw_flat_sheet(ax2, ext)
    draw_subspace(ax2, col, ext, "m", "column space C(A)", m)
    draw_subspace(ax2, left, ext, "gray", "left null space N(Aᵀ)", m)
    _draw_basis_arrows(ax2, col, "m", "c")
    _draw_basis_arrows(ax2, left, "k", "l")
    flatten_view(ax2, m)
    ax2.set_title(f"Codomain R$^{m}$:  column space (dim {r})  ⊥  left null space (dim {m - r})",
                  fontsize=10)
    ax2.legend(loc="upper left", fontsize=7)

    fig.suptitle(f"The four fundamental subspaces of A ({m}x{n}), rank {r}", fontsize=13)
    fig.tight_layout()


# ----------------------------------------------------------------------
# span and independence (Span tab)
# ----------------------------------------------------------------------

def build_span(fig, V, w, d):
    """Vectors (rows of V) as arrows in R^d, span shaded, w in orange.
    d is the dict from core.span_text."""
    V = np.asarray(V, dtype=float)
    k, dim = V.shape
    fig.clear()
    if dim > MAX_PLOT_DIM:
        fig.text(0.5, 0.55, f"{k} vectors in R^{dim}", ha="center", fontsize=15)
        fig.text(0.5, 0.42, f"Plots need vectors in R^1, R^2 or R^3.\nThe algebra on the "
                 "left still works.", ha="center", fontsize=11, color="gray")
        return
    ax = fig.add_subplot(111, projection="3d")
    vecs = [V[i] for i in range(k)] + ([np.asarray(w, dtype=float)] if w is not None else [])
    ext = set_equal_limits(ax, vecs + [np.ones(dim)])
    if dim <= 2:
        draw_flat_sheet(ax, ext)
    basis = [V[c] for c in d["pivot"]]
    draw_subspace(ax, basis, ext, "c", "span", dim)
    colors = ["b", "g", "m", "r", "k", "y", "c", "tab:brown"]
    for i in range(k):
        redundant = i in d["free"]
        quiver3(ax, V[i], colors[i % len(colors)],
                f"v{i + 1} = {fmt_vec(V[i])}" + ("  (combination of the others)" if redundant else ""),
                linewidth=1.2 if redundant else 2.2, linestyle="dashed" if redundant else "solid")
    if w is not None:
        w = np.asarray(w, dtype=float)
        tag = {True: "in the span", False: "NOT in the span", None: ""}[d["in_span"]]
        quiver3(ax, w, "orange", f"w = {fmt_vec(w)}  ({tag})", linewidth=2.5)
        if d["in_span"] is False and basis:
            B = _orthonormal(basis)
            w3 = embed3(w)
            proj = sum((w3 @ b) * b for b in B)
            ax.plot([w3[0], proj[0]], [w3[1], proj[1]], [w3[2], proj[2]],
                    color="orange", linestyle=":", lw=1.2, label="distance from w to the span")
    flatten_view(ax, dim)
    r = d["rank"]
    verdict = "independent" if not d["free"] else f"dependent ({len(d['free'])} redundant)"
    ax.set_title(f"{k} vector{'s' if k != 1 else ''} in R$^{dim}$: {verdict};  "
                 f"span has dimension {r}" + ("  = all of R$^%d$" % dim if r == dim else ""),
                 fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()


# ----------------------------------------------------------------------
# determinant: unit square / cube and its image (Determinant tab)
# ----------------------------------------------------------------------

def build_det(fig, A, det):
    """Unit square (n=2) or unit cube (n=3) in gray and its image under A
    in color; the image's area/volume is |det A|."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    det = float(det)
    fig.clear()
    if n not in (2, 3):
        fig.text(0.5, 0.55, f"A is {n}x{n}", ha="center", fontsize=15)
        fig.text(0.5, 0.42, "The picture needs a 2x2 or 3x3 matrix.\nThe determinant and "
                 "inverse on the left still work.", ha="center", fontsize=11, color="gray")
        return
    ax = fig.add_subplot(111, projection="3d")
    color = "tab:blue" if det > 0 else "tab:red" if det < 0 else "gray"

    if n == 2:
        corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
        image = corners @ A.T
        ext = set_equal_limits(ax, [embed3(p) for p in image] + [np.ones(3)])
        draw_flat_sheet(ax, ext)
        sq = np.column_stack([corners, np.zeros(4)]); im = np.column_stack([image, np.zeros(4)])
        ax.add_collection3d(Poly3DCollection([sq], facecolor="gray", alpha=0.25, edgecolor="k"))
        ax.add_collection3d(Poly3DCollection([im], facecolor=color, alpha=0.35, edgecolor=color, lw=2))
        quiver3(ax, A[:, 0], "b", f"A e1 = column 1 = {fmt_vec(A[:, 0])}")
        quiver3(ax, A[:, 1], "g", f"A e2 = column 2 = {fmt_vec(A[:, 1])}")
        ax.plot([], [], color="gray", lw=8, alpha=0.4, label="unit square (area 1)")
        ax.plot([], [], color=color, lw=8, alpha=0.5, label=f"image parallelogram (area {abs(det):g})")
        what = "area"
    else:
        V = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
        faces_idx = [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
        image = V @ A.T
        ext = set_equal_limits(ax, list(image) + [np.ones(3)])
        ax.add_collection3d(Poly3DCollection([V[f] for f in faces_idx], facecolor="gray", alpha=0.12, edgecolor="k", lw=0.8))
        ax.add_collection3d(Poly3DCollection([image[f] for f in faces_idx], facecolor=color, alpha=0.25, edgecolor=color, lw=1.5))
        for j, c in enumerate("bgm"):
            quiver3(ax, A[:, j], c, f"A e{j + 1} = column {j + 1} = {fmt_vec(A[:, j])}")
        ax.plot([], [], color="gray", lw=8, alpha=0.4, label="unit cube (volume 1)")
        ax.plot([], [], color=color, lw=8, alpha=0.5, label=f"image parallelepiped (volume {abs(det):g})")
        what = "volume"
    flatten_view(ax, n)
    orient = ("orientation preserved" if det > 0 else "orientation REVERSED (reflection)"
              if det < 0 else f"flattened: {what} 0, A is singular")
    ax.set_title(f"det A = {det:g}:  {what} scale factor {abs(det):g},  {orient}", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()


# ----------------------------------------------------------------------
# linear transformations: shapes and an updatable scene (Transform tab)
# ----------------------------------------------------------------------

SHAPES_2D = ["grid + unit square", "circle", "letter F", "unit square only"]
SHAPES_3D = ["cube + axes", "sphere", "grid on xy-plane + axes", "arrow"]


def transform_shape(name, dim):
    """Return a list of (points (N x dim), style dict) polylines."""
    L = []
    if dim == 2:
        if name.startswith("grid"):
            for k in np.arange(-2, 2.01, 0.5):
                L.append((np.array([[k, -2], [k, 2]]), dict(color="tab:blue", lw=0.6, alpha=0.6)))
                L.append((np.array([[-2, k], [2, k]]), dict(color="tab:blue", lw=0.6, alpha=0.6)))
            L.append((np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]), dict(color="tab:orange", lw=2.5)))
        elif name == "circle":
            t = np.linspace(0, 2 * np.pi, 121)
            L.append((np.column_stack([np.cos(t), np.sin(t)]), dict(color="tab:green", lw=2)))
            for k in range(12):                       # spokes show the twist
                a = k * np.pi / 6
                L.append((np.array([[0, 0], [np.cos(a), np.sin(a)]]), dict(color="tab:green", lw=0.6, alpha=0.5)))
        elif name == "letter F":
            F = np.array([[0, 0], [0, 2], [1.2, 2], [1.2, 1.6], [0.4, 1.6], [0.4, 1.1], [1, 1.1],
                          [1, 0.7], [0.4, 0.7], [0.4, 0], [0, 0]]) - [0.6, 1.0]
            L.append((F, dict(color="tab:purple", lw=2.5)))
        else:
            L.append((np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]), dict(color="tab:orange", lw=2.5)))
        return L
    # ---- 3D --------------------------------------------------------
    if name.startswith("cube"):
        V = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
        for i in range(8):
            for j in range(i + 1, 8):
                if np.sum(np.abs(V[i] - V[j])) == 1:
                    L.append((V[[i, j]], dict(color="tab:orange", lw=2)))
        for j, c in enumerate("bgm"):
            L.append((np.array([[0, 0, 0], np.eye(3)[j] * 1.5]), dict(color=c, lw=2.5)))
    elif name == "sphere":
        u = np.linspace(0, 2 * np.pi, 61)
        for lat in np.linspace(-np.pi / 3, np.pi / 3, 5):
            L.append((np.column_stack([np.cos(lat) * np.cos(u), np.cos(lat) * np.sin(u), np.full_like(u, np.sin(lat))]),
                      dict(color="tab:green", lw=0.8)))
        v = np.linspace(-np.pi / 2, np.pi / 2, 41)
        for lon in np.linspace(0, np.pi, 6, endpoint=False):
            L.append((np.column_stack([np.cos(v) * np.cos(lon), np.cos(v) * np.sin(lon), np.sin(v)]),
                      dict(color="tab:green", lw=0.8)))
    elif name.startswith("grid"):
        for k in np.arange(-2, 2.01, 0.5):
            L.append((np.array([[k, -2, 0], [k, 2, 0]]), dict(color="tab:blue", lw=0.6, alpha=0.6)))
            L.append((np.array([[-2, k, 0], [2, k, 0]]), dict(color="tab:blue", lw=0.6, alpha=0.6)))
        for j, c in enumerate("bgm"):
            L.append((np.array([[0, 0, 0], np.eye(3)[j] * 1.5]), dict(color=c, lw=2.5)))
    else:  # arrow: asymmetric so reflections show
        pts = np.array([[0, -0.3, 0], [1.2, -0.3, 0], [1.2, -0.6, 0], [2, 0, 0], [1.2, 0.6, 0],
                        [1.2, 0.3, 0], [0, 0.3, 0], [0, -0.3, 0]], dtype=float)
        L.append((pts, dict(color="tab:purple", lw=2.5)))
        L.append((pts + [0, 0, 0.5], dict(color="tab:purple", lw=1.5, alpha=0.6)))
        for p in pts[:-1]:
            L.append((np.array([p, p + [0, 0, 0.5]]), dict(color="tab:purple", lw=0.8, alpha=0.6)))
    return L


class TransformScene:
    """Draws a shape and its image under M(t) = (1-t) I + t A, and updates
    the image cheaply for animation."""

    def __init__(self, fig, A, lines, dim):
        self.A = np.asarray(A, dtype=float)
        self.dim = dim
        self.lines = lines
        fig.clear()
        self.ax = ax = fig.add_subplot(111, projection="3d")
        pts = np.vstack([P for P, _ in lines])
        allpts = np.vstack([pts, pts @ self.A.T])
        ext = set_equal_limits(ax, [embed3(p) for p in allpts])
        self.ext = ext
        if dim == 2:
            draw_flat_sheet(ax, ext)
        # ghost of the original
        for P, kw in lines:
            Q = np.array([embed3(p) for p in P])
            ax.plot(Q[:, 0], Q[:, 1], Q[:, 2], color="gray", lw=kw.get("lw", 1) * 0.8, alpha=0.25)
        # moving copies
        self.artists = []
        for P, kw in lines:
            Q = np.array([embed3(p) for p in P])
            art, = ax.plot(Q[:, 0], Q[:, 1], Q[:, 2], **kw)
            self.artists.append(art)
        self.quivers = []
        self.title = ax.set_title("t = 1.00    M(t) = (1-t) I + t A    det M(t) = 0.000",
                                  fontsize=10, pad=12)
        flatten_view(ax, dim)
        ax.plot([], [], color="gray", lw=3, alpha=0.4, label="original")
        ax.plot([], [], color="k", lw=3, label="image under M(t)")
        for j, c in enumerate("bgm"[:dim]):
            ax.plot([], [], color=c, lw=2, label=f"M(t) e{j + 1}")
        ax.legend(loc="upper left", fontsize=8)
        fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.04)
        self.update(1.0)

    def M(self, t):
        return (1 - t) * np.eye(self.dim) + t * self.A

    def update(self, t):
        M = self.M(t)
        for (P, _), art in zip(self.lines, self.artists):
            Q = np.array([embed3(p) for p in P @ M.T])
            art.set_data_3d(Q[:, 0], Q[:, 1], Q[:, 2])
        for q in self.quivers:
            q.remove()
        self.quivers = [quiver3(self.ax, M[:, j], c, linewidth=2)
                        for j, c in enumerate("bgm"[:self.dim])]
        det = np.linalg.det(M)
        self.title.set_text(f"t = {t:.2f}    M(t) = (1-t) I + t A    det M(t) = {det:.3g}")
        return self.artists


# ----------------------------------------------------------------------
# eigenvectors (Eigen tab)
# ----------------------------------------------------------------------

EIG_COLORS = ["tab:red", "tab:blue", "tab:green", "tab:purple"]


def _real_eigvecs(d):
    """[(lambda float, unit vector float, color)] for the real eigenvalues."""
    out = []
    k = 0
    for e in d["eigs"]:
        if not e["real"]:
            continue
        for v in e["vectors"]:
            v = np.array([float(q) for q in v]); v = v / np.linalg.norm(v)
            out.append((float(e["value"]), v, EIG_COLORS[k % len(EIG_COLORS)])); k += 1
    return out


def build_eigen(fig, A, d):
    """n = 2: unit circle and its image with eigen-directions.
    n = 3: eigen-directions with v and Av arrows and the image of a cube edge set."""
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    fig.clear()
    if n not in (2, 3):
        fig.text(0.5, 0.55, f"A is {n}x{n}", ha="center", fontsize=15)
        fig.text(0.5, 0.42, "The picture needs a 2x2 or 3x3 matrix.\nEigenvalues and "
                 "eigenvectors on the left still work.", ha="center", fontsize=11, color="gray")
        return
    ax = fig.add_subplot(111, projection="3d")
    ev = _real_eigvecs(d)
    if n == 2:
        t = np.linspace(0, 2 * np.pi, 181)
        circ = np.column_stack([np.cos(t), np.sin(t)])
        img = circ @ A.T
        ext = set_equal_limits(ax, [embed3(p) for p in img] + [np.ones(3)])
        draw_flat_sheet(ax, ext)
        ax.plot(circ[:, 0], circ[:, 1], 0 * t, color="gray", lw=1, alpha=0.6, label="unit circle")
        ax.plot(img[:, 0], img[:, 1], 0 * t, color="k", lw=1.5, label="its image A x")
    else:
        V = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float) - 0.5
        img = V @ A.T
        ext = set_equal_limits(ax, list(img) + [np.ones(3)] + [lam * v for lam, v, _ in ev])
        first = True
        for i in range(8):
            for j in range(i + 1, 8):
                if np.sum(np.abs(V[i] - V[j])) == 1:
                    ax.plot(*V[[i, j]].T, color="gray", lw=0.8, alpha=0.5, label="cube" if first else None)
                    ax.plot(*img[[i, j]].T, color="k", lw=1, alpha=0.7, label="its image" if first else None)
                    first = False
    for lam, v, c in ev:
        plot_span_line(ax, v, ext, color=c, lw=1, alpha=0.5, linestyle="--")
        quiver3(ax, v, c, f"v = {fmt_vec(np.round(v, 3))}", linewidth=2.5)
        if abs(lam) > 1e-9:
            quiver3(ax, lam * v, c, f"A v = {lam:.4g} v", linewidth=1.2, alpha=0.7)
    flatten_view(ax, n)
    vals = ", ".join(("%.4g" % float(e["value"])) if e["real"] else
                     ("%.3g%+.3gi" % (e["value"].real, e["value"].imag)) for e in d["eigs"])
    note = "" if ev else "   (no real eigenvectors: A turns every direction)"
    ax.set_title(f"eigenvalues: {vals}{note}\ndashed lines = eigen-directions (A keeps them)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()


class EigenSweep:
    """2x2 only: a unit vector x(θ) sweeps the circle; A x(θ) is drawn with
    it, and a strip chart shows the angle between x and A x. Eigenvectors
    are where that angle is 0° (λ > 0) or 180° (λ < 0)."""

    def __init__(self, fig, A, d, n_frames=180):
        self.A = np.asarray(A, dtype=float)
        fig.clear()
        gs = fig.add_gridspec(2, 1, height_ratios=[2.6, 1], hspace=0.3)
        self.ax = ax = fig.add_subplot(gs[0], projection="3d")
        self.ax2 = ax2 = fig.add_subplot(gs[1])
        self.theta = np.linspace(0, 2 * np.pi, n_frames)
        self.xs = np.column_stack([np.cos(self.theta), np.sin(self.theta)])
        self.Axs = self.xs @ self.A.T
        with np.errstate(invalid="ignore", divide="ignore"):
            cosang = np.sum(self.xs * self.Axs, axis=1) / np.linalg.norm(self.Axs, axis=1)
        self.ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        self.ang = np.nan_to_num(self.ang)
        ext = set_equal_limits(ax, [embed3(p) for p in self.Axs] + [np.ones(3)])
        draw_flat_sheet(ax, ext)
        ax.plot(self.xs[:, 0], self.xs[:, 1], 0 * self.theta, color="gray", lw=1, alpha=0.6)
        ax.plot(self.Axs[:, 0], self.Axs[:, 1], 0 * self.theta, color="k", lw=1, alpha=0.4)
        for lam, v, c in _real_eigvecs(d):
            plot_span_line(ax, v, ext, color=c, lw=1, alpha=0.6, linestyle="--")
        flatten_view(ax, 2)
        ax.plot([], [], color="tab:orange", lw=2.5, label="x (unit vector)")
        ax.plot([], [], color="tab:blue", lw=2.5, label="A x")
        ax.legend(loc="upper left", fontsize=8)
        self.title = ax.set_title("θ = 0°", fontsize=10, pad=10)
        ax2.plot(np.degrees(self.theta), self.ang, color="gray", alpha=0.3, lw=2)
        self.line, = ax2.plot([], [], color="tab:blue", lw=2)
        self.marker, = ax2.plot([], [], "ko", ms=6)
        ax2.axhline(0, color="k", lw=0.5); ax2.axhline(180, color="k", lw=0.5)
        ax2.set_xlim(0, 360); ax2.set_ylim(-10, 190); ax2.set_yticks([0, 90, 180])
        ax2.set_xlabel("direction of x, θ (degrees)"); ax2.set_ylabel("angle(x, A x)")
        ax2.set_title("eigenvectors: where the angle is 0° (λ > 0) or 180° (λ < 0)", fontsize=9)
        self.q = []
        fig.subplots_adjust(left=0.08, right=0.97, top=0.93, bottom=0.08)
        self.update(0)

    def update(self, i):
        for q in self.q:
            q.remove()
        x, Ax = self.xs[i], self.Axs[i]
        self.q = [quiver3(self.ax, x, "tab:orange", linewidth=2.5),
                  quiver3(self.ax, Ax, "tab:blue", linewidth=2.5)]
        deg = np.degrees(self.theta)
        self.line.set_data(deg[:i + 1], self.ang[:i + 1])
        self.marker.set_data([deg[i]], [self.ang[i]])
        aligned = self.ang[i] < 2 or self.ang[i] > 178
        self.title.set_text(f"θ = {deg[i]:.0f}°    x = {fmt_vec(np.round(x, 2))}    "
                            f"A x = {fmt_vec(np.round(Ax, 2))}    angle = {self.ang[i]:.0f}°"
                            + ("   <-- EIGENVECTOR" if aligned else ""))
        return self.q + [self.line, self.marker]


# ----------------------------------------------------------------------
# dot / projection / cross product (Vectors tab)
# ----------------------------------------------------------------------

def build_vectors(fig, u, v, w, d):
    """u, v (and w) as arrows; parallelogram of u and v shaded; projection
    of u onto v dashed with its perpendicular dotted; u x v in 3D; w's
    projection onto the plane of u and v when w is given."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    u = np.asarray(u, dtype=float); v = np.asarray(v, dtype=float)
    dim = len(u)
    fig.clear()
    if dim not in (2, 3):
        fig.text(0.5, 0.5, "Pick dimension 2 or 3.", ha="center", fontsize=13, color="gray")
        return
    ax = fig.add_subplot(111, projection="3d")
    vecs = [u, v, u + v]
    if "cross" in d:
        vecs.append(np.array(d["cross"]))
    if w is not None:
        vecs.append(np.asarray(w, dtype=float))
    ext = set_equal_limits(ax, [embed3(p) for p in vecs] + [np.ones(3)])
    if dim == 2:
        draw_flat_sheet(ax, ext)
    U, V = embed3(u), embed3(v)
    para = np.array([np.zeros(3), U, U + V, V])
    ax.add_collection3d(Poly3DCollection([para], facecolor="tab:cyan", alpha=0.2, edgecolor="tab:cyan", lw=1))
    ax.plot([], [], color="tab:cyan", lw=8, alpha=0.4,
            label=f"parallelogram of u, v (area {np.linalg.norm(np.cross(U, V)):.4g})")
    quiver3(ax, u, "r", f"u = {fmt_vec(u)}", linewidth=2.5)
    quiver3(ax, v, "b", f"v = {fmt_vec(v)}", linewidth=2.5)
    if "proj" in d:
        p = embed3(d["proj"]); q = embed3(d["perp"])
        quiver3(ax, p, "orange", f"proj of u onto v = {fmt_vec(np.round(p[:dim], 3))}",
                linewidth=2, linestyle="dashed")
        ax.plot([p[0], U[0]], [p[1], U[1]], [p[2], U[2]], color="orange", linestyle=":", lw=1.5,
                label="perpendicular part of u")
    if "cross" in d:
        c = np.array(d["cross"])
        if np.linalg.norm(c) > 1e-12:
            quiver3(ax, c, "g", f"u x v = {fmt_vec(c)}", linewidth=2.5)
        if np.linalg.norm(np.cross(U, V)) > 1e-12:
            nrm = np.cross(U, V); nrm /= np.linalg.norm(nrm)
            B = _orthonormal([U, V])
            plot_span_plane(ax, B[0], B[1], 1.2 * ext, color="tab:cyan", alpha=0.08)
    if w is not None:
        W = embed3(w)
        quiver3(ax, W, "m", f"w = {fmt_vec(w)}", linewidth=2.5)
        if "w_plane" in d:
            wp = embed3(d["w_plane"])
            quiver3(ax, wp, "m", f"proj of w onto plane = {fmt_vec(np.round(wp, 3))}",
                    linewidth=1.8, linestyle="dashed")
            ax.plot([wp[0], W[0]], [wp[1], W[1]], [wp[2], W[2]], color="m", linestyle=":", lw=1.5)
    flatten_view(ax, dim)
    ttl = f"angle(u, v) = {d['angle']:.4g}°" if "angle" in d else ""
    if "cross" in d:
        ttl += f"     |u x v| = {np.linalg.norm(d['cross']):.4g}"
    ax.set_title(ttl, fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()


# ----------------------------------------------------------------------
# Gram-Schmidt (Orthogonalize tab)
# ----------------------------------------------------------------------

def build_gram_schmidt(fig, V, d):
    """Originals thin, orthogonalized u_i bold in the same colour, the
    subtracted projections dashed, the span shaded."""
    V = np.asarray(V, dtype=float)
    k, dim = V.shape
    fig.clear()
    if dim > MAX_PLOT_DIM:
        fig.text(0.5, 0.55, f"{k} vectors in R^{dim}", ha="center", fontsize=15)
        fig.text(0.5, 0.42, "Plots need vectors in R^1, R^2 or R^3.\nThe algebra on the left "
                 "still works.", ha="center", fontsize=11, color="gray")
        return
    ax = fig.add_subplot(111, projection="3d")
    us = [np.array([float(q) for q in u]) if u is not None else None for u in d["us"]]
    vecs = [V[i] for i in range(k)] + [u for u in us if u is not None]
    ext = set_equal_limits(ax, [embed3(p) for p in vecs] + [np.ones(3)])
    if dim <= 2:
        draw_flat_sheet(ax, ext)
    basis = [u for u in us if u is not None]
    draw_subspace(ax, basis, ext, "c", "span", dim)
    colors = ["tab:red", "tab:blue", "tab:green", "tab:purple", "tab:orange", "tab:brown"]
    for j in range(k):
        c = colors[j % len(colors)]
        quiver3(ax, V[j], c, f"v{j + 1} = {fmt_vec(V[j])}", linewidth=1.2, alpha=0.6)
        if us[j] is not None:
            quiver3(ax, us[j], c, f"u{j + 1} = {fmt_vec(np.round(us[j], 3))}  (orthogonalized)", linewidth=3)
            # the projection that was removed: v_j - u_j, drawn from u_j's tip to v_j's tip
            P, Uj = embed3(V[j]), embed3(us[j])
            if np.linalg.norm(P - Uj) > 1e-9:
                ax.plot([Uj[0], P[0]], [Uj[1], P[1]], [Uj[2], P[2]], color=c, linestyle=":", lw=1.5)
        else:
            ax.plot([], [], " ", label=f"v{j + 1} dependent: dropped")
    flatten_view(ax, dim)
    r = len(basis)
    ax.set_title(f"Gram-Schmidt: {k} vectors -> {r} orthogonal vectors (bold);  dotted = removed projection",
                 fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()


# ----------------------------------------------------------------------
# change of basis (Basis tab)
# ----------------------------------------------------------------------

def _clip_segment(p0, p1, ext):
    """Clip the 2-D segment p0-p1 to the square [-ext, ext]^2 (Liang-Barsky)."""
    p0 = np.asarray(p0, dtype=float); p1 = np.asarray(p1, dtype=float)
    dvec = p1 - p0
    t0, t1 = 0.0, 1.0
    for axis in (0, 1):
        for sign, bound in ((-1.0, -ext), (1.0, ext)):
            p = sign * dvec[axis]
            q = bound - p0[axis] if sign > 0 else p0[axis] + ext
            if p == 0:
                if q < 0:
                    return None
                continue
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return None
    return p0 + t0 * dvec, p0 + t1 * dvec


def build_basis(fig, B, x, d):
    """Basis arrows, the skewed B-grid (2D), and x as a path of basis
    steps c1 b1 then c2 b2 ..."""
    B = np.asarray(B, dtype=float); x = np.asarray(x, dtype=float)
    n = B.shape[0]
    fig.clear()
    if n not in (2, 3) or not d.get("ok"):
        msg = f"R^{n}: the picture needs n = 2 or 3." if n not in (2, 3) else "Not a basis: nothing to draw."
        fig.text(0.5, 0.5, msg, ha="center", fontsize=13, color="gray")
        return
    ax = fig.add_subplot(111, projection="3d")
    c = np.array(d["coords"])
    vecs = [B[i] for i in range(n)] + [x] + [B[i] * c[i] for i in range(n)]
    ext = set_equal_limits(ax, [embed3(p) for p in vecs] + [np.ones(3)])
    if n == 2:
        draw_flat_sheet(ax, ext)
        m = int(np.ceil(ext / max(np.linalg.norm(B, axis=1).min(), 1e-9))) + 1
        m = min(m, 12)
        for k in range(-m, m + 1):                      # B-grid: lines k b1 + t b2 and t b1 + k b2
            for a, b in ((B[0], B[1]), (B[1], B[0])):
                seg = _clip_segment(k * a - m * b, k * a + m * b, ext)
                if seg is not None:
                    (x0, y0), (x1, y1) = seg
                    ax.plot([x0, x1], [y0, y1], [0, 0], color="tab:cyan", lw=0.6, alpha=0.6)
        ax.plot([], [], color="tab:cyan", lw=1.5, label="grid of the new basis")
    colors = ["tab:blue", "tab:green", "tab:purple"]
    for i in range(n):
        quiver3(ax, B[i], colors[i], f"b{i + 1} = {fmt_vec(B[i])}", linewidth=2.5)
    quiver3(ax, x, "r", f"x = {fmt_vec(x)} = " + " + ".join(f"({c[i]:g}) b{i + 1}" for i in range(n)), linewidth=2.5)
    # staircase path: c1 b1, then + c2 b2, ...
    pos = np.zeros(3)
    for i in range(n):
        step = embed3(B[i] * c[i])
        if np.linalg.norm(step) > 1e-12:
            ax.plot([pos[0], pos[0] + step[0]], [pos[1], pos[1] + step[1]], [pos[2], pos[2] + step[2]],
                    color=colors[i], linestyle="--", lw=1.8,
                    label=(f"{c[i]:g} b{i + 1}" if i == 0 else
                           f"{'+' if c[i] >= 0 else '-'} {abs(c[i]):g} b{i + 1}"))
        pos = pos + step
    flatten_view(ax, n)
    ax.set_title("x in the new basis: [x]_B = " + fmt_vec(np.round(c, 4)) +
                 "   (dashed: the steps c1 b1, c2 b2, ... that reach x)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()


# ----------------------------------------------------------------------
# matrix powers / Markov (Powers tab)
# ----------------------------------------------------------------------

def build_powers(fig, A, d):
    """Top: the trajectory x0, x1, ... in state space (n = 2, 3) with the
    real eigen-directions dashed. Bottom: each component of x_j against j,
    with the Markov steady state as horizontal lines when present."""
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    traj = d["traj"]
    k = traj.shape[0] - 1
    fig.clear()
    if n in (2, 3):
        gs = fig.add_gridspec(2, 1, height_ratios=[2.2, 1], hspace=0.35)
        ax = fig.add_subplot(gs[0], projection="3d")
        ax2 = fig.add_subplot(gs[1])
        pts = np.array([embed3(p) for p in traj])
        ext = set_equal_limits(ax, list(pts) + [np.ones(3) * 1e-9])
        if n == 2:
            draw_flat_sheet(ax, ext)
        for lam, v, c in _real_eigvecs(d["eig"]):
            plot_span_line(ax, v, ext, color=c, lw=1, alpha=0.6, linestyle="--",
                           label=f"eigen-direction, λ = {lam:.3g}")
        ax.plot(pts[:, 0], pts[:, 1], pts[:, 2], color="k", lw=1, alpha=0.5)
        cols = np.linspace(0.15, 1.0, k + 1)
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], c=cols, cmap="viridis", s=30, depthshade=False)
        quiver3(ax, traj[0], "tab:orange", "x0", linewidth=2.5)
        quiver3(ax, traj[-1], "tab:purple", f"x_{k}", linewidth=2.5)
        if "steady" in d:
            s = embed3(d["steady"] * traj[0].sum())
            ax.scatter([s[0]], [s[1]], [s[2]], color="r", marker="*", s=160, label="steady state")
        flatten_view(ax, n)
        ax.set_title(f"x_j = A^j x0 for j = 0..{k}   (dark -> bright = later steps)", fontsize=10)
        ax.legend(loc="upper left", fontsize=8)
    else:
        ax2 = fig.add_subplot(111)
    js = np.arange(k + 1)
    for i in range(n):
        ax2.plot(js, traj[:, i], marker="o", ms=3, lw=1.5, label=f"component {i + 1}")
        if "steady" in d:
            ax2.axhline(d["steady"][i] * traj[0].sum(), color=f"C{i}", linestyle=":", lw=1)
    if "steady" in d:
        ax2.plot([], [], color="gray", linestyle=":", label="steady state")
    ax2.set_xlabel("step j"); ax2.set_ylabel("entries of x_j")
    ax2.set_title("components of x_j against j", fontsize=9)
    ax2.legend(loc="best", fontsize=8)
    ax2.grid(alpha=0.3)
    if n in (2, 3):
        fig.subplots_adjust(left=0.1, right=0.97, top=0.94, bottom=0.08)
    else:
        fig.tight_layout()


# ----------------------------------------------------------------------
# SVD picture (SVD tab)
# ----------------------------------------------------------------------

def _unit_shape(n):
    """Polylines tracing the unit circle (n=2) or a sphere wireframe (n=3)
    plus the standard basis arrows, as (points, style) pairs."""
    L = []
    if n == 2:
        t = np.linspace(0, 2 * np.pi, 121)
        L.append((np.column_stack([np.cos(t), np.sin(t)]), dict(color="k", lw=1.5)))
    else:
        u = np.linspace(0, 2 * np.pi, 61)
        for lat in np.linspace(-np.pi / 3, np.pi / 3, 5):
            L.append((np.column_stack([np.cos(lat) * np.cos(u), np.cos(lat) * np.sin(u), np.full_like(u, np.sin(lat))]),
                      dict(color="k", lw=0.6, alpha=0.6)))
        v = np.linspace(-np.pi / 2, np.pi / 2, 41)
        for lon in np.linspace(0, np.pi, 6, endpoint=False):
            L.append((np.column_stack([np.cos(v) * np.cos(lon), np.cos(v) * np.sin(lon), np.sin(v)]),
                      dict(color="k", lw=0.6, alpha=0.6)))
    return L


def _draw_stage(ax, lines, M, arrows, ext, dim, title):
    """Draw shape lines transformed by M and a list of (vector, color, label) arrows."""
    if dim == 2:
        draw_flat_sheet(ax, ext)
    for P, kw in lines:
        Q = np.array([embed3(p) for p in P @ M.T])
        ax.plot(Q[:, 0], Q[:, 1], Q[:, 2], **kw)
    for vec, c, label in arrows:
        if np.linalg.norm(vec) > 1e-12:
            quiver3(ax, vec, c, label, linewidth=2.2)
    set_equal_limits(ax, [np.ones(3) * ext])
    flatten_view(ax, dim)
    ax.set_title(title, fontsize=9)
    ax.legend(loc="upper left", fontsize=7)


def build_svd(fig, A, d):
    """Square 2x2 / 3x3: four stages (identity, V^T, Σ V^T, U Σ V^T = A).
    Other shapes with m, n <= 3: domain with v_i and codomain with σ_i u_i."""
    A = np.asarray(A, dtype=float)
    m, n = A.shape
    U, sv, Vt = d["U"], d["s"], d["Vt"]
    fig.clear()
    if m > MAX_PLOT_DIM or n > MAX_PLOT_DIM:
        draw_unplottable(fig, A)
        return
    cols = ["tab:red", "tab:blue", "tab:green"]
    if m == n:
        lines = _unit_shape(n)
        S = np.diag(sv)
        ext = 1.15 * max(sv.max(), 1.0)
        stages = [
            (np.eye(n), [(Vt[i], cols[i], f"v{i + 1}") for i in range(n)], "1. unit shape with v1, v2, ... (right singular vectors)"),
            (Vt, [(Vt @ Vt[i], cols[i], f"Vᵀ v{i + 1} = e{i + 1}") for i in range(n)], "2. after Vᵀ: the v_i now sit on the axes"),
            (S @ Vt, [(S @ (Vt @ Vt[i]), cols[i], f"σ{i + 1} e{i + 1}") for i in range(n)], "3. after Σ Vᵀ: stretched along the axes by σ_i"),
            (A, [(A @ Vt[i], cols[i], f"A v{i + 1} = σ{i + 1} u{i + 1}") for i in range(n)], "4. after U Σ Vᵀ = A: rotated into place"),
        ]
        for k, (M, arrows, title) in enumerate(stages):
            ax = fig.add_subplot(2, 2, k + 1, projection="3d")
            _draw_stage(ax, lines, M, arrows, ext, n, title)
        fig.suptitle(f"A = U Σ Vᵀ,  σ = {', '.join(f'{v:.3g}' for v in sv)}", fontsize=12)
        fig.subplots_adjust(left=0.03, right=0.97, top=0.9, bottom=0.03, wspace=0.05, hspace=0.2)
        return
    # non-square: domain and codomain
    ax1 = fig.add_subplot(121, projection="3d")
    _draw_stage(ax1, _unit_shape(n) if n >= 2 else [], np.eye(n),
                [(Vt[i], cols[i], f"v{i + 1}") for i in range(n)], 1.15, n,
                f"domain R^{n}: unit shape and the v_i")
    ax2 = fig.add_subplot(122, projection="3d")
    ext = 1.15 * max(sv.max(), 1.0)
    _draw_stage(ax2, _unit_shape(n) if n >= 2 else [], A,
                [(sv[i] * U[:, i], cols[i], f"σ{i + 1} u{i + 1}") for i in range(min(m, n))], ext, m,
                f"codomain R^{m}: its image, an ellipse with semi-axes σ_i along u_i")
    fig.suptitle(f"A = U Σ Vᵀ,  σ = {', '.join(f'{v:.3g}' for v in sv)}", fontsize=12)
    fig.tight_layout()


# ----------------------------------------------------------------------
# least-squares fit (Fit tab) -- an ordinary 2-D axes
# ----------------------------------------------------------------------

def build_fit(fig, d):
    """Scatter of the data, the fitted curve, and each residual as a
    vertical dashed drop; a small residual plot beneath."""
    fig.clear()
    xs, ys, c = d["xs"], d["ys"], d["c"]
    gs = fig.add_gridspec(2, 1, height_ratios=[2.6, 1], hspace=0.35)
    ax = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax)
    span = (xs.max() - xs.min()) or 1.0
    xx = np.linspace(xs.min() - 0.1 * span, xs.max() + 0.1 * span, 300)
    yy = sum(c[j] * xx ** j for j in range(len(c)))
    ax.plot(xx, yy, color="tab:blue", lw=2, label="least-squares fit")
    ax.scatter(xs, ys, color="k", zorder=3, label="data")
    if "yhat" in d:
        for x, y, yh in zip(xs, ys, d["yhat"]):
            ax.plot([x, x], [y, yh], color="tab:red", linestyle="--", lw=1)
        ax.plot([], [], color="tab:red", linestyle="--", label="residuals")
        ax.scatter(xs, d["yhat"], color="tab:blue", s=18, zorder=3)
        ax2.bar(xs, d["res"], width=0.06 * span, color="tab:red", alpha=0.7)
        ax2.axhline(0, color="k", lw=0.8)
        ax2.set_ylabel("residual"); ax2.set_title(f"residuals (sum of squares = {d['sse']:.4g})", fontsize=9)
    ax2.set_xlabel("x"); ax.set_ylabel("y"); ax.grid(alpha=0.3); ax2.grid(alpha=0.3)
    terms = " + ".join(f"{c[j]:.4g}" + ("" if j == 0 else " x" + (f"^{j}" if j > 1 else "")) for j in range(len(c)))
    ax.set_title(f"degree {d['degree']} fit to {d['k']} points:   y = {terms}", fontsize=10)
    ax.legend(loc="best", fontsize=8)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.93, bottom=0.08)


# ----------------------------------------------------------------------
# complex eigenvalues: rotation-scaling picture (Complex Eigen tab)
# ----------------------------------------------------------------------

def build_complex_eigen(fig, A, d, upto=None):
    """Left: standard plane with Re v, Im v, the ellipse P(unit circle)
    and the trajectory x_j. Right: P-coordinates u_j = P^-1 x_j, where
    the same points sit on a true spiral (or circle) turning by φ."""
    fig.clear()
    if not d.get("ok"):
        fig.text(0.5, 0.55, "Real eigenvalues: no rotation to draw.", ha="center", fontsize=14)
        fig.text(0.5, 0.45, "Pick a preset or enter a 2x2 with trace² < 4·det.", ha="center", fontsize=11, color="gray")
        return
    traj, utraj = d["traj"], d["utraj"]
    k = traj.shape[0] - 1
    n_show = k + 1 if upto is None else min(upto + 1, k + 1)
    P, r, phi = d["P"], d["r"], d["phi"]
    t = np.linspace(0, 2 * np.pi, 181)
    circ = np.column_stack([np.cos(t), np.sin(t)])
    ax1 = fig.add_subplot(121); ax2 = fig.add_subplot(122)
    # left: standard coordinates
    s0 = np.linalg.norm(utraj[0])
    ell = (circ * s0) @ P.T
    ax1.plot(ell[:, 0], ell[:, 1], color="tab:cyan", lw=1.2, label="ellipse P(circle) through x0")
    ax1.annotate("", xy=d["Re"], xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="tab:blue", lw=2))
    ax1.annotate("", xy=d["Im"], xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="tab:green", lw=2))
    ax1.plot([], [], color="tab:blue", lw=2, label=f"Re v = {fmt_vec(np.round(d['Re'], 3))}")
    ax1.plot([], [], color="tab:green", lw=2, label=f"Im v = {fmt_vec(np.round(d['Im'], 3))}")
    ax1.plot(traj[:n_show, 0], traj[:n_show, 1], color="k", lw=0.8, alpha=0.5)
    ax1.scatter(traj[:n_show, 0], traj[:n_show, 1], c=np.arange(n_show), cmap="viridis", s=36, zorder=3)
    for j in range(min(n_show, 6)):
        ax1.annotate(str(j), traj[j], textcoords="offset points", xytext=(4, 4), fontsize=8)
    lim = 1.15 * max(np.abs(ell).max(), np.abs(traj).max(), 1e-9)
    ax1.set_xlim(-lim, lim); ax1.set_ylim(-lim, lim); ax1.set_aspect("equal"); ax1.grid(alpha=0.3)
    ax1.axhline(0, color="k", lw=0.5); ax1.axvline(0, color="k", lw=0.5)
    ax1.set_title("standard coordinates: x_j = A^j x0 (skewed spiral on an ellipse)", fontsize=9)
    ax1.legend(loc="upper left", fontsize=7)
    # right: P-coordinates
    ax2.plot(circ[:, 0] * s0, circ[:, 1] * s0, color="tab:cyan", lw=1.2, label="circle |u| = |u0|")
    spiral_t = np.linspace(0, k, 400)
    sp = np.array([(r ** tt) * s0 * np.array([np.cos(np.radians(phi) * tt + np.arctan2(utraj[0, 1], utraj[0, 0])),
                                             np.sin(np.radians(phi) * tt + np.arctan2(utraj[0, 1], utraj[0, 0]))]) for tt in spiral_t])
    ax2.plot(sp[:, 0], sp[:, 1], color="gray", lw=0.8, alpha=0.6, label=f"r^t x rotation by φ t")
    ax2.scatter(utraj[:n_show, 0], utraj[:n_show, 1], c=np.arange(n_show), cmap="viridis", s=36, zorder=3)
    for j in range(min(n_show, 6)):
        ax2.annotate(str(j), utraj[j], textcoords="offset points", xytext=(4, 4), fontsize=8)
    lim2 = 1.15 * max(np.abs(utraj).max(), s0, 1e-9)
    ax2.set_xlim(-lim2, lim2); ax2.set_ylim(-lim2, lim2); ax2.set_aspect("equal"); ax2.grid(alpha=0.3)
    ax2.axhline(0, color="k", lw=0.5); ax2.axvline(0, color="k", lw=0.5)
    ax2.set_title(f"P-coordinates u_j = P⁻¹ x_j: rotate by {phi:.3g}°, scale by {r:.3g} each step", fontsize=9)
    ax2.legend(loc="upper left", fontsize=7)
    fig.suptitle(f"λ = {d['a']:.3g} ± {d['b']:.3g} i,   |λ| = {r:.3g},   φ = {phi:.3g}°,   A = P C P⁻¹", fontsize=11)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.08, wspace=0.2)
