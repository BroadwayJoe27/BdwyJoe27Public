#!/usr/bin/env python3
"""Prove levels solvable under the app's rules, by finding a solution.

A Python port of Board.evaluate() (GameModel.swift), including iron bars
and lava, and a best-first push search in C++ (solver/soko_solve.cpp, built
on first use with the system c++). A level counts as
solved when the hero can walk to the up stairs, or on a prize level to
every closet the prize might be in. Not every pit or hole has to be
filled: some UnNetHack levels have more traps than boulders.

Each solution the C++ search finds is replayed here step by step,
walking included, through the Python rules before it is reported, so a pass means a real move list
exists. No scrolls of earth and no pick-axe are assumed.

    python3 tools/solve_levels.py                 # every Expanded level
    python3 tools/solve_levels.py unh-soko2-3 ... # just these (also the way to
                                                  # try a level marked unproven)
    python3 tools/solve_levels.py --classic       # the eight Classic ones
    --search          search afresh even where tools/solutions.json already
                      has a move list (by default a stored list is just
                      re-checked, which takes a moment)
    --scale=X         multiply every search time limit by X
    --write           save the move lists to tools/solutions.json, for
                      tools/replay_solutions/main.swift to replay through
                      the real Board on the Mac
"""
import os, sys, time, collections, pathlib, io, contextlib, subprocess

here = pathlib.Path(__file__).parent
sys.path.insert(0, str(here))

DIRS8 = [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)]
DIRS4 = DIRS8[:4]


class Level:
    def __init__(self, lv):
        self.id = lv["id"]
        self.rows = lv["rows"]
        self.w, self.h = len(self.rows[0]), len(self.rows)
        self.start = tuple(lv["start"])
        self.boulders = frozenset(map(tuple, lv["boulders"]))
        self.traps = frozenset(map(tuple, lv["traps"]))
        self.goals = [tuple(lv["exit"])] if lv["exit"] else [tuple(p) for p in lv["places"]]

    def t(self, p):
        x, y = p
        return self.rows[y][x] if 0 <= x < self.w and 0 <= y < self.h else " "

    def rock(self, p):   # Terrain.isRock: stone and walls
        return self.t(p) in " -|"


def evaluate(L, boulders, traps, u, d, allow_push):
    """Mirror of Board.evaluate: 'move', 'push' or 'blocked'."""
    t = (u[0] + d[0], u[1] + d[1])
    tt = L.t(t)
    if tt in " -|":
        return "blocked"
    diag = d[0] and d[1]
    if diag:
        if tt == "+" or L.t(u) == "+":
            return "blocked"
        a, b = (u[0], t[1]), (t[0], u[1])
        if (L.rock(a) or a in boulders) and (L.rock(b) or b in boulders):
            return "blocked"
    if tt == "F":
        return "blocked"
    if t in boulders:
        if not allow_push or diag:
            return "blocked"
        beyond = (t[0] + d[0], t[1] + d[1])
        if L.rock(beyond) or L.t(beyond) == "F" or beyond in boulders:
            return "blocked"
        return "push"
    if t in traps or tt == "L":
        return "blocked"
    return "move"


def apply_push(L, boulders, traps, bl, d):
    beyond = (bl[0] + d[0], bl[1] + d[1])
    nb = set(boulders); nb.remove(bl)
    nt = traps
    if beyond in traps:
        nt = traps - {beyond}
    elif L.t(beyond) != "L":          # into lava: the boulder sinks
        nb.add(beyond)
    return frozenset(nb), nt


def region(L, boulders, traps, start):
    seen = {start: None}
    q = collections.deque([start])
    while q:
        u = q.popleft()
        for d in DIRS8:
            v = (u[0] + d[0], u[1] + d[1])
            if v not in seen and evaluate(L, boulders, traps, u, d, False) == "move":
                seen[v] = u
                q.append(v)
    return seen


SOLVER_SRC = here / "solver" / "soko_solve.cpp"
SOLVER_BIN = here / "solver" / "build" / "soko_solve"


def solver_binary():
    """Build the C++ search on first use (and whenever its source changes)."""
    if not SOLVER_BIN.exists() or SOLVER_BIN.stat().st_mtime < SOLVER_SRC.stat().st_mtime:
        SOLVER_BIN.parent.mkdir(exist_ok=True)
        subprocess.run(["c++", "-O2", "-std=c++17", "-o", str(SOLVER_BIN), str(SOLVER_SRC)], check=True)
    return SOLVER_BIN


# Search settings tried in turn until one finds a solution: (arguments to
# soko_solve, seconds). The arguments are the starting cap on rearranging
# boulder moves between fills, the queue order and a random seed for
# tie-breaks; see main() in soko_solve.cpp. Different levels fall to
# different settings, and the randomised orders crack levels where every
# deterministic one stalls.
PORTFOLIO = ([(["1", "0"], 30), (["2", "0"], 60), (["6", "1"], 30)]
             + [(["12", order, str(seed)], 20) for seed in range(1, 51) for order in ("2", "3")])

# Settings already known to crack a level, tried before the portfolio so
# that re-solving it takes seconds rather than many minutes.
HINTS = {
    "unh-soko1-4": (["12", "2", "5"], 30),
    "unh-soko1-5": (["12", "3", "2"], 60),
    "unh-soko1-6": (["2", "0"], 120),
    "unh-soko2-3": (["12", "2", "5"], 60),
    "unh-soko3-13": (["6", "1"], 60),
}


def solve(L, scale=1.0):
    """Ask the C++ search for a push list. Returns (pushes or None, note)."""
    lines = [f"{L.w} {L.h}"] + [f'"{r}"' for r in L.rows]
    lines.append(f"{L.start[0]} {L.start[1]}")
    for ps in (sorted(L.boulders), sorted(L.traps), L.goals):
        lines.append(" ".join([str(len(ps))] + [f"{x} {y}" for x, y in ps]))
    t0 = time.time()
    for args, secs in ([HINTS[L.id]] if L.id in HINTS else []) + PORTFOLIO:
        inp = "\n".join(lines + [str(secs * scale)]) + "\n"
        out = subprocess.run([str(solver_binary())] + args, input=inp,
                             capture_output=True, text=True, check=True).stdout.split("\n")
        head = out[0].split()
        if head[0] == "SOLVED":
            pushes = []
            for row in out[1:1 + int(head[1])]:
                x, y, dx, dy = map(int, row.split())
                pushes.append(((x, y), (dx, dy)))
            return pushes, f"{time.time() - t0:.0f}s, settings {' '.join(args)}"
    return None, f"{time.time() - t0:.0f}s, every setting ran out of time"


# NetHack's movement keys, which tools/replay_solutions/main.swift reads back.
KEYS = {(-1, 0): "h", (0, 1): "j", (0, -1): "k", (1, 0): "l",
        (-1, -1): "y", (1, -1): "u", (-1, 1): "b", (1, 1): "n"}


def replay(L, pushes):
    """Walk and push through the solution one step at a time. Returns the
    moves as NetHack direction keys, or raises if any step is refused."""
    b, t, p = set(L.boulders), set(L.traps), L.start
    keys = []
    def walk(target):
        nonlocal p
        par = region(L, frozenset(b), frozenset(t), p)
        assert target in par, (L.id, "unreachable", target)
        path = []
        while target != p:
            path.append(target); target = par[target]
        for q in reversed(path):
            d = (q[0] - p[0], q[1] - p[1])
            assert evaluate(L, b, t, p, d, False) == "move", (L.id, p, d)
            p = q; keys.append(KEYS[d])
    for bl, d in pushes:
        walk((bl[0] - d[0], bl[1] - d[1]))
        assert evaluate(L, b, t, p, d, True) == "push", (L.id, "push refused", bl, d)
        nb, nt = apply_push(L, frozenset(b), frozenset(t), bl, d)
        b, t, p = set(nb), set(nt), bl
        keys.append(KEYS[d])
    for goal in L.goals:
        walk(goal)
    return "".join(keys)


def load(classic):
    with contextlib.redirect_stderr(io.StringIO()):
        if classic:
            import gen_levels as g
            return g.levels
        import gen_expanded as g
        return g.levels


def replay_keys(L, keys):
    """Check a stored move list against the Python rules: every step taken,
    the goal (every prize closet) visited by the end."""
    b, t, p = set(L.boulders), set(L.traps), L.start
    seen = {p}
    dirs = {k: d for d, k in KEYS.items()}
    for i, k in enumerate(keys):
        d = dirs[k]
        r = evaluate(L, b, t, p, d, True)
        assert r != "blocked", (L.id, "move", i + 1, "refused at", p, k)
        if r == "push":
            bl = (p[0] + d[0], p[1] + d[1])
            nb, nt = apply_push(L, frozenset(b), frozenset(t), bl, d)
            b, t = set(nb), set(nt)
        p = (p[0] + d[0], p[1] + d[1])
        seen.add(p)
    missed = [g for g in L.goals if g not in seen]
    assert not missed, (L.id, "never reached", missed)
    return len(keys)


def work(job):
    lv, scale, stored = job
    L = Level(lv)
    if stored is not None:
        return L.id, stored, f"stored solution checks out, {replay_keys(L, stored)} moves"
    pushes, note = solve(L, scale)
    if pushes is None:
        return L.id, None, f"NOT SOLVED ({note})"
    keys = replay(L, pushes)
    replay_keys(L, keys)
    return L.id, keys, f"solved, {len(pushes)} pushes, {len(keys)} moves ({note})"


if __name__ == "__main__":
    import json, multiprocessing
    args = sys.argv[1:]
    classic = "--classic" in args
    write = "--write" in args
    fresh = "--search" in args
    scale = next((float(a.split("=")[1]) for a in args if a.startswith("--scale=")), 1.0)
    ids = [a for a in args if not a.startswith("--")]
    out = here / "solutions.json"
    solutions = json.loads(out.read_text()) if out.exists() else {}
    # Levels marked unproven in gen_expanded.py are searched only on request.
    jobs = [(lv, scale, None if fresh else solutions.get(lv["id"]))
            for lv in load(classic)
            if (lv["id"] in ids) or (not ids and lv.get("proven", True))]
    solver_binary()
    failed = 0
    with multiprocessing.Pool(min(4, os.cpu_count() or 1)) as pool:
        for lid, keys, note in pool.imap(work, jobs):
            print(f"{lid}: {note}", flush=True)
            if keys is None:
                failed += 1
            else:
                solutions[lid] = keys
    if write:
        out.write_text(json.dumps(dict(sorted(solutions.items())), indent=1) + "\n")
        print(f"wrote {out.name} ({len(solutions)} levels)")
    print("ALL SOLVED" if not failed else f"{failed} NOT SOLVED")
    sys.exit(1 if failed else 0)
