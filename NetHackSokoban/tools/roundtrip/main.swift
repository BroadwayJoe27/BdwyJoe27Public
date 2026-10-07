// Round-trip check for saved games: a half-played board and a part-way run
// must survive JSON encode/decode and then behave identically to the
// original. Every level is wandered at random, saved, restored, and then
// played in lockstep with the original for another 200 moves.
//
// Run from the project root:
//   swiftc -O -o /tmp/roundtrip NetHackSokoban/GameModel.swift NetHackSokoban/Levels.swift NetHackSokoban/Progress.swift tools/roundtrip/main.swift && /tmp/roundtrip
// Expected last line: ALL OK

import Foundation

func describe(_ b: Board) -> String {
    "\(b.level.id) p=\(b.player) m=\(b.moves) pen=\(b.penalties) solved=\(b.solved) "
    + "seen=\(b.prizeSeen) prize=\(String(describing: b.prize)) glyph=\(b.prizeGlyph) "
    + "B=\(b.boulders.inReadingOrder) T=\(b.traps.inReadingOrder) R=\(b.rocks.inReadingOrder) "
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

for level in SokobanLevels.all {
    var board = Board(level: level)
    // Wander for a while: random legal steps, plus an occasional pick-axe.
    for i in 0..<400 where !board.solved {
        if i == 150, let b = board.boulders.first(where: { $0.chebyshev(to: board.player) == 1 }) {
            board.breakBoulder(at: b)
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

// A run part-way through: encode, decode, and check every field comes back.
var run = SokobanRun.random()
_ = run.advance()
run.moves = 321; run.penalties = 2; run.resets = 1
var mid = Board(level: run.current)
for _ in 0..<50 { mid.step(dir: Point.directions.randomElement(using: &rng)!) }
let saved = run.saved(board: mid.snapshot)
let back = try! dec.decode(SavedRun.self, from: try! enc.encode(saved))
guard let rerun = SokobanRun(back) else { fatalError("run would not restore") }
check(rerun.levels.map(\.id) == run.levels.map(\.id), "run levels")
check(rerun.index == 1 && rerun.moves == 321 && rerun.penalties == 2 && rerun.resets == 1, "run totals")
check(rerun.resumeBoard == mid.snapshot, "run board snapshot")
check(back.totalMoves == 321 + mid.moves, "run totalMoves")
check(Board(snapshot: rerun.resumeBoard!)?.player == mid.player, "run board rebuilds")
// A snapshot from the wrong level must be dropped, not trusted.
var wrong = back
wrong.board!.levelID = SokobanLevels.all.first { $0.id != run.current.id }!.id
check(SokobanRun(wrong)?.resumeBoard == nil, "mismatched snapshot dropped")
// Garbage level ids must refuse the whole run.
var junk = back
junk.levelIDs = ["soko9-9"] + junk.levelIDs.dropFirst()
check(SokobanRun(junk) == nil, "unknown level id refused")
print("run: ok (\(run.variantSummary), \(try! enc.encode(saved).count) bytes saved)")

print(failures == 0 ? "ALL OK" : "\(failures) FAILURES")
exit(failures == 0 ? 0 : 1)
