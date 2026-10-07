// Solvability check through the real rules: replays every move list in
// tools/solutions.json (written by `tools/solve_levels.py --write`) through
// Board (GameModel.swift). Every step must be accepted and the level must
// end solved. On a prize level the move list visits every closet, and the
// replay stops as soon as it reaches the one the prize landed in.
//
// Run from the project root:
//   swiftc -O -o /tmp/replay_solutions NetHackSokoban/GameModel.swift NetHackSokoban/Levels.swift NetHackSokoban/ExpandedLevels.swift NetHackSokoban/Progress.swift tools/replay_solutions/main.swift && /tmp/replay_solutions
// Expected last line: ALL OK

import Foundation

let keys: [Character: Point] = [
    "h": Point(-1, 0), "j": Point(0, 1), "k": Point(0, -1), "l": Point(1, 0),
    "y": Point(-1, -1), "u": Point(1, -1), "b": Point(-1, 1), "n": Point(1, 1),
]

let url = URL(fileURLWithPath: "tools/solutions.json")
guard let data = try? Data(contentsOf: url),
      let solutions = try? JSONDecoder().decode([String: String].self, from: data) else {
    print("cannot read \(url.path); run from the project root"); exit(1)
}

var failures = 0
for set in LevelSet.allCases {
    for level in set.levels {
        guard let moves = solutions[level.id] else {
            // Expanded levels must all have one, bar those marked unproven
            // (never dealt in a run). Classic ones are NetHack's own and have
            // been played for decades; the search has not cracked them all.
            if set == .expanded && level.proven {
                print("\(level.id): NO SOLUTION in solutions.json"); failures += 1
            } else {
                print("\(level.id): skipped, no stored solution")
            }
            continue
        }
        // The prize closet is random; replay against every one it could be.
        let prizes: [Point?] = level.prizeSpots.isEmpty ? [nil] : level.prizeSpots
        for prize in prizes {
            var board = Board(level: level)
            var refused: String?
            for (i, k) in moves.enumerated() where !board.solved {
                guard let d = keys[k] else { refused = "bad key \(k)"; break }
                let before = board.player
                if !board.step(dir: d) {
                    refused = "move \(i + 1) (\(k) from \(before)) refused: \(board.message)"
                    break
                }
                // Board picks its own prize closet; count the level solved
                // once the hero stands where this replay put the prize.
                if let prize, board.player == prize { break }
            }
            let done = board.solved || prize.map { board.player == $0 } ?? false
            if let refused {
                print("\(level.id): FAIL, \(refused)"); failures += 1
            } else if !done {
                print("\(level.id): FAIL, moves ran out before the goal"); failures += 1
            } else {
                let at = prize.map { " (prize at \($0.x),\($0.y))" } ?? ""
                print("\(level.id): ok, \(board.moves) moves\(at)")
            }
        }
    }
}
print(failures == 0 ? "ALL OK" : "\(failures) FAILURES")
exit(failures == 0 ? 0 : 1)
