#!/usr/bin/env python3
"""Sanity check: port of Board.evaluate() from GameModel.swift plus a BFS
Sokoban solver over push-moves. If a level is solvable under these rules,
the rules and the map data are at least consistent."""
import sys, time, collections
sys.path.insert(0, ".")
import gen_levels  # parses sokoban.des; also regenerates Levels.swift (harmless)

DIRS8 = [(0,-1),(0,1),(-1,0),(1,0),(-1,-1),(1,-1),(-1,1),(1,1)]
DIRS4 = DIRS8[:4]

class Level:
    def __init__(self, lv):
        self.rows = lv["rows"]; self.w = len(self.rows[0]); self.h = len(self.rows)
        self.start = lv["start"]; self.exit = lv["exit"]
        self.boulders = frozenset(lv["boulders"]); self.traps = frozenset(lv["traps"])
        self.goal = self.exit or lv["places"][0]
        self.id = lv["id"]
    def inb(self, p): return 0 <= p[0] < self.w and 0 <= p[1] < self.h
    def terrain(self, p): return self.rows[p[1]][p[0]] if self.inb(p) else " "
    def is_rock(self, p): return self.terrain(p) in " -|"

def evaluate(L, boulders, traps, u, d, allow_push):
    t = (u[0]+d[0], u[1]+d[1])
    if not L.inb(t) or L.is_rock(t): return "blocked"
    diag = d[0] != 0 and d[1] != 0
    bad = lambda p: L.is_rock(p) or p in boulders
    if diag:
        if L.terrain(t) == "+" or L.terrain(u) == "+": return "blocked"
        if bad((u[0], t[1])) and bad((t[0], u[1])): return "blocked"
    if t in boulders:
        if not allow_push or diag: return "blocked"
        b = (t[0]+d[0], t[1]+d[1])
        if not L.inb(b) or L.is_rock(b) or b in boulders: return "blocked"
        return "push"
    if t in traps: return "blocked"
    return "move"

def reachable(L, boulders, traps, start):
    seen = {start}; q = collections.deque([start])
    while q:
        u = q.popleft()
        for d in DIRS8:
            if evaluate(L, boulders, traps, u, d, False) == "move":
                v = (u[0]+d[0], u[1]+d[1])
                if v not in seen: seen.add(v); q.append(v)
    return seen

def frozen(L, p):
    """Boulder wedged against walls on both axes; can never move again."""
    ns = L.is_rock((p[0], p[1]-1)) or L.is_rock((p[0], p[1]+1))
    ew = L.is_rock((p[0]-1, p[1])) or L.is_rock((p[0]+1, p[1]))
    return ns and ew

def solve(L, limit_s=300):
    t0 = time.time()
    start = (L.boulders, L.traps, L.start)
    def key(state):
        b, t, p = state
        return (b, t, min(reachable(L, b, t, p)))
    seen = {key(start): None}
    q = collections.deque([start])
    parent = {}
    while q:
        b, t, p = q.popleft()
        region = reachable(L, b, t, p)
        if L.goal in region:
            n = 0; k = key((b, t, p))
            while parent.get(k): n += 1; k = parent[k]
            return n, len(seen), time.time() - t0
        if time.time() - t0 > limit_s: return None, len(seen), time.time() - t0
        for bl in b:
            for d in DIRS4:
                u = (bl[0]-d[0], bl[1]-d[1])
                if u not in region: continue
                if evaluate(L, b, t, u, d, True) != "push": continue
                beyond = (bl[0]+d[0], bl[1]+d[1])
                nb = set(b); nb.remove(bl); nt = set(t)
                if beyond in t: nt.remove(beyond)
                else: nb.add(beyond)
                nb, nt = frozenset(nb), frozenset(nt)
                # prune: not enough movable boulders left for the remaining traps
                movable = sum(1 for x in nb if not frozen(L, x))
                if movable < len(nt): continue
                ns = (nb, nt, bl)
                k = key(ns)
                if k in seen: continue
                seen[k] = True; parent[k] = key((b, t, p)); q.append(ns)
    return None, len(seen), time.time() - t0

ids = sys.argv[1:] or ["soko4-1", "soko4-2"]
for lv in gen_levels.levels:
    if lv["id"] not in ids: continue
    L = Level(lv)
    pushes, states, secs = solve(L)
    print(f'{L.id}: {"SOLVED in %d pushes" % pushes if pushes is not None else "NOT solved"}; {states} states, {secs:.1f}s')
