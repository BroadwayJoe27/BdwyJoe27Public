# NetHack Sokoban for iPhone

A small SwiftUI app that plays NetHack's Sokoban with NetHack's movement
rules. Intended for personal sideloading with Xcode and a free Apple ID.

The boot screen offers two modes, each with its own runs and saved run:

- **Classic**: the eight levels from NetHack 3.6 (two variants of each of
  the four levels).
- **Expanded**: 27 more NetHack-style levels from UnNetHack, the variant
  that added them: 14 entry levels (pits), 9 middle levels (holes) and 4
  prize levels. Runs are three levels long, as in UnNetHack.

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
and drag the `.swift` files from the `NetHackSokoban/` folder into
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

Some Expanded levels add two more terrains. Iron bars (`#`) stop you and
boulders alike, but unlike walls they don't stop you slipping diagonally
past them. Lava (`}`) can't be walked into; a boulder pushed into it sinks
(NetHack fills the lava one time in ten, the app never does). A few
Expanded levels have more pits or holes than boulders: fill only the
ones between you and the stairs. Scrolls of earth are left out, as all
other items are. 26 of the 27 Expanded levels have been proven solvable
without them (see below). The last, Level 2B, is marked "not yet proven
solvable" in the list and is never dealt in a run, but can still be
played on its own.

## Layout

- `NetHackSokoban/GameModel.swift`: `Board` (rules, travel pathfinding)
  and `Game` (tap handling, travel animation).
- `NetHackSokoban/GameView.swift`: canvas rendering and gestures.
- `NetHackSokoban/HomeView.swift`: the boot screen (Classic or Expanded).
- `NetHackSokoban/LevelSelectView.swift`: one mode's runs and level list
  with best scores.
- `NetHackSokoban/Progress.swift`: best scores and runs in UserDefaults.
- `NetHackSokoban/Levels.swift`: generated (Classic). Regenerate with
  `python3 tools/gen_levels.py` after editing `tools/sokoban.des`.
- `NetHackSokoban/ExpandedLevels.swift`: generated (Expanded). Regenerate
  with `python3 tools/gen_expanded.py` from `tools/unnethack_sokoban.des`.

## Checking that levels can be solved

`python3 tools/solve_levels.py` (add `--classic` for the Classic levels)
proves each level solvable under the app's rules by finding a solution:
a Python port of `Board.evaluate()` plus a push search in C++
(`tools/solver/soko_solve.cpp`, built on first use with the system `c++`).
Found move lists are kept in `tools/solutions.json`; with no `--search`
the script just re-checks those. On the Mac,
`tools/replay_solutions/main.swift` replays the same move lists through
the real `Board` (the compile line is at the top of that file).
