#!/usr/bin/env python3
"""WCAG 2.x contrast check for palette themes (design-8 criterio 3; clase cerrada en R5).

Pairs are DERIVED from tools/system-colors.txt — there is no hand-written PAIRS list (H2, H5
and H6 were all pairs the manual list did not cover). Derivation rules, 100% coverage like
gen-palette: every text token must find its background IN THE LIST or the check exits != 0
naming the token.

  * system_on_<rol>[_<mode>]      -> system_<rol>[_<mode>]       (same mode)
  * system_on_<rol>_fixed_variant -> system_<rol>_fixed_dim      (M3: the less-emphasised
    "variant" text sits on the dim fixed container; decided + documented in the i8 PR)
  * system_text_*_inverse[*]      -> system_inverse_surface[_<mode>]  (snackbars/toasts:
    M3 pairs textColor*Inverse with inverseSurface, same mode)
  * system_inverse_on_<rol>[..]   -> system_inverse_<rol>[..]    (same mode)
  * H7: system_on_surface[_variant]_<mode> -> ALL of the M3 surface family in the list
    (surface, surface_dim, surface_bright, surface_container{,_low,_lowest,_high,_highest},
    same mode) — that text sits on every surface; the homonym-only pairing of R5 lost the
    surface_bright pair (H5) again. on_surface_variant also keeps its surface_variant
    homonym (the H2 pair). One measured pair per background (100% rule per background).

Not text (out of the sweep, classified here so nothing is silent): outline_* (borders),
control_* (legacy AOSP textColorControl* used as control state tints), scrim/shadow (overlay),
the 65+13 ramps, palette_key_color_* (seeds), notification_accent_color (accent singleton),
and every surface/background/primary/… role.

Thresholds (explicit, never silent):
  * 4.5 text (WCAG 2.x AA) — default
  * DISABLED set below: inactive-UI text is exempt (WCAG 2.x 1.4.3 "part of an inactive user
    interface component"): measured and printed as "exento", never decides the exit
  * ICONS dict below: 3.0 (WCAG 2.x 1.4.11 non-text) per named icon/accent pair

Exit != 0 if any non-exempt pair falls below its threshold, or a text token has no pairable
background.

Usage: tools/check-contrast.py [themes/<id>/theme.toml ...]   (default: themes/*/theme.toml)
"""
import importlib.util, sys, tomllib
from pathlib import Path

THRESHOLD = 4.5
ICON_THRESHOLD = 3.0
TEXT_PREFIXES = ("on_", "text_", "inverse_on_")  # tras "system_": los tokens de texto

# Exención explícita (nunca silenciosa): texto de componente inactivo — WCAG 2.x 1.4.3.
DISABLED = {
    "system_on_surface_disabled",
    "system_text_primary_inverse_disable_only_dark",
    "system_text_primary_inverse_disable_only_light",
    "system_text_secondary_and_tertiary_inverse_disabled_dark",
    "system_text_secondary_and_tertiary_inverse_disabled_light",
}

# Pares icono/decorativo al 3.0 (WCAG 2.x 1.4.11 non-text), justificados por nombre:
ICONS = {
    # M3 inversePrimary: icono/acento sobre la superficie invertida (FAB, acción de snackbar),
    # no texto de lectura — de ahí 3.0 y no 4.5.
    "system_inverse_primary_dark": "system_inverse_surface_dark",
    "system_inverse_primary_light": "system_inverse_surface_light",
}

# H7: familia M3 de superficies que hospedan el texto on_surface{,_variant} (mismo modo).
SURFACE_FAMILY = (
    "surface", "surface_dim", "surface_bright",
    "surface_container", "surface_container_low", "surface_container_lowest",
    "surface_container_high", "surface_container_highest",
)
SURFACE_TEXT = {
    "system_on_surface_dark", "system_on_surface_light",
    "system_on_surface_variant_dark", "system_on_surface_variant_light",
}


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

def _split_mode(rest):
    for mode in ("dark", "light"):
        if rest.endswith("_" + mode):
            return rest[: -(len(mode) + 1)], mode
    return rest, None

def backgrounds_for(name):
    """Lista de fondos emparejables de un token de texto ([] si no le corresponde).

    H7: on_surface{,_variant} es el texto de TODA la familia de superficies M3, no solo de
    su homónimo (R5 perdió así el par de H5 sobre surface_bright). on_surface_variant
    conserva además su homónimo surface_variant (par de H2).
    """
    if name in SURFACE_TEXT:
        mode = name.rsplit("_", 1)[1]
        bgs = [f"system_{stem}_{mode}" for stem in SURFACE_FAMILY]
        if name.startswith("system_on_surface_variant_"):
            bgs.append(f"system_surface_variant_{mode}")
        return bgs
    if name.startswith("system_on_"):
        rol, mode = _split_mode(name[len("system_on_"):])
        suffix = f"_{mode}" if mode else ""
        if rol.endswith("_fixed_variant"):
            rol = rol[: -len("_fixed_variant")] + "_fixed_dim"
            return ["system_" + rol + suffix]
        # H1 (audit-26, ColorSpec2021.java:763-771): on_<rol>_fixed (sin _variant)
        # tiene DOS fondos en M3 — primaryFixedDim() como fondo principal (setBackground) y
        # primaryFixed() como segundo fondo (setSecondBackground) — ambos deben leer >= 4.5.
        if rol.endswith("_fixed"):
            dim = rol[: -len("_fixed")] + "_fixed_dim"
            return ["system_" + rol + suffix, "system_" + dim + suffix]
        return ["system_" + rol + suffix]
    if name.startswith("system_text_") and "_inverse" in name:
        _, mode = _split_mode(name[len("system_text_"):])
        return ["system_inverse_surface" + (f"_{mode}" if mode else "")]
    if name.startswith("system_inverse_on_"):
        return ["system_inverse_" + name[len("system_inverse_on_"):]]
    return []

def derive_pairs(names):
    """(fg, bg, kind) por cada token de texto/icono de tools/system-colors.txt (regla 100%:
    todo token de texto empareja con todos sus fondos, y cada fondo debe existir en la lista)."""
    known = set(names)
    pairs = []
    for name in names:
        if name in ICONS:
            pairs.append((name, ICONS[name], "icon"))
            continue
        if not name[len("system_"):].startswith(TEXT_PREFIXES):
            continue  # no es texto (clasificación en el docstring, no silenciosa)
        bgs = backgrounds_for(name)
        if not bgs:
            sys.exit(f"check-contrast: {name}: sin fondo emparejable — regla 100%")
        for bg in bgs:
            if bg not in known:
                sys.exit(f"check-contrast: {name}: fondo {bg} no está en system-colors.txt "
                         f"— regla 100%")
            pairs.append((name, bg, "disabled" if name in DISABLED else "text"))
    return pairs

NAMES = tuple(ln for ln in
              Path(__file__).with_name("system-colors.txt").read_text().splitlines() if ln.strip())
PAIRS = derive_pairs(NAMES)  # derivado del txt: el recuento que usan los tests sale de aquí

def main(paths):
    gp = load_gen()
    bad = False
    for path in paths:
        theme = tomllib.loads(Path(path).read_text())
        colors = gp.palette(theme)
        for fg_name, bg_name, kind in PAIRS:
            ratio = contrast(colors[fg_name], colors[bg_name], gp.hex2rgb)
            if kind == "disabled":
                status = "exento (WCAG 1.4.3)"
            else:
                thr = ICON_THRESHOLD if kind == "icon" else THRESHOLD
                ok = ratio >= thr
                bad |= not ok
                status = f"OK (>= {thr:g})" if ok else f"FALLA (< {thr:g})"
            print(f"{path} {fg_name}={colors[fg_name]} vs "
                  f"{bg_name}={colors[bg_name]}: {ratio:.2f} {status}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = sorted(str(p) for p in Path("themes").glob("*/theme.toml"))
    if not args:
        sys.exit("check-contrast: no hay themes/*/theme.toml que comprobar")
    main(args)
