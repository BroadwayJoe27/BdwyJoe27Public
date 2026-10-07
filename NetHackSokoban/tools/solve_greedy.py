#!/usr/bin/env python3
import sys, time, heapq, itertools
sys.path.insert(0, ".")
from solve_check import Level, evaluate, reachable, frozen, DIRS4, gen_levels

def solve(L, limit_s=240):
    t0 = time.time()
    trap_list = list(L.traps)
    def h(b, t):
        if not t: return (0, 0)
        # each remaining trap needs a boulder; sum of nearest-boulder distance per trap
        s = 0
        for tr in t:
            s += min(abs(tr[0]-x)+abs(tr[1]-y) for x, y in b)
        return (len(t), s)
    start = (L.boulders, L.traps, L.start)
    def key(b, t, p): return (b, t, min(reachable(L, b, t, p)))
    counter = itertools.count()
    seen = {key(*start)}
    heap = [(h(L.boulders, L.traps), 0, next(counter), start, [])]
    while heap:
        _, g, _, (b, t, p), path = heapq.heappop(heap)
        region = reachable(L, b, t, p)
        if L.goal in region: return path, len(seen), time.time()-t0
        if time.time()-t0 > limit_s: return None, len(seen), time.time()-t0
        for bl in b:
            for d in DIRS4:
                u = (bl[0]-d[0], bl[1]-d[1])
                if u not in region or evaluate(L, b, t, u, d, True) != "push": continue
                beyond = (bl[0]+d[0], bl[1]+d[1])
                nb = set(b); nb.remove(bl); nt = set(t)
                if beyond in t: nt.remove(beyond)
                else: nb.add(beyond)
                nb, nt = frozenset(nb), frozenset(nt)
                if sum(1 for x in nb if not frozen(L, x)) < len(nt): continue
                k = key(nb, nt, bl)
                if k in seen: continue
                seen.add(k)
                heapq.heappush(heap, (h(nb, nt), g+1, next(counter), (nb, nt, bl), path + [(bl, d)]))
    return None, len(seen), time.time()-t0

for lv in gen_levels.levels:
    if lv["id"] not in sys.argv[1:]: continue
    L = Level(lv)
    path, states, secs = solve(L)
    if path is None:
        print(f"{L.id}: NOT solved; {states} states, {secs:.1f}s")
    else:
        print(f"{L.id}: SOLVED with {len(path)} pushes; {states} states, {secs:.1f}s")
        print("   pushes:", " ".join(f"{b}{'NSWE'[DIRS4.index(d)]}" for b, d in path))
