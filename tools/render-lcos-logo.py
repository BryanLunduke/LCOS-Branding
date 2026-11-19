#!/usr/bin/env python3
"""Render the LCOS badge (navy disc + white neon line art) from the vector mark.

Source of truth: LCOS-Branding logo/lcos-logo-black.svg (hand-built geometry +
Overpass glyph outlines). This script recolours it white, adds a vector navy
silhouette (disc r=332 + plate), a soft neon glow clipped inside the badge, and
writes every size by supersampling (8x or more) then Lanczos downscale in
premultiplied alpha, so every edge gets a real antialiased alpha ramp.

Usage: render-lcos-logo.py SRC_SVG OUTDIR
"""
import io, os, re, sys
import cairosvg
from PIL import Image, ImageFilter, ImageChops

SRC, OUT = sys.argv[1], sys.argv[2]
raw = open(SRC).read()
body = raw[raw.index('>', raw.index('<svg')) + 1: raw.rindex('</svg>')]
body = re.sub(r'<title>.*?</title>', '', body, flags=re.S)
white = body.replace('#000', '#fff')

# Square canvas around the 706x682 art, 9 units padding left/right.
VB = (-9, -21, 724, 724)
CX, CY = 352.0, 341.0
DISC_R = 332.0
PLATE = (16.0, 226.0, 690.0, 456.5, 36.0)  # x0 y0 x1 y1 radius

def svg(inner, defs=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB[0]} {VB[1]} {VB[2]} {VB[3]}">'
            f'<defs>{defs}</defs>{inner}</svg>')

x0, y0, x1, y1, r = PLATE
SIL = (f'<circle cx="{CX}" cy="{CY}" r="{DISC_R}"/>'
       f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" rx="{r}" ry="{r}"/>')
GRAD = ('<radialGradient id="g" cx="352" cy="300" r="380" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#34557f"/><stop offset="0.55" stop-color="#21406a"/>'
        '<stop offset="1" stop-color="#14294a"/></radialGradient>')

def small_art():
    # <=32 px: drop the hairline outer circle and the small text; thicken lines.
    art = white
    art = re.sub(r'<circle[^>]*r="320\.00"[^>]*/>', '', art)
    art = art.replace('stroke-width="18.75"', 'stroke-width="30"')
    art = art.replace('stroke-width="2.25"', 'stroke-width="12"')
    paths = re.findall(r'<path d="[^"]*"/>', art)
    # keep only glyph paths whose first y is in the LUNDUKE band (y 270-365)
    keep = []
    for p in paths:
        m = re.match(r'<path d="M[\d.]+ ([\d.]+)', p)
        if m and 300 <= float(m.group(1)) <= 370:
            keep.append(p)
        art = art.replace(p, '')
    # the top-gap of the plate outline for "THE" stays but THE is gone: close it
    art = art.replace('M412.00,231.50H653.25', 'M352.00,231.50H653.25').replace('H289.00"', 'H352.00"')
    return art.replace('<g fill="#fff">', '<g fill="#fff">' + ''.join(keep))

def raster(doc, px):
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=doc.encode(), output_width=px, output_height=px))).convert('RGBA')

def master(px, small=False):
    art = small_art() if small else white
    sil = raster(svg(f'<g fill="#000">{SIL}</g>'), px).getchannel('A')
    base = raster(svg(f'<g fill="url(#g)">{SIL}</g>', GRAD), px)
    lines = raster(svg(art), px).getchannel('A')
    u = px / VB[2]                                   # pixels per SVG unit
    g1 = lines.filter(ImageFilter.GaussianBlur(3.0 * u))
    g2 = lines.filter(ImageFilter.GaussianBlur(10.0 * u))
    k = 0.0 if small else 1.0
    glow = Image.merge('L', [g1]).point(lambda v: min(255, int(v * 1.1 * k)))
    halo = g2.point(lambda v: min(255, int(v * 0.85 * k)))
    # inner rim: darken a thin band just inside the silhouette edge for crispness
    inner = sil.filter(ImageFilter.GaussianBlur(2.5 * u))
    rim = ImageChops.subtract(sil, inner).point(lambda v: min(255, v * 3))
    out = base.copy()
    out = Image.composite(Image.new('RGBA', out.size, (8, 20, 40, 255)), out, rim.point(lambda v: int(v * 0.55)))
    out = Image.composite(Image.new('RGBA', out.size, (150, 185, 230, 255)), out, halo.point(lambda v: int(v * 0.6)))
    out = Image.composite(Image.new('RGBA', out.size, (225, 238, 255, 255)), out, glow.point(lambda v: int(v * 0.75)))
    out = Image.composite(Image.new('RGBA', out.size, (255, 255, 255, 255)), out, lines)
    out.putalpha(sil)                                # glow clipped to the badge
    return out

def down(img, size):
    return img.convert('RGBa').resize((size, size), Image.LANCZOS).convert('RGBA')

os.makedirs(OUT, exist_ok=True)
big = master(4096)
big.save(f'{OUT}/lcos-logo-4096.png')
small = master(1024, small=True)
sizes = [16, 22, 24, 32, 48, 64, 96, 128, 256, 512]
for s in sizes:
    for scale in (1, 2):
        px = s * scale
        src = small if px <= 32 else big
        d = f'{OUT}/hicolor/{s}x{s}{"@2" if scale == 2 else ""}/apps'
        os.makedirs(d, exist_ok=True)
        down(src, px).save(f'{d}/lcos-logo.png', optimize=True)
down(big, 256).save(f'{OUT}/lcos-logo.png', optimize=True)     # /usr/share/pixmaps/lcos-logo.png
# Monochrome 32 px mark (whisker-menu button-icon, About 32 px icon): same
# look as the old 1-bit lcos32.png (white badge, dark ring gap, dark plate
# border) but drawn from vector with a real alpha ramp.
MONO = (f'<g fill="#fff">{SIL}</g>'
        f'<clipPath id="nr"><rect x="-9" y="-21" width="724" height="245"/><rect x="-9" y="453" width="724" height="250"/></clipPath>'
        f'<circle cx="{CX}" cy="{CY}" r="296" fill="none" stroke="#1b1b1b" stroke-width="26" clip-path="url(#nr)"/>'
        f'<rect x="{x0+14}" y="{y0+14}" width="{x1-x0-28}" height="{y1-y0-28}" rx="{r-10}" fill="#fff" stroke="#111" stroke-width="34"/>')
down(raster(svg(MONO), 512), 32).save(f'{OUT}/lcos32.png', optimize=True)
down(big, 512).save(f'{OUT}/lcos-logo-512.png', optimize=True)
# Vector badge without glow (scalable icon; glow is raster-only)
open(f'{OUT}/lcos-logo.svg', 'w').write(svg(f'<g fill="url(#g)">{SIL}</g>' + white, GRAD))
print('ok')
