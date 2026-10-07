"""The NetHack Sokoban app icon (regenerates Assets.xcassets/AppIcon.appiconset/AppIcon.png): hero, boulder, pit in a row on a dungeon floor.

Drawn in the app's own palette (Palette in GameView.swift) with SF Mono Bold,
the same monospaced face the board renders glyphs in. Writes the single
1024x1024 image the AppIcon.appiconset asks for.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

S = 1024
BOULDER, HERO, HERO_FILL, PIT = (242, 242, 242), (255, 255, 255), (38, 64, 102), (150, 163, 201)
GRID_LINE = (13, 15, 20)

def font(px):
    f = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", px)
    try: f.set_variation_by_name("Bold")
    except Exception: pass
    return f

def draw():
    img = Image.new("RGB", (S, S), (25, 27, 33))
    d = ImageDraw.Draw(img)
    # Floor, lit a little from the top.
    for y in range(S):
        t = y / S
        d.line([(0, y), (S, y)], fill=(int(30-10*t), int(32-10*t), int(39-13*t)))
    cell = S / 3
    for i in (1, 2):
        d.line([(i*cell, 0), (i*cell, S)], fill=GRID_LINE, width=5)
        d.line([(0, i*cell), (S, i*cell)], fill=GRID_LINE, width=5)

    cy, gs = S/2, int(S*0.42)
    tile = S*0.33
    hx = S*0.19
    d.rounded_rectangle([hx-tile/2, cy-tile/2, hx+tile/2, cy+tile/2], radius=tile*0.18, fill=HERO_FILL)
    d.text((hx,      cy), "@", font=font(gs),           fill=HERO,    anchor="mm")
    d.text((S*0.50,  cy), "0", font=font(gs),           fill=BOULDER, anchor="mm")
    d.text((S*0.825, cy), "^", font=font(int(gs*0.97)), fill=PIT,     anchor="mm")
    return img

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "AppIcon.png"
    draw().save(out)
    print("wrote", out)
