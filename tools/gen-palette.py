#!/usr/bin/env python3
"""theme.toml -> colors.xml for a palette RRO (android.theme.customization.system_palette).

Emits the 65 public `system_{accent1,accent2,accent3,neutral1,neutral2}_{0..1000}` colours that
Material You apps read (API 31+). Tones are made by mixing the Omarchy colour with white (low
tones) or black (high tones) — ponytail: linear sRGB mix, upgrade to HCT (material-color-utilities)
when contrast complaints appear. The ~136 Android 14+ `system_primary_*`/`system_surface_*` tokens
are issue M2-palette; they follow the same table.

Usage: tools/gen-palette.py themes/tokyo-night/theme.toml > overlay/themes/tokyo-night/OmarchyPaletteTokyoNight/res/values/colors.xml
"""
import sys, tomllib

TONES = [0, 10, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
ROLES = {  # AOSP palette role -> theme.toml key
    "accent1": "accent", "accent2": "magenta", "accent3": "cyan",
    "neutral1": "background", "neutral2": "lighter_background",
}

def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def rgb2hex(c): return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)
def mix(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

def tone(rgb, t):
    """t=0 -> white, t=1000 -> black, 500 -> the colour itself (AOSP convention: 0 lightest)."""
    if t <= 500: return mix((255, 255, 255), rgb, t / 500)
    return mix(rgb, (0, 0, 0), (t - 500) / 500)

def palette(theme):
    out = {}
    for role, key in ROLES.items():
        base = hex2rgb(theme[key])
        for t in TONES:
            out[f"system_{role}_{t}"] = rgb2hex(tone(base, t))
    return out

def to_xml(colors):
    body = "\n".join(f'    <color name="{k}">{v}</color>' for k, v in colors.items())
    return f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n{body}\n</resources>\n'

def selfcheck():
    p = palette({"accent": "#7aa2f7", "magenta": "#bb9af7", "cyan": "#449dab",
                 "background": "#1a1b26", "lighter_background": "#24283b"})
    assert len(p) == 65, len(p)
    assert p["system_accent1_0"] == "#ffffff" and p["system_accent1_1000"] == "#000000"
    assert p["system_accent1_500"] == "#7aa2f7", p["system_accent1_500"]
    assert p["system_neutral1_500"] == "#1a1b26"

if __name__ == "__main__":
    selfcheck()
    if len(sys.argv) != 2: sys.exit(__doc__)
    with open(sys.argv[1], "rb") as f: theme = tomllib.load(f)
    sys.stdout.write(to_xml(palette(theme)))
