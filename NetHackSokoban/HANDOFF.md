# Handoff: NetHack Sokoban iPhone app

Context for a Claude Code session on the Mac that picks this project up.
Written by the cloud session that created the code; updated 2026-09-18 by
the Mac session that first built and installed it.

## What the user wants

A personal, sideloaded iPhone app (Xcode + free Apple ID over USB, so
7-day installs) that plays the eight NetHack Sokoban levels with NetHack's
rules. Design decisions the user made explicitly:

- Movement is "press on a dungeon square" like iNethack2: a tap moves
  (or pushes) one step in the 8-way direction of the tapped square from
  the hero; pressing and holding a square (0.4 s, light haptic) travels
  there. No d-pad, no swipe. (Changed 2026-09-18 from tap-to-travel: the
  user found a light tap triggering a long travel too fluid compared to
  iNethack2.)
- No undo. Instead a **level reset** button and a **pick-axe with penalty**
  button (break an adjacent boulder, costs 1 Luck, tracked in the score).
- Native SwiftUI, iOS 17 minimum.

## What exists

```
NetHackSokoban.xcodeproj/project.pbxproj   hand-written, Xcode 16 format, untested
NetHackSokoban/
  NetHackSokobanApp.swift   @main, NavigationStack rooted at HomeView, injects Progress
  HomeView.swift            boot screen: Classic / Expanded; owns the LevelDef and SokobanRun destinations
  Levels.swift              GENERATED (Classic) from tools/sokoban.des, do not hand-edit
  ExpandedLevels.swift      GENERATED (Expanded) from tools/unnethack_sokoban.des, do not hand-edit
  GameModel.swift           Point, LevelSet, LevelDef, Board (rules + travel BFS), Game (taps, travel animation), SokobanRun
  GameView.swift            Canvas renderer, tap/pan/pinch gestures, HUD, solved alert
  LevelSelectView.swift     one LevelSet's runs and level list with best scores
  Progress.swift            UserDefaults-backed best scores, and run records and saved run per LevelSet
  Assets.xcassets/          AppIcon (1024x1024 PNG) + AccentColor
tools/sokoban.des           NetHack 3.6 dat/sokoban.des, verbatim
tools/unnethack_sokoban.des UnNetHack dat/sokoban.des, verbatim
tools/gen_levels.py         parses sokoban.des, validates positions, writes Levels.swift
tools/gen_expanded.py       parses unnethack_sokoban.des, keeps the 27 non-vanilla maps, writes ExpandedLevels.swift
tools/solve_levels.py       Python port of Board.evaluate() (bars, lava too); proves levels solvable (see below)
tools/solver/soko_solve.cpp the C++ search solve_levels.py drives; built into tools/solver/build/ on first use
tools/solutions.json        a checked move list (hjklyubn keys) for every level, both sets
tools/icon/make_icon.py     redraws Assets.xcassets/.../AppIcon.png (PIL, SF Mono Bold)
tools/roundtrip/main.swift  save/restore check for Board.Snapshot and SavedRun, both sets
tools/replay_wiki/main.swift  replays the wiki's entry-level solutions through Board
tools/replay_solutions/main.swift  replays tools/solutions.json through Board
README.md, NOTICE.md
```

Level naming: NetHack calls the entry level `soko4-*` and the prize level
`soko1-*`. The app presents them as Level 1 (entry) to Level 4 (prize),
variants A and B. `LevelDef.stage` is the app's number; `LevelDef.id` is
NetHack's name. All coordinates are (x, y) = (column, row), 0-based from
the top-left of the map, exactly as in the .des file.

## Classic and Expanded (added 2026-10-07 at the user's request)

The app now opens on a boot screen (`HomeView`) with two buttons. Classic
is everything that existed before, unchanged in play: NetHack 3.6's eight
levels and four-level runs. Expanded is 27 more levels, NetHack-style by
the user's choice (boulders, pits, holes, stairs; not standard Sokoban
boxes-on-goals, which the user wants to look at converting later).

Source: UnNetHack's `dat/sokoban.des` (NGPL like vanilla), which keeps the
eight vanilla maps and adds 27, credited to J Franklin Mentzer, Joseph L
Traub and Thinking Rabbit (all "heavily modified for NetHack by Pasi
Kallinen") and Steve Melenchuk. UnNetHack's Sokoban is three levels deep:
soko3 is the entry (pits), soko2 the middle (holes), soko1 the prize.
Melenchuk's two soko4 maps are pit levels UnNetHack's dungeon never uses;
they join the entry tier. So Expanded has stage 1 (14 variants, 1A-1N),
stage 2 (9, 2A-2I) and stage 3 (4, 3A-3D), and its runs are three levels.
Ids are `unh-` plus UnNetHack's name (e.g. `unh-soko3-7`), so they never
collide with Classic ids. `LevelDef.credit` carries the author.

What changed in the code:

- `LevelSet` (GameModel.swift): `.classic` / `.expanded`, with `levels`,
  `stages` and `stageTitle(_:)`. `LevelDef` gained `set` (default
  `.classic`, so the generated Levels.swift did not change) and `credit`.
  `LevelDef.withID(_:)` looks in both sets; saved boards and runs use it.
- `SokobanRun.random(in:)`; a run's `set` is its levels' set, and a saved
  run mixing sets is refused.
- `LevelDef.next` (free play "next level"): Classic climbs to the same
  variant letter as before; Expanded steps through the list (1A, 1B, ...
  1N, 2A, ...), labelled "On to" within a stage and "Climb to" across.
- `Progress`: per-level bests stay in one table (ids are unique); finished
  runs and the saved run are per set. Classic keeps its old UserDefaults
  keys (`sokoban.runs.v1`, `sokoban.savedrun.v1`), so nothing already on
  the phone is lost; Expanded uses `sokoban.expanded.runs.v1` and
  `sokoban.expanded.savedrun.v1`. "Reset progress" in a level list
  resets only that set.
- New terrain for Expanded maps: iron bars (`F` in the .des, drawn `#`
  cyan) and lava (`L`, drawn `}` red). See the rules section.
- `LevelDef.proven` (default true): false for a level the solver has not
  cracked. It is still listed (with an orange note) and playable, but
  `SokobanRun.random(in:)` never deals it. Only `unh-soko2-4` (Expanded
  2B) is unproven: 12 boulders for exactly 12 holes, and every search
  setting tried fills all but the last hole (the boulder it strands is
  the one starting at (12,4), whose pocket the hero can only get behind
  through the middle room). UnNetHack gives this level no scroll of
  earth, so it is meant to be solvable. If the user solves it by hand, or
  a better search does, add its move list to tools/solutions.json and
  take `soko2-4` out of `UNPROVEN` in gen_expanded.py.
- Left out, as Classic leaves out monsters and loot:
  random loot, the zoo, the giant mimics that pose as boulders on
  UnNetHack's prize levels, and UnNetHack's random flipping of maps.

## Run mode (added 2026-09-18 at the user's request)

`SokobanRun` (GameModel.swift) is a full Sokoban run as NetHack deals it:
`SokobanRun.random()` picks one variant per stage up front (e.g. "1B 2A 3A
4B"), and `GameView(run:)` plays them in order, summing moves and luck
penalties across levels and counting level resets (only when the level had
moves). Finishing the prize level stores a `RunRecord` via
`Progress.recordRun`, ranked by (penalties, resets, moves); the level list
shows "Start a run" plus the top five. Per-level bests still record during
a run.

**Run persistence (added 2026-09-18).** A run in progress is written to
UserDefaults (`sokoban.savedrun.v1`) after every move, so killing the app
or backing out to the level list only pauses it. The pieces:

- `Board.Snapshot` is the mutable half of a `Board` (boulders, traps, rocks,
  player, prize, moves, penalties, lastPushMove) keyed by level id;
  `Board.init?(snapshot:)` rebuilds the board on top of its `LevelDef`, so
  the terrain grid is never stored. The message line is deliberately not
  saved: a resumed level starts with a clear one.
- `SavedRun` (GameModel.swift) is that snapshot plus the run's level ids,
  index and totals. `SokobanRun.init?(_ SavedRun)` rebuilds it and refuses
  a run whose level ids no longer resolve, or drops a snapshot whose level
  does not match the run's current one (an old incompatible build).
- `Board.revision` counts every state change; `GameView` saves on
  `.onChange(of: game.board.revision)`, on `.task`, and after a reset (an
  untouched board bumps no revision but does re-roll the prize).
- A solved board is never saved. When a level is solved mid-run the save is
  written as the run will stand *after* the stairs are climbed, because the
  alert's only other choice is "Abandon run", which clears the save.
  Finishing the prize level clears it too.
- The level list shows "Resume run" (variants, level N of 4, total moves)
  with "Start a new run" below it, behind a confirmation that says the run
  in progress will be lost.

"Abandon run" in the solved alert, "New run" on completion, and "Start a
new run" on the level list are the only ways to drop a run.

## Rules implemented (Board.evaluate / Board.step in GameModel.swift)

Mirrors NetHack's `test_move()` and `moverock()` with Sokoban restrictions:

- Walls and solid rock block, silently.
- No diagonal move into or out of a doorway.
- No diagonal move when both orthogonal neighbours are "bad rock"
  (wall, rock, or boulder). This is the Sokoban "cannot pass that way" rule.
- Boulders push only orthogonally; blocked if the square beyond is rock or
  another boulder. Pushing into a pit or hole removes both boulder and trap.
- The hero is refused entry to an unfilled pit or hole (app-level guard;
  in NetHack you would fall in).
- Doors are treated as already open. Monsters and items are omitted.
- Win: step on the up stairs (levels 1 to 3) or on the prize square
  (level 4). The prize is placed at random in one of the three closets and
  drawn only once the hero is adjacent to it.
- Iron bars (Expanded only) block the hero and boulders, silently for the
  hero, as NetHack's test_move() and moverock() do. They are not
  IS_ROCK, so bad_rock() ignores them: you may slip diagonally between
  bars and a wall.
- Lava (Expanded only): the hero is refused entry (like pits). A boulder
  pushed into it sinks and the lava stays. NetHack's boulder_hits_pool()
  fills lava one time in ten; the app never does, so a level plays the
  same way every time. No Expanded solution needs lava filled.
- Pick-axe: `Board.breakBoulder(at:)` requires an adjacent boulder,
  leaves a `*` rock glyph (cosmetic, non-blocking), increments `penalties`.
- Scrolls of earth (added 2026-10-09 at the user's request): placed where
  the .des files put them (`LevelDef.scrolls`, both generators; every
  entry level has two; UnNetHack's second one is a 50% roll there, the
  app always places it). Autopickup on stepping onto the square
  (`Board.afterMove`). `Board.readEarth()` is the uncursed scroll: a
  boulder on each of the 8 neighbours that is not rock or bars (a pit or
  hole there is filled instead, lava swallows it), plus one under the
  hero. Costs **2** Luck, the user's house rule (NetHack charges 1). A
  second boulder onto an existing one is not stacked. Unread scrolls ride
  along a run in `SokobanRun.scrolls` / `SavedRun.scrolls`;
  `Game.scrollsCarriedIn` restores them on a reset. `Board.Snapshot`
  gained optional `scrolls` / `scrollsHeld`, so saves from older builds
  still load (roundtrip checks this). UI: a scroll button with the count,
  behind a confirmation; floor glyph `?` in `Palette.scroll`.

Travel (`Board.travelPath(to:)`): 8-direction BFS using the same legality
check with pushing disabled. If the target is unreachable it heads for the
reachable square with the smallest squared distance to the target,
mimicking NetHack's travel "guess". `Game.travel(to:)` animates it at
45 ms/step in a Task; any new touch cancels the travel. `Game.tap` is the
single step via `Point.direction(from:toward:)`.

## Verification status (2026-09-18)

- Builds clean with Xcode 26.6 (zero errors, zero warnings) for both the
  simulator and the device. The hand-written `project.pbxproj` was accepted
  as-is; only `DEVELOPMENT_TEAM` (774G4WJ84P, same as YearTree) and
  `PRODUCT_BUNDLE_IDENTIFIER` (`Hammon.NetHackSokoban`) were filled in.
- Positive rules check DONE: `tools/replay_wiki/main.swift` replays the NetHack
  wiki's full solutions for both entry levels through `Board` and passes
  (1A: 133 pushes, 9 pits filled; 1B: 139 pushes, 10 pits filled; stairs
  reached, `solved == true`). Every push and travel leg the wiki assumes is
  accepted, so `Board.evaluate` matches NetHack on those levels.
- `tools/gen_levels.py` position assertions still pass for all eight levels.
- Installed on the user's iPhone 17 (iOS 26.6.1). Not yet played by hand;
  the on-device feel items (tap vs. pan, solved alert, best-score save) are
  still to be confirmed by the user.
- Save/restore check DONE: `tools/roundtrip/main.swift` wanders every level
  at random, saves, restores, and plays the original and the restored board
  in lockstep for another 200 moves; all eight levels match on every field
  but the message line, and the `SavedRun` guards (mismatched snapshot,
  unknown level id) hold. A saved run is 400-800 bytes of JSON.
  Both harnesses now need `Progress.swift` on the swiftc line (`RunRecord`).

## Verification status (2026-10-07, Expanded mode)

Written in a cloud session with no Swift toolchain (swift.org downloads
are blocked there), so NONE of the Swift changes have been compiled yet.
First thing on the Mac:

1. Build for the simulator or device; expect it to need small fixes.
2. Run the three harnesses from the project root (compile lines at the top
   of each; all three now also need `ExpandedLevels.swift`):
   `tools/roundtrip` (now covers both sets and refuses mixed-set runs),
   `tools/replay_wiki`, and the new `tools/replay_solutions`, which replays
   `tools/solutions.json` through the real `Board`, once per possible
   prize closet on prize levels. Expected last line of each: ALL OK.

What was checked in the cloud session:

- `tools/gen_expanded.py` asserts pass for all 27 Expanded maps (every
  boulder, trap, stair and closet on floor, every `+` a declared door,
  one trap kind per level, pits at stage 1 and holes after).
- Solvability: `tools/solve_levels.py` found a solution for 26 of the 27
  Expanded levels, each re-checked move by move through the Python port
  of `Board.evaluate()` (bars and lava included) and stored in
  `tools/solutions.json`. Run it with no arguments to re-check them (a
  few seconds). The 27th, `unh-soko2-4`, is unproven; see above. Classic:
  the search also solves soko4-1, soko4-2, soko3-1 and soko2-2, while
  soko3-2, soko2-1, soko1-1 and soko1-2 defeat it. Those are NetHack's
  own levels, so they are only skipped by `replay_solutions`.
- How the search works (tools/solver/soko_solve.cpp): moves are whole
  "boulder moves" (one boulder pushed any distance alone), greedy on the
  number of traps still between the hero and the goal, with dead-state
  cuts: boulders frozen against walls count as walls; a boulder that can
  no longer reach any trap, given which side of it the hero can get to,
  is dead; fewer live boulders than traps in the way ends the line.
  Different levels need different settings, so the driver runs a fixed
  portfolio and keeps per-level hints for the slow ones.

## Deploying to the phone

The user prefers the real phone over the simulator. Recipe that worked:

```
xcodebuild -project NetHackSokoban.xcodeproj -scheme NetHackSokoban \
  -destination 'generic/platform=iOS' -derivedDataPath <dir> \
  -allowProvisioningUpdates build
xcrun devicectl device install app --device <device-id> \
  <dir>/Build/Products/Debug-iphoneos/NetHackSokoban.app
```

Build against `generic/platform=iOS`, not the device id: a device
destination needs the developer disk image mounted, which fails while the
phone is locked (`kAMDMobileImageMounterDeviceLocked`). Install works
locked; launching (`devicectl device process launch`) does not, so the
user taps the icon. The phone was paired over Wi-Fi (`localNetwork`).

## State as of 2026-09-18 evening

Everything is committed on `main`. The project now lives in
`NetHackSokoban/` of the public BdwyJoe27Public repo
(https://github.com/BroadwayJoe27/BdwyJoe27Public), imported 2026-10-07
without its history. Its earlier history (the initial app, the
tap-steps/hold-travels controls, run mode, run persistence and the app
icon) stays in the private repo where it was first developed. The build on
the phone includes run persistence, the 0.23 s hold and the app icon.

Confirmed by the user on the phone: Level 1A end to end, tap/pan, solved
alert, best-score save. The user liked the tap-steps/hold-travels change.
NOT yet tried by the user: run mode, resuming a run, the shorter hold, and
the icon (it lands on the home screen at the next install).

## Suggested next steps, in order

0. (2026-10-07) Build the Expanded-mode changes on the Mac, run the three
   harnesses, install, and have the user try the boot screen and an
   Expanded run. Then, at the user's request for later: look at converting
   free standard Sokoban sets (boxes onto goals) into NetHack-style levels.
1. User plays a run on the phone. Things to watch: the "Run 2/4" header,
   "Abandon run" in the solved alert, the "Sokoban complete!" alert on
   the prize level, and the ranked list on the level screen.
2. DONE (2026-09-18): runs persist. See "Run persistence" above.
3. Tune feel: `GameView.holdDuration` (now 0.23 s, was 0.4 s; the user asked
   for a shorter dwell before travel fires), `Game.travelStepDelay`
   (45 ms), cell fit padding, `Palette` colours.
4. Nice-to-haves the user has not asked for, so ask first: haptics on push,
   landscape layout. Undo was rejected as a design choice.

## App icon (added 2026-09-18)

The hero, a boulder and a pit in a row (`@ 0 ^`) on a three-cell dungeon
floor, drawn in the app's own `Palette` colours with SF Mono Bold, the same
monospaced face the board renders. The user picked this from five
candidates; the runners-up were the same two glyphs on a diagonal and a
large `@` alone. Regenerate with:

```
python3 tools/icon/make_icon.py NetHackSokoban/Assets.xcassets/AppIcon.appiconset/AppIcon.png
```

The asset catalog uses the single-size (1024x1024, `universal`/`ios`) form,
which Xcode 26 resizes for every slot. Keep the PNG opaque RGB: an alpha
channel is rejected by App Store tooling. No iOS 18 dark or tinted variants
are supplied; the icon is already dark and iOS derives the tinted one.

To rebuild and reinstall after any change, use the two commands under
"Deploying to the phone" above; the phone must be on the same Wi-Fi
(or USB) and unlocked only if you want to launch it from the Mac.

## Licensing

Level layouts are Copyright (c) 1998-1999 Kevin Hugo, NetHack General
Public License (see NOTICE.md). Keep the notice if the code goes anywhere.
