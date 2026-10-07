import SwiftUI

/// The boot screen: pick Classic or Expanded. Every other screen is pushed
/// from here, so the navigation destinations for levels and runs live here.
struct HomeView: View {
    @Environment(Progress.self) private var progress

    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            Text("@ 0 ^")
                .font(.system(size: 44, weight: .bold, design: .monospaced))
                .foregroundStyle(Palette.hero)
            Text("Sokoban")
                .font(.largeTitle.monospaced().bold())
            Spacer()
            ForEach(LevelSet.allCases) { set in
                NavigationLink(value: set) {
                    ModeCard(set: set, runInProgress: progress.savedRun(in: set) != nil)
                }
                .buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(.horizontal, 24)
        .frame(maxWidth: .infinity)
        .background(Palette.background)
        .navigationTitle("Sokoban")
        .toolbar(.hidden, for: .navigationBar)
        .navigationDestination(for: LevelSet.self) { set in
            LevelSelectView(set: set)
        }
        .navigationDestination(for: LevelDef.self) { level in
            GameView(level: level)
        }
        .navigationDestination(for: SokobanRun.self) { run in
            GameView(run: run)
        }
    }
}

private struct ModeCard: View {
    let set: LevelSet
    let runInProgress: Bool

    private var detail: String {
        switch set {
        case .classic: return "The eight NetHack 3.6 levels. Four-level runs."
        case .expanded: return "\(set.levels.count) more NetHack-style levels from UnNetHack. Three-level runs."
        }
    }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(set.title)
                    .font(.title2.monospaced().bold())
                Text(detail)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
                if runInProgress {
                    Label("Run in progress", systemImage: "play.fill")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }
            Spacer()
            Image(systemName: "chevron.right")
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(white: 0.12)))
        .contentShape(RoundedRectangle(cornerRadius: 14))
    }
}
