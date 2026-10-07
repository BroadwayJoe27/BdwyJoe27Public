"""
core.py -- math, step-by-step text, and the saved-matrix library for
MatrixLab.  Nothing here touches matplotlib or tkinter, so it is easy to
test.

Sections:
  * number parsing / formatting
  * the adjoint identity  (A x) . y = x . (A^T y)   (Transpose-Dot tab)
  * matrix products AB and BA                        (Multiply tab)
  * MatrixLibrary: named JSON files holding A and, optionally, x, y, B
"""

import json
import math
import threading
import os
import re
from fractions import Fraction

import numpy as np

# ----------------------------------------------------------------------
# Number parsing / formatting
# ----------------------------------------------------------------------

def parse_number(text):
    """Turn a cell's text into a float. Accepts ints, decimals, and
    fractions such as '1/2' or '-3/4'. Blank counts as 0."""
    s = text.strip()
    if s == "":
        return 0.0
    if re.fullmatch(r"[+-]?\d+\s*/\s*\d+", s):
        return float(Fraction(s.replace(" ", "")))
    return float(s)


def fmt(v):
    """Compact number formatting: 2.0 -> '2', 0.5 -> '0.5'."""
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.4g}"


def fmt_vec(v):
    return "[" + " ".join(fmt(a) for a in v) + "]"


def fmt_mat(M, indent="  "):
    cells = [[fmt(a) for a in row] for row in M]
    width = max(len(c) for row in cells for c in row)
    return "\n".join(indent + "[ " + "  ".join(c.rjust(width) for c in row) + " ]"
                     for row in cells)


# ----------------------------------------------------------------------
# The identity, step by step
# ----------------------------------------------------------------------

def compute(A, x, y):
    """Return (Ax, ATy, lhs, rhs) for the adjoint identity."""
    A = np.asarray(A, dtype=float)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    Ax = A @ x
    ATy = A.T @ y
    return Ax, ATy, float(Ax @ y), float(x @ ATy)


def subspaces(A, tol=1e-9):
    """Orthonormal bases for the row space and null space of A (via SVD).
    Returns (rank, row_basis (r x n), null_basis ((n-r) x n))."""
    A = np.asarray(A, dtype=float)
    _, s, Vt = np.linalg.svd(A)
    rank = int(np.sum(s > tol * max(1.0, s[0] if len(s) else 1.0)))
    return rank, Vt[:rank], Vt[rank:]


def steps_text(A, x, y):
    """Every arithmetic step of both sides, as one string."""
    A = np.asarray(A, dtype=float)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m, n = A.shape
    Ax, ATy, lhs, rhs = compute(A, x, y)
    bar = "=" * 60
    out = []

    out += [bar, "THE SETUP", bar,
            f"A ({m}x{n}) maps R^{n} -> R^{m}:", fmt_mat(A), "",
            f"x in R^{n} = {fmt_vec(x)}",
            f"y in R^{m} = {fmt_vec(y)}", ""]

    out += [bar, f"LEFT SIDE:  (A x) . y      [computed in R^{m}]", bar,
            "Step 1: A x  -- each entry is a ROW of A dotted with x:"]
    for i, row in enumerate(A):
        terms = " + ".join(f"{fmt(a)}*{fmt(b)}" for a, b in zip(row, x))
        out.append(f"   row {i + 1}: ({terms}) = {fmt(row @ x)}")
    out.append(f"   =>  A x = {fmt_vec(Ax)}   (a vector in R^{m})")
    terms = " + ".join(f"{fmt(a)}*{fmt(b)}" for a, b in zip(Ax, y))
    out += [f"Step 2: (A x) . y = {terms} = {fmt(lhs)}", ""]

    out += [bar, f"RIGHT SIDE:  x . (A^T y)   [computed in R^{n}]", bar,
            f"Step 1: A^T ({n}x{m}) =", fmt_mat(A.T), "",
            "Step 2: A^T y  -- a weighted sum of the ROWS of A",
            "        (the rows of A are the columns of A^T):"]
    parts = "  +  ".join(f"{fmt(y[i])}*{fmt_vec(A[i])}" for i in range(m))
    out += [f"   A^T y = {parts}",
            f"         = {fmt_vec(ATy)}   (a vector in R^{n}, inside A's row space)"]
    terms = " + ".join(f"{fmt(a)}*{fmt(b)}" for a, b in zip(x, ATy))
    out += [f"Step 3: x . (A^T y) = {terms} = {fmt(rhs)}", ""]

    out += [bar,
            f"IDENTITY CHECK:  (A x) . y = {fmt(lhs)}   and   x . (A^T y) = {fmt(rhs)}",
            f"Equal? {np.isclose(lhs, rhs)}", bar, ""]

    rank, _, null_basis = subspaces(A)
    out += ["GEOMETRY",
            f"rank(A) = {rank}",
            f"row space of A: a {rank}-dimensional subspace of R^{n}",
            f"null space of A: a {n - rank}-dimensional subspace of R^{n}, "
            "orthogonal to the row space"]
    if n - rank > 0:
        x_null = sum((x @ b) * b for b in null_basis)
        x_row = x - x_null
        out += [f"x = (row-space part) + (null-space part)",
                f"  = {fmt_vec(x_row)} + {fmt_vec(x_null)}",
                "Only the row-space part of x contributes to the dot product:",
                f"  (row-space part) . (A^T y) = {fmt(x_row @ ATy)}",
                f"  (null-space part) . (A^T y) = {fmt(x_null @ ATy)}   (always 0)"]
    else:
        out.append("The null space is {0}: all of x contributes to the dot product.")
    return "\n".join(out)


# ----------------------------------------------------------------------
# Matrix products
# ----------------------------------------------------------------------

def product_text(name, L, R, lname, rname, show_entries=True):
    """Describe the product L R (or why it is undefined)."""
    L = np.asarray(L, dtype=float); R = np.asarray(R, dtype=float)
    (a, b), (c, d) = L.shape, R.shape
    head = f"{name}:  ({a}x{b})({c}x{d})"
    if b != c:
        return [head,
                f"   UNDEFINED -- {lname} has {b} columns but {rname} has "
                f"{c} rows; the inner dimensions must match.", ""]
    P = L @ R
    out = [head + f"  ->  {a}x{d}", fmt_mat(P), ""]
    if show_entries:
        out.append(f"   each entry = (row of {lname}) . (column of {rname}):")
        for i in range(a):
            for j in range(d):
                terms = " + ".join(f"{fmt(u)}*{fmt(v)}" for u, v in zip(L[i], R[:, j]))
                out.append(f"   ({i + 1},{j + 1}):  {terms} = {fmt(P[i, j])}")
        out.append("")
    return out


def multiply_text(A, B, show_entries=True, k=None):
    """AB and BA in matrix form, with dimension bookkeeping; with a scalar
    k, the scalar products kA and kB and the (kA)B = k(AB) identity."""
    A = np.asarray(A, dtype=float); B = np.asarray(B, dtype=float)
    m, n = A.shape; n2, p = B.shape
    bar = "=" * 60
    out = [bar, "THE MATRICES", bar,
           f"A ({m}x{n}) =", fmt_mat(A), "",
           f"B ({n2}x{p}) =", fmt_mat(B), ""]
    if k is not None and k != 1:
        kf = to_fraction(k)
        out += [bar, f"SCALAR MULTIPLICATION  k = {fmt_frac(kf)}", bar,
                "A scalar multiplies EVERY entry (no size condition):", f"k A ({m}x{n}) ="]
        if show_entries:
            out.append("\n".join("  [ " + "  ".join(f"{fmt_frac(kf)}*{fmt(a)} = {fmt(k * a)}" for a in row) + " ]"
                                for row in A))
        else:
            out.append(fmt_mat(k * A))
        out += [f"k B ({n2}x{p}) =", fmt_mat(k * B)]
        if n == n2:
            out += ["", "Scalars slide through products:  (kA) B = k (AB) = A (kB)",
                    f"   (kA) B =", fmt_mat((k * A) @ B),
                    f"   k (AB) =", fmt_mat(k * (A @ B)), "   equal  ✓"]
        out.append("")
    out += [bar, "AB", bar]
    out += product_text("AB", A, B, "A", "B", show_entries)
    out += [bar, "BA", bar]
    out += product_text("BA", B, A, "B", "A", show_entries)
    if n == n2 and p == m:
        AB, BA = A @ B, B @ A
        out += [bar]
        if AB.shape == BA.shape:
            if np.allclose(AB, BA):
                out.append("AB = BA: these two matrices COMMUTE.")
            else:
                out += ["AB != BA: matrix multiplication is not commutative.",
                        "AB - BA =", fmt_mat(AB - BA)]
        else:
            out.append(f"AB is {AB.shape[0]}x{AB.shape[1]} but BA is "
                       f"{BA.shape[0]}x{BA.shape[1]}: different sizes, "
                       "so they can't be equal.")
    return "\n".join(out)


# ----------------------------------------------------------------------
# Row reduction (Gauss-Jordan) in exact fractions
# ----------------------------------------------------------------------

def to_fraction(v):
    """Exact fraction for a typed number (0.5 -> 1/2, 0.3333 -> 1/3)."""
    return Fraction(float(v)).limit_denominator(10 ** 6)


def fmt_frac(q):
    q = Fraction(q)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def fmt_frac_mat(M, indent="  ", bar_after=None, pivots=()):
    """Matrix of Fractions as text. bar_after=k draws | after column k
    (augmented matrices). pivots: set of (i, j) to mark with a star."""
    cells = [[fmt_frac(v) for v in row] for row in M]
    width = max(len(c) for row in cells for c in row) + (1 if pivots else 0)
    lines = []
    for i, row in enumerate(cells):
        parts = []
        for j, c in enumerate(row):
            if (i, j) in pivots:
                c = c + "*"
            parts.append(c.rjust(width))
            if bar_after is not None and j == bar_after - 1 and j < len(row) - 1:
                parts.append("|")
        lines.append(indent + "[ " + "  ".join(parts) + " ]")
    return "\n".join(lines)


def _coef(q):
    """Coefficient text for 'R2 - 3 R1' style descriptions."""
    q = Fraction(q)
    return "" if q == 1 else fmt_frac(q) + " "


def rref_steps(M, ncols=None):
    """Gauss-Jordan elimination with every elementary row operation logged.

    M      : matrix (any numbers; converted to Fractions)
    ncols  : reduce only the first ncols columns (for augmented [A | b])

    Returns (R, pivot_cols, steps) where steps is a list of
    (description, snapshot) and snapshot is the matrix after that step.
    A description starting with '--' is a milestone, not an operation.
    """
    R = [[to_fraction(v) for v in row] for row in M]
    m = len(R); n = len(R[0])
    if ncols is None:
        ncols = n
    steps = []
    pivots = []          # (row, col)
    r = 0

    # ---- forward phase: echelon form --------------------------------
    for c in range(ncols):
        if r >= m:
            break
        p = next((i for i in range(r, m) if R[i][c] != 0), None)
        if p is None:
            steps.append((f"-- column {c + 1}: no nonzero entry at or below "
                          f"row {r + 1}; no pivot here (free column)", None))
            continue
        if p != r:
            R[r], R[p] = R[p], R[r]
            steps.append((f"R{r + 1} <-> R{p + 1}   (bring a nonzero entry "
                          f"into the pivot position)", [row[:] for row in R]))
        if R[r][c] != 1:
            f = Fraction(1, 1) / R[r][c]
            R[r] = [v * f for v in R[r]]
            steps.append((f"R{r + 1} <- ({fmt_frac(f)}) R{r + 1}   (make the "
                          f"pivot 1)", [row[:] for row in R]))
        for i in range(r + 1, m):
            if R[i][c] != 0:
                k = R[i][c]
                R[i] = [a - k * b for a, b in zip(R[i], R[r])]
                sign = "-" if k > 0 else "+"
                steps.append((f"R{i + 1} <- R{i + 1} {sign} {_coef(abs(k))}R{r + 1}"
                              f"   (clear below the pivot)", [row[:] for row in R]))
        pivots.append((r, c))
        r += 1
    steps.append(("-- ROW ECHELON FORM reached: pivots are 1, zeros below "
                  "each pivot", [row[:] for row in R]))

    # ---- backward phase: reduced form --------------------------------
    for (pr, pc) in reversed(pivots):
        for i in range(pr - 1, -1, -1):
            if R[i][pc] != 0:
                k = R[i][pc]
                R[i] = [a - k * b for a, b in zip(R[i], R[pr])]
                sign = "-" if k > 0 else "+"
                steps.append((f"R{i + 1} <- R{i + 1} {sign} {_coef(abs(k))}R{pr + 1}"
                              f"   (clear above the pivot)", [row[:] for row in R]))
    steps.append(("-- REDUCED ROW ECHELON FORM reached: zeros above and below "
                  "every pivot", [row[:] for row in R]))
    return R, [c for _, c in pivots], steps


def null_space_from_rref(R, pivot_cols, n):
    """Basis vectors (lists of Fractions) of the null space read off RREF."""
    free = [j for j in range(n) if j not in pivot_cols]
    basis = []
    for f in free:
        v = [Fraction(0)] * n
        v[f] = Fraction(1)
        for i, pc in enumerate(pivot_cols):
            v[pc] = -R[i][f]
        basis.append(v)
    return free, basis


def rref_text(A):
    """Full narrated row reduction of A."""
    A = np.asarray(A, dtype=float)
    m, n = A.shape
    R, pivot_cols, steps = rref_steps(A)
    bar = "=" * 60
    out = [bar, f"ROW REDUCTION OF A ({m}x{n})", bar,
           "Start:", fmt_frac_mat([[to_fraction(v) for v in row] for row in A]), ""]
    k = 0
    for desc, snap in steps:
        if desc.startswith("--"):
            out += [desc[3:].strip(), ""]
            if snap is not None and "FORM" in desc:
                out += [fmt_frac_mat(snap), ""]
            continue
        k += 1
        out += [f"Step {k}:  {desc}", fmt_frac_mat(snap), ""]
    if k == 0:
        out += ["(A was already in reduced row echelon form)", ""]

    pivots = {(i, c) for i, c in enumerate(pivot_cols)}
    out += [bar, "READING OFF THE RESULT", bar,
            "RREF(A) with pivots starred:", fmt_frac_mat(R, pivots=pivots), "",
            f"pivot columns : {', '.join(str(c + 1) for c in pivot_cols) or 'none'}",
            f"rank(A)       : {len(pivot_cols)}"]
    free, basis = null_space_from_rref(R, pivot_cols, n)
    out.append(f"free columns  : {', '.join(str(c + 1) for c in free) or 'none'}")
    out.append(f"nullity       : {len(free)}     (rank + nullity = {len(pivot_cols)} + "
               f"{len(free)} = {n} = number of columns)")
    out.append("")
    if basis:
        out.append("Null space of A: set each free variable to 1 (others 0) and read")
        out.append("the pivot variables from RREF. Basis vectors:")
        for f, v in zip(free, basis):
            out.append(f"   x{f + 1} free ->  [{' '.join(fmt_frac(q) for q in v)}]")
        out.append("")
        out.append("Every solution of A x = 0 is a combination of these vectors.")
    else:
        out.append("No free columns: the null space is {0}. The columns of A are")
        out.append("linearly independent and A x = 0 only for x = 0.")
    if len(pivot_cols) == m:
        out.append(f"Every row has a pivot: the rows are independent and A x = b is")
        out.append(f"solvable for every b in R^{m}.")
    else:
        out.append(f"{m - len(pivot_cols)} zero row(s) in RREF: A x = b is solvable only "
                   f"for b in the {len(pivot_cols)}-dimensional column space.")
    return "\n".join(out)


# ----------------------------------------------------------------------
# LU factorization  PA = LU  (Row Reduce and Solve tabs)
# ----------------------------------------------------------------------

def _side_by_side(blocks, gap="    "):
    """Lay out text blocks [(title, text), ...] next to each other."""
    cols = [[title] + text.splitlines() for title, text in blocks]
    widths = [max(len(s) for s in col) for col in cols]
    h = max(len(col) for col in cols)
    return "\n".join(gap.join(col[i].ljust(w) if i < len(col) else " " * w
                              for col, w in zip(cols, widths)).rstrip()
                     for i in range(h))


def lu_steps(M):
    """Forward elimination with row replacements (no scaling), recording
    each multiplier in L. A row swap is made only when the pivot position
    holds 0. Works for any m x n.

    Returns (L, U, perm, steps): L unit lower triangular m x m, U echelon
    m x n, perm the row order so that PA = LU with P[i][perm[i]] = 1,
    steps a list of (description, U snapshot, L snapshot)."""
    U = [[to_fraction(v) for v in row] for row in M]
    m = len(U); n = len(U[0])
    L = [[Fraction(int(i == j)) for j in range(m)] for i in range(m)]
    perm = list(range(m))
    steps = []
    r = 0
    for c in range(n):
        if r >= m:
            break
        p = next((i for i in range(r, m) if U[i][c] != 0), None)
        if p is None:
            steps.append((f"-- column {c + 1}: nothing nonzero at or below row {r + 1}; "
                          "no pivot in this column", None, None))
            continue
        if p != r:
            U[r], U[p] = U[p], U[r]
            perm[r], perm[p] = perm[p], perm[r]
            L[r][:r], L[p][:r] = L[p][:r], L[r][:r]
            steps.append((f"R{r + 1} <-> R{p + 1}   (zero in the pivot position: swap, "
                          "recorded in P; multipliers already in L swap too)",
                          [row[:] for row in U], [row[:] for row in L]))
        for i in range(r + 1, m):
            if U[i][c] != 0:
                k = U[i][c] / U[r][c]
                U[i] = [a - k * b for a, b in zip(U[i], U[r])]
                L[i][r] = k
                sign = "-" if k > 0 else "+"
                steps.append((f"R{i + 1} <- R{i + 1} {sign} {_coef(abs(k))}R{r + 1}"
                              f"   multiplier l{i + 1}{r + 1} = {fmt_frac(k)} goes into L",
                              [row[:] for row in U], [row[:] for row in L]))
        r += 1
    return L, U, perm, steps


def perm_matrix(perm):
    m = len(perm)
    return [[Fraction(int(perm[i] == j)) for j in range(m)] for i in range(m)]


def _matmul_frac(A, B):
    return [[sum(a * b for a, b in zip(row, col)) for col in zip(*B)] for row in A]


def _lu_factor_lines(A, L, U, perm, steps, show_steps=True, indent=""):
    """Narration shared by lu_text and lu_solve_text."""
    Af = [[to_fraction(v) for v in row] for row in A]
    out = []
    k = 0
    for desc, snapU, snapL in steps:
        if desc.startswith("--"):
            if show_steps:
                out += [indent + desc[3:].strip(), ""]
            continue
        k += 1
        if show_steps:
            out += [f"{indent}Step {k}:  {desc}",
                    _side_by_side([("L so far", fmt_frac_mat(snapL, indent=indent)),
                                   ("U so far", fmt_frac_mat(snapU, indent=indent))]), ""]
    if not show_steps:
        out += [f"{indent}({k} row operation{'s' if k != 1 else ''}; turn on "
                "'Show row operations' to see them)", ""]
    elif k == 0:
        out += [f"{indent}(no row operations needed: A is already upper triangular)", ""]
    swapped = perm != list(range(len(perm)))
    P = perm_matrix(perm)
    PA = [Af[i] for i in perm]
    LU = _matmul_frac(L, U)
    blocks = ([("P", fmt_frac_mat(P, indent=indent))] if swapped else []) + [
        ("L", fmt_frac_mat(L, indent=indent)), ("U", fmt_frac_mat(U, indent=indent))]
    out += [_side_by_side(blocks), ""]
    name = "PA" if swapped else "A"
    out.append(f"{indent}Check: L U = {name}  " + ("✓" if LU == PA else "✗ (mismatch!)"))
    return out, swapped


def lu_text(A):
    """Narrated LU factorization of A (m x n): PA = LU."""
    A = np.asarray(A, dtype=float)
    m, n = A.shape
    L, U, perm, steps = lu_steps(A)
    bar = "=" * 60
    out = [bar, f"LU FACTORIZATION OF A ({m}x{n})", bar,
           "Eliminate downward using only 'Ri <- Ri - l Rj' (no scaling, so the",
           "pivots stay on U's diagonal). Each multiplier l is written into L",
           "at the spot it cleared. L is unit lower triangular, U is echelon.", ""]
    body, swapped = _lu_factor_lines(A, L, U, perm, steps)
    out += body
    out += ["", bar, "THE FACTORS", bar]
    if swapped:
        out += ["A zero pivot forced a row swap, so A itself has no LU factorization;",
                "P (the identity with rows reordered) fixes that:  PA = LU.",
                f"P puts the rows of A in the order {', '.join(f'R{p + 1}' for p in perm)}."]
    else:
        out += ["No swaps were needed:  A = LU.",
                "L undoes the elimination: its below-diagonal entries are exactly the",
                "multipliers, so L comes free as a record of what elimination did."]
    if m == n:
        diag = [U[i][i] for i in range(n)]
        nswaps = n - sum(1 for _ in _cycles(perm))
        det = Fraction((-1) ** nswaps)
        for q in diag:
            det *= q
        out.append("")
        prod = " x ".join(_signed(q) for q in diag)
        if swapped:
            out.append(f"det A = det P x (product of U's diagonal) = (-1)^{nswaps} x {prod}"
                       f" = {fmt_frac(det)}")
        else:
            out.append(f"det A = product of U's diagonal = {prod} = {fmt_frac(det)}")
        if det != 0:
            out += ["A is invertible: to solve A x = b for any b, solve L y = Pb",
                    "(forward substitution) then U x = y (back substitution).",
                    "Send A to Solve Ax = b and tick 'Solve by LU' to watch it."]
        else:
            out.append("A zero on U's diagonal: A is singular.")
    return "\n".join(out)


def _cycles(perm):
    """Cycles of a permutation (used to count the swaps for det's sign)."""
    seen = set()
    for s in range(len(perm)):
        if s in seen:
            continue
        cyc = []
        j = s
        while j not in seen:
            seen.add(j); cyc.append(j); j = perm[j]
        yield cyc


def lu_solve_text(A, b, show_steps=True):
    """Solve A x = b by PA = LU, forward and back substitution. Returns
    None (and a reason) when A is not square with a pivot in every column."""
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).ravel()
    m, n = A.shape
    if m != n:
        return None, (f"A is {m}x{n}, not square: LU substitution needs a square A "
                      "with a pivot in every column.")
    L, U, perm, steps = lu_steps(A)
    if any(U[i][i] == 0 for i in range(n)):
        return None, ("A is singular (a zero lands on U's diagonal), so back "
                      "substitution would divide by zero.")
    Af = [[to_fraction(v) for v in row] for row in A]
    bf = [to_fraction(v) for v in b]
    bar = "=" * 60
    out = [bar, f"SOLVE A x = b BY LU     A is {n}x{n}", bar,
           "Factor once (PA = LU), then each b costs only two triangular solves.", "",
           bar, "LU FACTORIZATION", bar]
    body, swapped = _lu_factor_lines(A, L, U, perm, steps, show_steps=show_steps)
    out += body + [""]

    Pb = [bf[p] for p in perm]
    out += [bar, "FORWARD SUBSTITUTION:  L y = " + ("Pb" if swapped else "b"), bar]
    if swapped:
        out.append(f"Pb = b with rows reordered = {_frac_vec(Pb)}")
    y = []
    for i in range(n):
        terms = [(L[i][j], j) for j in range(i) if L[i][j] != 0]
        val = Pb[i] - sum(l * y[j] for l, j in terms)
        rhs = fmt_frac(Pb[i])
        if terms:
            expr = " ".join(f"- ({fmt_frac(l)})({fmt_frac(y[j])})" for l, j in terms)
            sym = " ".join(f"- l{i + 1}{j + 1} y{j + 1}" for _, j in terms)
            out.append(f"   y{i + 1} = {'(Pb)' if swapped else 'b'}{i + 1} {sym} = {rhs} {expr} = {fmt_frac(val)}")
        else:
            out.append(f"   y{i + 1} = {'(Pb)' if swapped else 'b'}{i + 1} = {fmt_frac(val)}")
        y.append(val)
    out += [f"y = {_frac_vec(y)}", ""]

    out += [bar, "BACK SUBSTITUTION:  U x = y", bar]
    x = [Fraction(0)] * n
    for i in range(n - 1, -1, -1):
        terms = [(U[i][j], j) for j in range(i + 1, n) if U[i][j] != 0]
        num = y[i] - sum(u * x[j] for u, j in terms)
        x[i] = num / U[i][i]
        if terms:
            sym = " ".join(f"- u{i + 1}{j + 1} x{j + 1}" for _, j in terms)
            expr = " ".join(f"- ({fmt_frac(u)})({fmt_frac(x[j])})" for u, j in terms)
            out.append(f"   x{i + 1} = (y{i + 1} {sym}) / u{i + 1}{i + 1} = "
                       f"({fmt_frac(y[i])} {expr}) / {_signed(U[i][i])} = {fmt_frac(x[i])}")
        else:
            out.append(f"   x{i + 1} = y{i + 1} / u{i + 1}{i + 1} = {fmt_frac(y[i])} / "
                       f"{_signed(U[i][i])} = {fmt_frac(x[i])}")
    out += ["", f"UNIQUE SOLUTION:   x = {_frac_vec(x)}",
            f"Check: A x = {_frac_vec(_matvec_frac(Af, x))} = b  "
            + ("✓" if _matvec_frac(Af, x) == bf else "✗"),
            "", "Change b and only the two substitutions above change: L and U stay put."]
    return "\n".join(out), None


# ----------------------------------------------------------------------
# Solve A x = b
# ----------------------------------------------------------------------

def _frac_vec(v):
    return "[" + " ".join(fmt_frac(q) for q in v) + "]"


def _matvec_frac(A, x):
    return [sum(a * q for a, q in zip(row, x)) for row in A]


def _linear_expr(const, coeffs):
    """'3 - 2 x2 + 1/2 x4' from a constant and {var_index: coefficient}."""
    parts = [] if const == 0 else [fmt_frac(const)]
    for j, c in coeffs.items():
        if c == 0:
            continue
        sign = "-" if c < 0 else "+"
        mag = abs(c)
        term = f"x{j + 1}" if mag == 1 else f"{fmt_frac(mag)} x{j + 1}"
        if not parts:
            parts.append(("-" if c < 0 else "") + term)
        else:
            parts.append(f"{sign} {term}")
    return " ".join(parts) if parts else "0"


def solve_text(A, b, show_steps=True):
    """Narrated solution of A x = b: reduce [A | b], classify, write the
    solution set, verify; least squares when there is no solution."""
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).ravel()
    m, n = A.shape
    Af = [[to_fraction(v) for v in row] for row in A]
    bf = [to_fraction(v) for v in b]
    M = [row + [bv] for row, bv in zip(Af, bf)]
    R, pivot_cols, steps = rref_steps(M, ncols=n)
    bar = "=" * 60
    out = [bar, f"SOLVE A x = b     A is {m}x{n}, b in R^{m}", bar,
           "Augmented matrix [A | b]:", fmt_frac_mat(M, bar_after=n), ""]

    k = 0
    for desc, snap in steps:
        if desc.startswith("--"):
            if "FORM" in desc:
                out += [desc[3:].strip(), fmt_frac_mat(snap, bar_after=n), ""]
            elif show_steps:
                out += [desc[3:].strip(), ""]
            continue
        k += 1
        if show_steps:
            out += [f"Step {k}:  {desc}", fmt_frac_mat(snap, bar_after=n), ""]
    if not show_steps:
        out += [f"({k} row operation{'s' if k != 1 else ''}; turn on "
                "'Show row operations' to see them)", ""]

    # ---- consistency -----------------------------------------------
    out += [bar, "IS THERE A SOLUTION?", bar]
    bad_rows = [i for i in range(m)
                if all(R[i][j] == 0 for j in range(n)) and R[i][n] != 0]
    free = [j for j in range(n) if j not in pivot_cols]
    if bad_rows:
        i = bad_rows[0]
        out += [f"Row {i + 1} of the reduced matrix reads   0 = {fmt_frac(R[i][n])}",
                "which is impossible: the system is INCONSISTENT. No x satisfies A x = b.",
                f"b is not in the column space of A (rank [A|b] = {len(pivot_cols) + 1} "
                f"> rank A = {len(pivot_cols)}).", ""]
        out += _least_squares_text(A, b, Af, bf, bar)
        return "\n".join(out)

    out += ["No row reads 0 = (nonzero): the system is CONSISTENT.",
            f"rank A = rank [A|b] = {len(pivot_cols)}", ""]

    # ---- read off the solution ------------------------------------
    out += [bar, "THE SOLUTION", bar]
    if free:
        out.append(f"pivot variables: {', '.join(f'x{c + 1}' for c in pivot_cols)}"
                   f"     free variables: {', '.join(f'x{j + 1}' for j in free)}")
    else:
        out.append(f"every column has a pivot: all {n} variables are determined")
    out.append("Each pivot row of the RREF is one equation:")
    xp = [Fraction(0)] * n
    for i, pc in enumerate(pivot_cols):
        coeffs = {j: -R[i][j] for j in free}
        out.append(f"   x{pc + 1} = {_linear_expr(R[i][n], coeffs)}")
        xp[pc] = R[i][n]
    out.append("")
    if not free:
        out += [f"UNIQUE SOLUTION:   x = {_frac_vec(xp)}",
                f"Check: A x = {_frac_vec(_matvec_frac(Af, xp))} = b  ✓", ""]
    else:
        _, basis = null_space_from_rref(R, pivot_cols, n)
        out += ["INFINITELY MANY SOLUTIONS.",
                f"Particular solution (free variables = 0):  x_p = {_frac_vec(xp)}",
                "Null space of A (free variable = 1, others 0):"]
        for f, v in zip(free, basis):
            out.append(f"   x{f + 1} free ->  v = {_frac_vec(v)}")
        params = " + ".join(f"t{i + 1} {_frac_vec(v)}" for i, v in enumerate(basis))
        out += ["", f"General solution:  x = {_frac_vec(xp)} + {params}",
                f"   ({len(basis)}-dimensional family: a point plus the null space)",
                f"Check: A x_p = {_frac_vec(_matvec_frac(Af, xp))} = b  ✓"]
        for i, v in enumerate(basis):
            out.append(f"       A v{i + 1} = {_frac_vec(_matvec_frac(Af, v))} = 0  ✓")
        out.append("")
    return "\n".join(out)


def _least_squares_text(A, b, Af, bf, bar):
    """Least-squares section for an inconsistent system."""
    m, n = A.shape
    out = [bar, "LEAST SQUARES: the closest we can get", bar,
           "Since no x gives A x = b exactly, find x̂ minimizing |A x - b|.",
           "That x̂ makes the residual r = b - A x̂ orthogonal to every column",
           "of A, i.e. A^T r = 0, which is the NORMAL EQUATIONS  A^T A x̂ = A^T b.", ""]
    AtA = [[sum(Af[k][i] * Af[k][j] for k in range(m)) for j in range(n)] for i in range(n)]
    Atb = [sum(Af[k][i] * bf[k] for k in range(m)) for i in range(n)]
    out += [f"A^T A ({n}x{n}) =", fmt_frac_mat(AtA), f"A^T b = {_frac_vec(Atb)}", ""]
    N = [row + [v] for row, v in zip(AtA, Atb)]
    RN, piv, _ = rref_steps(N, ncols=n)
    if len(piv) == n:
        xhat = [RN[i][n] for i in range(n)]
        out += ["Row-reducing [A^T A | A^T b] gives a unique x̂ (A has independent columns):",
                fmt_frac_mat(RN, bar_after=n), "",
                f"x̂ = {_frac_vec(xhat)}"]
        p = _matvec_frac(Af, xhat)
        r = [bv - pv for bv, pv in zip(bf, p)]
        Atr = [sum(Af[k][i] * r[k] for k in range(m)) for i in range(n)]
        out += [f"projection of b onto the column space:  A x̂ = {_frac_vec(p)}",
                f"residual r = b - A x̂ = {_frac_vec(r)}",
                f"|r| = {np.sqrt(float(sum(q * q for q in r))):.4g}",
                f"A^T r = {_frac_vec(Atr)} = 0  ✓  (r is orthogonal to the column space)"]
    else:
        xhat, *_ = np.linalg.lstsq(A, b, rcond=None)
        p = A @ xhat; r = b - p
        out += [f"A^T A is singular (A has dependent columns, rank {len(piv)} < {n}),",
                "so there are infinitely many least-squares solutions. The one with",
                "smallest length (numpy lstsq):",
                f"x̂ = {fmt_vec(np.round(xhat, 6))}",
                f"A x̂ = {fmt_vec(np.round(p, 6))}     residual r = {fmt_vec(np.round(r, 6))}",
                f"|r| = {np.linalg.norm(r):.4g}     A^T r = {fmt_vec(np.round(A.T @ r, 6))}  (≈ 0)"]
    return out + [""]


# ----------------------------------------------------------------------
# The four fundamental subspaces
# ----------------------------------------------------------------------

def fundamental_subspaces(A):
    """Exact bases (lists of Fractions) for the four subspaces of A.

    Returns a dict:
      rank, pivot_cols, free_cols,
      col   : basis of the column space  C(A)    -- pivot columns of A   (in R^m)
      row   : basis of the row space     C(A^T)  -- nonzero rows of RREF (in R^n)
      null  : basis of the null space    N(A)    -- from RREF            (in R^n)
      left  : basis of the left null sp. N(A^T)  -- null space of A^T    (in R^m)
      R     : RREF(A)
    """
    A = np.asarray(A, dtype=float)
    m, n = A.shape
    Af = [[to_fraction(v) for v in row] for row in A]
    R, piv, _ = rref_steps(Af)
    free, null = null_space_from_rref(R, piv, n)
    col = [[Af[i][c] for i in range(m)] for c in piv]
    row = [R[i][:] for i in range(len(piv))]
    At = [[Af[i][j] for i in range(m)] for j in range(n)]
    Rt, pivt, _ = rref_steps(At)
    _, left = null_space_from_rref(Rt, pivt, m)
    return {"rank": len(piv), "pivot_cols": piv, "free_cols": free,
            "col": col, "row": row, "null": null, "left": left, "R": R,
            "m": m, "n": n}


def _basis_lines(name, vectors, space_dim, indent="   "):
    if not vectors:
        return [f"{indent}dimension 0: just the zero vector in R^{space_dim}"]
    return [f"{indent}{name}{k + 1} = {_frac_vec(v)}" for k, v in enumerate(vectors)]


def subspaces_text(A):
    d = fundamental_subspaces(A)
    m, n, r = d["m"], d["n"], d["rank"]
    bar = "=" * 60
    Af = [[to_fraction(v) for v in row] for row in np.asarray(A, dtype=float)]
    pivots = {(i, c) for i, c in enumerate(d["pivot_cols"])}
    out = [bar, f"THE FOUR FUNDAMENTAL SUBSPACES OF A ({m}x{n})", bar,
           "A =", fmt_frac_mat(Af), "",
           "RREF(A), pivots starred:", fmt_frac_mat(d["R"], pivots=pivots),
           f"rank r = {r}     pivot columns: "
           f"{', '.join(str(c + 1) for c in d['pivot_cols']) or 'none'}     "
           f"free columns: {', '.join(str(c + 1) for c in d['free_cols']) or 'none'}", ""]

    out += [bar, f"IN THE DOMAIN R^{n}  (where x lives)", bar,
            f"ROW SPACE  C(A^T):  dimension r = {r}",
            "   spanned by the rows of A; the nonzero rows of RREF are a basis:"]
    out += _basis_lines("r", d["row"], n)
    out += ["", f"NULL SPACE  N(A):  dimension n - r = {n} - {r} = {n - r}",
            "   all x with A x = 0; one basis vector per free column:"]
    out += _basis_lines("k", d["null"], n)
    out += ["", f"   {r} + {n - r} = {n}: row space and null space fill R^{n} together,",
            "   and they are ORTHOGONAL (every row of A dots to 0 with every null vector):"]
    for i, rv in enumerate(d["row"]):
        for j, kv in enumerate(d["null"]):
            dot = sum(a * b for a, b in zip(rv, kv))
            out.append(f"      r{i + 1} . k{j + 1} = {fmt_frac(dot)}")
    if not d["row"] or not d["null"]:
        out.append("      (one of them is {0}, so there is nothing to check)")

    out += ["", bar, f"IN THE CODOMAIN R^{m}  (where A x and b live)", bar,
            f"COLUMN SPACE  C(A):  dimension r = {r}",
            "   all vectors A x; the PIVOT columns of the original A are a basis",
            "   (not the columns of RREF -- row operations change the column space):"]
    out += _basis_lines("c", d["col"], m)
    out += ["", f"LEFT NULL SPACE  N(A^T):  dimension m - r = {m} - {r} = {m - r}",
            "   all y with A^T y = 0 (equivalently y^T A = 0); found by reducing A^T:"]
    out += _basis_lines("l", d["left"], m)
    out += ["", f"   {r} + {m - r} = {m}: column space and left null space fill R^{m},",
            "   and they are ORTHOGONAL:"]
    for i, cv in enumerate(d["col"]):
        for j, lv in enumerate(d["left"]):
            dot = sum(a * b for a, b in zip(cv, lv))
            out.append(f"      c{i + 1} . l{j + 1} = {fmt_frac(dot)}")
    if not d["col"] or not d["left"]:
        out.append("      (one of them is {0}, so there is nothing to check)")

    out += ["", bar, "WHAT IT MEANS", bar,
            f"A x = b has a solution exactly when b is in the column space (dim {r}).",
            f"When it does, the solutions form a copy of the null space (dim {n - r})",
            "shifted to pass through one particular solution.",
            f"A is one-to-one on the row space: it maps the {r}-dimensional row space",
            f"onto the {r}-dimensional column space and squashes the null space to 0."]
    if r == n:
        out.append(f"Full column rank (r = n): the null space is {{0}}; solutions are unique.")
    if r == m:
        out.append(f"Full row rank (r = m): the column space is all of R^{m}; every b works.")
    return "\n".join(out), d


# ----------------------------------------------------------------------
# Span and linear independence
# ----------------------------------------------------------------------

def _combo_text(coeffs, names):
    """'2 v1 - 1/2 v3' from a list of Fractions and vector names."""
    parts = []
    for c, nm in zip(coeffs, names):
        if c == 0:
            continue
        sign = "-" if c < 0 else "+"
        mag = abs(c)
        term = nm if mag == 1 else f"{fmt_frac(mag)} {nm}"
        parts.append(("-" if c < 0 else "") + term if not parts else f"{sign} {term}")
    return " ".join(parts) if parts else "0"


def span_text(V, w=None):
    """V: k vectors in R^d given as ROWS (k x d). w: optional target in R^d.
    Returns (text, data) where data has rank, pivot (indices of the
    independent vectors), relations, and w's coordinates if in the span."""
    V = np.asarray(V, dtype=float)
    k, d = V.shape
    Vf = [[to_fraction(v) for v in row] for row in V]
    A = [[Vf[j][i] for j in range(k)] for i in range(d)]      # vectors as columns
    R, piv, _ = rref_steps(A)
    free = [j for j in range(k) if j not in piv]
    names = [f"v{j + 1}" for j in range(k)]
    bar = "=" * 60
    out = [bar, f"SPAN AND INDEPENDENCE OF {k} VECTOR{'S' if k != 1 else ''} IN R^{d}", bar]
    for j in range(k):
        out.append(f"   v{j + 1} = {_frac_vec(Vf[j])}")
    out += ["", "Put the vectors side by side as the COLUMNS of A and row-reduce:",
            f"A = [v1 ... v{k}]  ({d}x{k}) =", fmt_frac_mat(A), "",
            "RREF(A), pivots starred:",
            fmt_frac_mat(R, pivots={(i, c) for i, c in enumerate(piv)}),
            f"rank = {len(piv)}     pivot columns: {', '.join(str(c + 1) for c in piv) or 'none'}", ""]

    # ---- independence ------------------------------------------------
    out += [bar, "LINEARLY INDEPENDENT?", bar,
            "c1 v1 + ... + ck vk = 0 is the system A c = 0. Independent means",
            "the only solution is c = 0, i.e. every column of A has a pivot."]
    relations = []
    if not free:
        out += [f"Every column has a pivot (rank {len(piv)} = {k}): the vectors are INDEPENDENT.", ""]
    else:
        cols = ", ".join(str(j + 1) for j in free)
        out.append((f"Column {cols} has" if len(free) == 1 else f"Columns {cols} have")
                   + " no pivot: the vectors are DEPENDENT.")
        out.append("Each free column gives one dependence (read its RREF column):")
        for f in free:
            coeffs = [R[i][f] for i in range(len(piv))]
            combo = _combo_text(coeffs, [names[c] for c in piv])
            rel = [Fraction(0)] * k
            for c, i in zip(piv, range(len(piv))):
                rel[c] = coeffs[i]
            rel[f] = Fraction(-1)
            relations.append((f, rel))
            out.append(f"   v{f + 1} = {combo}      i.e.   {_combo_text(rel, names)} = 0")
        if k > d:
            out.append(f"(Any {k} vectors in R^{d} must be dependent: more vectors than dimensions.)")
        out.append("")

    # ---- span ----------------------------------------------------------
    out += [bar, "THE SPAN", bar,
            f"span{{v1..v{k}}} = all combinations c1 v1 + ... + ck vk = the column space of A.",
            f"dimension = rank = {len(piv)}"]
    if piv:
        out.append("basis = the pivot vectors (the free ones are combinations of these):")
        for c in piv:
            out.append(f"   v{c + 1} = {_frac_vec(Vf[c])}")
    shape = {0: "just the origin", 1: "a line through the origin",
             2: "a plane through the origin", 3: "a 3-dimensional space"}.get(len(piv), f"a {len(piv)}-dimensional subspace")
    if len(piv) == d:
        out.append(f"The span is ALL of R^{d}: these vectors can reach every point.")
    else:
        out.append(f"The span is {shape} inside R^{d}; it misses most of R^{d}.")
        if k < d:
            out.append(f"({k} vectors can never span R^{d}: you need at least {d}.)")
    out.append("")

    # ---- membership ----------------------------------------------------
    coords = None
    if w is not None:
        wf = [to_fraction(v) for v in np.asarray(w, dtype=float).ravel()]
        out += [bar, f"IS w = {_frac_vec(wf)} IN THE SPAN?", bar,
                "Solve A c = w: reduce the augmented matrix [A | w]."]
        M = [A[i] + [wf[i]] for i in range(d)]
        RM, pivM, _ = rref_steps(M, ncols=k)
        out.append(fmt_frac_mat(RM, bar_after=k))
        bad = [i for i in range(d) if all(RM[i][j] == 0 for j in range(k)) and RM[i][k] != 0]
        if bad:
            out += [f"Row {bad[0] + 1} reads 0 = {fmt_frac(RM[bad[0]][k])}: NO. w is NOT in the span.",
                    f"(Adding w raises the rank to {len(pivM) + 1}: w points out of the span.)"]
        else:
            coords = [Fraction(0)] * k
            for i, c in enumerate(pivM):
                coords[c] = RM[i][k]
            out.append(f"YES. w = {_combo_text(coords, names)}")
            check = [sum(coords[j] * Vf[j][i] for j in range(k)) for i in range(d)]
            out.append(f"check: {_frac_vec(check)} = w  ✓")
            if free:
                out.append(f"(with {len(free)} free coefficient{'s' if len(free) != 1 else ''}, "
                           "other combinations reach w too; this one sets them to 0)")
        out.append("")
    data = {"k": k, "d": d, "rank": len(piv), "pivot": piv, "free": free,
            "relations": relations, "in_span": (coords is not None) if w is not None else None,
            "coords": coords}
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Determinant and inverse
# ----------------------------------------------------------------------

def _minor(M, i, j):
    return [row[:j] + row[j + 1:] for r, row in enumerate(M) if r != i]


def _det_frac(M):
    """Exact determinant by cofactor expansion (fine for n <= 8)."""
    n = len(M)
    if n == 1:
        return M[0][0]
    if n == 2:
        return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    return sum((-1) ** j * M[0][j] * _det_frac(_minor(M, 0, j)) for j in range(n))


def _signed(q):
    q = Fraction(q)
    return f"({fmt_frac(q)})" if q < 0 else fmt_frac(q)


def det_cofactor_lines(M, indent="   "):
    """Narrated cofactor expansion along row 1. Full detail for n <= 3;
    for larger n the minors' determinants are stated, not expanded."""
    n = len(M)
    if n == 1:
        return M[0][0], [f"{indent}det [a] = a = {fmt_frac(M[0][0])}"]
    if n == 2:
        a, b = M[0]; c, d = M[1]
        val = a * d - b * c
        return val, [f"{indent}det = ad - bc = {_signed(a)}*{_signed(d)} - {_signed(b)}*{_signed(c)} "
                     f"= {fmt_frac(a * d)} - {_signed(b * c)} = {fmt_frac(val)}"]
    lines = [f"{indent}Expand along row 1:  det = sum over j of (-1)^(1+j) * a_1j * M_1j,",
             f"{indent}where M_1j is the determinant of A with row 1 and column j removed."]
    terms = []
    val = Fraction(0)
    for j in range(n):
        sign = (-1) ** j
        sub = _minor(M, 0, j)
        mval = _det_frac(sub)
        term = sign * M[0][j] * mval
        val += term
        lines.append(f"{indent}j = {j + 1}: sign {'+' if sign > 0 else '-'},  a_1{j + 1} = {fmt_frac(M[0][j])},  "
                     f"minor M_1{j + 1} = det of")
        lines.append(fmt_frac_mat(sub, indent=indent + "      "))
        if n == 3:
            _, sublines = det_cofactor_lines(sub, indent=indent + "      ")
            lines += sublines
        else:
            lines.append(f"{indent}      = {fmt_frac(mval)}")
        lines.append(f"{indent}   term = {'+' if sign > 0 else '-'} {_signed(M[0][j])} * {_signed(mval)} = {fmt_frac(term)}")
        terms.append(fmt_frac(term))
    lines.append(f"{indent}det A = {' + '.join(f'({t})' for t in terms)} = {fmt_frac(val)}")
    return val, lines


def det_elimination(M):
    """Determinant by elimination to upper-triangular form using ONLY swaps
    (sign flips) and 'add a multiple of a row' (no change). Returns
    (det, steps, swaps, U) with steps as (description, snapshot)."""
    U = [row[:] for row in M]
    n = len(U)
    steps = []; swaps = 0
    for c in range(n):
        p = next((i for i in range(c, n) if U[i][c] != 0), None)
        if p is None:
            steps.append((f"column {c + 1} has no nonzero entry on or below the diagonal: "
                          "a zero will sit on the diagonal, so det = 0", [r[:] for r in U]))
            continue
        if p != c:
            U[c], U[p] = U[p], U[c]; swaps += 1
            steps.append((f"R{c + 1} <-> R{p + 1}   (swap: det changes SIGN)", [r[:] for r in U]))
        for i in range(c + 1, n):
            if U[i][c] != 0:
                k = U[i][c] / U[c][c]
                U[i] = [a - k * b for a, b in zip(U[i], U[c])]
                sign = "-" if k > 0 else "+"
                steps.append((f"R{i + 1} <- R{i + 1} {sign} {_coef(abs(k))}R{c + 1}   (det unchanged)",
                              [r[:] for r in U]))
    diag = [U[i][i] for i in range(n)]
    det = Fraction((-1) ** swaps)
    for q in diag:
        det *= q
    return det, steps, swaps, diag, U


def det_inverse_text(A, show_steps=True):
    """Determinant (two ways) and inverse (Gauss-Jordan, plus adjugate for
    n <= 3). Returns (text, data) with data = {n, det, inverse or None}."""
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    if A.shape[1] != n:
        raise ValueError("Determinants and inverses need a square matrix.")
    M = [[to_fraction(v) for v in row] for row in A]
    bar = "=" * 60
    out = [bar, f"DETERMINANT OF A ({n}x{n})", bar, "A =", fmt_frac_mat(M), ""]

    out += ["METHOD 1: COFACTOR EXPANSION"]
    det1, lines = det_cofactor_lines(M)
    out += lines + [""]

    out += ["METHOD 2: ELIMINATION TO TRIANGULAR FORM",
            "   Adding a multiple of one row to another leaves det unchanged;",
            "   swapping two rows flips its sign. Then det = (sign) x (product of the diagonal)."]
    det2, steps, swaps, diag, U = det_elimination(M)
    k = 0
    for desc, snap in steps:
        k += 1
        if show_steps:
            out += [f"   Step {k}: {desc}", fmt_frac_mat(snap, indent="      ")]
    if not show_steps and steps:
        out.append(f"   ({k} row operation{'s' if k != 1 else ''} hidden; turn on 'Show row operations')")
    out += ["   Upper triangular U =", fmt_frac_mat(U, indent="      "),
            f"   diagonal: {', '.join(fmt_frac(q) for q in diag)}     swaps: {swaps}",
            f"   det A = (-1)^{swaps} x {' x '.join(_signed(q) for q in diag)} = {fmt_frac(det2)}", ""]
    assert det1 == det2
    det = det1
    out += [bar, f"det A = {fmt_frac(det)}", bar]
    if det == 0:
        out += ["det A = 0: A is SINGULAR. Its columns are dependent, it squashes",
                f"R^{n} onto a lower-dimensional space, and it has NO inverse."]
    else:
        out += [f"det A = {fmt_frac(det)} is not 0: A is INVERTIBLE.",
                f"|det A| = {fmt_frac(abs(det))} is the factor by which A scales "
                f"{'area' if n == 2 else 'volume' if n == 3 else 'n-dimensional volume'};"]
        out.append("orientation is " + ("PRESERVED (det > 0)." if det > 0 else "REVERSED (det < 0): a reflection is involved."))
    out.append("")

    # ---- inverse -------------------------------------------------------
    out += [bar, "INVERSE", bar]
    inverse = None
    if det == 0:
        R, piv, _ = rref_steps(M)
        _, basis = null_space_from_rref(R, piv, n)
        out += ["Row-reducing A cannot reach the identity: RREF(A) has a zero row.",
                fmt_frac_mat(R), "",
                f"Witness: A k = 0 for k = {_frac_vec(basis[0])} (not the zero vector)." if basis else "",
                "If A had an inverse, k = A^-1 (A k) = A^-1 0 = 0, a contradiction.", ""]
    else:
        out += ["Gauss-Jordan on [A | I]: the row operations that turn A into I",
                "turn I into A^-1 (each operation is a matrix; their product is A^-1)."]
        aug = [M[i] + [Fraction(int(i == j)) for j in range(n)] for i in range(n)]
        R, piv, steps = rref_steps(aug, ncols=n)
        out += ["[A | I] =", fmt_frac_mat(aug, bar_after=n)]
        k = 0
        for desc, snap in steps:
            if desc.startswith("--"):
                continue
            k += 1
            if show_steps:
                out += [f"   Step {k}: {desc}", fmt_frac_mat(snap, indent="      ", bar_after=n)]
        if not show_steps:
            out.append(f"   ({k} row operation{'s' if k != 1 else ''} hidden; turn on 'Show row operations')")
        inverse = [row[n:] for row in R]
        out += ["[I | A^-1] =", fmt_frac_mat(R, bar_after=n), "", "A^-1 =", fmt_frac_mat(inverse), ""]
        prod = [[sum(M[i][k2] * inverse[k2][j] for k2 in range(n)) for j in range(n)] for i in range(n)]
        out += ["Check A A^-1 =", fmt_frac_mat(prod), "= I  ✓", ""]
        if n <= 3:
            out += ["METHOD 2: ADJUGATE FORMULA   A^-1 = adj(A) / det A"]
            if n == 1:
                out.append(f"   A^-1 = [1/a] = [{fmt_frac(1 / M[0][0])}]")
            elif n == 2:
                a, b = M[0]; c, d = M[1]
                out += ["   For a 2x2, swap the diagonal, negate the off-diagonal, divide by det:",
                        f"   A^-1 = (1/{_signed(det)}) x", fmt_frac_mat([[d, -b], [-c, a]], indent="      ")]
            else:
                C = [[(-1) ** (i + j) * _det_frac(_minor(M, i, j)) for j in range(n)] for i in range(n)]
                adj = [[C[j][i] for j in range(n)] for i in range(n)]
                out += ["   cofactor matrix C (C_ij = (-1)^(i+j) x minor_ij):", fmt_frac_mat(C, indent="      "),
                        "   adj(A) = C^T:", fmt_frac_mat(adj, indent="      "),
                        f"   A^-1 = adj(A) / {_signed(det)}  -- same matrix as above  ✓"]
            out.append("")
        out += [f"det(A^-1) = 1 / det A = {fmt_frac(1 / det)}", ""]
    return "\n".join(out), {"n": n, "det": det, "inverse": inverse}


# ----------------------------------------------------------------------
# Linear transformations (2D / 3D): what does A do geometrically?
# ----------------------------------------------------------------------

def transform_presets(n, angle_deg=45.0):
    """Named example matrices for the Transform tab."""
    th = np.radians(angle_deg); c, s_ = np.cos(th), np.sin(th)
    if n == 2:
        return {
            "identity": [[1, 0], [0, 1]],
            f"rotation by {angle_deg:g}°": [[c, -s_], [s_, c]],
            "rotation by 90°": [[0, -1], [1, 0]],
            "reflection across x-axis": [[1, 0], [0, -1]],
            "reflection across y = x": [[0, 1], [1, 0]],
            f"reflection across line at {angle_deg:g}°": [[np.cos(2 * th), np.sin(2 * th)], [np.sin(2 * th), -np.cos(2 * th)]],
            "scaling x by 2, y by 1/2": [[2, 0], [0, 0.5]],
            "uniform scaling by 1.5": [[1.5, 0], [0, 1.5]],
            "horizontal shear (k = 1)": [[1, 1], [0, 1]],
            "vertical shear (k = 1)": [[1, 0], [1, 1]],
            "projection onto x-axis": [[1, 0], [0, 0]],
            "projection onto line y = x": [[0.5, 0.5], [0.5, 0.5]],
            "squash to a line (singular)": [[1, 2], [2, 4]],
            "rotate + stretch": [[1, -1], [1, 1]],
        }
    return {
        "identity": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        f"rotation about z by {angle_deg:g}°": [[c, -s_, 0], [s_, c, 0], [0, 0, 1]],
        f"rotation about x by {angle_deg:g}°": [[1, 0, 0], [0, c, -s_], [0, s_, c]],
        "reflection through xy-plane": [[1, 0, 0], [0, 1, 0], [0, 0, -1]],
        "scaling (2, 1, 1/2)": [[2, 0, 0], [0, 1, 0], [0, 0, 0.5]],
        "shear x by z (k = 1)": [[1, 0, 1], [0, 1, 0], [0, 0, 1]],
        "projection onto xy-plane": [[1, 0, 0], [0, 1, 0], [0, 0, 0]],
        "squash to a plane (singular)": [[1, 0, 1], [0, 1, 1], [1, 1, 2]],
        "cyclic permutation of axes": [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
    }


def fmt_num(v, max_den=100):
    """Simple fractions as fractions, everything else as a short decimal."""
    q = to_fraction(v)
    if q.denominator <= max_den:
        return fmt_frac(q)
    return f"{float(v):.4g}"


def _num_vec(v):
    return "[" + " ".join(fmt_num(a) for a in v) + "]"


def _num_mat(M, indent="  "):
    cells = [[fmt_num(a) for a in row] for row in M]
    width = max(len(c) for row in cells for c in row)
    return "\n".join(indent + "[ " + "  ".join(c.rjust(width) for c in row) + " ]" for row in cells)


def transform_text(A, tol=1e-9):
    """Geometric description of a 2x2 or 3x3 matrix as a map R^n -> R^n.
    Works in floating point (presets contain cos/sin) with a tolerance."""
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    det = float(np.linalg.det(A))
    if abs(det) < tol:
        det = 0.0
    bar = "=" * 60
    names = ["x", "y", "z"]
    out = [bar, f"A AS A TRANSFORMATION OF R^{n}", bar, "A =", _num_mat(A), ""]

    out += ["WHERE THE BASIS VECTORS GO  (the columns of A):"]
    for j in range(n):
        out.append(f"   e{j + 1} = {names[j]}-direction  ->  A e{j + 1} = {_num_vec(A[:, j])}")
    out += ["   Every other vector follows by linearity: A(a e1 + b e2 + ...) = a(A e1) + b(A e2) + ...", ""]

    what = "area" if n == 2 else "volume"
    out += ["SIZE AND ORIENTATION", f"   det A = {fmt_num(det)}"]
    if det == 0:
        r = int(np.linalg.matrix_rank(A, tol=1e-9))
        shape = {0: "the origin", 1: "a line", 2: "a plane"}[r]
        out += [f"   det = 0: A is SINGULAR. It flattens R^{n} onto {shape} (its column space, dim {r}),",
                f"   so {what} becomes 0 and A cannot be undone."]
    else:
        out.append(f"   |det| = {fmt_num(abs(det))}: every region's {what} is multiplied by {fmt_num(abs(det))}.")
        out.append("   det > 0: orientation preserved." if det > 0 else
                   "   det < 0: orientation REVERSED (a reflection is hiding inside A).")
    out.append("")

    out += ["WHAT KIND OF MAP?"]
    kinds = []
    I = np.eye(n)
    with np.errstate(invalid="ignore"):          # Accelerate's spurious tiny-matmul warning
        orth = np.allclose(A.T @ A, I, atol=1e-7)
        proj = np.allclose(A @ A, A, atol=1e-7) and not np.allclose(A, I, atol=tol)
    diag = np.allclose(A, np.diag(np.diag(A)), atol=tol)
    sym = np.allclose(A, A.T, atol=tol)
    unit_diag = np.allclose(np.diag(A), 1, atol=tol)
    tri = np.allclose(A, np.triu(A), atol=tol) or np.allclose(A, np.tril(A), atol=tol)
    if np.allclose(A, I, atol=tol):
        kinds.append("IDENTITY: nothing moves.")
    elif orth:
        if det > 0:
            if n == 2:
                ang = np.degrees(np.arctan2(A[1, 0], A[0, 0]))
                kinds.append(f"ROTATION by {ang:.4g}° (A^T A = I and det = 1): lengths and angles are preserved.")
            else:
                ang = np.degrees(np.arccos(np.clip((np.trace(A) - 1) / 2, -1, 1)))
                axis = np.array([A[2, 1] - A[1, 2], A[0, 2] - A[2, 0], A[1, 0] - A[0, 1]])
                if np.linalg.norm(axis) > 1e-9:
                    axis = axis / np.linalg.norm(axis)
                    kinds.append(f"ROTATION by {ang:.4g}° about the axis {_num_vec(np.round(axis, 4))} (A^T A = I, det = 1).")
                else:
                    kinds.append(f"ROTATION by {ang:.4g}° (A^T A = I, det = 1).")
        else:
            if n == 2:
                ang = np.degrees(np.arctan2(A[1, 0], A[0, 0])) / 2
                kinds.append(f"REFLECTION across the line through the origin at {ang:.4g}° (A^T A = I, det = -1).")
            elif sym:
                kinds.append("REFLECTION through a plane (A^T A = I, det = -1, A = A^T).")
            else:
                kinds.append("ROTATION COMBINED WITH A REFLECTION (A^T A = I, det = -1).")
    elif diag:
        kinds.append("SCALING along the axes by factors " + ", ".join(fmt_num(A[i, i]) for i in range(n)) + ".")
    elif unit_diag and tri:
        kinds.append("SHEAR: ones on the diagonal, off-diagonal entries slide layers past each other; "
                     f"{what} unchanged.")
    elif proj:
        kinds.append(("ORTHOGONAL PROJECTION" if sym else "PROJECTION (oblique)") +
                     ": A^2 = A, so applying it twice changes nothing; it drops vectors onto its column space.")
    elif sym:
        kinds.append("SYMMETRIC (A = A^T): a pure stretch along some set of perpendicular axes, no twist.")
    else:
        kinds.append("A general map: a stretch along perpendicular axes followed by a rotation (see below).")
    out += ["   " + k for k in kinds] + [""]

    U, sv, Vt = np.linalg.svd(A)
    sv = np.where(sv < 1e-9, 0.0, sv)
    out += ["STRETCH FACTORS  (singular values)",
            f"   The unit {'circle' if n == 2 else 'sphere'} is sent to an {'ellipse' if n == 2 else 'ellipsoid'} "
            f"with semi-axes {', '.join(fmt_num(v) for v in sv)}."]
    for i, v in enumerate(sv):
        out.append(f"   direction {_num_vec(np.round(Vt[i], 4))} is stretched by {fmt_num(v)}"
                   f"{'  (max)' if i == 0 else '  (min)' if i == n - 1 else ''}")
    out.append(f"   Product of the stretch factors = {fmt_num(np.prod(sv))} = |det A|.")
    out.append("")
    out += ["THE ANIMATION",
            "   The picture morphs from the identity to A along M(t) = (1 - t) I + t A.",
            "   Faint gray = the original shape; colour = its image under M(t)."]
    return "\n".join(out)


# ----------------------------------------------------------------------
# Eigenvalues and eigenvectors
# ----------------------------------------------------------------------

def char_poly(Af):
    """Coefficients (Fractions, highest power first) of det(lambda I - A)
    by Faddeev-LeVerrier: exact for any size."""
    n = len(Af)
    I = [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    def matmul(X, Y):
        return [[sum(X[i][k] * Y[k][j] for k in range(n)) for j in range(n)] for i in range(n)]
    c = [Fraction(0)] * (n + 1)
    c[n] = Fraction(1)
    M = [[Fraction(0)] * n for _ in range(n)]
    for k in range(1, n + 1):
        M = matmul(Af, M)
        for i in range(n):
            M[i][i] += c[n - k + 1]
        AM = matmul(Af, M)
        c[n - k] = -sum(AM[i][i] for i in range(n)) / k
    return [c[n - i] for i in range(n + 1)]          # highest power first


def poly_text(coeffs, var="λ"):
    n = len(coeffs) - 1
    parts = []
    for i, c in enumerate(coeffs):
        p = n - i
        if c == 0:
            continue
        mag = abs(c)
        mono = "" if p == 0 else var if p == 1 else f"{var}^{p}"
        coef = "" if (mag == 1 and p > 0) else fmt_frac(mag)
        term = (coef + (" " if coef and mono else "") + mono) if (coef or mono) else "1"
        if not parts:
            parts.append(("-" if c < 0 else "") + term)
        else:
            parts.append(("- " if c < 0 else "+ ") + term)
    return " ".join(parts) if parts else "0"


def _poly_eval(coeffs, x):
    v = Fraction(0)
    for c in coeffs:
        v = v * x + c
    return v


def _poly_div(coeffs, root):
    """Divide by (x - root) with synthetic division; returns quotient."""
    out = [coeffs[0]]
    for c in coeffs[1:]:
        out.append(c + out[-1] * root)
    return out[:-1]                                  # last entry is the remainder (0)


def _divisors(m, cap=2000):
    """Positive divisors of |m| by trial division up to sqrt; None if there
    would be too many to try (then we fall back to numeric roots)."""
    m = abs(int(m))
    if m == 0:
        return [1]
    small, large = [], []
    i = 1
    while i * i <= m:
        if m % i == 0:
            small.append(i)
            if i != m // i:
                large.append(m // i)
            if len(small) + len(large) > cap:
                return None
        i += 1
        if i > 2 * 10 ** 5:                   # give up on huge coefficients
            return None
    return small + large[::-1]


def rational_roots(coeffs, max_candidates=20000):
    """Exact rational roots (with multiplicity) and the leftover factor.
    Skips the search when the coefficients make it too expensive."""
    roots = []
    rem = list(coeffs)
    while len(rem) > 1:
        if rem[-1] == 0:                              # root 0
            roots.append(Fraction(0)); rem = rem[:-1]; continue
        den = 1
        for c in rem:
            den = den * c.denominator // math.gcd(den, c.denominator)
        ints = [int(c * den) for c in rem]
        d0, dn = _divisors(ints[-1]), _divisors(ints[0])
        if d0 is None or dn is None or len(d0) * len(dn) > max_candidates:
            break
        found = None
        for p in d0:
            for q in dn:
                for sign in (1, -1):
                    cand = Fraction(sign * p, q)
                    if _poly_eval(rem, cand) == 0:
                        found = cand; break
                if found is not None: break
            if found is not None: break
        if found is None:
            break
        roots.append(found)
        rem = _poly_div(rem, found)
    return roots, rem


def eigen_analysis(A):
    """Everything the Eigen tab needs. Exact where the eigenvalue is
    rational, numeric otherwise."""
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    Af = [[to_fraction(v) for v in row] for row in A]
    coeffs = char_poly(Af)
    rroots, rem = rational_roots(coeffs)
    other = []
    if len(rem) > 1:
        other = [complex(z) for z in np.roots([float(c) for c in rem])]
    # group eigenvalues with multiplicities
    eigs = []                                        # dicts
    for r in sorted(set(rroots), key=lambda q: float(q)):
        eigs.append({"value": r, "exact": True, "alg": rroots.count(r), "real": True})
    used = [False] * len(other)
    for i, z in enumerate(other):
        if used[i]:
            continue
        mult = 1
        for j in range(i + 1, len(other)):
            if not used[j] and abs(other[j] - z) < 1e-6:
                used[j] = True; mult += 1
        used[i] = True
        if abs(z.imag) < 1e-9:
            eigs.append({"value": z.real, "exact": False, "alg": mult, "real": True})
        else:
            eigs.append({"value": z, "exact": False, "alg": mult, "real": False})
    # eigenvectors for real eigenvalues
    for e in eigs:
        if not e["real"]:
            e["vectors"] = []; e["geo"] = 0; continue
        if e["exact"]:
            lam = e["value"]
            B = [[Af[i][j] - (lam if i == j else 0) for j in range(n)] for i in range(n)]
            R, piv, _ = rref_steps(B)
            _, basis = null_space_from_rref(R, piv, n)
            e["B"] = B; e["R"] = R; e["vectors"] = basis
        else:
            lam = float(e["value"])
            B = A - lam * np.eye(n)
            u, sv, vt = np.linalg.svd(B)
            rank = int(np.sum(sv > 1e-7 * max(1.0, sv[0])))
            e["B"] = None; e["R"] = None
            e["vectors"] = [vt[k] for k in range(rank, n)]
        e["geo"] = len(e["vectors"])
    total_geo = sum(e["geo"] for e in eigs)
    diagonalizable = total_geo == n and all(e["real"] for e in eigs)
    return {"n": n, "A": Af, "coeffs": coeffs, "rem": rem, "eigs": eigs,
            "diagonalizable": diagonalizable, "trace": sum(Af[i][i] for i in range(n)),
            "det": _det_frac(Af), "symmetric": all(Af[i][j] == Af[j][i] for i in range(n) for j in range(n))}


def _fmt_eig(e):
    v = e["value"]
    if e["exact"]:
        return fmt_frac(v)
    if e["real"]:
        return f"{float(v):.4g}"
    re_ = 0.0 if abs(v.real) < 1e-12 else v.real
    return f"{re_:.4g} {'+' if v.imag >= 0 else '-'} {abs(v.imag):.4g}i"


def _fmt_vec_any(v):
    if len(v) and isinstance(v[0], Fraction):
        return _frac_vec(v)
    return "[" + " ".join(f"{float(a):.4g}" for a in v) + "]"


def eigen_text(A):
    d = eigen_analysis(A)
    n, Af, coeffs = d["n"], d["A"], d["coeffs"]
    bar = "=" * 60
    out = [bar, f"EIGENVALUES AND EIGENVECTORS OF A ({n}x{n})", bar, "A =", fmt_frac_mat(Af), "",
           "An eigenvector v is a direction A only stretches:  A v = λ v.",
           "Then (A - λI) v = 0 has a nonzero solution, so det(A - λI) = 0.", ""]

    out += ["CHARACTERISTIC POLYNOMIAL  p(λ) = det(λI - A)"]
    if n == 2:
        a, b = Af[0]; c, e_ = Af[1]
        out += ["   det [ λ-a   -b  ]  =  (λ - a)(λ - d) - bc,   with a, b, c, d the entries of A",
                "       [ -c   λ-d  ]",
                f"   = (λ - {_signed(a)})(λ - {_signed(e_)}) - ({fmt_frac(b)})({fmt_frac(c)})",
                f"   = λ^2 - (a + d) λ + (ad - bc) = λ^2 - (trace) λ + det"]
    else:
        out.append("   expanding det(λI - A) by cofactors (done exactly) gives")
    out += [f"   p(λ) = {poly_text(coeffs)}",
            f"   (the {'λ' if n == 2 else f'λ^{n - 1}'} coefficient is -trace A = {fmt_frac(-d['trace'])}; "
            f"the constant is {'-' if n % 2 else ''}det A = {fmt_frac((-1) ** n * d['det'])})", ""]

    out += ["EIGENVALUES  (roots of p)"]
    rat = [e for e in d["eigs"] if e["exact"]]
    if rat:
        factors = " ".join(f"(λ {'-' if e['value'] >= 0 else '+'} {fmt_frac(abs(e['value']))})"
                           + (f"^{e['alg']}" if e["alg"] > 1 else "") for e in rat)
        left = poly_text(d["rem"]) if len(d["rem"]) > 1 else ""
        out.append(f"   p(λ) = {factors}" + (f" ({left})" if left else ""))
    elif len(d["rem"]) > 1:
        out.append("   no rational roots; solving numerically")
    for e in d["eigs"]:
        mult = f"   (algebraic multiplicity {e['alg']})" if e["alg"] > 1 else ""
        out.append(f"   λ = {_fmt_eig(e)}{mult}" + ("" if e["real"] else "   COMPLEX"))
    if any(not e["real"] for e in d["eigs"]):
        out += ["   Complex eigenvalues: no real direction is kept fixed. A rotates every",
                "   vector (a rotation, or a rotation combined with a stretch)."]
    out += [f"   check: sum of eigenvalues = trace A = {fmt_frac(d['trace'])},   "
            f"product = det A = {fmt_frac(d['det'])}", ""]

    for e in d["eigs"]:
        if not e["real"]:
            continue
        lam = _fmt_eig(e)
        out += [bar, f"EIGENVECTORS FOR λ = {lam}", bar,
                f"Solve (A - λI) v = 0 with λ = {lam}:"]
        if e["exact"]:
            out += ["A - λI =", fmt_frac_mat(e["B"]), "RREF:", fmt_frac_mat(e["R"])]
        else:
            out.append("   (λ is irrational: solved numerically)")
        out.append(f"   null space dimension = {e['geo']}  (geometric multiplicity)")
        for k, v in enumerate(e["vectors"]):
            Av = [sum(Af[i][j] * v[j] for j in range(n)) for i in range(n)] if e["exact"] else \
                 list(np.asarray(A, dtype=float) @ np.asarray(v, dtype=float))
            lamv = [e["value"] * q for q in v] if e["exact"] else [float(e["value"]) * float(q) for q in v]
            out.append(f"   v{k + 1} = {_fmt_vec_any(v)}      check: A v = {_fmt_vec_any(Av)} = λ v = {_fmt_vec_any(lamv)}  ✓")
        if e["geo"] < e["alg"]:
            out.append(f"   DEFECTIVE: algebraic multiplicity {e['alg']} but only {e['geo']} independent "
                       "eigenvector(s). A is not diagonalizable.")
        out.append("")

    out += [bar, "DIAGONALIZATION", bar]
    if d["diagonalizable"]:
        out += [f"A has {n} independent eigenvectors, so A = P D P^-1 with the eigenvectors",
                "as the columns of P and the eigenvalues on the diagonal of D:"]
        cols = []; lams = []
        for e in d["eigs"]:
            for v in e["vectors"]:
                cols.append(v); lams.append(e["value"])
        if all(e["exact"] for e in d["eigs"]):
            P = [[cols[j][i] for j in range(n)] for i in range(n)]
            D = [[lams[i] if i == j else Fraction(0) for j in range(n)] for i in range(n)]
            out += ["P =", fmt_frac_mat(P), "D =", fmt_frac_mat(D)]
        else:
            P = np.array([[float(cols[j][i]) for j in range(n)] for i in range(n)])
            out += ["P =", _num_mat(P), "D = diag(" + ", ".join(f"{float(l):.4g}" for l in lams) + ")"]
        out += ["In the eigenvector basis A is just a scaling: A^k = P D^k P^-1.", ""]
        if d["symmetric"]:
            out += ["A is SYMMETRIC: its eigenvalues are real and eigenvectors for different",
                    "eigenvalues are orthogonal (P can be taken orthogonal: A = Q D Q^T)."]
            checks = []
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    if lams[i] != lams[j]:
                        dot = sum(float(a) * float(b) for a, b in zip(cols[i], cols[j]))
                        checks.append(f"v{i + 1}.v{j + 1} = {dot:.4g}")
            if checks:
                out.append("   " + ",  ".join(checks))
    else:
        if any(not e["real"] for e in d["eigs"]):
            out.append("Not diagonalizable over the reals (complex eigenvalues).")
        else:
            out.append(f"Only {sum(e['geo'] for e in d['eigs'])} independent eigenvectors for a {n}x{n}: "
                       "NOT diagonalizable (defective).")
    return "\n".join(out), d


# ----------------------------------------------------------------------
# Dot product, projections, cross product (Vectors tab)
# ----------------------------------------------------------------------

def _dot_terms(u, v):
    return " + ".join(f"{_signed(a)}*{_signed(b)}" for a, b in zip(u, v))


def _sqrt_text(q):
    """'sqrt(14) = 3.742' or '3' when the square root is exact."""
    q = Fraction(q)
    r = float(q) ** 0.5
    rq = to_fraction(round(r, 9))
    if rq * rq == q:
        return fmt_frac(rq)
    return f"sqrt({fmt_frac(q)}) = {r:.4g}"


def vectors_text(u, v, w=None):
    """Dot product, angle, projection of u onto v, cross product (3D) with
    area and orthogonality, and with w: triple product / volume and the
    projection of w onto the plane of u and v. Returns (text, data)."""
    uf = [to_fraction(a) for a in np.asarray(u, dtype=float).ravel()]
    vf = [to_fraction(a) for a in np.asarray(v, dtype=float).ravel()]
    d = len(uf)
    bar = "=" * 60
    data = {"dim": d}
    out = [bar, f"TWO VECTORS IN R^{d}", bar, f"u = {_frac_vec(uf)}", f"v = {_frac_vec(vf)}", ""]

    # ---- dot product, lengths, angle -----------------------------------
    dot = sum(a * b for a, b in zip(uf, vf))
    uu = sum(a * a for a in uf); vv = sum(a * a for a in vf)
    out += ["DOT PRODUCT", f"   u . v = {_dot_terms(uf, vf)} = {fmt_frac(dot)}",
            f"   |u| = sqrt(u . u) = {_sqrt_text(uu)}", f"   |v| = sqrt(v . v) = {_sqrt_text(vv)}"]
    if uu > 0 and vv > 0:
        if dot * dot == uu * vv:                      # exactly (anti)parallel
            cos, ang = (1.0, 0.0) if dot > 0 else (-1.0, 180.0)
        else:
            cos = float(dot) / (float(uu) ** 0.5 * float(vv) ** 0.5)
            ang = float(np.degrees(np.arccos(np.clip(cos, -1, 1))))
        data["angle"] = ang
        out.append(f"   cos θ = u . v / (|u| |v|) = {cos:.4g}   ->   θ = {ang:.4g}°")
        if dot == 0:
            out.append("   u . v = 0: u and v are ORTHOGONAL (perpendicular).")
        elif dot > 0:
            out.append("   u . v > 0: the angle is acute (they point broadly the same way).")
        else:
            out.append("   u . v < 0: the angle is obtuse (they point broadly opposite ways).")
    else:
        out.append("   (a zero vector has no direction, so no angle)")
    out.append("")

    # ---- projection of u onto v ----------------------------------------
    out += ["PROJECTION OF u ONTO v"]
    if vv > 0:
        k = dot / vv
        proj = [k * b for b in vf]
        perp = [a - p for a, p in zip(uf, proj)]
        check = sum(a * b for a, b in zip(perp, vf))
        pp = sum(a * a for a in perp)
        data["proj"] = [float(q) for q in proj]; data["perp"] = [float(q) for q in perp]
        out += ["   The part of u that lies along v:  proj_v(u) = (u . v / v . v) v",
                f"   = ({fmt_frac(dot)} / {fmt_frac(vv)}) v = {fmt_frac(k)} v = {_frac_vec(proj)}",
                f"   The leftover, perpendicular to v:  u - proj = {_frac_vec(perp)}",
                f"   check: (u - proj) . v = {fmt_frac(check)}  ✓",
                f"   distance from the tip of u to the line through v = |u - proj| = {_sqrt_text(pp)}",
                f"   so u = (along v) + (perpendicular to v) = {_frac_vec(proj)} + {_frac_vec(perp)}"]
    else:
        out.append("   v = 0: nothing to project onto.")
    out.append("")

    # ---- cross product -------------------------------------------------
    if d == 3:
        c = [uf[1] * vf[2] - uf[2] * vf[1], uf[2] * vf[0] - uf[0] * vf[2], uf[0] * vf[1] - uf[1] * vf[0]]
        data["cross"] = [float(q) for q in c]
        cc = sum(a * a for a in c)
        out += ["CROSS PRODUCT  u x v", "   Expand the symbolic determinant along the top row:",
                "        |   i   j   k |",
                f"        | {fmt_frac(uf[0]):>3} {fmt_frac(uf[1]):>3} {fmt_frac(uf[2]):>3} |",
                f"        | {fmt_frac(vf[0]):>3} {fmt_frac(vf[1]):>3} {fmt_frac(vf[2]):>3} |",
                f"   i-part: u2 v3 - u3 v2 = {_signed(uf[1])}*{_signed(vf[2])} - {_signed(uf[2])}*{_signed(vf[1])} = {fmt_frac(c[0])}",
                f"   j-part: u3 v1 - u1 v3 = {_signed(uf[2])}*{_signed(vf[0])} - {_signed(uf[0])}*{_signed(vf[2])} = {fmt_frac(c[1])}   (note the sign flip: -(u1 v3 - u3 v1))",
                f"   k-part: u1 v2 - u2 v1 = {_signed(uf[0])}*{_signed(vf[1])} - {_signed(uf[1])}*{_signed(vf[0])} = {fmt_frac(c[2])}",
                f"   u x v = {_frac_vec(c)}", "",
                "   Properties:",
                f"   (u x v) . u = {fmt_frac(sum(a * b for a, b in zip(c, uf)))},   (u x v) . v = "
                f"{fmt_frac(sum(a * b for a, b in zip(c, vf)))}   -> perpendicular to BOTH  ✓",
                f"   |u x v| = {_sqrt_text(cc)} = area of the parallelogram spanned by u and v"]
        if uu > 0 and vv > 0 and "angle" in data:
            sin = float(np.sin(np.radians(data["angle"])))
            out.append(f"   check: |u| |v| sin θ = {float(uu) ** 0.5:.4g} x {float(vv) ** 0.5:.4g} x {sin:.4g} = "
                       f"{float(uu) ** 0.5 * float(vv) ** 0.5 * sin:.4g}  ✓")
        if cc == 0:
            out.append("   u x v = 0: u and v are PARALLEL (or one is zero); they span no area.")
        else:
            out.append("   direction: right-hand rule (curl fingers from u to v, thumb = u x v).")
        out += [f"   v x u = {_frac_vec([-q for q in c])} = -(u x v): the order matters (anticommutative).", ""]
    elif d == 2:
        z = uf[0] * vf[1] - uf[1] * vf[0]
        data["cross2"] = float(z)
        out += ["SIGNED AREA  (the 2-D stand-in for the cross product)",
                f"   u1 v2 - u2 v1 = {_signed(uf[0])}*{_signed(vf[1])} - {_signed(uf[1])}*{_signed(vf[0])} = {fmt_frac(z)}",
                f"   |{fmt_frac(z)}| = area of the parallelogram spanned by u and v;",
                "   the sign says whether v is counter-clockwise (+) or clockwise (-) from u.",
                "   (Embed in R^3 with z = 0 and u x v = [0 0 " + fmt_frac(z) + "].)", ""]

    # ---- third vector -------------------------------------------------
    if w is not None and d == 3:
        wf = [to_fraction(a) for a in np.asarray(w, dtype=float).ravel()]
        c = [Fraction(q) for q in [uf[1] * vf[2] - uf[2] * vf[1], uf[2] * vf[0] - uf[0] * vf[2], uf[0] * vf[1] - uf[1] * vf[0]]]
        cc = sum(a * a for a in c)
        triple = sum(a * b for a, b in zip(wf, c))
        out += [bar, f"A THIRD VECTOR  w = {_frac_vec(wf)}", bar,
                "TRIPLE PRODUCT  w . (u x v)",
                f"   = {_dot_terms(wf, c)} = {fmt_frac(triple)}",
                "   = det of the matrix with rows u, v, w:", fmt_frac_mat([uf, vf, wf]),
                f"   |{fmt_frac(triple)}| = volume of the parallelepiped spanned by u, v, w"]
        if triple == 0:
            out.append("   = 0: w lies IN the plane of u and v (the three are coplanar / dependent).")
        else:
            out.append("   nonzero: u, v, w are independent and span R^3"
                       + (" (right-handed set)." if triple > 0 else " (left-handed set)."))
        out.append("")
        if cc > 0:
            kk = triple / cc
            wn = [kk * q for q in c]
            wp = [a - b for a, b in zip(wf, wn)]
            data["w_plane"] = [float(q) for q in wp]; data["w_normal"] = [float(q) for q in wn]
            out += ["PROJECTION OF w ONTO THE PLANE OF u AND v",
                    "   n = u x v is normal to the plane. Remove w's component along n:",
                    f"   (w . n / n . n) n = ({fmt_frac(triple)} / {fmt_frac(cc)}) n = {_frac_vec(wn)}",
                    f"   proj_plane(w) = w - that = {_frac_vec(wp)}",
                    f"   check: proj . n = {fmt_frac(sum(a * b for a, b in zip(wp, c)))}  ✓   "
                    f"(it lies in the plane)",
                    f"   distance from w to the plane = |w . n| / |n| = {abs(float(triple)) / float(cc) ** 0.5:.4g}", ""]
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Gram-Schmidt and QR
# ----------------------------------------------------------------------

def gram_schmidt_text(V):
    """V: k vectors in R^d as ROWS. Orthogonalize step by step (exact),
    normalize (decimal), and build A = Q R for A = [v1 ... vk] (columns).
    Returns (text, data)."""
    V = np.asarray(V, dtype=float)
    k, d = V.shape
    vf = [[to_fraction(a) for a in row] for row in V]
    bar = "=" * 60
    out = [bar, f"GRAM-SCHMIDT ON {k} VECTOR{'S' if k != 1 else ''} IN R^{d}", bar]
    for j in range(k):
        out.append(f"   v{j + 1} = {_frac_vec(vf[j])}")
    out += ["", "Idea: keep v1; from each later vector subtract its projections onto the",
            "orthogonal vectors found so far. What is left is orthogonal to all of them.", ""]

    us = []            # exact orthogonal vectors (may contain None for dependent inputs)
    coeffs = []        # coeffs[j] = {i: v_j . u_i / u_i . u_i} for kept u_i
    for j in range(k):
        v = vf[j]
        out.append(f"STEP {j + 1}:  u{j + 1} = v{j + 1}" +
                   "".join(f" - proj_u{i + 1}(v{j + 1})" for i, u in enumerate(us) if u is not None))
        resid = list(v)
        cj = {}
        for i, u in enumerate(us):
            if u is None:
                continue
            uu = sum(a * a for a in u)
            c = sum(a * b for a, b in zip(v, u)) / uu
            cj[i] = c
            out.append(f"   proj_u{i + 1}(v{j + 1}) = (v{j + 1} . u{i + 1} / u{i + 1} . u{i + 1}) u{i + 1} = "
                       f"({fmt_frac(sum(a * b for a, b in zip(v, u)))} / {fmt_frac(uu)}) u{i + 1} = "
                       f"{fmt_frac(c)} u{i + 1} = {_frac_vec([c * a for a in u])}")
            resid = [r - c * a for r, a in zip(resid, u)]
        coeffs.append(cj)
        if all(r == 0 for r in resid):
            us.append(None)
            out += [f"   u{j + 1} = {_frac_vec(resid)} = 0:  v{j + 1} was already a combination of the earlier",
                    "   vectors (dependent). It contributes nothing new and is dropped.", ""]
            continue
        us.append(resid)
        out.append(f"   u{j + 1} = {_frac_vec(resid)}")
        checks = [f"u{j + 1} . u{i + 1} = {fmt_frac(sum(a * b for a, b in zip(resid, u)))}"
                  for i, u in enumerate(us[:-1]) if u is not None]
        if checks:
            out.append("   check orthogonality: " + ",  ".join(checks) + "  ✓")
        out.append("")

    kept = [(j, u) for j, u in enumerate(us) if u is not None]
    r = len(kept)
    out += [bar, "NORMALIZE  q_i = u_i / |u_i|", bar]
    qs = []
    for j, u in kept:
        uu = sum(a * a for a in u)
        q = np.array([float(a) for a in u]) / float(uu) ** 0.5
        qs.append(q)
        out.append(f"   |u{j + 1}| = {_sqrt_text(uu)}     q{j + 1} = u{j + 1} / {_sqrt_text(uu).split(' = ')[0]} = {fmt_vec(np.round(q, 4))}")
    out += ["", f"   {r} orthonormal vector{'s' if r != 1 else ''}: unit length, mutually perpendicular.",
            f"   They span the same {r}-dimensional space as the original vectors."]
    if r:
        Q = np.column_stack(qs)
        G = Q.T @ Q
        out.append(f"   Q^T Q = I check: max |Q^T Q - I| = {np.max(np.abs(G - np.eye(r))):.1e}")
    out.append("")

    data = {"k": k, "d": d, "us": us, "qs": qs, "kept": [j for j, _ in kept], "coeffs": coeffs}
    out += [bar, "QR FACTORIZATION  A = Q R", bar,
            f"A = [v1 ... v{k}] as COLUMNS ({d}x{k}):", fmt_frac_mat([[vf[j][i] for j in range(k)] for i in range(d)])]
    if r == 0:
        out.append("   all vectors are zero: nothing to factor.")
        return "\n".join(out), data
    Q = np.column_stack(qs)
    A = V.T
    R = Q.T @ A
    R[np.abs(R) < 1e-12] = 0.0
    data["Q"] = Q; data["R"] = R
    qnames = " ".join(f"q{j + 1}" for j in data["kept"])
    out += [f"Q = [{qnames}] ({d}x{r}), orthonormal columns:", _num_mat(np.round(Q, 4)),
            f"R = Q^T A ({r}x{k}), upper triangular (r_ij = q_i . v_j):", _num_mat(np.round(R, 4)),
            "   R is triangular because v_j has no component along q_i for i > j:",
            "   v_j lives in span{q1..qj}.",
            f"   check: max |Q R - A| = {np.max(np.abs(Q @ R - A)):.1e}", ""]
    if r < k:
        out.append(f"   (rank {r} < {k}: Q has only {r} columns and R has a zero row for each dependent v.)")
        out.append("")
    unames = " ".join(f"u{j + 1}" for j in data["kept"])
    out += ["EXACT VERSION (before normalizing)",
            f"   A = U C with U = [{unames}] (orthogonal, not unit) and C upper triangular",
            "   holding the projection coefficients with 1s on the diagonal:"]
    U = [[us[j][i] for j in data["kept"]] for i in range(d)]
    C = [[Fraction(0)] * k for _ in range(r)]
    for col in range(k):
        for row_i, j in enumerate(data["kept"]):
            if j == col:
                C[row_i][col] = Fraction(1)
            elif j in coeffs[col]:
                C[row_i][col] = coeffs[col][j]
    out += ["U =", fmt_frac_mat(U), "C =", fmt_frac_mat(C), ""]
    out += ["WHY BOTHER", "   With an orthonormal basis, the projection of any w onto the span is simply",
            "   (w . q1) q1 + (w . q2) q2 + ...  -- no system to solve. Least squares becomes",
            "   R x = Q^T b, a triangular system solved by back-substitution."]
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Change of basis
# ----------------------------------------------------------------------

def _inverse_frac(M):
    """Exact inverse via Gauss-Jordan (None if singular)."""
    n = len(M)
    aug = [list(M[i]) + [Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    R, piv, _ = rref_steps(aug, ncols=n)
    if len(piv) < n:
        return None
    return [row[n:] for row in R]


def _matmul_frac(X, Y):
    return [[sum(X[i][k] * Y[k][j] for k in range(len(Y))) for j in range(len(Y[0]))] for i in range(len(X))]


def basis_text(B, x, A=None):
    """B: n basis vectors of R^n as ROWS. x: a vector in standard
    coordinates. A: optional n x n matrix to re-express. Returns (text, data)."""
    B = np.asarray(B, dtype=float)
    n = B.shape[0]
    if B.shape[1] != n:
        raise ValueError(f"A basis of R^{B.shape[1]} needs exactly {B.shape[1]} vectors.")
    bf = [[to_fraction(a) for a in row] for row in B]
    xf = [to_fraction(a) for a in np.asarray(x, dtype=float).ravel()]
    P = [[bf[j][i] for j in range(n)] for i in range(n)]          # basis vectors as columns
    bar = "=" * 60
    names = [f"b{j + 1}" for j in range(n)]
    out = [bar, f"CHANGE OF BASIS IN R^{n}", bar]
    for j in range(n):
        out.append(f"   b{j + 1} = {_frac_vec(bf[j])}")
    out += ["", "P = [b1 ... bn] with the basis vectors as COLUMNS (the change-of-basis matrix):",
            fmt_frac_mat(P)]
    det = _det_frac(P)
    data = {"n": n, "ok": det != 0}
    out.append(f"   det P = {fmt_frac(det)}")
    if det == 0:
        out += [f"   det P = 0: these vectors are DEPENDENT, so they are NOT a basis of R^{n}.",
                "   Fix a vector (or use Random fill) so that det P is not 0."]
        return "\n".join(out), data
    out += [f"   det P is not 0: the vectors are independent, so they form a BASIS of R^{n}.", ""]
    Pinv = _inverse_frac(P)
    data["P"] = P; data["Pinv"] = Pinv

    # ---- coordinates of x -----------------------------------------------
    out += [bar, f"COORDINATES OF x = {_frac_vec(xf)} IN THE BASIS", bar,
            "Want c1, ..., cn with  x = c1 b1 + ... + cn bn,  i.e.  P c = x.",
            "Reduce [P | x]:"]
    aug = [P[i] + [xf[i]] for i in range(n)]
    R, piv, _ = rref_steps(aug, ncols=n)
    out.append(fmt_frac_mat(R, bar_after=n))
    c = [R[i][n] for i in range(n)]
    data["coords"] = [float(q) for q in c]
    combo = " + ".join(f"({fmt_frac(q)}) {nm}" for q, nm in zip(c, names))
    recon = [sum(c[j] * bf[j][i] for j in range(n)) for i in range(n)]
    out += [f"   [x]_B = {_frac_vec(c)}",
            f"   check: {combo} = {_frac_vec(recon)} = x  ✓", "",
            "The same thing with the inverse:  [x]_B = P^-1 x", "P^-1 =", fmt_frac_mat(Pinv),
            f"   P^-1 x = {_frac_vec([sum(Pinv[i][j] * xf[j] for j in range(n)) for i in range(n)])}  ✓", "",
            "Reading the two matrices:",
            "   P     converts B-coordinates to standard coordinates:  x = P [x]_B",
            "   P^-1  converts standard coordinates to B-coordinates:  [x]_B = P^-1 x",
            "   The columns of P^-1 are the B-coordinates of the standard basis vectors e1, e2, ...", ""]

    # ---- a matrix in the new basis -------------------------------------
    if A is not None:
        Af = [[to_fraction(a) for a in row] for row in np.asarray(A, dtype=float)]
        AB = _matmul_frac(_matmul_frac(Pinv, Af), P)
        data["AB"] = [[float(q) for q in row] for row in AB]
        out += [bar, "A MATRIX IN THE NEW BASIS   [A]_B = P^-1 A P", bar, "A (standard coordinates) =", fmt_frac_mat(Af), "",
                "To apply A to B-coordinates: convert to standard (P), apply A, convert back (P^-1).",
                "[A]_B = P^-1 A P =", fmt_frac_mat(AB)]
        isdiag = all(AB[i][j] == 0 for i in range(n) for j in range(n) if i != j)
        if isdiag:
            out += ["   DIAGONAL! Each b_i is an EIGENVECTOR of A: A b_i = " +
                    ", ".join(f"({fmt_frac(AB[i][i])}) b{i + 1}" for i in range(n)) + ".",
                    "   In this basis A is just a scaling along each axis."]
        Ax = [sum(Af[i][j] * xf[j] for j in range(n)) for i in range(n)]
        AxB = [sum(Pinv[i][j] * Ax[j] for j in range(n)) for i in range(n)]
        ABc = [sum(AB[i][j] * c[j] for j in range(n)) for i in range(n)]
        out += ["", "   check on x:",
                f"      A x = {_frac_vec(Ax)}  ->  [A x]_B = P^-1 (A x) = {_frac_vec(AxB)}",
                f"      [A]_B [x]_B = {_frac_vec(ABc)}   same  ✓", "",
                "   Similar matrices share what does not depend on coordinates:",
                f"      trace: {fmt_frac(sum(Af[i][i] for i in range(n)))} = {fmt_frac(sum(AB[i][i] for i in range(n)))}"
                f"      det: {fmt_frac(_det_frac(Af))} = {fmt_frac(_det_frac(AB))}"
                "      (and the eigenvalues).", ""]
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Matrix powers and Markov chains
# ----------------------------------------------------------------------

def powers_text(A, x0, k=10):
    """A^2, A^3, ..., the sequence x_j = A^j x0, the eigen-explanation of
    its long-run behaviour, and Markov steady state when A is stochastic.
    Returns (text, data) with data['traj'] the (k+1) x n float trajectory."""
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    x0 = np.asarray(x0, dtype=float).ravel()
    Af = [[to_fraction(a) for a in row] for row in A]
    xf = [to_fraction(a) for a in x0]
    bar = "=" * 60
    out = [bar, f"POWERS OF A ({n}x{n}) AND THE SEQUENCE x_j = A^j x0", bar, "A =", fmt_frac_mat(Af),
           f"x0 = {_frac_vec(xf)}", ""]

    # ---- exact powers -------------------------------------------------
    out += ["THE POWERS  (A^j = A applied j times)"]
    Pk = [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    shown = {2, 3, k} if k > 3 else set(range(2, k + 1))
    xk = list(xf)
    traj = [x0.copy()]
    for j in range(1, k + 1):
        Pk = _matmul_frac(Af, Pk)
        xk = [sum(Af[i][m] * xk[m] for m in range(n)) for i in range(n)]
        traj.append(np.array([float(q) for q in xk]))
        if j in shown:
            big = any(q.denominator > 10 ** 6 or abs(q) > 10 ** 9 for row in Pk for q in row)
            out.append(f"A^{j} =")
            out.append(_num_mat([[float(q) for q in row] for row in Pk]) if big else fmt_frac_mat(Pk))
    out.append("")
    traj = np.array(traj)
    data = {"n": n, "k": k, "traj": traj}

    out += ["THE SEQUENCE  x_j = A x_(j-1) = A^j x0"]
    for j in range(0, k + 1):
        if j <= 6 or j == k or j % max(1, k // 6) == 0:
            out.append(f"   x_{j:<2} = {fmt_vec(np.round(traj[j], 4))}     |x_{j}| = {np.linalg.norm(traj[j]):.4g}")
    out.append("")

    # ---- Markov? -------------------------------------------------------
    col_stoch = np.all(A >= -1e-12) and np.allclose(A.sum(axis=0), 1)
    row_stoch = np.all(A >= -1e-12) and np.allclose(A.sum(axis=1), 1)
    data["markov"] = bool(col_stoch)
    if col_stoch:
        out += [bar, "MARKOV CHAIN", bar,
                "Entries are >= 0 and every COLUMN sums to 1: A is a (column-)stochastic matrix.",
                "A_ij = probability of moving to state i from state j; x_j = state distribution",
                f"after j steps (x0 sums to {fmt_frac(sum(xf))}; the sum is preserved at every step)."]
        # steady state: null space of A - I, normalized to sum 1
        B = [[Af[i][j] - (1 if i == j else 0) for j in range(n)] for i in range(n)]
        R, piv, _ = rref_steps(B)
        _, basis = null_space_from_rref(R, piv, n)
        if basis:
            v = basis[0]; tot = sum(v)
            if tot != 0:
                ss = [q / tot for q in v]
                data["steady"] = np.array([float(q) for q in ss])
                out += ["Steady state: the distribution s with A s = s, i.e. (A - I) s = 0, scaled to sum 1:",
                        "   (A - I) reduced:", fmt_frac_mat(R),
                        f"   s = {_frac_vec(ss)} = {fmt_vec(np.round(data['steady'], 4))}"]
                positive = np.all(np.linalg.matrix_power(A, n * n) > 0)
                if positive:
                    dist = np.linalg.norm(traj[-1] / max(traj[-1].sum(), 1e-12) - data["steady"])
                    out += ["   A is REGULAR (some power has all entries > 0), so every starting",
                            "   distribution converges to s. Distance of x_k (normalized) from s: "
                            f"{dist:.2e}"]
                else:
                    out.append("   A is not regular (some transitions stay impossible); convergence is not guaranteed.")
            if len(basis) > 1:
                out.append(f"   ({len(basis)} independent steady states: the chain has separate absorbing parts.)")
        out.append("")
    elif row_stoch and not np.allclose(A, A.T):
        out += ["Note: the ROWS of A sum to 1 (row-stochastic). This tab multiplies x_(j+1) = A x_j,",
                "so use the transpose of A to treat it as a Markov chain here.", ""]

    # ---- eigen explanation --------------------------------------------
    out += [bar, "WHY IT BEHAVES THIS WAY: EIGENVALUES", bar]
    d = eigen_analysis(A)
    data["eig"] = d
    eigvals = [e for e in d["eigs"]]
    out.append("   eigenvalues: " + ", ".join(_fmt_eig(e) + (f" (x{e['alg']})" if e["alg"] > 1 else "") for e in eigvals))
    mags = [abs(complex(e["value"])) for e in eigvals]
    if d["diagonalizable"]:
        vecs = [v for e in d["eigs"] for v in e["vectors"]]
        lams = [e["value"] for e in d["eigs"] for _ in e["vectors"]]
        P = np.array([[float(v[i]) for v in vecs] for i in range(n)])
        c = np.linalg.solve(P, x0)
        out += ["   A is diagonalizable: A^j = P D^j P^-1, so with x0 = c1 v1 + ... + cn vn,",
                "      x_j = c1 λ1^j v1 + c2 λ2^j v2 + ...   (each eigen-part just scales by λ_i each step)",
                "   coefficients c = P^-1 x0: " + ", ".join(f"c{i + 1} = {ci:.4g}" for i, ci in enumerate(c))]
        for i, (lam, v) in enumerate(zip(lams, vecs)):
            vv = np.array([float(q) for q in v])
            out.append(f"      λ{i + 1} = {fmt_num(float(lam))},  v{i + 1} = {fmt_vec(np.round(vv, 4))}: "
                       + ("grows" if abs(float(lam)) > 1 else "decays" if abs(float(lam)) < 1 else "stays")
                       + (" and flips sign each step" if float(lam) < 0 else ""))
        order = np.argsort([-abs(float(l)) for l in lams])
        i0 = order[0]
        if len(lams) > 1 and abs(abs(float(lams[i0])) - abs(float(lams[order[1]]))) > 1e-9 and abs(c[i0]) > 1e-12:
            out += [f"   Dominant eigenvalue λ{i0 + 1} = {fmt_num(float(lams[i0]))}: for large j, "
                    f"x_j ≈ c{i0 + 1} λ{i0 + 1}^j v{i0 + 1}, so",
                    f"   the DIRECTION of x_j settles onto v{i0 + 1} and |x_j| changes by the factor "
                    f"{abs(float(lams[i0])):.4g} per step."]
            vv = np.array([float(q) for q in vecs[i0]]); vv /= np.linalg.norm(vv)
            xk = traj[-1] / max(np.linalg.norm(traj[-1]), 1e-300)
            out.append(f"   check at j = {k}: |cos(angle between x_k and v{i0 + 1})| = {abs(xk @ vv):.6f}")
            out.append(f"   ratio |x_{k}| / |x_{k - 1}| = {np.linalg.norm(traj[-1]) / max(np.linalg.norm(traj[-2]), 1e-300):.6g}"
                       f"   (-> |λ{i0 + 1}| = {abs(float(lams[i0])):.6g})")
    elif any(not e["real"] for e in eigvals):
        z = next(complex(e["value"]) for e in eigvals if not e["real"])
        rmod, ang = abs(z), np.degrees(np.arctan2(z.imag, z.real))
        out += [f"   complex eigenvalues {_fmt_eig(next(e for e in eigvals if not e['real']))}: each step ROTATES by "
                f"{abs(ang):.4g}° and scales by |λ| = {rmod:.4g},",
                "   so the sequence " + ("spirals outward." if rmod > 1 else "spirals inward to 0." if rmod < 1 else "circles (an ellipse) forever.")]
    else:
        out += ["   A is defective (not diagonalizable): powers pick up polynomial factors in j",
                "   on top of λ^j (e.g. a shear grows linearly)."]
    if max(mags) < 1 - 1e-9:
        out.append("   All |λ| < 1: x_j -> 0 whatever x0 is.")
    elif abs(max(mags) - 1) < 1e-9 and not any(not e["real"] for e in eigvals):
        out.append("   Largest |λ| = 1: the sequence settles (or oscillates) without blowing up.")
    elif max(mags) > 1 + 1e-9:
        out.append(f"   Largest |λ| = {max(mags):.4g} > 1: the sequence blows up.")
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Singular value decomposition
# ----------------------------------------------------------------------

def _rng(name, a, b):
    """'u1' or 'u1..u3'."""
    return f"{name}{a}" if a == b else f"{name}{a}..{name}{b}"


def svd_text(A):
    """A = U S V^T built from the eigen-decomposition of A^T A, with checks
    and the geometric reading. Returns (text, data{U, s, Vt, r})."""
    A = np.asarray(A, dtype=float)
    m, n = A.shape
    Af = [[to_fraction(a) for a in row] for row in A]
    bar = "=" * 60
    out = [bar, f"SINGULAR VALUE DECOMPOSITION OF A ({m}x{n})", bar, "A =", fmt_frac_mat(Af), "",
           "Every matrix factors as  A = U Σ V^T:",
           f"   V ({n}x{n}) orthonormal columns v_i in R^{n}   (right singular vectors)",
           f"   Σ ({m}x{n}) diagonal with σ1 >= σ2 >= ... >= 0  (singular values)",
           f"   U ({m}x{m}) orthonormal columns u_i in R^{m}   (left singular vectors)",
           "   Meaning: A sends v_i to σ_i u_i. Perpendicular directions in, perpendicular out,",
           "   each stretched by its own σ_i. (A = rotate/reflect, then stretch, then rotate/reflect.)", ""]

    # ---- via A^T A --------------------------------------------------------
    AtA = [[sum(Af[k][i] * Af[k][j] for k in range(m)) for j in range(n)] for i in range(n)]
    out += ["HOW TO FIND IT:  A^T A = V Σ^T Σ V^T is symmetric, so its eigenvectors are the v_i",
            "and its eigenvalues are σ_i^2 (never negative).", f"A^T A ({n}x{n}) =", fmt_frac_mat(AtA)]
    d = eigen_analysis(AtA)
    lam_txt = ", ".join(_fmt_eig(e) + (f" (x{e['alg']})" if e["alg"] > 1 else "") for e in d["eigs"])
    out.append(f"   eigenvalues of A^T A: {lam_txt}")
    for e in d["eigs"]:
        if e["real"] and e["exact"] and e["vectors"]:
            out.append(f"   λ = {_fmt_eig(e)} -> σ = {_sqrt_text(e['value']) if e['value'] >= 0 else '0'}"
                       f",  eigenvector(s): " + ", ".join(_frac_vec(v) for v in e["vectors"]))
        elif e["real"] and e["vectors"]:
            out.append(f"   λ = {_fmt_eig(e)} -> σ = {max(float(e['value']), 0) ** 0.5:.4g},  eigenvector: "
                       + ", ".join(fmt_vec(np.round(np.asarray(v, dtype=float), 4)) for v in e["vectors"]))
    out.append("   (numerically, normalized and ordered by σ:)")

    U, sv, Vt = np.linalg.svd(A)
    sv = np.where(sv < 1e-10, 0.0, sv)
    r = int(np.sum(sv > 0))
    data = {"U": U, "s": sv, "Vt": Vt, "r": r, "m": m, "n": n}
    S = np.zeros((m, n)); S[:len(sv), :len(sv)] = np.diag(sv)
    out += ["V^T =", _num_mat(np.round(Vt, 4)), "Σ =", _num_mat(np.round(S, 4)), "U =", _num_mat(np.round(U, 4)), ""]
    out += ["CHECKS"]
    for i in range(min(m, n)):
        Av = A @ Vt[i]
        out.append(f"   A v{i + 1} = {fmt_vec(np.round(Av, 4))} = σ{i + 1} u{i + 1} = "
                   f"{fmt_num(sv[i])} x {fmt_vec(np.round(U[:, i], 4))}  ✓")
    out += [f"   U Σ V^T reproduces A: max error {np.max(np.abs(U @ S @ Vt - A)):.1e}",
            f"   U^T U = I: {np.max(np.abs(U.T @ U - np.eye(m))):.1e},   V^T V = I: {np.max(np.abs(Vt @ Vt.T - np.eye(n))):.1e}", ""]

    # ---- reading it -----------------------------------------------------
    out += [bar, "WHAT THE SVD TELLS YOU", bar,
            f"   singular values: {', '.join(fmt_num(v) for v in sv)}",
            f"   rank(A) = number of nonzero σ = {r}"]
    if r:
        out.append(f"   column space of A: spanned by {_rng('u', 1, r)}")
    if r < n:
        out.append(f"   null space of A: spanned by {_rng('v', r + 1, n)}  (A squashes those directions to 0)")
    if r < m:
        out.append(f"   left null space: spanned by {_rng('u', r + 1, m)}")
    out.append(f"   unit {'circle' if n == 2 else 'sphere' if n == 3 else 'sphere'} in R^{n} -> "
               f"{'ellipse' if m == 2 else 'ellipsoid'} in R^{m} with semi-axes σ_i along u_i")
    if r:
        out.append(f"   largest stretch σ1 = {fmt_num(sv[0])} (along v1);  smallest nonzero σ{r} = {fmt_num(sv[r - 1])}")
        if r == min(m, n) and sv[r - 1] > 0:
            out.append(f"   condition number σ1/σ{r} = {sv[0] / sv[r - 1]:.4g}"
                       + ("   (large: A is nearly singular, solutions are sensitive)" if sv[0] / sv[r - 1] > 30 else ""))
    out.append(f"   |A|_F = sqrt(σ1^2 + σ2^2 + ...) = {np.sqrt(np.sum(sv ** 2)):.4g}")
    if m == n:
        detA = float(np.linalg.det(A))
        out.append(f"   |det A| = σ1 σ2 ... = {np.prod(sv):.4g}" + (f"   (det A = {detA:.4g})" if abs(detA) > 1e-12 else ""))
        if np.allclose(A, A.T):
            out.append("   A is symmetric: σ_i = |λ_i| and the singular vectors are eigenvectors.")
    out.append("")
    if r >= 2:
        A1 = sv[0] * np.outer(U[:, 0], Vt[0])
        out += ["LOW-RANK APPROXIMATION", "   A = σ1 u1 v1^T + σ2 u2 v2^T + ... (rank-1 pieces, biggest first).",
                "   Keeping only the first piece:", "   A1 = σ1 u1 v1^T =", _num_mat(np.round(A1, 4)),
                f"   error |A - A1| (spectral norm) = σ2 = {fmt_num(sv[1])}: the best rank-1 approximation.", ""]
    out += ["THE PICTURE", "   Watch the unit circle/sphere go through the three stages:",
            "      V^T rotates it (v_i land on the axes), Σ stretches along the axes by σ_i,",
            "      U rotates the result into place. Their product is A."]
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Compact solve summary (for hand-off results)
# ----------------------------------------------------------------------

def solve_summary(A, b):
    """{'label', 'x', 'null'}: the unique / particular / least-squares
    solution as floats, plus a null-space basis (rows) when solutions
    form a family."""
    A = np.asarray(A, dtype=float); b = np.asarray(b, dtype=float).ravel()
    m, n = A.shape
    M = [[to_fraction(v) for v in row] + [to_fraction(bv)] for row, bv in zip(A, b)]
    R, piv, _ = rref_steps(M, ncols=n)
    bad = any(all(R[i][j] == 0 for j in range(n)) and R[i][n] != 0 for i in range(m))
    if bad:
        xhat = np.linalg.lstsq(A, b, rcond=None)[0]
        return {"label": "least-squares solution x̂", "x": xhat, "null": None}
    xp = np.zeros(n)
    for i, c in enumerate(piv):
        xp[c] = float(R[i][n])
    free, basis = null_space_from_rref(R, piv, n)
    if basis:
        return {"label": "particular solution x_p", "x": xp,
                "null": np.array([[float(q) for q in v] for v in basis])}
    return {"label": "solution x", "x": xp, "null": None}


# ----------------------------------------------------------------------
# Least-squares curve fitting
# ----------------------------------------------------------------------

def fit_text(D, degree=1):
    """Fit y = c0 + c1 x + ... + cd x^d to points (rows of D) by least
    squares, exactly via the normal equations. Returns (text, data)."""
    D = np.asarray(D, dtype=float)
    if D.ndim != 2 or D.shape[1] != 2:
        raise ValueError("Data needs two columns: x and y, one point per row.")
    xs, ys = D[:, 0], D[:, 1]
    k = len(xs); p = degree + 1
    xf = [to_fraction(v) for v in xs]; yf = [to_fraction(v) for v in ys]
    A = [[x ** j for j in range(p)] for x in xf]
    bar = "=" * 60
    model = " + ".join(["c0"] + [f"c{j} x" + (f"^{j}" if j > 1 else "") for j in range(1, p)])
    out = [bar, f"LEAST-SQUARES FIT OF {k} POINTS BY  y = {model}", bar]
    for i in range(k):
        out.append(f"   ({fmt_frac(xf[i])}, {fmt_frac(yf[i])})")
    out += ["", "Each point gives one equation in the unknown coefficients c:",
            f"   c0 + c1 x_i" + (" + ..." if p > 2 else "") + " = y_i     i.e.   A c = y   with the design matrix",
            f"A ({k}x{p}), rows [1, x_i" + (", x_i^2, ..." if p > 2 else "") + "]:", fmt_frac_mat(A),
            f"y = {_frac_vec(yf)}", ""]
    if k > p:
        out += [f"{k} equations, {p} unknowns: usually NO exact solution. Least squares picks the c",
                "that makes the residual r = y - A c as short as possible."]
    elif k == p:
        out += [f"{k} equations, {p} unknowns: the curve can pass through every point exactly (if the x's differ)."]
    else:
        out += [f"only {k} points for {p} unknowns: infinitely many curves fit exactly; the normal equations are singular."]
    out.append("")

    AtA = [[sum(A[r][i] * A[r][j] for r in range(k)) for j in range(p)] for i in range(p)]
    Aty = [sum(A[r][i] * yf[r] for r in range(k)) for i in range(p)]
    out += ["NORMAL EQUATIONS   A^T A c = A^T y", "   (they say A^T r = 0: the residual is orthogonal to every column of A)",
            f"A^T A ({p}x{p}) =", fmt_frac_mat(AtA), f"A^T y = {_frac_vec(Aty)}", "Reduce [A^T A | A^T y]:"]
    aug = [AtA[i] + [Aty[i]] for i in range(p)]
    R, piv, _ = rref_steps(aug, ncols=p)
    out.append(fmt_frac_mat(R, bar_after=p))
    data = {"k": k, "degree": degree, "xs": xs, "ys": ys}
    if len(piv) < p:
        out += ["   A^T A is singular: too few distinct x values for this degree.",
                "   Lower the degree or add points with new x values."]
        c = np.linalg.lstsq(np.array([[float(v) for v in row] for row in A]), ys, rcond=None)[0]
        out.append(f"   (minimum-norm coefficients from numpy: {fmt_vec(np.round(c, 4))})")
        data["c"] = c; data["exact"] = False
    else:
        cf = [R[i][p] for i in range(p)]
        c = np.array([float(q) for q in cf])
        data["c"] = c; data["exact"] = True
        out += [f"   c = {_frac_vec(cf)}", "",
                "FITTED CURVE   y = " + " + ".join(f"({fmt_frac(cf[j])})" + ("" if j == 0 else " x" + (f"^{j}" if j > 1 else "")) for j in range(p))]
        yhat = [sum(A[r][j] * cf[j] for j in range(p)) for r in range(k)]
        res = [yf[r] - yhat[r] for r in range(k)]
        sse = sum(q * q for q in res)
        out += ["", "   x        y        fitted     residual"]
        for r in range(k):
            out.append(f"   {fmt_frac(xf[r]):<8} {fmt_frac(yf[r]):<8} {fmt_num(yhat[r]):<10} {fmt_num(res[r])}")
        Atr = [sum(A[r][i] * res[r] for r in range(k)) for i in range(p)]
        ybar = sum(yf) / k
        sst = sum((q - ybar) ** 2 for q in yf)
        out += ["", f"   sum of squared residuals SSE = {fmt_num(sse)}     (the minimum possible for this model)",
                f"   check A^T r = {_frac_vec(Atr)} = 0  ✓   (r is perpendicular to the column space of A)"]
        if sst > 0:
            out.append(f"   R^2 = 1 - SSE/SST = 1 - ({fmt_num(sse)})/({fmt_num(sst)}) = {float(1 - sse / sst):.4f}"
                       "   (share of the variation in y that the curve explains)")
        if sse == 0:
            out.append("   SSE = 0: the curve passes through every point exactly.")
        data["yhat"] = np.array([float(q) for q in yhat]); data["res"] = np.array([float(q) for q in res])
        data["sse"] = float(sse)
        # QR route as a cross-check
        An = np.array([[float(v) for v in row] for row in A])
        Q, Rq = np.linalg.qr(An)
        cq = np.linalg.solve(Rq, Q.T @ ys)
        out += ["", "THE SAME ANSWER VIA QR   (A = QR, then R c = Q^T y, a triangular solve)",
                f"   c = {fmt_vec(np.round(cq, 4))}   max difference from the normal-equations c: {np.max(np.abs(cq - c)):.1e}", "",
                "GEOMETRY", "   A c is the projection of y onto the column space of A (the space of all",
                "   values this model can produce). The fit is the closest reachable point; the",
                "   residual is the perpendicular drop from y to that space."]
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Complex eigenvalues of a real 2x2: rotation-scaling
# ----------------------------------------------------------------------

def _cvec(z):
    """'(-0.8 - 0.4i, 0.8 - 0.6i)' for a complex vector."""
    parts = []
    for c in np.asarray(z):
        re_, im_ = (0.0 if abs(c.real) < 1e-12 else c.real), (0.0 if abs(c.imag) < 1e-12 else c.imag)
        parts.append(f"{re_:.4g} {'+' if im_ >= 0 else '-'} {abs(im_):.4g}i")
    return "(" + ", ".join(parts) + ")"


def complex_eigen_text(A, x0=(1.0, 0.0), k=12):
    """For a real 2x2 with eigenvalues a ± bi: the factorization
    A = P C P^-1 with C = [[a, -b], [b, a]] = r x (rotation by phi), P =
    [Re v  Im v], plus the trajectory A^j x0 in both coordinate systems.
    Returns (text, data)."""
    A = np.asarray(A, dtype=float)
    if A.shape != (2, 2):
        raise ValueError("This module is for 2x2 matrices.")
    x0 = np.asarray(x0, dtype=float).ravel()
    Af = [[to_fraction(v) for v in row] for row in A]
    tr = Af[0][0] + Af[1][1]; det = Af[0][0] * Af[1][1] - Af[0][1] * Af[1][0]
    disc = tr * tr - 4 * det
    bar = "=" * 60
    out = [bar, "COMPLEX EIGENVALUES OF A REAL 2x2: ROTATION AND SCALING", bar, "A =", fmt_frac_mat(Af), "",
           "CHARACTERISTIC POLYNOMIAL",
           f"   p(λ) = λ^2 - (trace) λ + det = λ^2 - ({fmt_frac(tr)}) λ + ({fmt_frac(det)})",
           f"   discriminant = trace^2 - 4 det = {fmt_frac(tr * tr)} - {fmt_frac(4 * det)} = {fmt_frac(disc)}"]
    data = {"ok": disc < 0}
    if disc >= 0:
        out += ["   discriminant >= 0: the eigenvalues are REAL. There is no rotation hiding in A;",
                "   use the Eigen module for real eigenvectors. (Try a preset here for a complex pair.)"]
        return "\n".join(out), data
    a = float(tr) / 2; b = float(np.sqrt(-float(disc))) / 2
    r = float(np.hypot(a, b)); phi = float(np.degrees(np.arctan2(b, a)))
    out += ["   discriminant < 0: the roots are a COMPLEX CONJUGATE PAIR",
            f"   λ = ({fmt_num(tr)})/2 ± i sqrt({fmt_frac(-disc)})/2 = {a:.4g} ± {b:.4g} i", "",
            "WHAT A COMPLEX EIGENVALUE MEANS",
            "   No real direction is kept fixed, so A must turn every vector. Write λ in polar form:",
            f"   |λ| = sqrt(a^2 + b^2) = {r:.4g}        angle φ = atan2(b, a) = {phi:.4g}°",
            "   The claim: in the right coordinates, A is exactly 'rotate by φ, scale by |λ|'.", ""]

    # complex eigenvector for lambda = a - b i  (Lay's convention gives C = [[a,-b],[b,a]])
    lam = complex(a, -b)
    M = A.astype(complex) - lam * np.eye(2)
    # v solves M v = 0: take v = (-M[0,1], M[0,0]) unless that row is zero
    if abs(M[0, 0]) + abs(M[0, 1]) > 1e-12:
        v = np.array([-M[0, 1], M[0, 0]])
    else:
        v = np.array([-M[1, 1], M[1, 0]])
    v = v / v[np.argmax(np.abs(v))]              # tidy scale
    Re, Im = v.real, v.imag
    P = np.column_stack([Re, Im])
    C = np.array([[a, -b], [b, a]])
    Pinv = np.linalg.inv(P)
    Cchk = Pinv @ A @ P
    out += [f"AN EIGENVECTOR FOR λ = {a:.4g} - {b:.4g} i",
            f"   solve (A - λI) v = 0:   v = {fmt_vec(np.round(Re, 4))} + i {fmt_vec(np.round(Im, 4))}",
            f"   check: A v = {_cvec(A @ v)}  and  λ v = {_cvec(lam * v)}  ✓", "",
            "THE FACTORIZATION   A = P C P^-1",
            "   P = [Re v  Im v] (real and imaginary parts as columns), C = [[a, -b], [b, a]]:",
            "P =", _num_mat(np.round(P, 4)), "C =", _num_mat(np.round(C, 4)),
            "   check P^-1 A P =", _num_mat(np.round(Cchk, 4)), f"   max error {np.max(np.abs(Cchk - C)):.1e}  ✓", "",
            "READING C",
            f"   C = |λ| x [[cos φ, -sin φ], [sin φ, cos φ]] = {r:.4g} x rotation by {phi:.4g}°",
            f"   ({r:.4g} cos {phi:.4g}° = {round(r * np.cos(np.radians(phi)), 10):.4g} = a,   "
            f"{r:.4g} sin {phi:.4g}° = {round(r * np.sin(np.radians(phi)), 10):.4g} = b)",
            "   So A acts on P-coordinates (u = P^-1 x) as a pure rotation-scaling. In standard",
            "   coordinates the rotation looks skewed: circles become the ellipse P(unit circle).", ""]
    behaviour = ("spiral INWARD toward 0" if r < 1 - 1e-9 else "spiral OUTWARD" if r > 1 + 1e-9 else "go round an ELLIPSE forever (|λ| = 1)")
    out += ["THE TRAJECTORY  x_j = A^j x0", f"   x0 = {fmt_vec(x0)};  each step rotates by {phi:.4g}° (in P-coordinates) and scales by {r:.4g},",
            f"   so the points {behaviour}. After {360 / abs(phi) if phi else float('inf'):.3g} steps they have gone once around."]
    traj = [x0.copy()]
    for _ in range(k):
        traj.append(A @ traj[-1])
    traj = np.array(traj)
    utraj = traj @ Pinv.T
    out.append("   j     x_j (standard)          u_j = P^-1 x_j (P-coords)     |u_j|")
    for j in range(min(k, 8) + 1):
        out.append(f"   {j:<3}  {fmt_vec(np.round(traj[j], 3)):<22}  {fmt_vec(np.round(utraj[j], 3)):<26}  {np.linalg.norm(utraj[j]):.4g}")
    if k > 8:
        out.append(f"   ...  (to j = {k})")
    out += [f"   |u_j| shrinks/grows by exactly {r:.4g} each step, and the angle of u_j advances by {phi:.4g}°.", "",
            "POWERS", f"   A^j = P C^j P^-1 with C^j = {r:.4g}^j x rotation by j x {phi:.4g}°."]
    data.update({"a": a, "b": b, "r": r, "phi": phi, "P": P, "C": C, "Pinv": Pinv, "Re": Re, "Im": Im,
                 "traj": traj, "utraj": utraj, "k": k})
    return "\n".join(out), data


# ----------------------------------------------------------------------
# Saved-matrix library: one JSON file per named matrix
# ----------------------------------------------------------------------

# The library lives in Application Support: a bundled app can read and
# write there freely. Folders under ~/Documents need a macOS consent
# dialog (again after every rebuild of an ad-hoc-signed app), which was
# blocking the app for minutes when the dialog went unnoticed.
SUPPORT_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "MatrixLab")
DEFAULT_LIBRARY_DIR = os.path.join(SUPPORT_DIR, "Matrices")
OLD_LIBRARY_DIRS = [os.path.join(os.path.expanduser("~"), "Documents", "MatrixLab Matrices"),
                    os.path.join(os.path.expanduser("~"), "Documents", "TransposeDot Matrices")]
DOCUMENTS_SHORTCUT = os.path.join(os.path.expanduser("~"), "Documents", "MatrixLab Matrices")

DEFAULT_EXAMPLE = {
    "A": [[1, 0, 1], [0, 1, 2]],
    "x": [1, 2, 2],
    "y": [2, 1],
    "B": [[1, 2], [3, 4], [5, 6]],
}
FIELDS = ("A", "x", "y", "B", "b", "V", "w", "u", "v", "D", "k")


class MatrixLibrary:
    """Named JSON files in a folder. The folder normally sits in
    ~/Documents, where every access from a bundled app goes through
    macOS privacy checks (and iCloud file coordination), which can take
    seconds. So: touch the folder lazily, and cache the listing."""

    CACHE_SECONDS = 15

    def __init__(self, directory=DEFAULT_LIBRARY_DIR):
        self.directory = directory
        self._names = None
        self._names_time = 0.0
        self._ready = False
        self._lock = threading.Lock()

    def _ensure_dir(self):
        if self._ready:
            return
        os.makedirs(self.directory, exist_ok=True)
        self._ready = True

    def migrate_from_documents(self):
        """Move saved matrices from the old Documents folders into the
        library (one-time; touches Documents, so call it off the UI
        thread). Returns the number of files moved."""
        if self.directory != DEFAULT_LIBRARY_DIR:
            return 0
        moved = 0
        for old in OLD_LIBRARY_DIRS:
            try:
                if os.path.islink(old) or not os.path.isdir(old):
                    continue
                self._ensure_dir()
                for f in os.listdir(old):
                    if f.endswith(".json") and not f.startswith("."):
                        dst = os.path.join(self.directory, f)
                        if not os.path.exists(dst):
                            os.rename(os.path.join(old, f), dst)
                            moved += 1
                if not os.listdir(old):
                    os.rmdir(old)
            except OSError:
                continue
        if moved:
            self.invalidate()
        return moved

    def invalidate(self):
        """Forget the cached listing (after a save/delete, or on demand)."""
        self._names = None

    def _path(self, name):
        safe = re.sub(r"[^\w .,()+\-]", "_", name).strip()
        if not safe:
            raise ValueError("Please give the matrix a name.")
        return os.path.join(self.directory, safe + ".json")

    def names(self, force=False):
        import time as _time
        with self._lock:
            if (not force and self._names is not None
                    and _time.time() - self._names_time < self.CACHE_SECONDS):
                return list(self._names)
            self._ensure_dir()
            self._names = sorted(os.path.splitext(f)[0] for f in os.listdir(self.directory)
                                 if f.endswith(".json") and not f.startswith("."))
            self._names_time = _time.time()
            return list(self._names)

    def warm_up(self):
        """List the folder on a background thread so the first module to
        open finds the listing already cached (the first access from a
        bundled app can take a second or two of privacy checks)."""
        threading.Thread(target=self.names, daemon=True).start()

    @staticmethod
    def _clean(v):
        v = np.asarray(v, dtype=float)
        return v.tolist()

    def save(self, name, **fields):
        """Save/merge fields (A, x, y, B). Fields not given keep whatever
        the file already holds, so the Multiply tab's B survives a save
        from the Transpose-Dot tab and vice versa."""
        self._ensure_dir()
        path = self._path(name)
        data = {}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
        for k, v in fields.items():
            if k in FIELDS and v is not None:
                data[k] = self._clean(v)
        if not any(k in data for k in FIELDS):
            raise ValueError("Nothing to save.")
        data["name"] = name
        if "A" in data:
            data["rows"], data["cols"] = len(data["A"]), len(data["A"][0])
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        if self._names is not None and name not in self._names:
            self._names = sorted(self._names + [name])

    def load(self, name):
        """Return a dict with A and whichever of x, y, B are stored."""
        with open(self._path(name)) as f:
            data = json.load(f)
        return {k: data[k] for k in FIELDS if k in data}

    def delete(self, name):
        os.remove(self._path(name))
        if self._names is not None and name in self._names:
            self._names.remove(name)
