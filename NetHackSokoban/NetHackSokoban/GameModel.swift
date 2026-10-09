import Foundation
import Observation

// MARK: - Basic types

struct Point: Hashable, Codable {
    var x: Int
    var y: Int
    init(_ x: Int, _ y: Int) { self.x = x; self.y = y }

    static func + (a: Point, b: Point) -> Point { Point(a.x + b.x, a.y + b.y) }
    static func - (a: Point, b: Point) -> Point { Point(a.x - b.x, a.y - b.y) }

    /// King-move distance; 1 means adjacent (including diagonals).
    func chebyshev(to o: Point) -> Int { max(abs(x - o.x), abs(y - o.y)) }
    /// Squared Euclidean distance, what NetHack's dist2() uses for travel guessing.
    func dist2(to o: Point) -> Int { (x - o.x) * (x - o.x) + (y - o.y) * (y - o.y) }

    /// Orthogonal directions first so BFS prefers straight paths on ties.
    static let directions: [Point] = [
        Point(0, -1), Point(0, 1), Point(-1, 0), Point(1, 0),
        Point(-1, -1), Point(1, -1), Point(-1, 1), Point(1, 1),
    ]

    /// The 8-way direction that points most nearly from `a` toward `b`
    /// (45-degree sectors, like iNethack2's tap-to-step), or nil if equal.
    static func direction(from a: Point, toward b: Point) -> Point? {
        let dx = b.x - a.x, dy = b.y - a.y
        if dx == 0 && dy == 0 { return nil }
        let sector = Int((atan2(Double(dy), Double(dx)) / (.pi / 4)).rounded())
        switch (sector + 8) % 8 {
        case 0: return Point(1, 0)
        case 1: return Point(1, 1)
        case 2: return Point(0, 1)
        case 3: return Point(-1, 1)
        case 4: return Point(-1, 0)
        case 5: return Point(-1, -1)
        case 6: return Point(0, -1)
        default: return Point(1, -1)
        }
    }
}

enum TrapKind: String {
    case pit, hole
}

enum Terrain: Equatable {
    case stone          // solid rock outside the map (' ')
    case wall(Character) // '-' or '|'
    case floor
    case door
    case bars           // iron bars ('F' in the .des), Expanded levels only
    case lava           // molten lava ('L' in the .des), Expanded levels only

    /// NetHack's IS_ROCK. Iron bars and lava are not rock, so they never
    /// count toward the no-squeezing rule, though neither can be entered.
    var isRock: Bool {
        switch self {
        case .stone, .wall: return true
        case .floor, .door, .bars, .lava: return false
        }
    }
}

/// The two halves of the app, picked on the boot screen. Each has its own
/// levels, runs and run in progress; per-level bests share one table, as
/// level ids never collide.
enum LevelSet: String, CaseIterable, Identifiable, Hashable {
    /// NetHack 3.6's eight levels: four stages, two variants each.
    case classic
    /// UnNetHack's 27 additional levels: three stages, like its Sokoban.
    case expanded

    var id: String { rawValue }
    var title: String { self == .classic ? "Classic" : "Expanded" }
    var levels: [LevelDef] { self == .classic ? SokobanLevels.all : ExpandedLevels.all }
    var stages: [Int] { Array(Set(levels.map(\.stage))).sorted() }
    var lastStage: Int { stages.last ?? 1 }

    func stageTitle(_ stage: Int) -> String {
        let pits = levels.first { $0.stage == stage }?.trapKind == .pit
        if stage == lastStage { return "Level \(stage) · the prize" }
        if stage == 1 { return "Level 1 · entry (\(pits ? "pits" : "holes"))" }
        return "Level \(stage)" + (self == .expanded ? " · \(pits ? "pits" : "holes")" : "")
    }
}

struct LevelDef: Identifiable, Hashable {
    let id: String          // NetHack's name, e.g. "soko4-1"
    let stage: Int          // 1 = entry level ... 4 = prize level
    let variant: String     // "A" or "B"
    let rows: [String]
    let start: Point
    let exit: Point?        // up staircase; nil on the prize level
    let trapKind: TrapKind
    let boulders: [Point]
    let traps: [Point]
    let doors: [Point]
    let prizeSpots: [Point] // closets that may hold the prize on the top level
    var scrolls: [Point] = [] // scrolls of earth lying on the floor (entry levels)
    var set: LevelSet = .classic
    var credit: String? = nil   // the level's author, where the source names one
    /// False for a level tools/solve_levels.py has not yet solved. It can be
    /// played from the list but is never dealt in a run.
    var proven = true

    var width: Int { rows.first?.count ?? 0 }
    var height: Int { rows.count }
    var title: String { "Level \(stage)\(variant)" }

    static func == (a: LevelDef, b: LevelDef) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    /// Where "next" goes after a free-play solve. Classic climbs the stairs,
    /// keeping the variant letter. Expanded stages have different numbers of
    /// variants, so it steps through the list instead: the next variant of
    /// this stage, then the first of the next stage.
    var next: LevelDef? {
        switch set {
        case .classic:
            return SokobanLevels.all.first { $0.stage == stage + 1 && $0.variant == variant }
        case .expanded:
            let all = ExpandedLevels.all
            guard let i = all.firstIndex(of: self), i + 1 < all.count else { return nil }
            return all[i + 1]
        }
    }

    /// Any level in either set, by id.
    static func withID(_ id: String) -> LevelDef? {
        SokobanLevels.all.first { $0.id == id } ?? ExpandedLevels.all.first { $0.id == id }
    }
}

// MARK: - Board (pure game state + rules)

/// One in-progress Sokoban level. The rules mirror NetHack's test_move() and
/// moverock() with the Sokoban-specific restrictions applied.
struct Board {
    let level: LevelDef
    let width: Int
    let height: Int
    private let terrainGrid: [[Terrain]]   // [y][x]

    var boulders: Set<Point>
    var traps: Set<Point>
    var rocks: Set<Point> = []             // left behind by a broken boulder, cosmetic
    var scrolls: Set<Point>                // scrolls of earth still on the floor
    var scrollsHeld: Int                   // scrolls of earth in the hero's pack
    var player: Point
    private(set) var prize: Point?
    private(set) var prizeGlyph: Character // '(' bag of holding or '"' amulet of reflection
    var prizeSeen = false
    var moves = 0
    var penalties = 0                       // luck penalties incurred (pick-axe, scroll of earth)
    var solved = false
    var message = ""
    /// Bumped by every change worth saving, so a view can persist on change.
    private(set) var revision = 0
    private var lastPushMove = -10

    /// `scrollsHeld` is what the hero carries up from the level below in a run.
    init(level: LevelDef, scrollsHeld: Int = 0) {
        self.level = level
        width = level.width
        height = level.height
        terrainGrid = level.rows.map { row in
            row.map { ch -> Terrain in
                switch ch {
                case ".": return .floor
                case "+": return .door
                case "-", "|": return .wall(ch)
                case "F": return .bars
                case "L": return .lava
                default: return .stone
                }
            }
        }
        boulders = Set(level.boulders)
        traps = Set(level.traps)
        scrolls = Set(level.scrolls)
        self.scrollsHeld = scrollsHeld
        player = level.start
        prize = level.prizeSpots.randomElement()
        prizeGlyph = Bool.random() ? "(" : "\""
    }

    var trapKind: TrapKind { level.trapKind }
    var goal: Point? { level.exit ?? prize }

    func inBounds(_ p: Point) -> Bool {
        p.x >= 0 && p.y >= 0 && p.x < width && p.y < height
    }

    func terrain(at p: Point) -> Terrain {
        inBounds(p) ? terrainGrid[p.y][p.x] : .stone
    }

    /// NetHack's bad_rock(): walls, solid rock, and (in Sokoban) boulders.
    func badRock(_ p: Point) -> Bool {
        terrain(at: p).isRock || boulders.contains(p)
    }

    enum MoveCheck {
        case move
        case push
        case blocked(String?)
    }

    /// Can the hero at `u` step in direction `d`? Does not mutate.
    func evaluate(from u: Point, dir d: Point, allowPush: Bool) -> MoveCheck {
        let t = u + d
        guard inBounds(t), !terrain(at: t).isRock, terrain(at: t) != .bars else {
            return .blocked(nil)   // NetHack is silent about walls and bars unless mention_walls is set
        }
        let diagonal = d.x != 0 && d.y != 0
        if diagonal {
            if terrain(at: t) == .door {
                return .blocked("You can't move diagonally into an intact doorway.")
            }
            if terrain(at: u) == .door {
                return .blocked("You can't move diagonally out of an intact doorway.")
            }
            // Sokoban: no squeezing diagonally between boulders and/or walls.
            if badRock(Point(u.x, t.y)) && badRock(Point(t.x, u.y)) {
                return .blocked("You cannot pass that way.")
            }
        }
        if boulders.contains(t) {
            guard allowPush else { return .blocked(nil) }
            if diagonal {
                return .blocked("The boulder won't roll diagonally on this floor.")
            }
            let beyond = t + d
            if !inBounds(beyond) || terrain(at: beyond).isRock || terrain(at: beyond) == .bars
                || boulders.contains(beyond) {
                return .blocked("You try to move the boulder, but in vain.")
            }
            return .push
        }
        if traps.contains(t) {
            return .blocked("There is a \(trapKind.rawValue) there; you would fall in.")
        }
        if terrain(at: t) == .lava {
            return .blocked("That is molten lava; you would burn to a crisp.")
        }
        return .move
    }

    /// Attempt one step (with pushing). Returns true if the hero moved.
    @discardableResult
    mutating func step(dir d: Point) -> Bool {
        guard !solved else { return false }
        let u = player
        switch evaluate(from: u, dir: d, allowPush: true) {
        case .blocked(let m):
            if let m { message = m }
            return false
        case .move:
            player = u + d
            moves += 1
            message = ""
        case .push:
            let t = u + d
            let beyond = t + d
            boulders.remove(t)
            if traps.contains(beyond) {
                traps.remove(beyond)
                message = trapKind == .pit ? "The boulder fills a pit." : "The boulder plugs a hole."
            } else if terrain(at: beyond) == .lava {
                // NetHack fills the lava one time in ten; here it always sinks,
                // so a level plays the same way every time.
                message = "You push the boulder into the lava. It sinks without a trace!"
            } else {
                boulders.insert(beyond)
                message = (moves - lastPushMove > 2) ? "With great effort you move the boulder." : ""
            }
            player = t
            moves += 1
            lastPushMove = moves
        }
        revision += 1
        afterMove()
        return true
    }

    private mutating func afterMove() {
        if scrolls.remove(player) != nil {   // autopickup
            scrollsHeld += 1
            message = scrollsHeld == 1
                ? "You pick up a scroll of earth."
                : "You pick up a scroll of earth (\(scrollsHeld) carried)."
        }
        if let prize, player.chebyshev(to: prize) <= 1 {
            prizeSeen = true
        }
        if let goal, player == goal {
            solved = true
            message = level.exit != nil
                ? "You climb the stairs. Level solved!"
                : "You found the \(prizeGlyph == "(" ? "bag of holding" : "amulet of reflection")! Sokoban complete!"
        }
    }

    /// Apply a pick-axe to an adjacent boulder. Costs one point of Luck, as in NetHack.
    @discardableResult
    mutating func breakBoulder(at p: Point) -> Bool {
        guard !solved else { return false }
        guard p.chebyshev(to: player) == 1, boulders.contains(p) else {
            message = "There is no boulder next to you there."
            return false
        }
        boulders.remove(p)
        rocks.insert(p)
        penalties += 1
        revision += 1
        message = "You hit the boulder with all your might. The boulder falls apart. (Luck \u{2212}1)"
        return true
    }

    /// Read a scroll of earth, uncursed, as NetHack's seffects() does: a
    /// boulder drops on every open square around the hero and one on the
    /// hero's own head, which then sits under the hero. A boulder landing in
    /// a pit or hole fills it and one landing in lava sinks, as when pushed.
    /// NetHack charges one point of Luck for this in Sokoban; the app
    /// charges two, by the user's choice. Where a boulder already stands,
    /// NetHack would stack a second one; the app leaves it at one.
    @discardableResult
    mutating func readEarth() -> Bool {
        guard !solved, scrollsHeld > 0 else { return false }
        scrollsHeld -= 1
        var filled = 0
        for d in Point.directions {
            let q = player + d
            let t = terrain(at: q)
            guard inBounds(q), !t.isRock, t != .bars else { continue }
            if traps.remove(q) != nil {
                filled += 1
            } else if t != .lava {
                boulders.insert(q)
            }
        }
        boulders.insert(player)
        penalties += 2
        revision += 1
        var m = "The ceiling rumbles around you! You are hit by a boulder!"
        if filled > 0 {
            let what = trapKind == .pit ? "pit" : "hole"
            m += " \(filled == 1 ? "A \(what) is" : "\(filled) \(what)s are") filled."
        }
        message = m + " (Luck \u{2212}2)"
        return true
    }

    /// Path for the travel command: BFS over squares the hero can walk to
    /// without pushing anything. If the target is unreachable, head for the
    /// reachable square nearest to it, like NetHack's travel "guess" mode.
    /// Returns the squares to step through, excluding the current one.
    func travelPath(to target: Point) -> [Point] {
        guard inBounds(target), target != player else { return [] }
        var parent: [Point: Point] = [player: player]
        var queue = [player]
        var i = 0
        search: while i < queue.count {
            let u = queue[i]
            i += 1
            for d in Point.directions {
                let v = u + d
                if parent[v] != nil { continue }
                if case .move = evaluate(from: u, dir: d, allowPush: false) {
                    parent[v] = u
                    queue.append(v)
                    if v == target { break search }
                }
            }
        }
        var goal = target
        if parent[target] == nil {
            var best = player
            var bestD = player.dist2(to: target)
            for q in queue where q.dist2(to: target) < bestD {   // BFS order breaks ties by fewest steps
                best = q
                bestD = q.dist2(to: target)
            }
            if best == player { return [] }
            goal = best
        }
        var path: [Point] = []
        var c = goal
        while c != player {
            path.append(c)
            c = parent[c]!
        }
        return path.reversed()
    }

    // MARK: Saving

    /// Everything about a board that its `LevelDef` does not already say, so
    /// a half-played level survives the app being killed. A solved board is
    /// never saved, so `solved` is not part of it.
    struct Snapshot: Codable, Hashable {
        var levelID: String
        var boulders: [Point]
        var traps: [Point]
        var rocks: [Point]
        var player: Point
        var prize: Point?
        var prizeGlyph: String
        var prizeSeen: Bool
        var moves: Int
        var penalties: Int
        var lastPushMove: Int
        // Added with scrolls of earth; nil in a save from an earlier build,
        // which then gets the level's scrolls and an empty pack.
        var scrolls: [Point]?
        var scrollsHeld: Int?
    }

    var snapshot: Snapshot {
        Snapshot(levelID: level.id,
                 boulders: boulders.inReadingOrder,
                 traps: traps.inReadingOrder,
                 rocks: rocks.inReadingOrder,
                 player: player,
                 prize: prize,
                 prizeGlyph: String(prizeGlyph),
                 prizeSeen: prizeSeen,
                 moves: moves,
                 penalties: penalties,
                 lastPushMove: lastPushMove,
                 scrolls: scrolls.inReadingOrder,
                 scrollsHeld: scrollsHeld)
    }

    /// Rebuild a saved board on top of its level. Nil if the level is unknown.
    init?(snapshot s: Snapshot) {
        guard let level = LevelDef.withID(s.levelID) else { return nil }
        self.init(level: level)
        boulders = Set(s.boulders)
        traps = Set(s.traps)
        rocks = Set(s.rocks)
        player = s.player
        prize = s.prize
        prizeGlyph = s.prizeGlyph.first ?? prizeGlyph
        prizeSeen = s.prizeSeen
        moves = s.moves
        penalties = s.penalties
        lastPushMove = s.lastPushMove
        if let ss = s.scrolls { scrolls = Set(ss) }
        scrollsHeld = s.scrollsHeld ?? 0
    }
}

extension Set where Element == Point {
    /// Reading order, so a saved board encodes the same way every time.
    var inReadingOrder: [Point] { sorted { ($0.y, $0.x) < ($1.y, $1.x) } }
}

// MARK: - Game (drives a Board, handles taps and travel animation)

@Observable
@MainActor
final class Game {
    let level: LevelDef
    /// Scrolls of earth carried in from the level below; a reset restores them.
    let scrollsCarriedIn: Int
    private(set) var board: Board
    var pickaxeMode = false
    private var travelTask: Task<Void, Never>?

    /// Delay between steps while travelling, so the walk is visible.
    static let travelStepDelay: Duration = .milliseconds(45)

    /// `board` resumes a saved level; nil starts it fresh.
    init(level: LevelDef, scrollsCarriedIn: Int = 0, board: Board? = nil) {
        self.level = level
        self.scrollsCarriedIn = scrollsCarriedIn
        self.board = board ?? Board(level: level, scrollsHeld: scrollsCarriedIn)
    }

    var isTravelling: Bool { travelTask != nil }

    func reset() {
        cancelTravel()
        pickaxeMode = false
        board = Board(level: level, scrollsHeld: scrollsCarriedIn)
    }

    func cancelTravel() {
        travelTask?.cancel()
        travelTask = nil
    }

    func readEarth() {
        cancelTravel()
        pickaxeMode = false
        board.readEarth()
    }

    func togglePickaxe() {
        cancelTravel()
        pickaxeMode.toggle()
        board.message = pickaxeMode
            ? "Apply the pick-axe to which boulder? (tap one next to you)"
            : "Never mind."
    }

    /// A tap: one step (or push) in the direction of the tapped square from
    /// the hero, iNethack2 style. Tapping an adjacent square is the same
    /// thing. In pick-axe mode the tap picks the boulder instead.
    func tap(_ p: Point) {
        cancelTravel()
        guard !board.solved else { return }
        if pickaxeMode {
            pickaxeMode = false
            board.breakBoulder(at: p)
            return
        }
        guard let d = Point.direction(from: board.player, toward: p) else { return }
        board.step(dir: d)
    }

    /// A press-and-hold: travel to the held square (NetHack's `_` command).
    func travel(to p: Point) {
        cancelTravel()
        guard !board.solved, !pickaxeMode, board.inBounds(p), p != board.player else { return }
        if p.chebyshev(to: board.player) == 1 {
            board.step(dir: p - board.player)
            return
        }
        let path = board.travelPath(to: p)
        guard !path.isEmpty else { return }
        board.message = ""
        travelTask = Task { [weak self] in
            for q in path {
                guard let self, !Task.isCancelled else { return }
                let moved = board.step(dir: q - board.player)
                if !moved || board.solved { break }
                try? await Task.sleep(for: Game.travelStepDelay)
            }
            self?.travelTask = nil
        }
    }
}

// MARK: - Run (one random variant per stage, played in order, one score)

/// A full Sokoban run as NetHack deals it: one randomly chosen variant of
/// each stage, entry to prize, with moves and penalties totalled across
/// the levels. Classic runs are four levels long; Expanded runs three, as
/// in UnNetHack. Saved to `Progress` as a `SavedRun` after every move, so
/// killing the app or backing out to the level list only pauses it.
struct SokobanRun: Hashable {
    let levels: [LevelDef]        // one per stage, in play order
    var index = 0                 // the level being played
    var moves = 0                 // totals over completed levels only
    var penalties = 0
    var resets = 0
    /// Scrolls of earth the hero brought onto the current level.
    var scrolls = 0
    /// Set only when resuming: the half-played board to open the level with.
    var resumeBoard: Board.Snapshot?

    static func random(in set: LevelSet = .classic) -> SokobanRun {
        let picks = set.stages.compactMap { stage in
            set.levels.filter { $0.stage == stage && $0.proven }.randomElement()
        }
        return SokobanRun(levels: picks)
    }

    var set: LevelSet { levels.first?.set ?? .classic }
    var current: LevelDef { levels[index] }
    var isLastLevel: Bool { index == levels.count - 1 }
    var nextLevel: LevelDef? { isLastLevel ? nil : levels[index + 1] }
    var variantSummary: String { levels.map { "\($0.stage)\($0.variant)" }.joined(separator: " ") }

    mutating func completeCurrentLevel(moves m: Int, penalties p: Int, scrollsHeld: Int) {
        moves += m
        penalties += p
        scrolls = scrollsHeld
    }

    /// Step to the next level. Returns it, or nil if the run is over.
    mutating func advance() -> LevelDef? {
        guard let next = nextLevel else { return nil }
        index += 1
        resumeBoard = nil
        return next
    }

    var record: RunRecord {
        RunRecord(date: .now, variants: levels.map(\.variant), moves: moves, penalties: penalties, resets: resets)
    }
}

// MARK: - Saving a run in progress

/// A run part-way through, small enough to live in UserDefaults. The levels
/// are stored by id and looked up again on the way back.
struct SavedRun: Codable {
    var levelIDs: [String]
    var index: Int
    var moves: Int
    var penalties: Int
    var resets: Int
    var scrolls: Int?            // carried onto the current level; nil in older saves
    var board: Board.Snapshot?   // nil: start the current level fresh
    var date: Date

    /// Moves shown on the level list: completed levels plus the one in hand.
    var totalMoves: Int { moves + (board?.moves ?? 0) }
}

extension SokobanRun {
    /// This run's state, with `board` as the level in progress.
    func saved(board: Board.Snapshot?) -> SavedRun {
        SavedRun(levelIDs: levels.map(\.id), index: index, moves: moves,
                 penalties: penalties, resets: resets, scrolls: scrolls, board: board, date: .now)
    }

    /// Rebuild a saved run. Nil if the level ids no longer line up, which
    /// would mean a saved run from an incompatible build.
    init?(_ s: SavedRun) {
        let defs = s.levelIDs.compactMap(LevelDef.withID)
        guard defs.count == s.levelIDs.count, s.index >= 0, s.index < defs.count,
              Set(defs.map(\.set)).count == 1 else { return nil }
        let board = s.board?.levelID == defs[s.index].id ? s.board : nil
        self.init(levels: defs, index: s.index, moves: s.moves,
                  penalties: s.penalties, resets: s.resets, scrolls: s.scrolls ?? 0, resumeBoard: board)
    }
}
