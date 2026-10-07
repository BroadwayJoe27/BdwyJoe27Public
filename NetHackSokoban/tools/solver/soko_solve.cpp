// Fast search for NetHack-rules Sokoban levels. Driven by
// tools/solve_levels.py, which feeds it one level on stdin and replays the
// pushes it prints through the Python port of Board.evaluate(), so this
// program only has to find a solution, not be trusted.
//
// The search moves one boulder at a time, as far as it likes (a "boulder
// move": any run of pushes of that boulder alone, the others standing
// still). It is greedy about the pits and holes still between the hero and
// the goal, and within each count it looks for the fewest boulder moves
// that fill the next one, up to a cap on rearranging moves that is raised
// round by round if a round runs dry. Dead positions are cut early: boulders
// frozen against walls count as walls, and a state whose goal is walled off,
// or that has fewer usable boulders than traps in the way, is dropped.
//
// Build: c++ -O2 -std=c++17 -o soko_solve soko_solve.cpp
//
// Input (stdin):
//   W H
//   H map rows, each wrapped in quotes ("..."), so leading spaces survive
//   sx sy                       hero start
//   nb  x y ...                 boulders
//   nt  x y ...                 traps (pits or holes)
//   ng  x y ...                 goals: the up stairs, or every prize closet
//   limit_seconds
// Output: "SOLVED n" then n lines "x y dx dy" (the boulder's square and the
// push direction), or "UNSOLVED states".
#include <algorithm>
#include <cstdlib>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <iostream>
#include <queue>
#include <string>
#include <unordered_set>
#include <vector>

static int W, H, N;
static std::vector<char> T;  // terrain: ' ' rock, '.' floor, '+' door, 'F' bars, 'L' lava
static const int DX[8] = {0, 0, -1, 1, -1, 1, -1, 1};
static const int DY[8] = {-1, 1, 0, 0, -1, -1, 1, 1};
static int WORDS;

struct Bits {
    std::vector<uint64_t> w;
    Bits() : w(WORDS, 0) {}
    bool get(int i) const { return (w[i >> 6] >> (i & 63)) & 1; }
    void set(int i) { w[i >> 6] |= 1ull << (i & 63); }
    void clr(int i) { w[i >> 6] &= ~(1ull << (i & 63)); }
};

static inline bool inb(int x, int y) { return x >= 0 && y >= 0 && x < W && y < H; }
static inline char ter(int x, int y) { return inb(x, y) ? T[y * W + x] : ' '; }
static inline bool rock(int x, int y) { return ter(x, y) == ' '; }

enum { BLOCKED, MOVE, PUSH };

// Mirror of Board.evaluate() in GameModel.swift.
static int evaluate(const Bits& b, const Bits& t, int ux, int uy, int d, bool allowPush) {
    int tx = ux + DX[d], ty = uy + DY[d];
    char tt = ter(tx, ty);
    if (tt == ' ') return BLOCKED;
    bool diag = DX[d] && DY[d];
    if (diag) {
        if (tt == '+' || ter(ux, uy) == '+') return BLOCKED;
        bool a = rock(ux, ty) || (inb(ux, ty) && b.get(ty * W + ux));
        bool c = rock(tx, uy) || (inb(tx, uy) && b.get(uy * W + tx));
        if (a && c) return BLOCKED;
    }
    if (tt == 'F') return BLOCKED;
    int ti = ty * W + tx;
    if (b.get(ti)) {
        if (!allowPush || diag) return BLOCKED;
        int bx = tx + DX[d], by = ty + DY[d];
        char bt = ter(bx, by);
        if (bt == ' ' || bt == 'F' || b.get(by * W + bx)) return BLOCKED;
        return PUSH;
    }
    if (t.get(ti) || tt == 'L') return BLOCKED;
    return MOVE;
}

// Squares the hero can walk to (no pushing). Returns them as a bitset and
// the smallest index in it, which names the region in the state key.
static int region(const Bits& b, const Bits& t, int start, Bits& out, std::vector<int>& q) {
    out = Bits();
    q.clear();
    q.push_back(start);
    out.set(start);
    int mn = start;
    for (size_t i = 0; i < q.size(); i++) {
        int u = q[i], ux = u % W, uy = u / W;
        for (int d = 0; d < 8; d++) {
            int v = (uy + DY[d]) * W + ux + DX[d];
            if (!inb(ux + DX[d], uy + DY[d]) || out.get(v)) continue;
            if (evaluate(b, t, ux, uy, d, false) == MOVE) {
                out.set(v);
                q.push_back(v);
                mn = std::min(mn, v);
            }
        }
    }
    return mn;
}


// Boulders that can never move again: blocked on both axes by walls, bars,
// or other such boulders (the greatest set closed under that rule). A push
// needs the hero on one side and room on the other, so a wall, bars or lava
// on either side blocks that axis for good.
static Bits frozenBoulders(const Bits& b) {
    Bits f = b;
    auto solid = [&](int x, int y, const Bits& fz) {
        char c = ter(x, y);
        return c == ' ' || c == 'F' || c == 'L' || fz.get(y * W + x);
    };
    for (bool changed = true; changed;) {
        changed = false;
        for (int i = 0; i < N; i++) {
            if (!f.get(i)) continue;
            int x = i % W, y = i / W;
            bool h = solid(x - 1, y, f) || solid(x + 1, y, f);
            bool v = solid(x, y - 1, f) || solid(x, y + 1, f);
            if (!(h && v)) { f.clr(i); changed = true; }
        }
    }
    return f;
}

// Fewest traps on any route from `src` cells, boulders ignored. dist[v] counts
// traps entered up to and including v. Unreached cells stay at INF.
static const int INF = 1 << 29;
static void trapDist(const Bits& t, const Bits& frozen, const std::vector<int>& src, std::vector<int>& dist) {
    dist.assign(N, INF);
    std::deque<int> dq;
    for (int s : src) { dist[s] = 0; dq.push_back(s); }
    while (!dq.empty()) {
        int u = dq.front(); dq.pop_front();
        int ux = u % W, uy = u / W;
        for (int d = 0; d < 8; d++) {
            int vx = ux + DX[d], vy = uy + DY[d];
            if (!inb(vx, vy)) continue;
            char vt = ter(vx, vy);
            if (vt == ' ' || vt == 'F' || vt == 'L' || frozen.get(vy * W + vx)) continue;
            if (DX[d] && DY[d]) {
                if (vt == '+' || ter(ux, uy) == '+') continue;
                if (rock(ux, vy) && rock(vx, uy)) continue;
            }
            int v = vy * W + vx;
            int c = dist[u] + (t.get(v) ? 1 : 0);
            if (c < dist[v]) {
                dist[v] = c;
                if (c == dist[u]) dq.push_front(v); else dq.push_back(v);
            }
        }
    }
}

// A search state. The hero's whereabouts are kept as the smallest square
// of the region it can walk to, which is all that matters between moves.
struct Node {
    Bits b, t;
    int key;                 // smallest square of the hero's region
    int player;              // where the hero actually stands
    int parent;
    std::vector<int> pushes; // from the parent: boulder square * 4 + dir, each
};

static std::vector<int> traps, goals;
static std::vector<std::vector<int>> pdist;   // pdist[k][sq]: lone-boulder pushes from sq into trap k

// Hero-aware dead squares, worked out once per level. With a lone boulder
// on square c, comp[c][p] names the part of the level the hero at p can
// walk around in (other boulders ignored, traps walkable: the most room
// the hero could ever have). A boulder can only be pushed from a square in
// the hero's part, so (c, part) is the boulder's real situation. liveAt
// says whether a boulder in that situation can still be got into some
// trap. If not, no later move of other boulders can change that: it is
// dead, which catches boulders shoved into one-way corridors and corners
// that the plain dead-square test (pdist) misses.
static std::vector<std::vector<short>> comp;
static std::vector<int> compBase;     // index of (c, 0) in liveAt
static std::vector<char> liveAt;

static bool boulderSquare(int i) { char c = T[i]; return c == '.' || c == '+'; }

static void buildLiveness(const std::vector<int>& trapList) {
    std::vector<char> isTrap(N, 0);
    for (int t : trapList) isTrap[t] = 1;
    comp.assign(N, std::vector<short>());
    compBase.assign(N, -1);
    int total = 0;
    std::vector<int> q;
    for (int c = 0; c < N; c++) {
        if (!boulderSquare(c) || isTrap[c]) continue;
        auto& cc = comp[c];
        cc.assign(N, -1);
        short n = 0;
        auto bad = [&](int x, int y) { return rock(x, y) || y * W + x == c; };
        for (int s0 = 0; s0 < N; s0++) {
            if (s0 == c || cc[s0] >= 0 || !boulderSquare(s0)) continue;
            q.assign(1, s0);
            cc[s0] = n;
            for (size_t i = 0; i < q.size(); i++) {
                int u = q[i], ux = u % W, uy = u / W;
                for (int d = 0; d < 8; d++) {
                    int vx = ux + DX[d], vy = uy + DY[d];
                    if (!inb(vx, vy)) continue;
                    int v = vy * W + vx;
                    if (v == c || cc[v] >= 0 || !boulderSquare(v)) continue;
                    if (DX[d] && DY[d]) {
                        if (T[v] == '+' || T[u] == '+') continue;
                        if (bad(ux, vy) && bad(vx, uy)) continue;
                    }
                    cc[v] = n;
                    q.push_back(v);
                }
            }
            n++;
        }
        compBase[c] = total;
        total += n;
    }
    // A situation is live if some push from it lands in a trap, or in a live
    // situation. Fixpoint by repeated sweeps; the levels are small.
    liveAt.assign(total, 0);
    for (bool changed = true; changed;) {
        changed = false;
        for (int c = 0; c < N; c++) {
            if (compBase[c] < 0) continue;
            int cx = c % W, cy = c / W;
            for (int d = 0; d < 4; d++) {
                int ux = cx - DX[d], uy = cy - DY[d], tx = cx + DX[d], ty = cy + DY[d];
                if (!inb(ux, uy) || !inb(tx, ty)) continue;
                int u = uy * W + ux, t = ty * W + tx;
                if (!boulderSquare(u) || !boulderSquare(t)) continue;
                int k = comp[c][u];
                if (k < 0 || liveAt[compBase[c] + k]) continue;
                bool ok = isTrap[t] || (compBase[t] >= 0 && comp[t][c] >= 0 && liveAt[compBase[t] + comp[t][c]]);
                if (ok) { liveAt[compBase[c] + k] = 1; changed = true; }
            }
        }
    }
}

// Can the boulder on `c` still reach a trap, with the hero standing on `p`?
static bool boulderLive(int c, int p) {
    if (compBase[c] < 0) return false;
    int k = comp[c][p];
    return k >= 0 && liveAt[compBase[c] + k];
}

// (traps still on the cheapest route to the goals, pushes from the nearest
// boulder into a trap at the front of that route). False: a dead state.
// Boulders the hero would have to get past on the cheapest route to `goal`,
// counting traps first (each trap outweighs any number of boulders).
static int blockersTo(const Bits& b, const Bits& t, const Bits& fz, const std::vector<int>& src, int goal) {
    std::vector<int> dist(N, INF);
    typedef std::pair<int, int> E;
    std::priority_queue<E, std::vector<E>, std::greater<E>> pq;
    for (int s0 : src) { dist[s0] = 0; pq.push({0, s0}); }
    while (!pq.empty()) {
        auto [c, u] = pq.top(); pq.pop();
        if (c != dist[u]) continue;
        if (u == goal) return c % 1000;
        int ux = u % W, uy = u / W;
        for (int d = 0; d < 8; d++) {
            int vx = ux + DX[d], vy = uy + DY[d];
            if (!inb(vx, vy)) continue;
            char vt = ter(vx, vy);
            int v = vy * W + vx;
            if (vt == ' ' || vt == 'F' || vt == 'L' || fz.get(v)) continue;
            if (DX[d] && DY[d]) {
                if (vt == '+' || ter(ux, uy) == '+') continue;
                if (rock(ux, vy) && rock(vx, uy)) continue;
            }
            int nc = c + (t.get(v) ? 1000 : 0) + (b.get(v) ? 1 : 0);
            if (nc < dist[v]) { dist[v] = nc; pq.push({nc, v}); }
        }
    }
    return 999;
}

// Fewest other boulders standing in the way of rolling some boulder into
// trap `tr`: counted over the squares it rolls through and the squares the
// hero pushes from. 0 means a clear run exists (hero access aside).
static int obstruction(const Bits& b, const Bits& t, const Bits& fz, int tr) {
    // Backward from the trap: dist[sq] = obstructions to roll a boulder from sq into tr.
    std::vector<int> dist(N, INF);
    std::deque<int> dq{tr};
    dist[tr] = 0;
    while (!dq.empty()) {
        int s0 = dq.front(); dq.pop_front();
        int sx = s0 % W, sy = s0 / W;
        for (int d = 0; d < 4; d++) {
            int bx = sx - DX[d], by = sy - DY[d], ux = bx - DX[d], uy = by - DY[d];
            char bt = ter(bx, by), ut = ter(ux, uy);
            if ((bt != '.' && bt != '+') || (ut != '.' && ut != '+')) continue;
            int bi = by * W + bx, ui = uy * W + ux;
            if (fz.get(ui) || (t.get(bi) && bi != tr)) continue;
            int c = dist[s0] + (s0 != tr && b.get(s0) ? 1 : 0) + (b.get(ui) ? 1 : 0);
            if (c < dist[bi]) {
                dist[bi] = c;
                if (c == dist[s0]) dq.push_front(bi); else dq.push_back(bi);
            }
        }
    }
    int best = INF;
    for (int i = 0; i < N; i++)
        if (b.get(i) && !fz.get(i) && dist[i] < best) best = dist[i];
    return best;
}

static bool score(const Node& nd, const Bits& reg, int& need, int& minF, int& blk, int& obs) {
    Bits fz = frozenBoulders(nd.b);
    std::vector<int> src, fwd, gd;
    for (int i = 0; i < N; i++) if (reg.get(i)) src.push_back(i);
    trapDist(nd.t, fz, src, fwd);
    need = 0;
    int worst = 0;
    for (size_t g = 0; g < goals.size(); g++) {
        if (fwd[goals[g]] >= INF) return false;
        if (fwd[goals[g]] > need) { need = fwd[goals[g]]; worst = (int)g; }
    }
    int live = 0;
    for (int i = 0; i < N; i++) {
        if (!nd.b.get(i) || fz.get(i) || !boulderLive(i, nd.player)) continue;
        for (size_t k = 0; k < traps.size(); k++)
            if (nd.t.get(traps[k]) && pdist[k][i] < INF) { live++; break; }
    }
    if (live < need) return false;
    blk = blockersTo(nd.b, nd.t, fz, src, goals[worst]);
    minF = 0;
    obs = 0;
    if (need > 0) {
        minF = INF;
        trapDist(nd.t, fz, {goals[worst]}, gd);
        for (size_t k = 0; k < traps.size(); k++) {
            int tr = traps[k];
            if (!nd.t.get(tr) || fwd[tr] != 1 || fwd[tr] + gd[tr] - 1 != need) continue;
            for (int i = 0; i < N; i++)
                if (nd.b.get(i) && pdist[k][i] < minF) minF = pdist[k][i];
        }
        if (minF >= INF) minF = 1000;
        obs = INF;
        for (size_t k = 0; k < traps.size(); k++) {
            int tr = traps[k];
            if (!nd.t.get(tr) || fwd[tr] != 1 || fwd[tr] + gd[tr] - 1 != need) continue;
            obs = std::min(obs, obstruction(nd.b, nd.t, fz, tr));
        }
        if (obs >= INF) obs = 100;
    }
    return true;
}

// Every place one boulder can be taken by pushing it alone, starting from
// `nd`. Each result is a child node (parent and pushes filled in) whose
// boulder ended on a new square, in a trap, or in lava.
static void boulderMoves(const Node& nd, int from, int self, std::vector<Node>& out) {
    struct S { int pos, player, key, prev, push; bool gone; };
    std::vector<S> st;
    std::unordered_set<long long> seenS;
    Bits b = nd.b, t = nd.t, reg;
    std::vector<int> q;
    st.push_back({from, nd.player, nd.key, -1, -1, false});
    seenS.insert((long long)from * N + nd.key);
    for (size_t i = 0; i < st.size(); i++) {
        S cur = st[i];
        if (cur.gone) continue;
        // Board as of this sub-state: the boulder at cur.pos, traps as in nd
        // except the one this boulder may have filled (only at the end).
        b = nd.b; b.clr(from); b.set(cur.pos);
        region(b, t, cur.player, reg, q);
        int bx = cur.pos % W, by = cur.pos / W;
        for (int d = 0; d < 4; d++) {
            int ux = bx - DX[d], uy = by - DY[d];
            if (!inb(ux, uy) || !reg.get(uy * W + ux)) continue;
            if (evaluate(b, t, ux, uy, d, true) != PUSH) continue;
            int be = (by + DY[d]) * W + bx + DX[d];
            S nx{be, cur.pos, 0, (int)i, cur.pos * 4 + d, false};
            Bits nb = b;
            nb.clr(cur.pos);
            if (t.get(be) || T[be] == 'L') {
                nx.gone = true;
                nx.key = -1;
            } else {
                nb.set(be);
                Bits r2;
                std::vector<int> q2;
                nx.key = region(nb, t, cur.pos, r2, q2);
                long long k = (long long)be * N + nx.key;
                if (!seenS.insert(k).second) continue;
            }
            st.push_back(nx);
        }
    }
    for (size_t i = 1; i < st.size(); i++) {
        const S& s = st[i];
        if (!s.gone && s.pos == from) continue;
        Node ch;
        ch.b = nd.b; ch.t = nd.t;
        ch.b.clr(from);
        if (s.gone) { if (ch.t.get(s.pos)) ch.t.clr(s.pos); }
        else ch.b.set(s.pos);
        ch.player = s.player;
        Bits r; std::vector<int> qq;
        ch.key = region(ch.b, ch.t, ch.player, r, qq);
        ch.parent = self;
        for (int j = (int)i; st[j].prev >= 0; j = st[j].prev) ch.pushes.push_back(st[j].push);
        std::reverse(ch.pushes.begin(), ch.pushes.end());
        out.push_back(std::move(ch));
    }
}

int main(int argc, char** argv) {
    // Arguments: starting cap on rearranging boulder moves between fills,
    // queue order, random seed. Every order puts fewer traps in the way
    // first; then
    //   0: fewer boulder moves since the last fill, then the nearest trip;
    //   1: fewer boulders in the hero's way, then the nearest trip;
    //   2: fewer moves since the last fill, ties broken at random;
    //   3: fewer moves plus boulders in the way (of the hero, and of the
    //      best boulder's run to the next trap), ties broken at random.
    // Orders 2 and 3 want a nonzero seed; seed 0 breaks ties by nearest trip.
    int startCap = argc > 1 ? atoi(argv[1]) : 1;
    int order = argc > 2 ? atoi(argv[2]) : 0;
    unsigned seed = argc > 3 ? (unsigned)atoi(argv[3]) : 0;
    uint64_t rng = seed * 0x9E3779B97F4A7C15ull + 1;
    auto rnd = [&]() { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (int)(rng % 1000); };
    std::cin >> W >> H;
    N = W * H;
    WORDS = (N + 63) / 64;
    T.assign(N, ' ');
    std::string line;
    std::getline(std::cin, line);
    for (int y = 0; y < H; y++) {
        std::getline(std::cin, line);
        size_t a = line.find('"'), z = line.rfind('"');
        std::string row = line.substr(a + 1, z - a - 1);
        for (int x = 0; x < W && x < (int)row.size(); x++) {
            char c = row[x];
            T[y * W + x] = (c == '-' || c == '|') ? ' ' : c;
        }
    }
    int sx, sy, n;
    std::cin >> sx >> sy;
    Node root;
    std::cin >> n;
    for (int i = 0; i < n; i++) { int x, y; std::cin >> x >> y; root.b.set(y * W + x); }
    std::cin >> n;
    for (int i = 0; i < n; i++) { int x, y; std::cin >> x >> y; root.t.set(y * W + x); traps.push_back(y * W + x); }
    std::cin >> n;
    for (int i = 0; i < n; i++) { int x, y; std::cin >> x >> y; goals.push_back(y * W + x); }
    double limit;
    std::cin >> limit;

    buildLiveness(traps);
    pdist.assign(traps.size(), std::vector<int>(N, INF));
    for (size_t k = 0; k < traps.size(); k++) {
        auto& dist = pdist[k];
        std::deque<int> q{traps[k]};
        dist[traps[k]] = 0;
        while (!q.empty()) {
            int s = q.front(); q.pop_front();
            int sx2 = s % W, sy2 = s / W;
            for (int d = 0; d < 4; d++) {
                int bx = sx2 - DX[d], by = sy2 - DY[d], ux = bx - DX[d], uy = by - DY[d];
                char bt = ter(bx, by), ut = ter(ux, uy);
                if ((bt != '.' && bt != '+') || (ut != '.' && ut != '+')) continue;
                int bi = by * W + bx;
                if (dist[bi] != INF) continue;
                dist[bi] = dist[s] + 1;
                q.push_back(bi);
            }
        }
    }

    auto t0 = std::chrono::steady_clock::now();
    auto elapsed = [&] { return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(); };
    Bits reg;
    std::vector<int> q;
    root.player = sy * W + sx;
    root.key = region(root.b, root.t, root.player, reg, q);
    root.parent = -1;
    size_t total = 0;

    // Rounds with a growing cap on rearranging boulder moves between fills.
    for (int cap = startCap; cap <= 12; cap++) {
        std::vector<Node> nodes{root};
        std::vector<int> since{0};   // boulder moves since the last fill
        auto hashNode = [&](int i) {
            const Node& nd = nodes[i];
            uint64_t h = 1469598103934665603ull ^ (uint64_t)nd.key;
            for (int k = 0; k < WORDS; k++) {
                h = (h ^ nd.b.w[k]) * 1099511628211ull;
                h = (h ^ (nd.t.w[k] * 0x9E3779B97F4A7C15ull)) * 1099511628211ull;
            }
            return (size_t)h;
        };
        auto eqNode = [&](int i, int j) {
            return nodes[i].key == nodes[j].key && nodes[i].b.w == nodes[j].b.w && nodes[i].t.w == nodes[j].t.w;
        };
        std::unordered_set<int, decltype(hashNode), decltype(eqNode)> seen(1 << 16, hashNode, eqNode);
        seen.insert(0);
        int need0, minF0, blk0, obs0;
        if (!score(root, reg, need0, minF0, blk0, obs0)) { printf("UNSOLVED 1\n"); return 0; }
        // ((traps in the way, moves since a fill, nearest trip), node), lowest first
        typedef std::pair<std::tuple<int, int, int, int>, int> QE;
        std::priority_queue<QE, std::vector<QE>, std::greater<QE>> open;
        open.push({{need0, 0, 0, 0}, 0});
        bool timeUp = false;
        long long pops = 0;
        std::vector<Node> kids;
        while (!open.empty()) {
            int cur = open.top().second;
            open.pop();
            if ((++pops & 63) == 0 && elapsed() > limit) { timeUp = true; break; }
            region(nodes[cur].b, nodes[cur].t, nodes[cur].player, reg, q);
            bool done = true;
            for (int g : goals) if (!reg.get(g)) { done = false; break; }
            if (done) {
                std::vector<int> pushes;
                for (int i = cur; nodes[i].parent >= 0; i = nodes[i].parent)
                    pushes.insert(pushes.begin(), nodes[i].pushes.begin(), nodes[i].pushes.end());
                printf("SOLVED %zu\n", pushes.size());
                for (int p : pushes) printf("%d %d %d %d\n", (p / 4) % W, (p / 4) / W, DX[p % 4], DY[p % 4]);
                return 0;
            }
            kids.clear();
            for (int bi = 0; bi < N; bi++)
                if (nodes[cur].b.get(bi)) boulderMoves(nodes[cur], bi, cur, kids);
            for (Node& ch : kids) {
                bool filled = ch.t.w != nodes[cur].t.w;
                int s = filled ? 0 : since[cur] + 1;
                if (s > cap) continue;
                nodes.push_back(std::move(ch));
                int id = (int)nodes.size() - 1;
                if (!seen.insert(id).second) { nodes.pop_back(); continue; }
                since.push_back(s);
                Bits r; std::vector<int> qq;
                region(nodes[id].b, nodes[id].t, nodes[id].player, r, qq);
                int need, minF, blk, obs;
                if (!score(nodes[id], r, need, minF, blk, obs)) continue;
                open.push({order == 0 ? std::make_tuple(need, s, minF, 0)
                         : order == 1 ? std::make_tuple(need, blk, minF, s)
                         : order == 2 ? std::make_tuple(need, s, seed ? rnd() : minF, 0)
                                      : std::make_tuple(need, obs + blk + s, seed ? rnd() : minF, 0), id});
            }
        }
        total += nodes.size();
        if (timeUp) break;
    }
    printf("UNSOLVED %zu\n", total);
    return 0;
}
