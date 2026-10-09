#!/usr/bin/env python3
"""Generate ExpandedLevels.swift from UnNetHack's dat/sokoban.des.

UnNetHack keeps vanilla NetHack's eight Sokoban maps and adds 27 more by
J Franklin Mentzer, Joseph L Traub, Thinking Rabbit (all adapted for
NetHack by Pasi Kallinen) and Steve Melenchuk. Expanded mode plays only
the 27 new ones; the eight vanilla maps are Classic mode.

UnNetHack's Sokoban branch has three levels, not four: soko3 is the entry
(pits), soko2 the middle (holes) and soko1 the prize level. Steve
Melenchuk's two soko4 maps are pit levels that UnNetHack's dungeon never
uses; they join the entry tier here. Expanded runs are therefore three
levels long.

Coordinates are (x, y) = (column, row), 0-based from the top-left of the
MAP block, as in gen_levels.py. Scrolls of earth are kept, as in Classic;
UnNetHack's second scroll on a level is a 50% chance, which the app always
places, so a level plays the same way every time. Random loot, the zoo and
the giant mimics are left out, as Classic leaves out monsters and loot.
"""
import re, sys, pathlib

here = pathlib.Path(__file__).parent
src = (here / "unnethack_sokoban.des").read_text().splitlines()

# Maps tools/solve_levels.py has not yet found a solution for. They stay
# playable from the level list but are kept out of Expanded runs, so a run
# can never deal a level that might be impossible without a scroll of
# earth. soko2-4 has exactly as many boulders as holes; every search
# setting fills all but the last hole. Take a name out once a solution is
# in tools/solutions.json.
UNPROVEN = {"soko2-4"}

# The maps UnNetHack shares with vanilla NetHack (Classic mode has them).
VANILLA = {"soko3-1", "soko3-2", "soko3-11", "soko3-12",
           "soko2-1", "soko2-2", "soko1-1", "soko1-2"}

def pts(s):
    return [(int(a), int(b)) for a, b in re.findall(r"\((\d+),\s*(\d+)\)", s)]

levels = []
cur = None
in_map = False
for line in src:
    m = re.match(r'LEVEL:"([^"]+)"', line)
    if m:
        cur = dict(name=m[1], rows=[], boulders=[], traps=[], doors=[], scrolls=[],
                   trapKind=None, start=None, exit=None, places=[], credit=None)
        levels.append(cur)
        continue
    if cur is None:
        continue
    if line == "MAP":
        in_map = True; continue
    if line == "ENDMAP":
        in_map = False; continue
    if in_map:
        cur["rows"].append(line); continue
    m = re.match(r'# "?([A-Z][^"<]*?)\s*(<[^>]*>)?"?\s*$', line)
    if m and cur["credit"] is None and not cur["rows"]:
        cur["credit"] = m[1].strip(); continue
    if line.startswith("BRANCH:"):
        n = re.findall(r"\d+", line)
        cur["start"] = (int(n[0]), int(n[1])); continue
    m = re.match(r"STAIR:\((\d+),(\d+)\),\s*(up|down)", line)
    if m:
        p = (int(m[1]), int(m[2]))
        if m[3] == "up": cur["exit"] = p
        else: cur["start"] = p
        continue
    if line.startswith("DOOR:"):
        cur["doors"] += pts(line); continue
    if re.match(r'OBJECT:\(\'`\',"boulder"\)', line):
        cur["boulders"] += pts(line); continue
    if re.match(r'(\[50%\]:\s*)?OBJECT:\(\'\?\',"earth"\)', line):
        cur["scrolls"] += pts(line); continue
    m = re.match(r'TRAP:"(pit|hole)"', line)
    if m:
        assert cur["trapKind"] in (None, m[1]), cur["name"]
        cur["trapKind"] = m[1]
        cur["traps"] += pts(line); continue
    m = re.match(r"\$place = \{(.*)\}", line)
    if m:
        cur["places"] = pts(m[1]); continue

names = [lv["name"] for lv in levels]
assert VANILLA <= set(names), VANILLA - set(names)
levels = [lv for lv in levels if lv["name"] not in VANILLA]

def cell(lv, p):
    x, y = p
    row = lv["rows"][y]
    return row[x] if x < len(row) else " "

for lv in levels:
    w = max(len(r) for r in lv["rows"])
    lv["rows"] = [r.ljust(w) for r in lv["rows"]]
    assert set("".join(lv["rows"])) <= set(" -|.+FL"), (lv["name"], set("".join(lv["rows"])))
    assert lv["start"] and lv["trapKind"] and lv["credit"], lv["name"]
    assert (lv["exit"] is None) == bool(lv["places"]), lv["name"]
    for p in lv["boulders"] + lv["traps"] + lv["places"] + lv["scrolls"] + [lv["start"]] + ([lv["exit"]] if lv["exit"] else []):
        assert cell(lv, p) == ".", (lv["name"], p, cell(lv, p))
    for p in lv["doors"]:
        assert cell(lv, p) == "+", (lv["name"], p, cell(lv, p))
    for y, r in enumerate(lv["rows"]):
        for x, ch in enumerate(r):
            if ch == "+":
                assert (x, y) in lv["doors"], (lv["name"], (x, y))
    assert len(set(lv["boulders"])) == len(lv["boulders"]), lv["name"]
    assert len(set(lv["traps"])) == len(lv["traps"]), lv["name"]
    assert not set(lv["boulders"]) & set(lv["traps"]), lv["name"]
    assert not set(lv["scrolls"]) & set(lv["boulders"]), lv["name"]

# soko3/soko4 (pits) -> stage 1, soko2 (holes) -> 2, soko1 (prize) -> 3.
def stage(lv):
    return {"soko4": 1, "soko3": 1, "soko2": 2, "soko1": 3}[lv["name"].split("-")[0]]
def sortkey(lv):
    tier, num = lv["name"].split("-")
    return (stage(lv), tier != "soko3", int(num))
levels.sort(key=sortkey)
for s in (1, 2, 3):
    tier = [lv for lv in levels if stage(lv) == s]
    for i, lv in enumerate(tier):
        lv["variant"] = chr(ord("A") + i)
assert UNPROVEN <= {lv["name"] for lv in levels}, UNPROVEN
for lv in levels:
    lv["id"] = "unh-" + lv["name"]
    lv["proven"] = lv["name"] not in UNPROVEN
    expect = "hole" if stage(lv) > 1 else "pit"
    assert lv["trapKind"] == expect, lv["name"]
    print(f'{lv["id"]:13} {stage(lv)}{lv["variant"]} {len(lv["rows"][0])}x{len(lv["rows"])} '
          f'boulders={len(lv["boulders"])} {lv["trapKind"]}s={len(lv["traps"])} scrolls={len(lv["scrolls"])} by {lv["credit"]}'
          + ("" if lv["proven"] else " (unproven)"),
          file=sys.stderr)

def pt(p): return f"P({p[0]}, {p[1]})"
def ptl(ps): return "[" + ", ".join(pt(p) for p in ps) + "]"

out = []
out.append("// Generated by tools/gen_expanded.py from UnNetHack's dat/sokoban.des")
out.append("// (tools/unnethack_sokoban.des). Level layouts by the authors credited")
out.append("// on each level, adapted for NetHack by Pasi Kallinen; see NOTICE.md.")
out.append("// Do not edit by hand.")
out.append("")
out.append("import Foundation")
out.append("")
out.append("private typealias P = Point")
out.append("")
out.append("enum ExpandedLevels {")
out.append("    static let all: [LevelDef] = [")
for lv in levels:
    out.append("        LevelDef(")
    out.append(f'            id: "{lv["id"]}",')
    out.append(f'            stage: {stage(lv)},')
    out.append(f'            variant: "{lv["variant"]}",')
    out.append("            rows: [")
    for r in lv["rows"]:
        out.append(f'                "{r}",')
    out.append("            ],")
    out.append(f'            start: {pt(lv["start"])},')
    out.append(f'            exit: {pt(lv["exit"]) if lv["exit"] else "nil"},')
    out.append(f'            trapKind: .{lv["trapKind"]},')
    out.append(f'            boulders: {ptl(lv["boulders"])},')
    out.append(f'            traps: {ptl(lv["traps"])},')
    out.append(f'            doors: {ptl(lv["doors"])},')
    out.append(f'            prizeSpots: {ptl(lv["places"])},')
    if lv["scrolls"]:
        out.append(f'            scrolls: {ptl(lv["scrolls"])},')
    out.append(f'            set: .expanded,')
    out.append(f'            credit: "{lv["credit"]}"' + ("" if lv["proven"] else ","))
    if not lv["proven"]:
        out.append(f'            proven: false')
    out.append("        ),")
out.append("    ]")
out.append("}")
if __name__ == "__main__":
    (here.parent / "NetHackSokoban" / "ExpandedLevels.swift").write_text("\n".join(out) + "\n")
    print(f"wrote ExpandedLevels.swift ({len(levels)} levels)", file=sys.stderr)
