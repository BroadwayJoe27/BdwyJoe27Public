# NetHack Sokoban for iPhone

A small SwiftUI app that plays the eight Sokoban levels from NetHack 3.6
(two variants of each of the four levels) with NetHack's movement rules.
Intended for personal sideloading with Xcode and a free Apple ID.

## Building and sideloading

1. Open `NetHackSokoban.xcodeproj` in Xcode 16 or newer.
2. Select the `NetHackSokoban` target, then *Signing & Capabilities*:
   pick your personal team and change the bundle identifier to something
   unique to you (for example `com.yourname.NetHackSokoban`).
3. Plug in the iPhone, choose it as the run destination, and press Run.
4. On the phone, trust the developer certificate under
   *Settings > General > VPN & Device Management* the first time.

With a free Apple ID the install expires after 7 days; re-run from Xcode
to refresh it.

If Xcode refuses to open the project file (it was written by hand and
has not been opened in Xcode yet), the fallback takes a minute:
create a new iOS App project named `NetHackSokoban` (SwiftUI, Swift),
delete its generated `ContentView.swift` and `NetHackSokobanApp.swift`,
and drag the six `.swift` files from the `NetHackSokoban/` folder into
the project. Set the deployment target to iOS 17.

## Playing

- **Tap a square next to you** to move there, or to push a boulder that
  is standing on it.
- **Tap a farther square** to travel there along the shortest path.
  Travel never pushes boulders. If the square can't be reached, you walk
  to the reachable square closest to it, like NetHack's `_` command.
- **Pinch** to zoom, **drag** to pan, **Fit** to reset the view.
- **Reset** starts the level over (with a confirmation).
- **Pick-axe** then tap an adjacent boulder to break it. Each use costs
  one point of Luck, shown in the header and recorded with your score.
- Reaching the up staircase solves levels 1 to 3. On level 4 the prize
  is in one of the three closets next to the treasure zoo; step onto it.

The rules that matter are the NetHack Sokoban ones:

- Boulders roll only orthogonally.
- You can't squeeze diagonally between two boulders, or a boulder and a
  wall, or two walls.
- You can't move diagonally into or out of a doorway.
- A boulder pushed into a pit or hole fills it.
- Walking into an unfilled pit or hole is refused, since in the real
  game that either traps you or drops you down a level.

Monsters, items, and the zoo are left out; doors count as open.

## Layout

- `NetHackSokoban/GameModel.swift`: `Board` (rules, travel pathfinding)
  and `Game` (tap handling, travel animation).
- `NetHackSokoban/GameView.swift`: canvas rendering and gestures.
- `NetHackSokoban/LevelSelectView.swift`: level list with best scores.
- `NetHackSokoban/Progress.swift`: best scores in UserDefaults.
- `NetHackSokoban/Levels.swift`: generated. Regenerate with
  `python3 tools/gen_levels.py` after editing `tools/sokoban.des`.
