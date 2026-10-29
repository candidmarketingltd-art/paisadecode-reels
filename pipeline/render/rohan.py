"""Rohan mascot: layered SVG generator for the Paisa Decode reels pipeline.

Layers are swappable so the renderer can animate:
  expression: neutral | smirk | shocked | serious
  mouth:      closed | smile | A (open) | O (round) | E (wide) | MBP (pressed)
  eyes:       open | blink | wide | narrow
  arm:        down | point
"""
import sys

SKIN = "#E5B590"; SKIN_SH = "#CC9670"; SKIN_HI = "#F1CBA9"
HAIR = "#1A1311"; HAIR_HI = "#3A2B24"; BEARD = "#211915"; BEARD_SH = "#16100D"
IRIS = "#3B2418"; LINE = "#141010"
JACKET = "#2C3355"; JACKET_SH = "#20263F"; JACKET_HI = "#3B4470"
TEE = "#F4F1EA"; TEE_SH = "#DAD5CA"; GOLD = "#F2B630"; GOLD_D = "#C98E12"
LIP = "#B8706A"; MOUTH = "#4A1F1F"; TONGUE = "#C9636A"; TEETH = "#FFFFFF"

W = 600; H = 900
OUT = f'stroke="{LINE}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"'


def body(arm="down"):
    s = []
    # neck
    s.append(f'<path d="M262 430 L262 520 Q300 545 338 520 L338 430 Z" fill="{SKIN_SH}" {OUT}/>')
    # tee
    s.append(f'<path d="M150 600 Q170 520 262 505 Q300 560 338 505 Q430 520 450 600 L460 900 L140 900 Z" fill="{TEE}" {OUT}/>')
    # rupee badge on tee
    s.append(f'<circle cx="300" cy="680" r="42" fill="{GOLD}" stroke="{GOLD_D}" stroke-width="5"/>')
    s.append(f'<text x="300" y="700" text-anchor="middle" font-family="Poppins, sans-serif" font-weight="700" font-size="56" fill="{LINE}">₹</text>')
    # jacket left & right panels (open corduroy jacket)
    s.append(f'<path d="M95 900 L105 640 Q115 548 200 520 L262 500 L238 560 L258 600 L240 900 Z" fill="{JACKET}" {OUT}/>')
    s.append(f'<path d="M505 900 L495 640 Q485 548 400 520 L338 500 L362 560 L342 600 L360 900 Z" fill="{JACKET}" {OUT}/>')
    # corduroy ribs
    for x in range(120, 240, 18):
        s.append(f'<line x1="{x}" y1="{620 + (x-120)*0.4}" x2="{x+6}" y2="900" stroke="{JACKET_SH}" stroke-width="4"/>')
    for x in range(372, 492, 18):
        s.append(f'<line x1="{x}" y1="{620 + (492-x)*0.4}" x2="{x-6}" y2="900" stroke="{JACKET_SH}" stroke-width="4"/>')
    # collars
    s.append(f'<path d="M262 500 L205 515 L222 585 L250 560 Z" fill="{JACKET_HI}" {OUT}/>')
    s.append(f'<path d="M338 500 L395 515 L378 585 L350 560 Z" fill="{JACKET_HI}" {OUT}/>')
    # buttons
    s.append(f'<circle cx="352" cy="700" r="9" fill="#C9C9C9" stroke="{LINE}" stroke-width="3"/>')
    s.append(f'<circle cx="352" cy="810" r="9" fill="#C9C9C9" stroke="{LINE}" stroke-width="3"/>')
    if arm == "point":
        # right arm (viewer's right) raised, index finger up
        s.append(f'<path d="M470 600 Q545 560 540 470 L590 455 Q610 560 520 650 Z" fill="{JACKET}" {OUT}/>')
        s.append(f'<path d="M538 470 Q530 430 548 420 L552 360 Q556 340 572 345 L574 418 Q596 420 596 450 Q596 478 568 480 Z" fill="{SKIN}" {OUT}/>')
    return "\n".join(s)


def head(expr="neutral", mouth="closed", eyes=None):
    eyes = eyes or {"shocked": "wide", "smirk": "narrow", "serious": "narrow"}.get(expr, "open")
    s = []
    # ears
    for cx, flip in ((184, -1), (416, 1)):
        s.append(f'<ellipse cx="{cx}" cy="310" rx="20" ry="32" fill="{SKIN}" {OUT}/>')
        s.append(f'<path d="M{cx - 6*flip} 296 Q{cx + 4*flip} 310 {cx - 6*flip} 324" fill="none" stroke="{SKIN_SH}" stroke-width="4"/>')
    # face
    s.append(f'<path d="M190 230 Q188 170 300 160 Q412 170 410 230 L410 360 Q400 450 300 470 Q200 450 190 360 Z" fill="{SKIN}" {OUT}/>')
    # cheek shading
    s.append(f'<path d="M196 300 Q200 360 228 380" fill="none" stroke="{SKIN_SH}" stroke-width="6" opacity=".55"/>')
    s.append(f'<path d="M404 300 Q400 360 372 380" fill="none" stroke="{SKIN_SH}" stroke-width="6" opacity=".55"/>')
    # beard: short, medium-density. Skin shows on cheeks; fuller on chin & jawline.
    import random
    rnd = random.Random(7)
    beard_path = ("M190 278 L194 330 Q202 420 250 455 Q300 488 350 455 Q398 420 406 330 L410 278 "
                  "Q400 330 372 372 Q345 362 300 366 Q255 362 228 372 Q200 330 190 278 Z")
    s.append(f'<clipPath id="bd"><path d="{beard_path}"/></clipPath>')
    # soft stubble base (skin still reads through)
    s.append(f'<path d="{beard_path}" fill="{BEARD}" opacity=".86"/>')
    # denser chin + jawline
    s.append(f'<path d="M232 420 Q300 500 368 420 Q340 395 300 405 Q260 395 232 420 Z" fill="{BEARD}" opacity=".55" clip-path="url(#bd)"/>')
    # hair strokes for texture (lighter ones break up the mass)
    strokes = []
    for _ in range(55):
        x = rnd.uniform(192, 408); y = rnd.uniform(290, 480)
        col = HAIR_HI
        strokes.append(f'<path d="M{x:.0f} {y:.0f} l{rnd.uniform(-2,3):.1f} {rnd.uniform(6,10):.1f}" stroke="{col}" stroke-width="2.4" stroke-linecap="round" opacity=".8"/>')
    s.append('<g clip-path="url(#bd)">' + "".join(strokes) + '</g>')
    # sparse stubble dots on upper cheeks above the beard line
    # soft stubble shadow fading up the cheeks
    s.append(f'<path d="M190 262 Q198 318 230 362 Q206 320 200 270 Z" fill="{BEARD}" opacity=".28"/>')
    s.append(f'<path d="M410 262 Q402 318 370 362 Q394 320 400 270 Z" fill="{BEARD}" opacity=".28"/>')
    # thin outline only on the outer jaw
    s.append(f'<path d="M194 330 Q202 420 250 455 Q300 488 350 455 Q398 420 406 330" fill="none" stroke="{LINE}" stroke-width="4" opacity=".6"/>')
    # mouth area (skin window in beard)
    s.append(mouth_svg(mouth))
    # mustache
    s.append(f'<path d="M252 368 Q272 352 300 357 Q328 352 348 368 Q328 364 300 368 Q272 364 252 368 Z" fill="{BEARD}" stroke="{BEARD}" stroke-width="4" stroke-linejoin="round"/>')
    # nose
    s.append(f'<path d="M298 262 Q296 300 286 322 Q284 338 300 340 Q316 338 314 322" fill="none" stroke="{SKIN_SH}" stroke-width="5" stroke-linecap="round"/>')
    s.append(f'<path d="M282 330 Q288 338 296 336 M318 330 Q312 338 304 336" fill="none" stroke="{LINE}" stroke-width="3.5" stroke-linecap="round"/>')
    # eyes
    s.append(eyes_svg(eyes))
    # brows
    s.append(brows_svg(expr))
    # hair: short faded sides + voluminous swept-up top
    s.append(f'<path d="M188 285 L186 215 Q188 175 210 160 L216 255 Q200 262 188 285 Z" fill="{HAIR}"/>')
    s.append(f'<path d="M412 285 L414 215 Q412 175 390 160 L384 255 Q400 262 412 285 Z" fill="{HAIR}"/>')
    # textured, swept-up quiff (volume on top, slightly to viewer's right)
    s.append(f'<path d="M186 262 Q176 200 184 160 Q192 122 222 106 Q232 84 258 92 Q270 62 302 74 '
             f'Q322 46 352 64 Q382 52 400 80 Q430 84 434 118 Q448 150 430 190 Q424 222 414 262 '
             f'Q410 214 388 202 Q346 190 300 198 Q252 190 222 204 Q196 216 186 262 Z" fill="{HAIR}" {OUT}/>')
    # strand texture following the sweep
    for d in ("M214 172 Q236 132 270 118", "M244 184 Q268 130 312 106", "M286 188 Q306 132 352 98",
              "M330 188 Q352 138 396 112", "M372 196 Q398 156 420 136"):
        s.append(f'<path d="{d}" fill="none" stroke="{HAIR_HI}" stroke-width="5" stroke-linecap="round"/>')
    # brand touch: thin gold highlight on the quiff
    s.append(f'<path d="M300 112 Q328 96 360 94" fill="none" stroke="{GOLD}" stroke-width="4" stroke-linecap="round" opacity=".85"/>')
    return "\n".join(s)


def eyes_svg(state):
    s = []
    for cx in (254, 346):
        if state == "blink":
            s.append(f'<path d="M{cx-26} 262 Q{cx} 272 {cx+26} 262" fill="none" stroke="{LINE}" stroke-width="5" stroke-linecap="round"/>')
            continue
        ry = {"open": 15, "wide": 21, "narrow": 10}[state]
        top = 262 - ry; bot = 262 + ry * 0.8
        s.append(f'<path d="M{cx-28} 262 Q{cx} {top-6} {cx+28} 262 Q{cx} {bot+4} {cx-28} 262 Z" fill="#FFFFFF" {OUT}/>')
        ir = 13 if state != "narrow" else 11
        s.append(f'<clipPath id="e{cx}{state}"><path d="M{cx-28} 262 Q{cx} {top-6} {cx+28} 262 Q{cx} {bot+4} {cx-28} 262 Z"/></clipPath>')
        s.append(f'<g clip-path="url(#e{cx}{state})"><circle cx="{cx}" cy="263" r="{ir}" fill="{IRIS}"/>'
                 f'<circle cx="{cx}" cy="263" r="{ir*0.55:.1f}" fill="{LINE}"/>'
                 f'<circle cx="{cx+4}" cy="258" r="3.5" fill="#FFFFFF"/></g>')
        # heavy upper lid (signature look)
        s.append(f'<path d="M{cx-30} 262 Q{cx} {top-8} {cx+30} 260" fill="none" stroke="{LINE}" stroke-width="7" stroke-linecap="round"/>')
        if state != "wide":
            s.append(f'<path d="M{cx-22} {top-14} Q{cx} {top-20} {cx+22} {top-14}" fill="none" stroke="{SKIN_SH}" stroke-width="3" opacity=".7"/>')
    return "\n".join(s)


def brows_svg(expr):
    # thick, straight-ish, slightly angled brows
    off = {"neutral": (0, 0, 0), "smirk": (-6, 6, 0), "shocked": (-14, -14, 0), "serious": (8, 8, 1)}[expr]
    l, r, frown = off
    s = []
    s.append(f'<path d="M218 {228+l} Q245 {214+l} {282} {226+l + (8 if frown else 0)} L280 {238+l + (8 if frown else 0)} Q246 {228+l} 220 {240+l} Z" fill="{HAIR}" stroke="{HAIR}" stroke-width="4" stroke-linejoin="round"/>')
    s.append(f'<path d="M382 {228+r} Q355 {214+r} {318} {226+r + (8 if frown else 0)} L320 {238+r + (8 if frown else 0)} Q354 {228+r} 380 {240+r} Z" fill="{HAIR}" stroke="{HAIR}" stroke-width="4" stroke-linejoin="round"/>')
    return "\n".join(s)


def lips(cy, curve=6, tilt=0, width=36):
    """Full lower lip + visible upper lip line, readable against the dark beard."""
    l, r = 300 - width, 300 + width
    return (f'<path d="M{l} {cy-tilt} Q300 {cy-6} {r} {cy+tilt} Q300 {cy+curve+4} {l} {cy-tilt} Z" fill="{LIP}" stroke="{LINE}" stroke-width="3"/>'
            f'<path d="M{l+4} {cy+2-tilt} Q300 {cy+curve+34} {r-4} {cy+2+tilt} Q300 {cy+curve+6} {l+4} {cy+2-tilt} Z" fill="{LIP}" stroke="{LINE}" stroke-width="3"/>'
            f'<path d="M{l} {cy-tilt} Q300 {cy+curve} {r} {cy+tilt}" fill="none" stroke="{LINE}" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M{300-14} {cy+curve+16} Q300 {cy+curve+20} {300+14} {cy+curve+16}" fill="none" stroke="#D99A90" stroke-width="3" stroke-linecap="round"/>')


def mouth_svg(m):
    cy = 380
    if m == "closed":
        return lips(cy, curve=4, width=42)
    if m == "smile":
        return lips(cy, curve=12, width=46)
    if m == "smirk":
        return lips(cy, curve=6, tilt=8, width=42)
    if m == "MBP":
        return lips(cy, curve=0, width=38)
    shapes = {"A": (36, 26), "O": (20, 26), "E": (42, 13)}
    rx, ry = shapes[m]
    s = [f'<ellipse cx="300" cy="{cy+8}" rx="{rx+6}" ry="{ry+6}" fill="{LIP}"/>',
         f'<ellipse cx="300" cy="{cy+8}" rx="{rx}" ry="{ry}" fill="{MOUTH}" {OUT}/>']
    if m in ("A", "E"):
        s.append(f'<clipPath id="m{m}"><ellipse cx="300" cy="{cy+8}" rx="{rx}" ry="{ry}"/></clipPath>')
        s.append(f'<g clip-path="url(#m{m})"><rect x="{300-rx}" y="{cy+8-ry}" width="{2*rx}" height="{ry*0.55:.0f}" fill="{TEETH}"/>'
                 f'<ellipse cx="300" cy="{cy+8+ry}" rx="{rx*0.7:.0f}" ry="{ry*0.6:.0f}" fill="{TONGUE}"/></g>')
    return "\n".join(s)


def rohan(expr="neutral", mouth="closed", eyes=None, arm="down", bg=None):
    bgsvg = f'<rect width="{W}" height="{H}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'{bgsvg}{body(arm)}{head(expr, mouth, eyes)}</svg>')


if __name__ == "__main__":
    import cairosvg, os
    os.makedirs("out", exist_ok=True)
    for name, kw in {
        "neutral": dict(expr="neutral", mouth="smile"),
        "talking": dict(expr="neutral", mouth="A", arm="point"),
        "smirk": dict(expr="smirk", mouth="smirk"),
        "shocked": dict(expr="shocked", mouth="O"),
        "serious": dict(expr="serious", mouth="closed"),
    }.items():
        svg = rohan(**kw)
        open(f"out/{name}.svg", "w").write(svg)
        cairosvg.svg2png(bytestring=svg.encode(), write_to=f"out/{name}.png")
    for m in ("closed", "MBP", "A", "E", "O", "smile"):
        svg = rohan(mouth=m)
        cairosvg.svg2png(bytestring=svg.encode(), write_to=f"out/mouth_{m}.png")
    print("ok")
