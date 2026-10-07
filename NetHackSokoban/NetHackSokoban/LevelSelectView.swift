import SwiftUI

struct LevelSelectView: View {
    @Environment(Progress.self) private var progress
    @State private var confirmReset = false
    @State private var confirmNewRun = false
    @State private var newRun: SokobanRun?

    private var stages: [Int] {
        Array(Set(SokobanLevels.all.map(\.stage))).sorted()
    }

    var body: some View {
        List {
            Section {
                if let saved = progress.savedRun, let resumed = SokobanRun(saved) {
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
                    NavigationLink(value: SokobanRun.random()) {
                        Label("Start a run", systemImage: "figure.walk")
                    }
                }
                ForEach(Array(progress.rankedRuns.prefix(5).enumerated()), id: \.element.id) { i, run in
                    RunRow(rank: i + 1, run: run)
                }
            } header: {
                Text("Sokoban run")
            } footer: {
                Text("One random variant of each level, entry to prize, one score. Ranked by luck penalty, then resets, then moves.")
            }
            ForEach(stages, id: \.self) { stage in
                Section(stageTitle(stage)) {
                    ForEach(SokobanLevels.all.filter { $0.stage == stage }) { level in
                        NavigationLink(value: level) {
                            LevelRow(level: level, record: progress.records[level.id])
                        }
                    }
                }
            }
            Section {
                Text("Tap to take one step (or push) toward the square you tapped. Press and hold a square to travel there. Boulders only roll orthogonally, and you can't squeeze diagonally between boulders or walls.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Sokoban")
        .navigationDestination(for: LevelDef.self) { level in
            GameView(level: level)
        }
        .navigationDestination(for: SokobanRun.self) { run in
            GameView(run: run)
        }
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
        .confirmationDialog("Forget all best scores and runs?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Reset progress", role: .destructive) { progress.resetAll() }
        }
        .confirmationDialog("Abandon the run in progress?", isPresented: $confirmNewRun, titleVisibility: .visible) {
            Button("Start a new run", role: .destructive) {
                progress.saveRun(nil)
                newRun = SokobanRun.random()
            }
        } message: {
            Text("The run you have going will be lost.")
        }
    }

    private func stageTitle(_ stage: Int) -> String {
        switch stage {
        case 1: return "Level 1 · entry (pits)"
        case 4: return "Level 4 · the prize"
        default: return "Level \(stage)"
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
