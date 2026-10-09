import SwiftUI

struct GameView: View {
    @Environment(Progress.self) private var progress
    @Environment(\.dismiss) private var dismiss

    @State private var level: LevelDef
    @State private var game: Game
    @State private var zoom: CGFloat = 1
    @State private var pinchZoom: CGFloat = 1
    @State private var pan: CGSize = .zero
    @State private var dragPan: CGSize = .zero
    @State private var isDragging = false
    @State private var holdTask: Task<Void, Never>?
    @State private var holdFired = false
    @State private var showSolved = false
    @State private var showRunComplete = false
    @State private var runWasBest = false
    @State private var confirmReset = false
    @State private var confirmEarth = false
    @State private var run: SokobanRun?

    /// Free play of one level.
    init(level: LevelDef) {
        _level = State(initialValue: level)
        _game = State(initialValue: Game(level: level))
    }

    /// A full run: the four levels in `run`, played in order, one score.
    /// `run.resumeBoard` reopens a level that was left half-played.
    init(run: SokobanRun) {
        _level = State(initialValue: run.current)
        _game = State(initialValue: Game(level: run.current, scrollsCarriedIn: run.scrolls,
                                         board: run.resumeBoard.flatMap(Board.init(snapshot:))))
        _run = State(initialValue: run)
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            GeometryReader { geo in
                MapCanvas(board: game.board, pickaxeMode: game.pickaxeMode, layout: layout(in: geo.size))
                    .contentShape(Rectangle())
                    .gesture(tapOrPan(in: geo.size).simultaneously(with: pinch))
            }
            .clipped()
            messageLine
            bottomBar
        }
        .background(Palette.background)
        .navigationTitle(level.title)
        .navigationBarTitleDisplayMode(.inline)
        .task { persistRun() }
        .onChange(of: game.board.revision) { persistRun() }
        .onChange(of: game.board.solved) { _, solved in
            guard solved else { return }
            progress.record(levelID: level.id, moves: game.board.moves, penalties: game.board.penalties)
            guard run != nil else { showSolved = true; return }
            run!.completeCurrentLevel(moves: game.board.moves, penalties: game.board.penalties,
                                      scrollsHeld: game.board.scrollsHeld)
            if run!.isLastLevel {
                runWasBest = progress.recordRun(run!.record, in: run!.set)
                progress.saveRun(nil, in: run!.set)
                showRunComplete = true
            } else {
                // Save the run as it will stand once the stairs are climbed:
                // the alert's only other choice is to abandon, which clears it.
                var ahead = run!
                _ = ahead.advance()
                progress.saveRun(ahead.saved(board: nil), in: ahead.set)
                showSolved = true
            }
        }
        .alert("Level solved", isPresented: $showSolved) {
            if let run, let next = run.nextLevel {
                Button("Climb to \(next.title)") { climbInRun() }
                Button("Abandon run", role: .cancel) {
                    progress.saveRun(nil, in: run.set)
                    dismiss()
                }
            } else {
                if let next = level.next {
                    Button(next.stage > level.stage ? "Climb to \(next.title)" : "On to \(next.title)") { load(next) }
                }
                Button("Play again") { game.reset() }
                Button("Levels") { dismiss() }
            }
        } message: {
            Text(solvedSummary)
        }
        .alert("Sokoban complete!", isPresented: $showRunComplete) {
            Button("New run") { startRun(SokobanRun.random(in: level.set)) }
            Button("Levels") { dismiss() }
        } message: {
            Text(runSummary)
        }
        .confirmationDialog("Start this level over?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Reset level", role: .destructive) {
                if run != nil, game.board.moves > 0 { run!.resets += 1 }
                game.reset()
                persistRun()
            }
        } message: {
            if run != nil { Text("Resets count against a run's score.") }
        }
        .confirmationDialog("Read a scroll of earth?", isPresented: $confirmEarth, titleVisibility: .visible) {
            Button("Read it (Luck \u{2212}2)", role: .destructive) { game.readEarth() }
        } message: {
            Text("Boulders fall on every open square around you, and one on you. In Sokoban that costs 2 Luck.")
        }
    }

    // MARK: Chrome

    private var header: some View {
        let luck = game.board.penalties + (run?.penalties ?? 0)
        return HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 0) {
                if let run {
                    Text("Run \(run.index + 1)/\(run.levels.count)").font(.caption.monospaced())
                }
                Text(level.id).font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(spacing: 0) {
                Text("Moves \(game.board.moves)").font(.callout.monospacedDigit())
                if let run {
                    Text("run \(run.moves + game.board.moves)")
                        .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
            }
            Spacer()
            Text(luck == 0 ? "Luck 0" : "Luck \u{2212}\(luck)")
                .font(.callout.monospacedDigit())
                .foregroundStyle(luck == 0 ? Color.secondary : Color.orange)
        }
        .padding(.horizontal)
        .padding(.vertical, 6)
    }

    private var messageLine: some View {
        Text(game.board.message.isEmpty ? " " : game.board.message)
            .font(.footnote.monospaced())
            .foregroundStyle(game.board.solved ? Palette.stairs : Color.primary)
            .lineLimit(2)
            .frame(maxWidth: .infinity, minHeight: 36, alignment: .leading)
            .padding(.horizontal)
    }

    private var bottomBar: some View {
        HStack(spacing: 12) {
            Button {
                confirmReset = true
            } label: {
                Label("Reset", systemImage: "arrow.counterclockwise")
            }
            Button {
                game.togglePickaxe()
            } label: {
                Label("Pick-axe", systemImage: "hammer")
            }
            .tint(game.pickaxeMode ? .orange : nil)
            .buttonStyle(.borderedProminent)
            if game.board.scrollsHeld > 0 {
                Button {
                    game.cancelTravel()
                    confirmEarth = true
                } label: {
                    Label("\u{00D7}\(game.board.scrollsHeld)", systemImage: "scroll")
                }
            }
            Button {
                withAnimation(.easeOut(duration: 0.2)) {
                    zoom = 1; pan = .zero
                }
            } label: {
                Label("Fit", systemImage: "arrow.down.left.and.arrow.up.right")
            }
        }
        .buttonStyle(.bordered)
        .controlSize(.regular)
        .padding(.horizontal)
        .padding(.bottom, 8)
        .disabled(game.board.solved)
    }

    private var solvedSummary: String {
        let b = game.board
        var s = "\(b.moves) moves"
        s += b.penalties == 0 ? ", no luck penalty." : ", luck penalty \u{2212}\(b.penalties)."
        if let r = progress.records[level.id], r.solves > 1 {
            s += "\nBest: \(r.bestMoves) moves"
            s += r.bestPenalties == 0 ? "." : " (luck \u{2212}\(r.bestPenalties))."
        }
        if let run {
            s += "\nRun so far: \(run.moves) moves"
            s += run.penalties == 0 ? "" : ", luck \u{2212}\(run.penalties)"
            s += run.resets == 0 ? "." : ", \(run.resets) reset\(run.resets == 1 ? "" : "s")."
        }
        return s
    }

    private var runSummary: String {
        guard let run else { return "" }
        var s = "\(run.variantSummary)\n\(run.moves) moves"
        s += run.penalties == 0 ? ", no luck penalty" : ", luck penalty \u{2212}\(run.penalties)"
        s += run.resets == 0 ? ", no resets." : ", \(run.resets) reset\(run.resets == 1 ? "" : "s")."
        if runWasBest {
            s += "\nYour best run."
        } else if let best = progress.bestRun(in: run.set) {
            s += "\nBest: \(best.moves) moves"
            s += best.penalties == 0 ? "" : ", luck \u{2212}\(best.penalties)"
            s += best.resets == 0 ? "." : ", \(best.resets) resets."
        }
        return s
    }

    private func load(_ next: LevelDef) {
        level = next
        game = Game(level: next, scrollsCarriedIn: run?.scrolls ?? 0)
        zoom = 1
        pan = .zero
    }

    private func climbInRun() {
        guard var r = run, let next = r.advance() else { return }
        run = r
        load(next)
    }

    private func startRun(_ r: SokobanRun) {
        run = r
        runWasBest = false
        load(r.current)
        persistRun()
    }

    /// Keep the run in progress on disk. A solved board is never saved; the
    /// solved handler has already written the run as it stands after it.
    private func persistRun() {
        guard let run, !game.board.solved else { return }
        progress.saveRun(run.saved(board: game.board.snapshot), in: run.set)
    }

    // MARK: Geometry and gestures

    private func layout(in size: CGSize) -> MapLayout {
        let cols = CGFloat(level.width)
        let rows = CGFloat(level.height)
        let fit = min((size.width - 8) / cols, (size.height - 8) / rows)
        let cell = max(4, fit * zoom * pinchZoom)
        let content = CGSize(width: cols * cell, height: rows * cell)
        let origin = CGPoint(
            x: (size.width - content.width) / 2 + pan.width + dragPan.width,
            y: (size.height - content.height) / 2 + pan.height + dragPan.height
        )
        return MapLayout(origin: origin, cell: cell, viewSize: size)
    }

    /// Hold this long on a square to travel there instead of stepping.
    private static let holdDuration: Duration = .milliseconds(230)

    /// One gesture handles all three: a touch that barely moves and lifts
    /// quickly is a tap (one step toward the square), a touch held still
    /// for `holdDuration` travels to the square, and a longer drag pans.
    private func tapOrPan(in size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { v in
                if holdTask == nil, !isDragging, !holdFired {
                    let target = layout(in: size).point(at: v.startLocation)
                    holdTask = Task { @MainActor in
                        try? await Task.sleep(for: GameView.holdDuration)
                        guard !Task.isCancelled else { return }
                        holdFired = true
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        game.travel(to: target)
                    }
                }
                if isDragging || hypot(v.translation.width, v.translation.height) > 10 {
                    holdTask?.cancel()
                    holdTask = nil
                    if holdFired { return }   // finger wandered after travel began; ignore
                    isDragging = true
                    dragPan = v.translation
                }
            }
            .onEnded { v in
                holdTask?.cancel()
                holdTask = nil
                defer { holdFired = false }
                if holdFired { return }
                if isDragging {
                    pan.width += dragPan.width
                    pan.height += dragPan.height
                    dragPan = .zero
                    isDragging = false
                } else {
                    game.tap(layout(in: size).point(at: v.location))
                }
            }
    }

    private var pinch: some Gesture {
        MagnifyGesture()
            .onChanged { v in pinchZoom = v.magnification }
            .onEnded { v in
                zoom = min(max(zoom * v.magnification, 1), 5)
                pinchZoom = 1
            }
    }
}

// MARK: - Map rendering

struct MapLayout {
    var origin: CGPoint
    var cell: CGFloat
    var viewSize: CGSize

    func rect(for p: Point) -> CGRect {
        CGRect(x: origin.x + CGFloat(p.x) * cell, y: origin.y + CGFloat(p.y) * cell, width: cell, height: cell)
    }

    func point(at loc: CGPoint) -> Point {
        Point(Int(floor((loc.x - origin.x) / cell)), Int(floor((loc.y - origin.y) / cell)))
    }
}

enum Palette {
    static let background = Color.black
    static let floorFill = Color(white: 0.09)
    static let floorDot = Color(white: 0.45)
    static let wall = Color(white: 0.7)
    static let boulder = Color(white: 0.95)
    static let rock = Color(white: 0.5)
    static let scroll = Color(red: 0.95, green: 0.85, blue: 0.55)
    static let pit = Color(red: 0.55, green: 0.6, blue: 0.75)
    static let hole = Color(red: 0.75, green: 0.5, blue: 0.2)
    static let door = Color(red: 0.85, green: 0.6, blue: 0.2)
    static let bars = Color(red: 0.3, green: 0.75, blue: 0.85)
    static let lava = Color(red: 0.95, green: 0.25, blue: 0.15)
    static let stairs = Color(white: 0.95)
    static let hero = Color.white
    static let heroFill = Color(red: 0.15, green: 0.25, blue: 0.4)
    static let prize = Color.cyan
    static let target = Color(red: 0.9, green: 0.55, blue: 0.1).opacity(0.35)
}

struct MapCanvas: View {
    let board: Board
    let pickaxeMode: Bool
    let layout: MapLayout

    var body: some View {
        Canvas(rendersAsynchronously: false) { ctx, size in
            let font = Font.system(size: layout.cell * 0.9, weight: .bold, design: .monospaced)
            let visible = CGRect(origin: .zero, size: size)
            for y in 0..<board.height {
                for x in 0..<board.width {
                    let p = Point(x, y)
                    let r = layout.rect(for: p)
                    guard r.intersects(visible) else { continue }
                    let a = appearance(of: p)
                    if let fill = a.fill {
                        ctx.fill(Path(r), with: .color(fill))
                    }
                    if a.glyph != " " {
                        let text = Text(String(a.glyph)).font(font).foregroundStyle(a.color)
                        ctx.draw(text, at: CGPoint(x: r.midX, y: r.midY), anchor: .center)
                    }
                }
            }
        }
    }

    private struct Appearance {
        var glyph: Character
        var color: Color
        var fill: Color?
    }

    private func appearance(of p: Point) -> Appearance {
        let terrain = board.terrain(at: p)
        var fill: Color? = terrain.isRock ? nil : Palette.floorFill

        if pickaxeMode, board.boulders.contains(p), p.chebyshev(to: board.player) == 1 {
            fill = Palette.target
        }
        if p == board.player {
            return Appearance(glyph: "@", color: Palette.hero, fill: Palette.heroFill)
        }
        if board.boulders.contains(p) {
            return Appearance(glyph: "0", color: Palette.boulder, fill: fill)
        }
        if board.traps.contains(p) {
            let c = board.trapKind == .pit ? Palette.pit : Palette.hole
            return Appearance(glyph: "^", color: c, fill: fill)
        }
        if let prize = board.prize, p == prize, board.prizeSeen {
            return Appearance(glyph: board.prizeGlyph, color: Palette.prize, fill: fill)
        }
        if let exit = board.level.exit, p == exit {
            return Appearance(glyph: "<", color: Palette.stairs, fill: fill)
        }
        if board.level.stage > 1, p == board.level.start {   // arrived by the down stairs
            return Appearance(glyph: ">", color: Palette.stairs, fill: fill)
        }
        if board.scrolls.contains(p) {
            return Appearance(glyph: "?", color: Palette.scroll, fill: fill)
        }
        if board.rocks.contains(p) {
            return Appearance(glyph: "*", color: Palette.rock, fill: fill)
        }
        switch terrain {
        case .stone: return Appearance(glyph: " ", color: .clear, fill: nil)
        case .wall(let ch): return Appearance(glyph: ch, color: Palette.wall, fill: nil)
        case .floor: return Appearance(glyph: ".", color: Palette.floorDot, fill: fill)
        case .door: return Appearance(glyph: "+", color: Palette.door, fill: fill)
        case .bars: return Appearance(glyph: "#", color: Palette.bars, fill: nil)
        case .lava: return Appearance(glyph: "}", color: Palette.lava, fill: fill)
        }
    }
}
