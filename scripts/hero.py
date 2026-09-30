"""Generate assets/hero.svg, the animated profile banner.

Text is converted to vector paths so the banner renders identically everywhere,
GitHub serves SVGs as images, so they can't load web fonts reliably.
Animation is SMIL only, which works in <img> on Chrome, Firefox and Safari.

    uv pip install --target .pylib fonttools uharfbuzz
    PYTHONPATH=.pylib python3 scripts/hero.py
"""

import math
import random
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".fonts"
OUT = ROOT / "assets" / "hero.svg"

FONTS = {
    "grotesk": "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "mono": "https://github.com/google/fonts/raw/main/ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
    "mono_medium": "https://github.com/google/fonts/raw/main/ofl/ibmplexmono/IBMPlexMono-Medium.ttf",
}

NAME = "André Figueira"
GREETING = "hey, I'm"
ROLES = [
    "principal engineer",
    "game developer",
    "independent researcher",
    "music producer",
    "founder, voidmode studios",
]
FOOTNOTE = "london  ·  shipping software since 2006"

W, H = 1200, 440
TEXT_X = 84
HOLE = (948, 222)

TEXT = "#f0f3f6"
MUTED = "#8b949e"
DIM = "#6b7480"
HOT = "#fff3df"
WARM = "#ffb46b"
EMBER = "#ff7a3d"


def font_path(key):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{key}.ttf"
    if not path.exists():
        urllib.request.urlretrieve(FONTS[key], path)
    return path


class Face:
    """A font we can shape with HarfBuzz and draw with fontTools."""

    def __init__(self, key, wght=None):
        path = font_path(key)
        self.tt = TTFont(path)
        if wght is not None:
            self.tt = instantiateVariableFont(self.tt, {"wght": wght})
            blob = hb.Blob(self._bytes())
        else:
            blob = hb.Blob.from_file_path(str(path))
        self.hb_font = hb.Font(hb.Face(blob))
        self.upem = self.tt["head"].unitsPerEm
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()

    def _bytes(self):
        from io import BytesIO

        buf = BytesIO()
        self.tt.save(buf)
        return buf.getvalue()

    def path(self, text, x, baseline, size):
        """Return (svg path data, advance width in px) for a line of text."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"kern": True, "liga": True})
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        cursor = 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = self.order[info.codepoint]
            gx = x + (cursor + pos.x_offset) * scale
            gy = baseline - pos.y_offset * scale
            self.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, gx, gy)))
            cursor += pos.x_advance
        return pen.getCommands(), cursor * scale


def stars(rng, count):
    out = []
    for i in range(count):
        x, y = rng.uniform(8, W - 8), rng.uniform(8, H - 8)
        # keep the black hole's shadow clean
        if math.hypot(x - HOLE[0], (y - HOLE[1]) * 1.4) < 120:
            continue
        r = rng.choice([0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5])
        o = rng.uniform(0.18, 0.75) if r < 1.2 else rng.uniform(0.5, 0.95)
        # only faint dust behind the text so nothing reads as a stray glyph
        if 70 < x < 680 and 115 < y < 370:
            r, o = 0.5, min(o, 0.22)
        star = f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" opacity="{o:.2f}"'
        if i % 4 == 0:
            dur = rng.uniform(2.5, 7)
            lo = max(0.05, o * 0.2)
            star += (
                f'><animate attributeName="opacity" values="{o:.2f};{lo:.2f};{o:.2f}" '
                f'dur="{dur:.1f}s" begin="{-rng.uniform(0, dur):.1f}s" repeatCount="indefinite"/></circle>'
            )
        else:
            star += "/>"
        out.append(star)
    return "\n    ".join(out)


def typing_timeline(mono_size):
    """Keyframes for a typewriter that cycles through ROLES, one at a time."""
    cw = mono_size * 0.6  # IBM Plex Mono advance is 600/1000 em
    type_step, delete_step, hold, gap = 0.075, 0.03, 2.4, 0.45
    events = []  # (time, role index, visible chars)
    t = 0.3
    for i, role in enumerate(ROLES):
        n = len(role)
        for j in range(1, n + 1):
            events.append((t, i, j))
            t += type_step
        t += hold
        for j in range(n - 1, -1, -1):
            events.append((t, i, j))
            t += delete_step
        t += gap
    total = t
    return events, total, cw


def discrete(frames, total):
    """Turn [(time, value)] into SMIL keyTimes/values for calcMode=discrete.

    frames must include a value at t=0, SMIL requires keyTimes to start at 0.
    """
    frames = sorted(frames)
    key_times, values = [], []
    for t, v in frames:
        kt = round(t / total, 5)
        if key_times and kt <= key_times[-1]:
            values[-1] = v
            continue
        key_times.append(kt)
        values.append(v)
    return key_times, values


def build():
    grotesk = Face("grotesk", wght=700)
    mono = Face("mono")
    mono_medium = Face("mono_medium")
    rng = random.Random(1987)

    greet_d, _ = mono.path(GREETING, TEXT_X + 2, 152, 19)
    name_d, name_w = grotesk.path(NAME, TEXT_X, 232, 76)
    foot_d, _ = mono.path(FOOTNOTE, TEXT_X + 2, 352, 15)

    role_size = 24
    prompt_d, prompt_w = mono_medium.path("›", TEXT_X + 2, 290, role_size)
    role_x = TEXT_X + 2 + prompt_w + 12
    role_paths = [mono.path(r, role_x, 290, role_size)[0] for r in ROLES]

    events, total, cw = typing_timeline(role_size)
    role_anims = []
    for i in range(len(ROLES)):
        frames = [(0.0, 0.0)] + [(t, j * cw) for t, ri, j in events if ri == i]
        kt, vals = discrete(frames, total)
        role_anims.append(
            f'<animate attributeName="width" calcMode="discrete" dur="{total:.2f}s" '
            f'repeatCount="indefinite" keyTimes="{";".join(map(str, kt))}" '
            f'values="{";".join(f"{v:.1f}" for v in vals)}"/>'
        )
    cursor_frames = [(0.0, role_x)] + [(t, role_x + j * cw) for t, _, j in events]
    kt, vals = discrete(cursor_frames, total)
    cursor_anim = (
        f'<animate attributeName="x" calcMode="discrete" dur="{total:.2f}s" '
        f'repeatCount="indefinite" keyTimes="{";".join(map(str, kt))}" '
        f'values="{";".join(f"{v:.1f}" for v in vals)}"/>'
    )

    clips = "\n    ".join(
        f'<clipPath id="r{i}"><rect x="{role_x - 2}" y="260" width="0" height="42">{a}</rect></clipPath>'
        for i, a in enumerate(role_anims)
    )
    roles = "\n    ".join(
        f'<path clip-path="url(#r{i})" d="{d}"/>' for i, d in enumerate(role_paths)
    )

    cx, cy = HOLE
    disk_rx, disk_ry = 236, 26
    shadow_r, halo_r = 70, 80
    # front half of the disk, the part that passes in front of the shadow
    front = f"M{cx - disk_rx},{cy} A{disk_rx},{disk_ry} 0 0 0 {cx + disk_rx},{cy}"
    lensed = f"M{cx - halo_r - 6},{cy + 6} A{halo_r + 6},{halo_r + 12} 0 0 1 {cx + halo_r + 6},{cy + 6}"
    full = (
        f"M{cx - disk_rx},{cy} A{disk_rx},{disk_ry} 0 0 1 {cx + disk_rx},{cy} "
        f"A{disk_rx},{disk_ry} 0 0 1 {cx - disk_rx},{cy}"
    )

    # a small saucer that drifts across every so often, for the UFO people
    ufo = f"""
  <g opacity="0">
    <animate attributeName="opacity" values="0;0;0.9;0.9;0;0" keyTimes="0;0.6;0.62;0.97;0.99;1" dur="34s" repeatCount="indefinite"/>
    <animateMotion dur="34s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.6;0.99;1" calcMode="linear"
      path="M-60,70 C200,40 420,96 640,62 S1040,40 1260,78"/>
    <ellipse cx="0" cy="3" rx="15" ry="4.2" fill="#2a2f38" stroke="#9aa4b2" stroke-width="0.8"/>
    <path d="M-7,1 C-6,-6 6,-6 7,1 Z" fill="#8fe3ff" opacity="0.55"/>
    <circle cx="-8" cy="4" r="1.1" fill="#8fe3ff"><animate attributeName="opacity" values="1;0.2;1" dur="0.8s" repeatCount="indefinite"/></circle>
    <circle cx="0" cy="5.2" r="1.1" fill="#8fe3ff"><animate attributeName="opacity" values="0.2;1;0.2" dur="0.8s" repeatCount="indefinite"/></circle>
    <circle cx="8" cy="4" r="1.1" fill="#8fe3ff"><animate attributeName="opacity" values="1;0.2;1" dur="0.8s" repeatCount="indefinite"/></circle>
  </g>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">André Figueira</title>
  <desc id="d">Principal engineer, game developer, independent researcher, music producer and founder of Voidmode Studios.</desc>
  <defs>
    <clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath>
    <radialGradient id="bg" cx="{cx / W:.3f}" cy="{cy / H:.3f}" r="0.9">
      <stop offset="0" stop-color="#0d0a10"/>
      <stop offset="0.45" stop-color="#06070c"/>
      <stop offset="1" stop-color="#030409"/>
    </radialGradient>
    <radialGradient id="bloom" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{EMBER}" stop-opacity="0.34"/>
      <stop offset="0.5" stop-color="{EMBER}" stop-opacity="0.08"/>
      <stop offset="1" stop-color="{EMBER}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="nebula" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#5b3cc4" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#5b3cc4" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="disk" x1="{cx - disk_rx}" x2="{cx + disk_rx}" y1="0" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{EMBER}" stop-opacity="0"/>
      <stop offset="0.16" stop-color="{EMBER}" stop-opacity="0.8"/>
      <stop offset="0.36" stop-color="{HOT}"/>
      <stop offset="0.6" stop-color="{WARM}"/>
      <stop offset="0.84" stop-color="{EMBER}" stop-opacity="0.55"/>
      <stop offset="1" stop-color="{EMBER}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="halo" x1="0" x2="0" y1="{cy - halo_r}" y2="{cy + halo_r}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{HOT}"/>
      <stop offset="0.5" stop-color="{WARM}" stop-opacity="0.75"/>
      <stop offset="1" stop-color="{HOT}" stop-opacity="0.9"/>
    </linearGradient>
    <linearGradient id="fade" x1="0" x2="1">
      <stop offset="0" stop-color="{TEXT}"/>
      <stop offset="1" stop-color="#c9d1d9"/>
    </linearGradient>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
    <filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>
    <filter id="haze" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
    {clips}
  </defs>

  <g clip-path="url(#card)">
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <ellipse cx="300" cy="360" rx="420" ry="190" fill="url(#nebula)"/>
  <g fill="#fff">
    {stars(rng, 190)}
  </g>
  {ufo}

  <g>
    <animateTransform attributeName="transform" type="translate" values="0,0;0,-3;0,0" dur="9s" repeatCount="indefinite"/>
    <circle cx="{cx}" cy="{cy}" r="250" fill="url(#bloom)">
      <animate attributeName="opacity" values="0.85;1;0.85" dur="6s" repeatCount="indefinite"/>
    </circle>
    <path d="{full}" fill="none" stroke="url(#disk)" stroke-width="30" filter="url(#glow)" opacity="0.7"/>
    <circle cx="{cx}" cy="{cy}" r="{halo_r}" fill="none" stroke="url(#halo)" stroke-width="16" filter="url(#glow)" opacity="0.8"/>
    <circle cx="{cx}" cy="{cy}" r="{halo_r}" fill="none" stroke="url(#halo)" stroke-width="5" filter="url(#soft)"/>
    <circle cx="{cx}" cy="{cy}" r="{halo_r - 3}" fill="none" stroke="{HOT}" stroke-width="1.2" opacity="0.9"/>
    <path d="{full}" fill="none" stroke="url(#disk)" stroke-width="7" filter="url(#soft)"/>
    <path d="{lensed}" fill="none" stroke="{WARM}" stroke-width="12" filter="url(#glow)" opacity="0.75"/>
    <path d="{lensed}" fill="none" stroke="{HOT}" stroke-width="3.5" filter="url(#soft)" opacity="0.9"/>
    <path d="{full}" fill="none" stroke="{HOT}" stroke-width="1.4" stroke-dasharray="2 22 1 38 3 30" opacity="0.55">
      <animate attributeName="stroke-dashoffset" from="0" to="-384" dur="7s" repeatCount="indefinite"/>
    </path>
    <circle cx="{cx}" cy="{cy}" r="{shadow_r}" fill="#000"/>
    <path d="{front}" fill="none" stroke="url(#disk)" stroke-width="22" filter="url(#glow)" opacity="0.85"/>
    <path d="{front}" fill="none" stroke="url(#disk)" stroke-width="8" filter="url(#soft)"/>
    <path d="{front}" fill="none" stroke="{HOT}" stroke-width="1.6" opacity="0.85"/>
    <path d="{front}" fill="none" stroke="{HOT}" stroke-width="1.4" stroke-dasharray="2 22 1 38 3 30" opacity="0.55">
      <animate attributeName="stroke-dashoffset" from="0" to="384" dur="7s" repeatCount="indefinite"/>
    </path>
  </g>

  <path d="{greet_d}" fill="{MUTED}"/>
  <path d="{name_d}" fill="url(#fade)"/>
  <path d="{prompt_d}" fill="{WARM}"/>
  <g fill="{TEXT}">
    {roles}
  </g>
  <rect x="{role_x}" y="270" width="{cw:.1f}" height="26" fill="{WARM}" opacity="0.9">
    {cursor_anim}
    <animate attributeName="opacity" values="0.9;0.9;0;0" keyTimes="0;0.5;0.5;1" calcMode="discrete" dur="1.05s" repeatCount="indefinite"/>
  </rect>
  <path d="{foot_d}" fill="{DIM}"/>
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="21.5" fill="none" stroke="#fff" stroke-opacity="0.08"/>
</svg>
"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT} ({len(svg) / 1024:.1f} KB), name ends at x={TEXT_X + name_w:.0f}, loop {total:.1f}s")


if __name__ == "__main__":
    build()
