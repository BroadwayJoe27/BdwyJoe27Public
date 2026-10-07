# MatrixLab

A small suite of linear-algebra demos, one per tab, sharing a matrix
editor and a library of saved matrices. Started life as a front end for
`TransposeDot.py` / `TransposeDotAnim.py` (still in the parent folder).

## Layout

A sidebar on the left lists the modules by chapter, in course order:

| chapter | modules |
|---|---|
| Vectors | Vectors, Span |
| Matrices as maps | Multiply, Transpose · Dot, Determinant · Inverse, Transform |
| Systems and subspaces | Row Reduce, Solve Ax = b, Subspaces, Basis, Orthogonalize, Fit |
| Eigen and beyond | Eigen, Complex Eigen, Powers · Markov, SVD |

The chosen module fills the rest of the window. Modules are built the
first time they are opened, so launch is instant. The **Overview** page
describes each module with a clickable name. Cmd+[ and Cmd+] step through
the modules, Cmd+0 returns to the Overview, and the Modules menu can reopen the last
module used (remembered in ~/Library/Application Support/MatrixLab).

### Results and hand-off

Every module records its characteristic results each time it recomputes:
Vectors gives u × v, the projections, the dot and triple products, lengths, the angle, and the matrix with rows u, v, w; Row Reduce its RREF and null
space basis, Solve the solution (or particular / least-squares solution)
and null space, Subspaces its four bases, Span the basis of the span,
Multiply AB and BA, Transpose·Dot Aᵀ, Ax and Aᵀy, Determinant A⁻¹, Eigen
the eigenvectors with P and D, Orthogonalize the orthogonal and
orthonormal sets with Q and R, Basis P, P⁻¹, [x]_B and [A]_B, Powers Aᵏ,
x_k and the steady state, SVD U, Σ, Vᵀ, V and the rank-1 approximation.

**Send…** (sidebar button, Modules menu, Cmd+Shift+S) opens a dialog
listing the module's inputs and results with a preview, the destination
module, and the slot to load into (only slots that fit are offered; a
vector can go into a one-row matrix slot, a one-row matrix into a
vector slot, and a scalar such as a determinant, dot product, triple
product, rank or R² arrives as a 1×1 matrix or a length-1 vector). The destination keeps its other inputs. **Save to
library…** in the same dialog stores the chosen input or result under a
name you confirm, so results never have to be retyped or saved by hand.
**Quick send inputs to…** is the one-click shortcut for passing the
current inputs unchanged.

## Modules

**Transpose · Dot** — the adjoint identity **(A x) · y = x · (Aᵀ y)**.
Edit A (m × n); x ∈ Rⁿ and y ∈ Rᵐ resize with it. Every arithmetic step is
printed, and for m, n ≤ 3 the two-panel figure (domain and codomain, row
space, null space, projection of x) and the sweeping-y animation are drawn.
File menu saves the figure as PNG or the animation as GIF.

**Multiply** — edit A (m × n) and B (n × p). B's row count is locked to A's
column count so AB always exists. A scalar k (default 1) adds scalar
multiplication: kA and kB entry by entry and the check (kA)B = k(AB), and
a scalar sent from another module lands in k. The result pane shows A, B, AB and BA in
matrix form, expands every entry as (row) · (column), says when BA is
undefined (p ≠ m), and whether AB = BA when both are the same size.

**Row Reduce** — edit A (m × n) and read Gauss-Jordan elimination as a
narrative: every elementary row operation (swap, scale, add a multiple of a
row) with the matrix after it, the point where row echelon form is reached,
then reduced row echelon form. Arithmetic is exact in fractions, so 0.5 is
1/2 and thirds stay thirds. The result section lists pivot columns, rank,
free columns, nullity, and a basis for the null space read off the RREF.
Ticking **LU factorization** adds PA = LU: the downward pass again but
without scaling, each multiplier ℓᵢⱼ written into L as it clears an entry
(L and U shown side by side at every step), P only when a zero pivot forces
a swap, a check that LU = PA, and det A from U's diagonal. L, U and P join
the tab's results for Send….

**Solve Ax = b** — edit A (m × n) and b ∈ Rᵐ (b's length follows A's
rows). The augmented matrix [A | b] is reduced with the same exact-fraction
engine (row operations optional). The pane then says whether the system is
consistent by looking for a "0 = c" row, gives the unique solution or the
general solution as a particular solution plus the null space with every
piece checked against A, and for an inconsistent system works the
least-squares x̂ from the normal equations, showing the projection of b,
the residual, and Aᵀr = 0. Ticking **Solve by LU** (square, invertible A)
factors PA = LU instead and shows forward substitution L y = Pb and back
substitution U x = y term by term; change b and only the substitutions
change. For a singular or non-square A it says why and falls back to row
reduction.

**Subspaces** — edit A (m × n) and get exact bases for the four
fundamental subspaces: row space (nonzero rows of RREF) and null space in
Rⁿ, column space (pivot columns of the original A) and left null space
(null space of Aᵀ) in Rᵐ. The text checks the dimension counts
r + (n − r) = n and r + (m − r) = m and dots every pair of basis vectors to
show the orthogonality. For m, n ≤ 3 the domain and codomain are drawn with
the subspaces shaded as lines or planes and their basis vectors as arrows.

**Span** — enter k vectors in Rᵈ as the rows of a grid, plus an optional
target w. The tab makes them the columns of A, reduces, and reports
independence or each dependence relation read from a free column ("v3 =
v1 + v2"), a basis and dimension for the span (line, plane, all of Rᵈ),
and whether w is in the span with the combination that reaches it. For
d ≤ 3 the vectors are drawn with redundant ones dashed, the span shaded,
and w in orange with its distance to the span when it lies outside.

**Determinant · Inverse** — edit a square A (columns follow rows). The
determinant is worked two ways: cofactor expansion along row 1, written
out in full for 2×2 and 3×3, and elimination to triangular form where row
additions leave det alone and swaps flip its sign. Then the inverse by
Gauss-Jordan on [A | I] with the check A·A⁻¹ = I, and for n ≤ 3 the
adjugate formula as a second method. A singular A shows the zero row of
RREF and a null vector as the witness that no inverse can exist. For n = 2
or 3 the unit square or cube and its image are drawn, with |det| as the
area or volume factor and a colour change when orientation is reversed.

**Transform** — a 2×2 or 3×3 matrix as a map of the plane or of space.
Pick a preset (rotation by an angle you type, reflections, shears,
scalings, projections, a singular squash) or enter A, choose a shape (grid
with unit square, circle, letter F, or cube, sphere, arrow), then drag the
t slider or press Play to morph the shape from the identity to A along
M(t) = (1 − t)I + tA. The original stays as a gray ghost and the images of
the basis vectors are drawn as arrows. The text says where each basis
vector goes, what the determinant means here, which kind of map A is
(rotation with its angle or axis, reflection with its line, scaling,
shear, projection, symmetric stretch, or general), and the stretch
factors that turn the unit circle or sphere into an ellipse or ellipsoid.

**Eigen** — a square A up to 6×6. The characteristic polynomial
det(λI − A) is built exactly (with the 2×2 expansion written out and the
trace/determinant coefficients pointed out), rational eigenvalues are
found exactly by the rational-root test and shown as factors, the rest
numerically; complex pairs are explained as "no fixed direction". For each
real eigenvalue, A − λI and its RREF are shown, the null space gives the
eigenvectors, and A v = λ v is checked. Algebraic vs geometric multiplicity
decides diagonalizability, with P and D printed when A = P D P⁻¹ exists
and orthogonality checks when A is symmetric. An examples menu covers
symmetric, shear (defective), rotation (complex), reflection, projection,
and irrational cases. For 2×2 and 3×3 the eigen-directions are drawn with
v and Av; for 2×2, Play sweeps a unit vector x around the circle next to
Ax with a strip chart of the angle between them, so eigenvectors appear as
the moments the two line up (0° or 180°).

**Vectors** — two vectors u and v in R² or R³ and an optional third
vector w. The text works u·v term by term, the lengths, the angle with its
acute/obtuse/orthogonal reading, the projection of u onto v with the
perpendicular remainder and the distance to the line, and in R³ the cross
product by the i-j-k determinant with the sign-flip on j pointed out,
orthogonality to both inputs, |u × v| as the parallelogram area checked
against |u||v| sin θ, the right-hand rule, and anticommutativity. In R² the
signed area stands in for the cross product. With w: the triple product
as a determinant and a volume, coplanarity, and the projection of w onto
the plane of u and v with its distance. The figure shades the
parallelogram, draws the projection and perpendicular, u × v, the plane,
and w with its drop onto the plane.

**Orthogonalize** — Gram-Schmidt and QR. Enter k vectors in Rᵈ as rows.
Each vector is orthogonalized against the ones before it in exact
fractions, with every projection coefficient (v·u / u·u) and subtracted
vector shown and orthogonality checked as it goes; a vector that comes out
as zero is reported as dependent and dropped. The survivors are
normalized, and A = QR is assembled with R = QᵀA shown upper triangular
and the reason why, plus the exact A = UC before normalizing. For d ≤ 3
the originals are drawn thin, the orthogonalized set bold in matching
colours, and the removed projections dotted.

**Basis** — change of basis. Enter n basis vectors of Rⁿ as rows (presets
include rotated, skewed, scaled and a 3D staircase), a vector x, and
optionally a matrix A. The text checks det P ≠ 0, finds [x]_B by reducing
[P | x] exactly and checks the recombination, prints P and P⁻¹ with what
each converts, expresses A in the new basis as [A]_B = P⁻¹AP with a check
on x and the shared trace and determinant, and celebrates when [A]_B is
diagonal because the basis is an eigenbasis. "Use eigenvectors of A" fills
the basis from the Eigen machinery when a real eigenbasis exists. For
n = 2 the skewed grid of the new basis is drawn; for n = 2, 3 the basis
arrows and x as the dashed path c₁b₁ then c₂b₂ ... that reaches it.

**Powers · Markov** — a square A, a start vector x₀ and a step count k.
The text prints A², A³ and Aᵏ exactly, the sequence xⱼ = Aʲx₀ with its
lengths, then explains the long-run behaviour through the eigenvalues:
Aʲ = PDʲP⁻¹ turns x₀ into a sum of eigen-parts each scaling by λⱼ, the
dominant eigenvalue sets the growth factor and the direction xⱼ settles
onto (checked numerically at step k), complex pairs give spirals with the
rotation angle and |λ|, and a defective A grows polynomially. When A is
column-stochastic the Markov reading appears: the steady state from
(A − I)s = 0 scaled to sum 1, whether the chain is regular, and how close
x_k is to the steady state. Examples include a weather chain, a 3-state
chain, an absorbing chain, Fibonacci, a spiral, growth vs decay, a shear,
and a reflection. The figure shows the trajectory in state space for
n = 2, 3 with eigen-directions and the steady state starred, plus every
component of xⱼ against j.

**SVD** — any m × n matrix. The text explains A = UΣVᵀ as "rotate, stretch,
rotate", derives it from AᵀA (symmetric, so its eigenvectors are the vᵢ
and its eigenvalues σᵢ², shown exactly when they are rational), prints
Vᵀ, Σ and U, and checks A vᵢ = σᵢ uᵢ, UΣVᵀ = A, and the orthonormality of
U and V. Then the reading: rank as the count of nonzero σ, column and null
space bases from the singular vectors, the unit circle or sphere mapped
to an ellipse or ellipsoid with semi-axes σᵢ, largest and smallest
stretch, condition number with a warning when it is large, Frobenius
norm, |det| as the product of σ, and the best rank-1 approximation with
its error σ₂. For square 2×2 and 3×3 the figure shows the four stages:
unit shape with the vᵢ, after Vᵀ (the vᵢ on the axes), after ΣVᵀ
(stretched), after UΣVᵀ = A. Other shapes up to 3×3 get a domain and
codomain pair.

**Fit** — least-squares curve fitting. Enter data points (x, y) one per
row and pick a polynomial degree (0 to 5), or use an example. The text
builds the design matrix A and the system A c = y, explains why there is
usually no exact solution, forms the normal equations AᵀA c = Aᵀy
exactly and solves them by reduction, prints the fitted curve, a table of
fitted values and residuals, the sum of squared residuals, the check
Aᵀr = 0, and R², then cross-checks the coefficients through QR and closes
with the projection picture. A singular AᵀA (too few distinct x values
for the degree) is explained. The figure shows the data, the curve, each
residual as a dashed drop, and a bar chart of the residuals.

**Complex Eigen** — a real 2×2 whose eigenvalues are a complex pair
a ± bi. The text computes the discriminant, writes λ in polar form
(|λ| and φ), finds a complex eigenvector, splits it into real and
imaginary parts to build P, and checks A = PCP⁻¹ with C = [[a, −b],
[b, a]] = |λ| × rotation by φ. It then follows x_j = Aʲx₀ in both
coordinate systems, tabulating |u_j| shrinking or growing by exactly |λ|
per step. Presets include Lay's example, a pure rotation, rotate-and-scale,
a spiral, a skewed circle with |λ| = 1, and a real-eigenvalue case that
explains why there is nothing to draw. The figure shows the skewed spiral
on the ellipse P(circle) with Re v and Im v beside the true spiral in
P-coordinates; Play reveals the steps one at a time.

## Shared behaviour

- Cells accept integers, decimals, or fractions like `1/2`. Sizes go up to 8 × 8.
- **Live update** (checkbox): recompute about a third of a second after you
  stop typing. Uncheck it to use the *Compute* button instead.
- **Saved matrices** panel on every module: one JSON file per name in
  `~/Library/Application Support/MatrixLab/Matrices/` (File menu opens the
  folder, or adds a shortcut to it in Documents). The library is kept out of
  Documents on purpose: a bundled app's access to Documents needs a macOS
  consent dialog, repeated after every rebuild, which blocked the app for
  minutes when the dialog went unnoticed. Matrices saved by earlier
  versions in Documents can be moved over with File > Import Matrices
  from the Old Documents Folder. The ↻ button
  rescans the folder after you add or remove files by hand. Click a
  name to preview it, double-click to load. The orange "Working on:" line
  shows what you are editing and whether it has unsaved edits. *Save /
  Update* overwrites the loaded name without asking. Each tab saves the
  fields it owns (A, x, y / A, B / A / A, b / A / V, w / A / A / A / u, v, w / V / V, x, A / A, x / A / D / A, x) and leaves the others alone, so one
  saved name can carry both a Transpose·Dot setup and a Multiply pair.
- Each module is split by a draggable divider between the controls and the
  result pane.

## Run from the terminal

```bash
python3 app.py
```

## Build the macOS application

```bash
./build_app.sh
```

produces `dist/MatrixLab.app`. Copy it to `/Applications` and double-click.
Rebuild after changing any `.py` file here, then replace the copy in
Applications.

## Files

| file | role |
|---|---|
| `core.py` | number parsing, adjoint-identity steps, AB/BA text, exact Gauss-Jordan engine (`rref_steps`), Ax = b solver with least squares, four-subspace bases, span/independence, determinant and inverse, transformation presets and description, exact characteristic polynomial and eigen-analysis, dot/cross/projection narration, Gram-Schmidt/QR, change of basis, matrix powers and Markov steady states, SVD narration, least-squares fitting, complex-eigenvalue rotation-scaling, matrix library |
| `plots.py` | figures for the Transpose·Dot, Subspaces, Span, Determinant, Transform, Eigen, Vectors, Orthogonalize, Basis, Powers and SVD tabs (dimensions ≤ 3) |
| `widgets.py` | `MatrixEditor`, `VectorEditor`, `LibraryPanel` shared by all tabs |
| `transpose_tab.py` | Transpose · Dot tab |
| `multiply_tab.py` | Multiply tab |
| `rowreduce_tab.py` | Row Reduce tab |
| `solve_tab.py` | Solve Ax = b tab |
| `subspaces_tab.py` | Subspaces tab |
| `span_tab.py` | Span tab |
| `det_tab.py` | Determinant · Inverse tab |
| `transform_tab.py` | Transform tab |
| `eigen_tab.py` | Eigen tab |
| `vectors_tab.py` | Vectors tab |
| `gs_tab.py` | Orthogonalize (Gram-Schmidt / QR) tab |
| `basis_tab.py` | Basis (change of basis) tab |
| `powers_tab.py` | Powers · Markov tab |
| `svd_tab.py` | SVD tab |
| `fit_tab.py` | Fit (least squares) tab |
| `cplx_tab.py` | Complex Eigen (rotation-scaling) tab |
| `app.py` | main window: sidebar navigator, overview page, lazy modules, send-to handoff, menus |
| `build_app.sh` | PyInstaller command for the `.app` |

## Adding a module

Make a `ttk.Frame` subclass that builds its controls from `MatrixEditor`
and `LibraryPanel`, provides `get_fields()` / `load_fields(fields)` (raise
`KeyError` naming the missing field when the given fields do not fit),
declares `ACCEPTS = {field: "matrix" | "vector"}`, fills `self.results`
(label → array) in `compute`, and add one line to `CHAPTERS` in `app.py`.
