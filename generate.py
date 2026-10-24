"""Profile card generator — based on metawka/metawka (Expressive Profile).

Modified variant:
  * monochrome black theme: every surface is #000000, icons / buttons / text are
    pure white or neutral grey (see data/palette.json)
  * compact layout: type, chips, paddings, card heights and vertical rhythm are
    scaled down (~0.8x) so the whole profile takes less space
  * one black theme for both colour schemes, so GitHub shows black in light mode
"""
import base64
import datetime
import hashlib
import json
import math
import os
import subprocess
import sys
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "assets"
USER = "Sokuza"
NAME = "Sokuza"
W = 840

PALETTE = json.loads((ROOT / "data/palette.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "data/icons.json").read_text(encoding="utf-8"))
METRICS = json.loads((ROOT / "data/metrics.json").read_text(encoding="utf-8"))
FONT = base64.b64encode((ROOT / "fonts/GoogleSansFlex-subset.woff2").read_bytes()).decode()
FONT_CYR = base64.b64encode((ROOT / "fonts/RobotoFlex-cyrillic.woff2").read_bytes()).decode()

SHAPES = ["cookie", "clover", "sunny", "flower"]

# compact design tokens (original metawka layout scaled down ~0.8x)
PAD = 24          # outer padding of every card
TITLE = 18        # section title size
BODY = 13         # row / chip label size
CHIP_H = 28       # chip height
CARD_W, CARD_H = 412, 176
CARD_R = 24       # corner radius

ICON_RULES = [
    (("zip", "archive", "7-zip", "rar", "rename", "bulk"), "folder_zip"),
    (("music", "audio", "spotify", "player", "sound"), "music_note"),
    (("dictat", "speech", "voice", "whisper", "mic"), "mic"),
    (("tracker", "screen time", "activity", "monitor", "stats"), "monitoring"),
    (("discord",), "brand:discord"),
    (("game", "minecraft", "mod "), "sports_esports"),
    (("site", "website", "web ", "landing", "portfolio", "gallery"), "language"),
    (("launcher", "installer"), "deployed_code"),
    (("theme", "design", "ui kit", "palette", "png", "image"), "palette"),
    (("blender", "geometry node", "geometry nodes", "addon"), "widgets"),
    (("math", "formula", "curve", "surface", "sympy", "animation", "3d"), "bolt"),
    (("terminal", "cli", "shell", "dotfiles", "hyprland", "export"), "terminal"),
]

LANG_ICONS = {
    "Rust": "brand:rust",
    "Python": "brand:python",
    "TypeScript": "brand:typescript",
    "JavaScript": "code",
    "HTML": "code",
    "CSS": "code",
    "C#": "desktop_windows",
    "Java": "brand:openjdk",
}

STACK = [
    ("Main", [("brand:python", "Python"), ("brand:nodedotjs", "JavaScript"), ("brand:dotnet", "C#")]),
    ("Also", [("code", "Three.js"), ("code", "SymPy"), ("widgets", "Geometry Nodes")]),
    ("Tools", [("brand:git", "Git"), ("brand:githubactions", "GitHub Actions"), ("terminal", "VS Code")]),
]

ABOUT = [
    ("person", "Independent developer"),
    ("code", "Math & 3D visualization"),
    ("widgets", "Blender addons, geometry nodes"),
    ("desktop_windows", "Small Windows utilities"),
]

HERO_GREETING = "Hi, I'm"
HERO_SUB = "Small tools for math, 3D and the Windows desktop — Blender addons, geometry-node experiments and utilities."
HERO_CHIPS = [("location_on", "Rancho Santa Margarita"), ("code", "Python · JS · C#")]

BUTTONS = [
    ("repos", "All repositories", "book_2", "filled", f"https://github.com/{USER}?tab=repositories"),
    ("latest", "Math Studio", "deployed_code", "tonal", f"https://github.com/{USER}/Math-Studio"),
]


# Helpers
def text_width(s, size, weight=400):
    table = METRICS[str(min((400, 500, 600, 700), key=lambda w: abs(w - weight)))]
    total = 0.0
    for c in s:
        # CJK glyphs are full width and come from a fallback font
        total += 1.0 if "\u2e80" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f" or "\uff00" <= c <= "\uffef" else table.get(c, 0.55)
    return total * size


def wrap(s, size, width, weight=400, lines=2):
    out, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if text_width(trial, size, weight) <= width:
            cur = trial
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        while text_width(out[-1] + "…", size, weight) > width:
            out[-1] = out[-1].rsplit(" ", 1)[0]
        out[-1] += "…"
    return out


def mix(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def shape(kind, cx, cy, r):
    n, a, sharp = {
        "cookie": (9, 0.07, 1.0),
        "cookie12": (12, 0.05, 1.0),
        "clover": (4, 0.2, 1.0),
        "sunny": (8, 0.1, 2.2),
        "flower": (8, 0.16, 1.0),
        "pill": (2, 0.0, 1.0),
    }[kind]
    pts = []
    steps = 180
    for i in range(steps):
        t = 2 * math.pi * i / steps
        wave = math.cos(n * t)
        wave = math.copysign(abs(wave) ** (1 / sharp), wave)
        rr = r * (1 - a + a * wave)
        pts.append((cx + rr * math.cos(t - math.pi / 2), cy + rr * math.sin(t - math.pi / 2)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"


def icon(name, x, y, size, fill):
    if name.startswith("brand:"):
        d = ICONS["brand"][name[6:]]
        s = size / 24
        return f'<path d="{d}" fill="{fill}" transform="translate({x:.1f} {y:.1f}) scale({s:.4f})"/>'
    sym = ICONS["symbol"][name]
    vx, vy, vw, vh = [float(v) for v in sym["vb"].split()]
    s = size / vw
    return f'<path d="{sym["d"]}" fill="{fill}" transform="translate({x - vx * s:.1f} {y - vy * s:.1f}) scale({s:.4f})"/>'


def txt(x, y, s, size, fill, weight=400, cls="", delay=None, anchor="start", extra=""):
    style = f"font-size:{size}px;font-weight:{weight};"
    if delay is not None:
        style += f"animation-delay:{delay:.2f}s;"
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" text-anchor="{anchor}" style="{style}"{c}{extra}>{escape(s)}</text>'


def svg(w, h, body, title):
    cyr = ""
    if any("\u0400" <= c <= "\u04ff" for c in body):
        cyr = f"@font-face{{font-family:R;src:url(data:font/woff2;base64,{FONT_CYR}) format('woff2');font-weight:400 800}}"
    css = f"""
@font-face{{font-family:G;src:url(data:font/woff2;base64,{FONT}) format('woff2');font-weight:400 800}}
{cyr}text{{font-family:G,R,'Google Sans','Segoe UI',Roboto,sans-serif;font-variation-settings:'ROND' 100}}
.up{{animation:up .8s cubic-bezier(.05,.7,.1,1) both}}
.pop{{transform-box:fill-box;transform-origin:center;animation:pop .6s cubic-bezier(.34,1.56,.64,1) both}}
.fade{{animation:fade .9s ease both}}
.spin{{transform-box:fill-box;transform-origin:center;animation:spin 40s linear infinite}}
.spin-r{{transform-box:fill-box;transform-origin:center;animation:spin 28s linear infinite reverse}}
.bob{{transform-box:fill-box;transform-origin:center;animation:bob 7s ease-in-out infinite}}
.breathe{{transform-box:fill-box;transform-origin:center;animation:breathe 6s ease-in-out infinite}}
.grow{{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.2,0,0,1) both}}
.wght{{animation:wght 1.6s cubic-bezier(.2,0,0,1) .2s both}}
.wave{{animation:wave 2.4s linear infinite}}
@keyframes up{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0;transform:scale(.6)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
@keyframes bob{{0%,100%{{transform:translateY(0) rotate(0)}}50%{{transform:translateY(-10px) rotate(12deg)}}}}
@keyframes breathe{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.06)}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes wght{{from{{font-variation-settings:'ROND' 100,'wght' 400}}to{{font-variation-settings:'ROND' 100,'wght' 760}}}}
@keyframes wave{{from{{transform:translateX(0)}}to{{transform:translateX(-48px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><style>{css}</style>{body}</svg>"
    )


def chip(x, y, label, p, ic=None, delay=0.0, h=CHIP_H, size=BODY, style="outlined"):
    pad = 10
    iw = 14 if ic else 0
    gap = 6 if ic else 0
    w = pad * 2 + iw + gap + text_width(label, size, 500)
    if style == "tonal":
        bg = f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="8" fill="{p["secondaryContainer"]}"/>'
        fg = p["onSecondaryContainer"]
    else:
        bg = f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1:.1f}" height="{h - 1}" rx="8" fill="{p["surfaceContainerHigh"]}" stroke="{p["outlineVariant"]}"/>'
        fg = p["onSurfaceVariant"]
    parts = [bg]
    if ic:
        parts.append(icon(ic, x + pad, y + (h - 14) / 2, 14, p["primary"]))
    parts.append(txt(x + pad + iw + gap, y + h / 2 + size * 0.36, label, size, fg, 500))
    return f'<g class="pop" style="animation-delay:{delay:.2f}s">{"".join(parts)}</g>', w


def avatar_data():
    try:
        req = urllib.request.Request(f"https://github.com/{USER}.png?size=320", headers={"User-Agent": "profile"})
        with urllib.request.urlopen(req, timeout=20) as r:
            kind = r.headers.get_content_type()
            return f"data:{kind};base64,{base64.b64encode(r.read()).decode()}"
    except Exception:
        return None


# Blocks
def hero(p, avatar):
    h = 212
    cx, cy = 112, 106
    b = [f'<clipPath id="card"><rect width="{W}" height="{h}" rx="{CARD_R}"/></clipPath>']
    b.append(f'<rect width="{W}" height="{h}" rx="{CARD_R}" fill="{p["surfaceContainer"]}"/>')
    b.append('<g clip-path="url(#card)">')
    b.append(f'<path class="spin" d="{shape("flower", 782, 22, 118)}" fill="{p["primaryContainer"]}"/>')
    b.append(f'<path class="bob" d="{shape("clover", 686, 226, 46)}" fill="{p["tertiaryContainer"]}"/>')
    b.append(f'<path class="spin-r" d="{shape("sunny", 792, 182, 26)}" fill="{p["secondaryContainer"]}"/>')
    b.append("</g>")
    b.append(f'<path class="spin" d="{shape("sunny", cx, cy, 84)}" fill="{p["primary"]}" opacity=".95"/>')
    b.append(f'<clipPath id="ava"><path d="{shape("cookie12", cx, cy, 74)}"/></clipPath>')
    b.append(f'<path d="{shape("cookie12", cx, cy, 78)}" fill="{p["surfaceContainer"]}"/>')
    if avatar:
        b.append(f'<g class="fade"><image href="{avatar}" x="{cx - 76}" y="{cy - 76}" width="152" height="152" clip-path="url(#ava)" preserveAspectRatio="xMidYMid slice"/></g>')
    else:
        b.append(f'<path d="{shape("cookie12", cx, cy, 74)}" fill="{p["primaryContainer"]}"/>')
    x = 224
    b.append(txt(x, 62, HERO_GREETING, 15, p["onSurfaceVariant"], 500, "up", 0.1))
    b.append(f'<g class="up" style="animation-delay:.2s">{txt(x - 2, 108, NAME, 46, p["onSurface"], 400, "wght")}</g>')
    lines = wrap(HERO_SUB, 13.5, 566, 400, 2)
    for i, line in enumerate(lines):
        b.append(txt(x, 138 + i * 18, line, 13.5, p["onSurfaceVariant"], 400, "up", 0.35 + i * 0.08))
    cx2 = x
    for i, (ic, label) in enumerate(HERO_CHIPS):
        g, w = chip(cx2, 168, label, p, ic, 0.6 + i * 0.1, style="tonal")
        b.append(g)
        cx2 += w + 6
    return svg(W, h, "".join(b), f"Hi, I'm {NAME}")


def section_title(x, y, label, ic, p, delay=0.0):
    tile = f'<path class="pop" style="animation-delay:{delay:.2f}s" d="{shape("cookie", x + 15, y + 15, 15)}" fill="{p["primaryContainer"]}"/>'
    i = f'<g class="pop" style="animation-delay:{delay + .05:.2f}s">{icon(ic, x + 7, y + 7, 16, p["onPrimaryContainer"])}</g>'
    return tile + i + txt(x + 40, y + 21, label, TITLE, p["onSurface"], 600, "up", delay)


def about(p):
    row = 40
    h = 62 + row * len(ABOUT) + 12
    b = [f'<rect width="{W}" height="{h}" rx="{CARD_R}" fill="{p["surfaceContainerLow"]}"/>']
    b.append(section_title(PAD, 16, "About me", "favorite", p))
    for i, (ic, label) in enumerate(ABOUT):
        y = 62 + i * row
        b.append(f'<g class="up" style="animation-delay:{0.15 + i * 0.1:.2f}s">')
        b.append(f'<rect x="{PAD}" y="{y}" width="{W - PAD * 2}" height="{row - 6}" rx="12" fill="{p["surfaceContainerHigh"]}"/>')
        b.append(f'<circle cx="{PAD + 22}" cy="{y + (row - 6) / 2}" r="11" fill="{p["secondaryContainer"]}"/>')
        b.append(icon(ic, PAD + 15.5, y + (row - 6) / 2 - 6.5, 13, p["onSecondaryContainer"]))
        b.append(txt(PAD + 42, y + (row - 6) / 2 + 4.5, label, BODY, p["onSurface"], 500))
        b.append("</g>")
    return svg(W, h, "".join(b), "About me")


def stack(p):
    b = []
    y = 58
    d = 0.1
    groups = []
    for title, items in STACK:
        gy = y
        groups.append(txt(PAD, gy + 11, title.upper(), 10, p["onSurfaceVariant"], 600, "fade", d, extra=' letter-spacing="1.2"'))
        x = PAD
        cy = gy + 20
        for ic, label in items:
            _, w = chip(0, 0, label, p, ic)
            if x + w > W - PAD:
                x = PAD
                cy += CHIP_H + 6
            g, w = chip(x, cy, label, p, ic, d)
            groups.append(g)
            x += w + 6
            d += 0.05
        y = cy + CHIP_H + 16
    h = y + 4
    b.append(f'<rect width="{W}" height="{h}" rx="{CARD_R}" fill="{p["surfaceContainerLow"]}"/>')
    b.append(section_title(PAD, 16, "Tech stack", "code", p))
    b.extend(groups)
    return svg(W, h, "".join(b), "Tech stack")


def pick_icon(pin):
    hay = f" {pin['name']} {pin['text']} {' '.join(pin['topics'])} ".lower().replace("-", " ")
    for keys, name in ICON_RULES:
        if any(k in hay for k in keys):
            return name
    return LANG_ICONS.get(pin["language"], "code")


def pin_tags(pin):
    tags = [pin["language"]] if pin["language"] else []
    hay = f"{pin['text']} {' '.join(pin['topics'])}".lower()
    if "winui" in hay and "WinUI 3" not in tags:
        tags.append("WinUI 3")
    return tags


def card(p, pin, index):
    w, h = CARD_W, CARD_H
    d0 = 0.08 * index
    proj = {
        "title": pin["name"],
        "text": pin["text"] or "No description yet.",
        "tags": pin_tags(pin),
        "icon": pick_icon(pin),
        "shape": SHAPES[index % len(SHAPES)],
        "fork": pin["fork"],
    }
    stars = pin["stars"]
    b = [f'<rect width="{w}" height="{h}" rx="{CARD_R}" fill="{p["surfaceContainerHigh"]}"/>']
    b.append(f'<g class="pop" style="animation-delay:{d0:.2f}s"><path class="spin" d="{shape(proj["shape"], 46, 44, 23)}" fill="{p["primaryContainer"]}"/></g>')
    b.append(f'<g class="pop" style="animation-delay:{d0 + .08:.2f}s">{icon(proj["icon"], 37, 35, 18, p["onPrimaryContainer"])}</g>')
    b.append(f'<circle cx="{w - 32}" cy="32" r="14" fill="{p["surfaceContainerHighest"]}"/>')
    b.append(icon("arrow_outward", w - 40, 24, 16, p["onSurfaceVariant"]))
    tx = 22
    b.append(txt(tx, 90, proj["title"], 17, p["onSurface"], 650, "up", d0 + 0.1))
    if proj.get("fork"):
        fw = text_width("Fork", 10, 600) + 14
        fx = tx + text_width(proj["title"], 17, 650) + 8
        b.append(f'<g class="pop" style="animation-delay:{d0 + .25:.2f}s"><rect x="{fx:.1f}" y="77" width="{fw:.1f}" height="18" rx="9" fill="{p["tertiaryContainer"]}"/>')
        b.append(txt(fx + fw / 2, 89.5, "Fork", 10, p["onTertiaryContainer"], 600, anchor="middle") + "</g>")
    for i, line in enumerate(wrap(proj["text"], 11.5, w - 44, 400, 2)):
        b.append(txt(tx, 111 + i * 15.5, line, 11.5, p["onSurfaceVariant"], 400, "up", d0 + 0.18 + i * 0.05))
    x = tx
    for i, tag in enumerate(proj["tags"]):
        g, cw = chip(x, 140, tag, p, None, d0 + 0.3 + i * 0.06, h=22, size=10.5, style="tonal")
        b.append(g)
        x += cw + 5
    if stars is not None:
        label = f"{stars}"
        sw = text_width(label, 11, 600)
        b.append(f'<g class="pop" style="animation-delay:{d0 + .4:.2f}s">')
        b.append(icon("star", w - 20 - sw - 17, 144, 14, p["primary"]))
        b.append(txt(w - 20, 155, label, 11, p["onSurfaceVariant"], 600, anchor="end"))
        b.append("</g>")
    return svg(w, h, "".join(b), proj["title"])


def stats(p, s):
    langs = s["languages"]
    total = sum(v for _, v in langs) or 1
    legend = []
    x, row = PAD, 0
    for name, v in langs:
        label = f"{name} {100 * v / total:.1f}%".replace(".0%", "%")
        lw = 12 + text_width(label, 11, 500) + 14
        if x + lw > W - PAD:
            x, row = PAD, row + 1
        legend.append((x, row, label))
        x += lw
    h = 288 + row * 22
    b = [f'<rect width="{W}" height="{h}" rx="{CARD_R}" fill="{p["surfaceContainerLow"]}"/>']
    b.append(section_title(PAD, 16, "GitHub activity", "monitoring", p))
    tiles = [
        ("star", f"{s['stars']}", "Stars earned", "cookie"),
        ("commit", f"{s['contributions']}", "Contributions this year", "clover"),
        ("book_2", f"{s['repos']}", "Public repos", "sunny"),
        ("group", f"{s['followers']}", "Followers", "flower"),
    ]
    for i, (ic, value, label, sh) in enumerate(tiles):
        tx = PAD + (i % 2) * 196
        ty = 60 + (i // 2) * 84
        d = 0.1 + i * 0.08
        b.append(f'<g class="up" style="animation-delay:{d:.2f}s">')
        b.append(f'<rect x="{tx}" y="{ty}" width="184" height="74" rx="18" fill="{p["surfaceContainerHigh"]}"/>')
        b.append(f'<path d="{shape(sh, tx + 28, ty + 26, 14)}" fill="{p["primaryContainer"]}"/>')
        b.append(icon(ic, tx + 20.5, ty + 18.5, 15, p["onPrimaryContainer"]))
        b.append(txt(tx + 52, ty + 38, value, 22, p["onSurface"], 700))
        b.append(txt(tx + 16, ty + 60, label, 11, p["onSurfaceVariant"], 500))
        b.append("</g>")
    rx = 428
    b.append(txt(rx, 74, "Last 21 days", 11, p["onSurfaceVariant"], 600, "fade", 0.1))
    gap = 5
    cw = (W - PAD - rx - gap * 6) / 7
    ch = 32
    for i, letter in enumerate("SMTWTFS"):
        b.append(txt(rx + i * (cw + gap) + cw / 2, 94, letter, 10, p["onSurfaceVariant"], 600, "fade", 0.15, anchor="middle"))
    base = p["surfaceContainerHighest"]
    levels = [base, mix(base, p["primary"], .4), mix(base, p["primary"], .65), mix(base, p["primary"], .85), p["primary"]]
    peak = max([d["c"] for wk in s["days"] for d in wk if d] + [1])
    for wi, wk in enumerate(s["days"]):
        for di, d in enumerate(wk):
            x = rx + di * (cw + gap)
            y = 104 + wi * (ch + 6)
            delay = 0.2 + (wi * 7 + di) * 0.025
            if d is None:
                b.append(f'<rect class="pop" style="animation-delay:{delay:.3f}s" x="{x + .75:.1f}" y="{y + .75}" width="{cw - 1.5:.1f}" height="{ch - 1.5}" rx="10" fill="none" stroke="{p["outlineVariant"]}" stroke-width="1.5" stroke-dasharray="3 3"/>')
                continue
            lvl = 0 if d["c"] == 0 else min(4, 1 + int(3 * d["c"] / peak + 0.5))
            fg = p["onPrimary"] if lvl >= 3 else p["onSurfaceVariant"]
            cell = f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ch}" rx="10" fill="{levels[lvl]}"/>'
            if d.get("today"):
                cell += f'<rect x="{x - 2.5:.1f}" y="{y - 2.5}" width="{cw + 5:.1f}" height="{ch + 5}" rx="12" fill="none" stroke="{p["primary"]}" stroke-width="1.5"/>'
            cell += txt(x + cw / 2, y + ch / 2 + 4, str(d["day"]), 11, fg, 600, anchor="middle")
            b.append(f'<g class="pop" style="animation-delay:{delay:.3f}s">{cell}</g>')
    ly = 236
    b.append(txt(PAD, ly, "Languages across all my repositories", 11, p["onSurfaceVariant"], 600, "fade", 0.3))
    surf = p["surfaceContainerLow"]
    colors = [p["primary"], p["tertiary"], p["secondary"], mix(p["primary"], surf, .45), mix(p["tertiary"], surf, .45), mix(p["secondary"], surf, .45), p["outline"], p["outlineVariant"]]
    bw = W - PAD * 2
    gaps = 4 * (len(langs) - 1)
    widths = [max(8.0, (bw - gaps) * v / total) for _, v in langs]
    k = (bw - gaps) / (sum(widths) or 1)
    x = PAD
    segs = []
    for i, sw in enumerate(widths):
        segs.append(f'<rect x="{x:.1f}" y="{ly + 10}" width="{sw * k:.1f}" height="11" rx="5.5" fill="{colors[i % len(colors)]}"/>')
        x += sw * k + 4
    b.append(f'<g class="grow" style="animation-delay:.4s">{"".join(segs)}</g>')
    for i, (lx, lrow, label) in enumerate(legend):
        ly2 = ly + 42 + lrow * 22
        b.append(f'<g class="fade" style="animation-delay:{0.6 + i * 0.06:.2f}s"><circle cx="{lx + 4}" cy="{ly2 - 4}" r="4" fill="{colors[i % len(colors)]}"/>')
        b.append(txt(lx + 12, ly2, label, 11, p["onSurfaceVariant"], 500) + "</g>")
    return svg(W, h, "".join(b), "GitHub activity")


def button(p, label, ic, kind):
    h = 40
    size = 13
    pad = 18
    iw = 16
    w = pad * 2 + iw + 8 + text_width(label, size, 600)
    if kind == "filled":
        bg, fg = p["primary"], p["onPrimary"]
    else:
        bg, fg = p["secondaryContainer"], p["onSecondaryContainer"]
    b = [f'<g class="pop"><rect width="{w:.1f}" height="{h}" rx="20" fill="{bg}"/>']
    b.append(icon(ic, pad, (h - iw) / 2, iw, fg))
    b.append(txt(pad + iw + 8, h / 2 + size * 0.36, label, size, fg, 600) + "</g>")
    return svg(round(w), h, "".join(b), label)


def wave(p):
    h = 18
    amp, length = 4, 48
    pts = []
    for i in range(0, W + length * 2 + 1, 4):
        pts.append(f"{i} {h / 2 + amp * math.sin(2 * math.pi * i / length):.1f}")
    d = "M" + " L".join(pts)
    b = [f'<clipPath id="w"><rect x="0" y="0" width="{W}" height="{h}"/></clipPath><g clip-path="url(#w)">']
    b.append(f'<path class="wave" d="{d}" fill="none" stroke="{p["primary"]}" stroke-width="3.5" stroke-linecap="round"/></g>')
    return svg(W, h, "".join(b), "divider")


# Data
def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


NOISE = {"Inno Setup", "Batchfile", "PowerShell", "VBScript", "Shell", "Makefile", "Dockerfile"}


def graphql(t, q, variables=None):
    body = json.dumps({"query": q, "variables": variables or {}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={"Authorization": f"bearer {t}", "User-Agent": "profile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"]


def all_languages(t):
    try:
        v = graphql(t, """{viewer{login repositories(ownerAffiliations:OWNER,first:100){nodes{isFork
          languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}""")["viewer"]
    except Exception:
        return None
    if v["login"].lower() != USER.lower():
        return None
    langs = {}
    for r in v["repositories"]["nodes"]:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name not in NOISE:
                langs[name] = langs.get(name, 0) + e["size"]
    return [list(kv) for kv in sorted(langs.items(), key=lambda kv: -kv[1])[:7]]


DESCRIPTION_OVERRIDES = {
    "Math-Studio": "Math functions and 3D animation studio for Windows (PyWebView + SymPy + Three.js + FFmpeg)",
    "blender-mathfunction": "Blender addon: math expressions to curves, surfaces, point clouds and volumes",
    "GeoStringAnim": "Blender Geometry Nodes addon: per-character typewriter, bounce and wave text animation",
    "geometry_nodes_exporter": "Export Blender Geometry Node trees as SVG or PDF",
}


def normalize(node):
    return {
        "name": node["name"],
        "url": node["url"],
        "text": DESCRIPTION_OVERRIDES.get(node["name"], (node["description"] or "").strip()),
        "fork": node["isFork"],
        "stars": node["stargazerCount"],
        "language": (node["primaryLanguage"] or {}).get("name"),
        "topics": [t["topic"]["name"] for t in node["repositoryTopics"]["nodes"]],
    }


def fetch_stats(cached):
    t = token()
    if not t:
        return None
    u = graphql(t, """query($login:String!){user(login:$login){
      followers{totalCount}
      repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){totalCount nodes{name url description isFork stargazerCount
        primaryLanguage{name} repositoryTopics(first:10){nodes{topic{name}}}}}
      pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name url description isFork stargazerCount
        primaryLanguage{name} repositoryTopics(first:10){nodes{topic{name}}}}}}
      contributionsCollection{contributionCalendar{totalContributions
        weeks{contributionDays{contributionCount date weekday}}}}}}""", {"login": USER})["user"]
    repos = u["repositories"]["nodes"]
    today = datetime.date.today().isoformat()
    days = []
    for w in u["contributionsCollection"]["contributionCalendar"]["weeks"][-3:]:
        row = [None] * 7
        for d in w["contributionDays"]:
            row[d["weekday"]] = {"c": d["contributionCount"], "day": int(d["date"][8:]), "today": d["date"] == today}
        days.append(row)
    while len(days) < 3:
        days.insert(0, [None] * 7)
    pins = [normalize(n) for n in u["pinnedItems"]["nodes"] if n]
    if not pins:
        # nothing pinned on the profile: fall back to the most starred own repos
        own = [r for r in repos if not r["isFork"]]
        own.sort(key=lambda r: (-r["stargazerCount"], r["name"].lower()))
        pins = [normalize(r) for r in own[:6]]
    return {
        "stars": sum(r["stargazerCount"] for r in repos if not r["isFork"]),
        "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "languages": all_languages(t) or (cached or {}).get("languages", []),
        "days": days,
        "pins": pins,
    }


# Readme
def slug(name):
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def pic(name, alt, width="100%"):
    return f'<img src="assets/{name}.svg" width="{width}" alt="{escape(alt)}">'


def readme(pins):
    cards = [f'<a href="{pin["url"]}">{pic("project-" + slug(pin["name"]), pin["name"], "49%")}</a>' for pin in pins]
    rows = ["&nbsp;".join(cards[i:i + 2]) for i in range(0, len(cards), 2)]
    buttons = "&nbsp;&nbsp;".join(f'<a href="{url}">{pic("button-" + key, label, "auto")}</a>' for key, label, _, _, url in BUTTONS)
    blocks = [
        pic("hero", f"Hi, I'm {NAME}"),
        pic("about", "About me"),
        pic("stack", "Tech stack"),
        *rows,
        pic("stats", "GitHub activity"),
        pic("wave", ""),
        buttons,
    ]
    return '<div align="center">\n\n' + "\n\n".join(blocks) + "\n\n</div>\n"


# Main
def meaningful(s):
    return {k: v for k, v in s.items() if k != "days"}


def main():
    OUT.mkdir(exist_ok=True)
    cache = ROOT / "data/stats.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
    try:
        s = fetch_stats(cached)
    except Exception as e:
        print("stats failed:", e)
        s = None
    if s is None:
        s = dict(cached)
    avatar = avatar_data()
    s["avatar"] = hashlib.sha1(avatar.encode()).hexdigest()[:12] if avatar else (cached or {}).get("avatar")
    if "--if-changed" in sys.argv and cached and meaningful(s) == meaningful(cached):
        print("no changes")
        return
    cache.write_text(json.dumps(s, indent=1))
    # one black theme for every client colour scheme
    p = PALETTE["dark"]
    files = {
        "hero": hero(p, avatar),
        "about": about(p),
        "stack": stack(p),
        "stats": stats(p, s),
        "wave": wave(p),
    }
    for i, pin in enumerate(s["pins"]):
        files[f"project-{slug(pin['name'])}"] = card(p, pin, i)
    for key, label, ic, kind, _ in BUTTONS:
        files[f"button-{key}"] = button(p, label, ic, kind)
    for name, content in files.items():
        (OUT / f"{name}.svg").write_text(content, encoding="utf-8")
    keep = {f"project-{slug(pin['name'])}" for pin in s["pins"]}
    for old in OUT.glob("*.svg"):
        stem = old.stem
        if stem.endswith(("-dark", "-light")):
            old.unlink()
        elif stem.startswith("project-") and stem not in keep:
            old.unlink()
    (ROOT / "README.md").write_text(readme(s["pins"]), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()

