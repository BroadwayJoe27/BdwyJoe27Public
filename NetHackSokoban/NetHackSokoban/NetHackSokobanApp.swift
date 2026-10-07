import SwiftUI

@main
struct NetHackSokobanApp: App {
    @State private var progress = Progress()

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                HomeView()
            }
            .environment(progress)
            .preferredColorScheme(.dark)
        }
    }
}
