#!/usr/bin/env python3
"""Generate pixel art avatar for the bot menu."""

import os
from PIL import Image

PIXEL = 16  # bigger blocks = more visible pixel texture
GRID = 32   # fewer cells for chunkier look
SIZE = GRID * PIXEL  # 512x512

# Dark blue palette
BG_DARK = (5, 6, 18)
BG_CIRCLE = (15, 22, 55)
SKIN = (90, 110, 170)
SKIN_LIGHT = (120, 140, 200)
SKIN_SHADOW = (60, 75, 130)
BEARD = (40, 55, 100)
BEARD_DARK = (25, 35, 70)
BEARD_LIGHT = (55, 70, 120)
GLASSES = (8, 10, 22)
GLASSES_FRAME = (55, 70, 130)
GLASSES_GLARE = (100, 120, 180)
HEAD_TOP = (100, 120, 185)
HEAD_SHINE = (140, 160, 220)
CIRCLE_EDGE = (50, 70, 145)
CIRCLE_GLOW = (30, 45, 100)
EAR = (75, 90, 150)

img = Image.new('RGB', (SIZE, SIZE), BG_DARK)


def put(x, y, color):
    if 0 <= x < GRID and 0 <= y < GRID:
        for dx in range(PIXEL):
            for dy in range(PIXEL):
                img.putpixel((x * PIXEL + dx, y * PIXEL + dy), color)


def circle_mask(cx, cy, r):
    pts = set()
    for x in range(GRID):
        for y in range(GRID):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                pts.add((x, y))
    return pts


CX, CY, R = 16, 16, 13
circle = circle_mask(CX, CY, R)
circle_border = circle_mask(CX, CY, R) - circle_mask(CX, CY, R - 1)
circle_glow = circle_mask(CX, CY, R + 1) - circle

for (x, y) in circle:
    put(x, y, BG_CIRCLE)
for (x, y) in circle_glow:
    put(x, y, CIRCLE_GLOW)
for (x, y) in circle_border:
    put(x, y, CIRCLE_EDGE)

# Head shape (bald, oval)
head_pixels = set()
for y in range(7, 21):
    if y < 9:
        hw = max(0, 4 - (9 - y))
    elif y <= 15:
        hw = 5
    elif y <= 17:
        hw = 5 - (y - 15)
    else:
        hw = max(0, 3 - (y - 17))
    for x in range(CX - hw, CX + hw + 1):
        head_pixels.add((x, y))

# Draw head
for (x, y) in head_pixels:
    if (x, y) not in circle:
        continue
    if y < 10:
        put(x, y, HEAD_TOP)
    elif x < CX - 1:
        put(x, y, SKIN_SHADOW)
    elif x > CX + 1:
        put(x, y, SKIN_LIGHT)
    else:
        put(x, y, SKIN)

# Dome shine
put(CX - 1, 8, HEAD_SHINE)
put(CX, 8, SKIN_LIGHT)
put(CX - 1, 7, SKIN_LIGHT)

# Ears
put(CX - 6, 12, EAR)
put(CX - 6, 13, EAR)
put(CX + 6, 12, EAR)
put(CX + 6, 13, EAR)

# Eyebrows
for x in range(CX - 4, CX - 1):
    put(x, 11, BEARD_DARK)
for x in range(CX + 2, CX + 5):
    put(x, 11, BEARD_DARK)

# Sunglasses
# Left lens
for x in range(CX - 5, CX - 1):
    for y in [12, 13]:
        put(x, y, GLASSES)
# Right lens
for x in range(CX + 2, CX + 6):
    for y in [12, 13]:
        put(x, y, GLASSES)
# Bridge
put(CX, 12, GLASSES_FRAME)
put(CX - 1, 12, GLASSES_FRAME)
put(CX + 1, 12, GLASSES_FRAME)
# Frame top + bottom
for x in range(CX - 5, CX + 6):
    put(x, 11, GLASSES_FRAME)
for x in range(CX - 5, CX - 1):
    put(x, 14, GLASSES_FRAME)
for x in range(CX + 2, CX + 6):
    put(x, 14, GLASSES_FRAME)
# Frame sides
for y in [11, 12, 13, 14]:
    put(CX - 5, y, GLASSES_FRAME)
    put(CX - 1, y, GLASSES_FRAME)
    put(CX + 2, y, GLASSES_FRAME)
    put(CX + 6, y, GLASSES_FRAME)
# Arms to ears
put(CX - 6, 12, GLASSES_FRAME)
put(CX + 6, 12, GLASSES_FRAME)
# Glare
put(CX - 4, 12, GLASSES_GLARE)
put(CX + 3, 12, GLASSES_GLARE)

# Nose
put(CX, 15, SKIN_SHADOW)

# Mustache
for x in range(CX - 3, CX + 4):
    put(x, 16, BEARD_DARK)

# Beard — long and thick, reaching bottom of circle
beard_pixels = set()
for y in range(16, 28):
    if y <= 18:
        bw = 5
    elif y <= 20:
        bw = 4
    elif y <= 22:
        bw = 3
    elif y <= 24:
        bw = 2
    elif y <= 26:
        bw = 1
    else:
        bw = 0
    for x in range(CX - bw, CX + bw + 1):
        beard_pixels.add((x, y))

for (x, y) in beard_pixels:
    if (x, y) not in circle:
        continue
    # Textured beard pattern
    if (x + y) % 2 == 0:
        put(x, y, BEARD_DARK)
    elif (x * 3 + y * 7) % 5 == 0:
        put(x, y, BEARD_LIGHT)
    else:
        put(x, y, BEARD)

# Sideburns
for y in range(14, 19):
    put(CX - 5, y, BEARD)
    put(CX + 5, y, BEARD)
    put(CX - 6, y, BEARD_DARK)
    put(CX + 6, y, BEARD_DARK)

# Mouth (small gap in beard)
put(CX - 1, 17, (20, 28, 55))
put(CX, 17, (20, 28, 55))
put(CX + 1, 17, (20, 28, 55))

output_path = os.path.join(os.path.dirname(__file__), 'bot', 'assets', 'bot_avatar.png')
img.save(output_path)
print(f'Saved to {output_path}')
print(f'Size: {SIZE}x{SIZE}px')
