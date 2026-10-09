// Round-trip check for saved games: a half-played board and a part-way run
// must survive JSON encode/decode and then behave identically to the
// original. Every level is wandered at random, saved, restored, and then
// played in lockstep with the original for another 200 moves.
//
// Run from the project root:
//   swiftc -O -o /tmp/roundtrip NetHackSokoban/GameModel.swift NetHackSokoban/Levels.swift NetHackSokoban/ExpandedLevels.swift NetHackSokoban/Progress.swift tools/roundtrip/main.swift && /tmp/roundtrip
// Expected last line: ALL OK

import Foundation

func describe(_ b: Board) -> String {
    "\(b.level.id) p=\(b.player) m=\(b.moves) pen=\(b.penalties) solved=\(b.solved) "
    + "seen=\(b.prizeSeen) prize=\(String(describing: b.prize)) glyph=\(b.prizeGlyph) "
    + "B=\(b.boulders.inReadingOrder) T=\(b.traps.inReadingOrder) R=\(b.rocks.inReadingOrder) "
    + "S=\(b.scrolls.inReadingOrder) held=\(b.scrollsHeld) "
}

/// The message line is deliberately not saved: a resumed level starts with a
/// clear message rather than a stale one. Everything else must match.
func describeWithMessage(_ b: Board) -> String { describe(b) + "msg=\(b.message)" }

var failures = 0
func check(_ ok: Bool, _ what: String) {
    if !ok { print("FAIL: \(what)"); failures += 1 }
}

var rng = SystemRandomNumberGenerator()
let enc = JSONEncoder(), dec = JSONDecoder()

for level in SokobanLevels.all + ExpandedLevels.all {
    // Wander for a while: random legal steps, plus an occasional pick-axe,
    // and a scroll of earth read on levels that have them.
    var board = Board(level: level, scrollsHeld: level.scrolls.isEmpty ? 0 : 1)
    for i in 0..<400 where !board.solved {
        if i == 150, let b = board.boulders.first(where: { $0.chebyshev(to: board.player) == 1 }) {
            board.breakBoulder(at: b)
        }
        if i == 250, board.scrollsHeld > 0 {
            let before = board.penalties
            check(board.readEarth() && board.penalties == before + 2 && board.boulders.contains(board.player),
                  "\(level.id) reads a scroll of earth")
        }
        board.step(dir: Point.directions.randomElement(using: &rng)!)
    }
    if board.solved { continue }   // solved boards are never saved

    let data = try! enc.encode(board.snapshot)
    guard var restored = Board(snapshot: try! dec.decode(Board.Snapshot.self, from: data)) else {
        print("FAIL: \(level.id) would not restore"); failures += 1; continue
    }
    check(describe(restored) == describe(board),
          "\(level.id) state after restore\n  was \(describe(board))\n  got \(describe(restored))")
    check(restored.message.isEmpty, "\(level.id) resumes with a clear message line")

    // And it must keep playing the same way, message text included.
    var original = board
    for _ in 0..<200 {
        let d = Point.directions.randomElement(using: &rng)!
        let a = original.step(dir: d), b = restored.step(dir: d)
        check(a == b && describe(original) == describe(restored),
              "\(level.id) diverged after restore\n  orig \(describe(original))\n  rest \(describe(restored))")
        if original.solved || describe(original) != describe(restored) { break }
    }
    print("\(level.id): ok (\(board.moves) moves, \(data.count) bytes saved)")
}

// A run part-way through, in each set: encode, decode, and check every field comes back.
for set in LevelSet.allCases {
    var run = SokobanRun.random(in: set)
    _ = run.advance()
    run.moves = 321; run.penalties = 2; run.resets = 1; run.scrolls = 1
    var mid = Board(level: run.current, scrollsHeld: 1)
    for _ in 0..<50 { mid.step(dir: Point.directions.randomElement(using: &rng)!) }
    let saved = run.saved(board: mid.snapshot)
    let back = try! dec.decode(SavedRun.self, from: try! enc.encode(saved))
    guard let rerun = SokobanRun(back) else { fatalError("run would not restore") }
    check(rerun.levels.map(\.id) == run.levels.map(\.id), "run levels")
    check(rerun.index == 1 && rerun.moves == 321 && rerun.penalties == 2 && rerun.resets == 1 && rerun.scrolls == 1, "run totals")
    check(rerun.resumeBoard == mid.snapshot, "run board snapshot")
    check(back.totalMoves == 321 + mid.moves, "run totalMoves")
    check(Board(snapshot: rerun.resumeBoard!)?.player == mid.player, "run board rebuilds")
    // A snapshot from the wrong level must be dropped, not trusted.
    var wrong = back
    wrong.board!.levelID = set.levels.first { $0.id != run.current.id }!.id
    check(SokobanRun(wrong)?.resumeBoard == nil, "mismatched snapshot dropped")
    // Garbage level ids must refuse the whole run.
    var junk = back
    junk.levelIDs = ["soko9-9"] + junk.levelIDs.dropFirst()
    check(SokobanRun(junk) == nil, "unknown level id refused")
    // A run mixing the two sets must be refused.
    var mixed = back
    mixed.levelIDs[0] = (set == .classic ? ExpandedLevels.all : SokobanLevels.all)[0].id
    check(SokobanRun(mixed) == nil, "mixed-set run refused")
    check(rerun.set == set, "run keeps its set")
    print("\(set.title) run: ok (\(run.variantSummary), \(try! enc.encode(saved).count) bytes saved)")
}

// A save from before scrolls of earth (no scroll keys) must still load.
do {
    let level = SokobanLevels.all[0]
    var b = Board(level: level)
    b.step(dir: Point(1, 0))
    var obj = try! JSONSerialization.jsonObject(with: try! enc.encode(b.snapshot)) as! [String: Any]
    obj["scrolls"] = nil; obj["scrollsHeld"] = nil
    let old = try! dec.decode(Board.Snapshot.self, from: try! JSONSerialization.data(withJSONObject: obj))
    let r = Board(snapshot: old)
    check(r?.scrolls == Set(level.scrolls) && r?.scrollsHeld == 0, "pre-scroll board save loads")
    var run = try! JSONSerialization.jsonObject(with: try! enc.encode(SokobanRun.random().saved(board: nil))) as! [String: Any]
    run["scrolls"] = nil
    let oldRun = try! dec.decode(SavedRun.self, from: try! JSONSerialization.data(withJSONObject: run))
    check(SokobanRun(oldRun)?.scrolls == 0, "pre-scroll run save loads")
}

// Picking up: walk onto each level's scrolls by travel, with the boulders
// and traps cleared away (the scrolls start behind them).
for level in SokobanLevels.all + ExpandedLevels.all where !level.scrolls.isEmpty {
    var b = Board(level: level)
    b.boulders.removeAll(); b.traps.removeAll()
    for s in level.scrolls {
        for q in b.travelPath(to: s) { b.step(dir: q - b.player) }
    }
    check(b.scrollsHeld == level.scrolls.count && b.scrolls.isEmpty,
          "\(level.id) picks up its scrolls (held \(b.scrollsHeld))")
}

print(failures == 0 ? "ALL OK" : "\(failures) FAILURES")
exit(failures == 0 ? 0 : 1)
