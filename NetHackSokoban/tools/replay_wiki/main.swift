// Positive rules check: replays the NetHack wiki's published solutions for
// both entry levels through Board (GameModel.swift) and asserts every push
// is accepted, travel reaches every stand square, and the stairs are reached.
// Wiki "Sokoban Level 1a" is NetHack soko4-2 (app Level 1B); wiki "1b" is
// soko4-1 (app Level 1A). Boulder labels are the wiki's letters.
//
// Run from the project root:
//   swiftc -O -o /tmp/replay NetHackSokoban/GameModel.swift NetHackSokoban/Levels.swift NetHackSokoban/Progress.swift tools/replay_wiki/main.swift && /tmp/replay
// Expected last line: ALL OK

import Foundation

let dirs: [Character: Point] = ["u": Point(0,-1), "d": Point(0,1), "l": Point(-1,0), "r": Point(1,0)]

func replay(levelID: String, labels: [Character: Point], solution: [String]) -> Bool {
    guard let level = SokobanLevels.all.first(where: { $0.id == levelID }) else { print("no level \(levelID)"); return false }
    var board = Board(level: level)
    var pos = labels
    for (k, p) in labels where !board.boulders.contains(p) {
        print("\(levelID): label \(k) at \(p) is not a boulder"); return false
    }
    var pushes = 0, filled = 0
    for line in solution {
        let label = line.first!
        let moves = line.dropFirst().filter { "udlr".contains($0) }
        for m in moves {
            let d = dirs[m]!
            guard let b = pos[label] else { print("\(levelID): \(label) already gone at '\(line)'"); return false }
            let stand = b - d
            if board.player != stand {
                let path = board.travelPath(to: stand)
                guard path.last == stand else {
                    print("\(levelID): cannot travel to \(stand) to push \(label) \(m) in '\(line)' (player \(board.player), path end \(String(describing: path.last)))"); return false
                }
                for q in path {
                    guard board.step(dir: q - board.player) else { print("\(levelID): travel step refused at \(q): \(board.message)"); return false }
                }
            }
            let willFill = board.traps.contains(b + d)
            guard case .push = board.evaluate(from: board.player, dir: d, allowPush: true) else {
                print("\(levelID): push \(label) \(m) refused in '\(line)': \(board.message)"); return false
            }
            board.step(dir: d)
            pushes += 1
            if willFill { pos[label] = nil; filled += 1 } else { pos[label] = b + d }
            guard board.boulders.contains(b + d) == !willFill else { print("\(levelID): boulder state wrong after push"); return false }
        }
    }
    let exit = level.exit!
    let path = board.travelPath(to: exit)
    guard path.last == exit else { print("\(levelID): exit unreachable after solution; player \(board.player)"); return false }
    for q in path { board.step(dir: q - board.player) }
    print("\(levelID) (\(level.title)): \(pushes) pushes, \(filled) pits filled, \(board.traps.count) pits left, moves \(board.moves), solved=\(board.solved): \(board.message)")
    return board.solved
}

// NetHack wiki "Sokoban Level 1a" == soko4-2 (app Level 1B)
let ok1 = replay(levelID: "soko4-2", labels: [
    "A": Point(5,2), "B": Point(6,2), "C": Point(11,2), "D": Point(6,3), "E": Point(7,3),
    "F": Point(10,3), "G": Point(12,3), "H": Point(9,5), "I": Point(7,8), "J": Point(8,8), "K": Point(9,8), "L": Point(10,8),
], solution: [
    "A d", "B rrrr", "H dd", "J u", "I l*", "L u", "K llll*", "L dlll lll*", "H dlll lll*", "J dlll llll u*",
    "F r", "B ddld dddl llll lllu u*", "G dlll dddd llll llll uuu*", "F lldd dddl llll lllu uuu*", "C ddll dddd llll llll uuuu u*",
    "E urrr ddld dddl llll lllu uuuu u*",
])

// NetHack wiki "Sokoban Level 1b" == soko4-1 (app Level 1A)
let ok2 = replay(levelID: "soko4-1", labels: [
    "A": Point(2,2), "B": Point(10,2), "C": Point(2,3), "D": Point(9,3), "E": Point(10,4),
    "F": Point(8,7), "G": Point(9,8), "H": Point(9,9), "I": Point(8,10), "J": Point(10,10),
], solution: [
    "A r", "C u", "D rlll llll", "E ddd",
    "H l", "I l*", "J llll*", "E dddl llll*", "G ddll lll*", "H dlll lllu*", "F dddl llll luu*",
    "B dddd dddd llll llll uuuu r*", "D rrrr rrrd dddd ddll llll lluu uurr*", "C drrr rrrr rddd dddd llll llll uuuu rrr*",
])
print(ok1 && ok2 ? "ALL OK" : "FAILED")
