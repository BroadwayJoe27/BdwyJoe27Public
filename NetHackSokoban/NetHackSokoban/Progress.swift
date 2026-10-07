import Foundation
import Observation

struct LevelRecord: Codable, Equatable {
    var solves = 0
    var bestMoves = Int.max
    var bestPenalties = Int.max
}

/// One finished run. Ranked by luck penalty, then resets, then moves.
struct RunRecord: Codable, Identifiable, Equatable {
    var id = UUID()
    var date: Date
    var variants: [String]   // in stage order, e.g. ["B", "A", "A", "B"]
    var moves: Int
    var penalties: Int
    var resets: Int

    var summary: String {
        variants.enumerated().map { "\($0.offset + 1)\($0.element)" }.joined(separator: " ")
    }
    var rank: (Int, Int, Int) { (penalties, resets, moves) }
}

/// Per-level bests, finished runs and the run in progress, in UserDefaults.
@Observable
final class Progress {
    private(set) var records: [String: LevelRecord] = [:]
    private(set) var runs: [RunRecord] = []
    /// The run the user is part-way through, if any.
    private(set) var savedRun: SavedRun?
    private let key = "sokoban.progress.v1"
    private let runsKey = "sokoban.runs.v1"
    private let savedRunKey = "sokoban.savedrun.v1"

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let decoded = try? JSONDecoder().decode([String: LevelRecord].self, from: data) {
            records = decoded
        }
        if let data = UserDefaults.standard.data(forKey: runsKey),
           let decoded = try? JSONDecoder().decode([RunRecord].self, from: data) {
            runs = decoded
        }
        if let data = UserDefaults.standard.data(forKey: savedRunKey) {
            savedRun = try? JSONDecoder().decode(SavedRun.self, from: data)
        }
    }

    /// Stores (or, with nil, forgets) the run in progress. Called after every
    /// move, so it is kept deliberately cheap.
    func saveRun(_ s: SavedRun?) {
        savedRun = s
        if let s, let data = try? JSONEncoder().encode(s) {
            UserDefaults.standard.set(data, forKey: savedRunKey)
        } else {
            UserDefaults.standard.removeObject(forKey: savedRunKey)
        }
    }

    /// Best first.
    var rankedRuns: [RunRecord] { runs.sorted { $0.rank < $1.rank } }
    var bestRun: RunRecord? { rankedRuns.first }

    /// Stores a finished run. Returns true if it is the new best.
    @discardableResult
    func recordRun(_ r: RunRecord) -> Bool {
        let isBest = bestRun.map { r.rank < $0.rank } ?? true
        runs.append(r)
        save()
        return isBest
    }

    func record(levelID: String, moves: Int, penalties: Int) {
        var r = records[levelID] ?? LevelRecord()
        r.solves += 1
        // Fewer luck penalties beats fewer moves.
        if (penalties, moves) < (r.bestPenalties, r.bestMoves) {
            r.bestPenalties = penalties
            r.bestMoves = moves
        }
        records[levelID] = r
        save()
    }

    func resetAll() {
        records = [:]
        runs = []
        saveRun(nil)
        save()
    }

    private func save() {
        if let data = try? JSONEncoder().encode(records) {
            UserDefaults.standard.set(data, forKey: key)
        }
        if let data = try? JSONEncoder().encode(runs) {
            UserDefaults.standard.set(data, forKey: runsKey)
        }
    }
}
