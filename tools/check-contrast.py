#!/usr/bin/env python3
"""WCAG 2.x contrast check for palette themes (design-8 criterio 3 + audit-8 H2).

For every themes/<id>/theme.toml each pair of PAIRS (Material 3 text/background tokens, dark
and light) must have a WCAG 2.x contrast ratio >= 4.5. Values are resolved through the same
token mapping as tools/gen-palette.py (imported: single source of truth, no second table).

Pairs (R2/H2): on_surface/surface, on_surface_variant/{surface,surface_variant} and
on_{primary,secondary,tertiary,error} y *_container sobre su fondo homónimo.

Exit != 0 if any pair falls below 4.5.

Usage: tools/check-contrast.py [themes/<id>/theme.toml ...]   (default: themes/*/theme.toml)
"""
import importlib.util, sys, tomllib
from pathlib import Path

THRESHOLD = 4.5
FAMILIES = ("primary", "secondary", "tertiary", "error")
PAIRS = [
    ("dark", "system_on_surface_dark", "system_surface_dark"),
    ("light", "system_on_surface_light", "system_surface_light"),
    ("dark", "system_on_surface_variant_dark", "system_surface_dark"),
    ("light", "system_on_surface_variant_light", "system_surface_light"),
    ("dark", "system_on_surface_variant_dark", "system_surface_variant_dark"),
    ("light", "system_on_surface_variant_light", "system_surface_variant_light"),
]
for _fam in FAMILIES:
    for _mode in ("dark", "light"):
        PAIRS.append((_mode, f"system_on_{_fam}_{_mode}", f"system_{_fam}_{_mode}"))
        PAIRS.append((_mode, f"system_on_{_fam}_container_{_mode}",
                      f"system_{_fam}_container_{_mode}"))

def load_gen():
    spec = importlib.util.spec_from_file_location(
        "gen_palette", Path(__file__).with_name("gen-palette.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def luminance(rgb):
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(h1, h2, hex2rgb):
    """WCAG 2.x contrast ratio (1.0 .. 21.0)."""
    a, b = sorted((luminance(hex2rgb(h1)), luminance(hex2rgb(h2))), reverse=True)
    return (a + 0.05) / (b + 0.05)

def main(paths):
    gp = load_gen()
    bad = False
    for path in paths:
        theme = tomllib.loads(Path(path).read_text())
        colors = gp.palette(theme)
        for mode, fg_name, bg_name in PAIRS:
            ratio = contrast(colors[fg_name], colors[bg_name], gp.hex2rgb)
            ok = ratio >= THRESHOLD
            bad |= not ok
            print(f"{path} [{mode}] {fg_name}={colors[fg_name]} vs "
                  f"{bg_name}={colors[bg_name]}: {ratio:.2f} "
                  f"{'OK' if ok else 'FALLA'} (>= {THRESHOLD})")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = sorted(str(p) for p in Path("themes").glob("*/theme.toml"))
    if not args:
        sys.exit("check-contrast: no hay themes/*/theme.toml que comprobar")
    main(args)
