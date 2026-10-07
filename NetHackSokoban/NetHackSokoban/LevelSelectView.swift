import SwiftUI

/// One mode's levels: its runs, then every level by stage.
struct LevelSelectView: View {
    let set: LevelSet
    @Environment(Progress.self) private var progress
    @State private var confirmReset = false
    @State private var confirmNewRun = false
    @State private var newRun: SokobanRun?

    var body: some View {
        List {
            Section {
                if let saved = progress.savedRun(in: set), let resumed = SokobanRun(saved) {
                    NavigationLink(value: resumed) {
                        Label {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Resume run")
                                Text("\(resumed.variantSummary) · level \(resumed.index + 1) of \(resumed.levels.count) · \(saved.totalMoves) moves")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "play.fill")
                        }
                    }
                    Button {
                        confirmNewRun = true
                    } label: {
                        Label("Start a new run", systemImage: "figure.walk")
                    }
                } else {
                    NavigationLink(value: SokobanRun.random(in: set)) {
                        Label("Start a run", systemImage: "figure.walk")
                    }
                }
                ForEach(Array(progress.rankedRuns(in: set).prefix(5).enumerated()), id: \.element.id) { i, run in
                    RunRow(rank: i + 1, run: run)
                }
            } header: {
                Text("Sokoban run")
            } footer: {
                Text("One random variant of each of the \(set.stages.count) levels, entry to prize, one score. Ranked by luck penalty, then resets, then moves.")
            }
            ForEach(set.stages, id: \.self) { stage in
                Section(set.stageTitle(stage)) {
                    ForEach(set.levels.filter { $0.stage == stage }) { level in
                        NavigationLink(value: level) {
                            LevelRow(level: level, record: progress.records[level.id])
                        }
                    }
                }
            }
            Section {
                Text("Tap to take one step (or push) toward the square you tapped. Press and hold a square to travel there. Boulders only roll orthogonally, and you can't squeeze diagonally between boulders or walls.")
                if set == .expanded {
                    Text("Iron bars (#) stop you and boulders alike, but you can slip diagonally past them. A boulder pushed into lava (}) sinks. Some levels have more pits or holes than boulders: fill only the ones in your way.")
                    Text("Levels from UnNetHack's Sokoban by J Franklin Mentzer, Joseph L Traub, Thinking Rabbit and Steve Melenchuk, adapted for NetHack by Pasi Kallinen.")
                }
            }
            .font(.footnote)
            .foregroundStyle(.secondary)
        }
        .navigationTitle(set.title)
        .navigationDestination(item: $newRun) { run in
            GameView(run: run)
        }
        .toolbar {
            Menu {
                Button("Reset progress", role: .destructive) { confirmReset = true }
            } label: {
                Image(systemName: "ellipsis.circle")
            }
        }
        .confirmationDialog("Forget all \(set.title) best scores and runs?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Reset progress", role: .destructive) { progress.resetAll(in: set) }
        } message: {
            Text("\(set == .classic ? LevelSet.expanded.title : LevelSet.classic.title) progress is kept.")
        }
        .confirmationDialog("Abandon the run in progress?", isPresented: $confirmNewRun, titleVisibility: .visible) {
            Button("Start a new run", role: .destructive) {
                progress.saveRun(nil, in: set)
                newRun = SokobanRun.random(in: set)
            }
        } message: {
            Text("The run you have going will be lost.")
        }
    }
}

private struct LevelRow: View {
    let level: LevelDef
    let record: LevelRecord?

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(level.title)
                Text("\(level.id) · \(level.boulders.count) boulders, \(level.traps.count) \(level.trapKind.rawValue)s")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let credit = level.credit {
                    Text("by \(credit)")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
                if !level.proven {
                    Text("Not yet proven solvable; never dealt in a run")
                        .font(.caption2)
                        .foregroundStyle(.orange)
                }
            }
            Spacer()
            if let record, record.solves > 0 {
                VStack(alignment: .trailing, spacing: 2) {
                    Label("\(record.bestMoves) moves", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    if record.bestPenalties > 0 {
                        Text("Luck \u{2212}\(record.bestPenalties)")
                            .foregroundStyle(.orange)
                    } else {
                        Text("no penalty")
                            .foregroundStyle(.secondary)
                    }
                }
                .font(.caption)
            }
        }
    }
}

private struct RunRow: View {
    let rank: Int
    let run: RunRecord

    var body: some View {
        HStack {
            Text("\(rank).")
                .font(.body.monospacedDigit())
                .foregroundStyle(rank == 1 ? Color.yellow : Color.secondary)
                .frame(width: 24, alignment: .trailing)
            VStack(alignment: .leading, spacing: 2) {
                Text(run.summary).font(.body.monospaced())
                Text(run.date, style: .date).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(run.moves) moves")
                HStack(spacing: 6) {
                    if run.penalties > 0 {
                        Text("Luck \u{2212}\(run.penalties)").foregroundStyle(.orange)
                    }
                    if run.resets > 0 {
                        Text("\(run.resets) reset\(run.resets == 1 ? "" : "s")").foregroundStyle(.secondary)
                    }
                    if run.penalties == 0 && run.resets == 0 {
                        Text("clean").foregroundStyle(.green)
                    }
                }
            }
            .font(.caption)
        }
    }
}
