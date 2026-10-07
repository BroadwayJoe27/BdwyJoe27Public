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
/// Runs and the run in progress are kept per `LevelSet`; Classic keeps the
/// keys it had before Expanded existed, so nothing already saved is lost.
@Observable
final class Progress {
    private(set) var records: [String: LevelRecord] = [:]
    private var runsBySet: [LevelSet: [RunRecord]] = [:]
    /// The run the user is part-way through in each set, if any.
    private var savedRuns: [LevelSet: SavedRun] = [:]
    private let key = "sokoban.progress.v1"

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let decoded = try? JSONDecoder().decode([String: LevelRecord].self, from: data) {
            records = decoded
        }
        for set in LevelSet.allCases {
            if let data = UserDefaults.standard.data(forKey: set.runsKey),
               let decoded = try? JSONDecoder().decode([RunRecord].self, from: data) {
                runsBySet[set] = decoded
            }
            if let data = UserDefaults.standard.data(forKey: set.savedRunKey) {
                savedRuns[set] = try? JSONDecoder().decode(SavedRun.self, from: data)
            }
        }
    }

    func savedRun(in set: LevelSet) -> SavedRun? { savedRuns[set] }

    /// Stores (or, with nil, forgets) the run in progress. Called after every
    /// move, so it is kept deliberately cheap.
    func saveRun(_ s: SavedRun?, in set: LevelSet) {
        savedRuns[set] = s
        if let s, let data = try? JSONEncoder().encode(s) {
            UserDefaults.standard.set(data, forKey: set.savedRunKey)
        } else {
            UserDefaults.standard.removeObject(forKey: set.savedRunKey)
        }
    }

    /// Best first.
    func rankedRuns(in set: LevelSet) -> [RunRecord] {
        (runsBySet[set] ?? []).sorted { $0.rank < $1.rank }
    }
    func bestRun(in set: LevelSet) -> RunRecord? { rankedRuns(in: set).first }

    /// Stores a finished run. Returns true if it is the new best.
    @discardableResult
    func recordRun(_ r: RunRecord, in set: LevelSet) -> Bool {
        let isBest = bestRun(in: set).map { r.rank < $0.rank } ?? true
        runsBySet[set, default: []].append(r)
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

    /// Forgets one set's bests, runs and run in progress; the other set's stay.
    func resetAll(in set: LevelSet) {
        let ids = Set(set.levels.map(\.id))
        records = records.filter { !ids.contains($0.key) }
        runsBySet[set] = []
        saveRun(nil, in: set)
        save()
    }

    private func save() {
        if let data = try? JSONEncoder().encode(records) {
            UserDefaults.standard.set(data, forKey: key)
        }
        for (set, runs) in runsBySet {
            if let data = try? JSONEncoder().encode(runs) {
                UserDefaults.standard.set(data, forKey: set.runsKey)
            }
        }
    }
}

private extension LevelSet {
    var runsKey: String { self == .classic ? "sokoban.runs.v1" : "sokoban.\(rawValue).runs.v1" }
    var savedRunKey: String { self == .classic ? "sokoban.savedrun.v1" : "sokoban.\(rawValue).savedrun.v1" }
}
