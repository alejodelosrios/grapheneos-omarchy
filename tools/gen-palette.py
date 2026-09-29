#!/usr/bin/env python3
"""theme.toml -> colors.xml for a palette RRO (android.theme.customization.system_palette).

Emits the 194 public `system_*` colours of tools/system-colors.txt (public-final.xml ref=17):
the classic 65 `system_{accent1,accent2,accent3,neutral1,neutral2}_{0..1000}` ramps (API 31+,
unchanged), the `system_error_{0..1000}` ramp and the Android 14+ tokens (`system_primary_*`,
`system_surface_*`, …). Tones are made by mixing the Omarchy colour with white (low tones) or
black (high tones) — ponytail: linear sRGB mix, upgrade to HCT (material-color-utilities) when
contrast complaints appear. No `--hct` flag in this wave.

Coverage rule (design-8): every name of tools/system-colors.txt must be mapped and nothing else
may be emitted, else exit != 0.

Usage: tools/gen-palette.py themes/tokyo-night/theme.toml > overlay/themes/tokyo-night/OmarchyPaletteTokyoNight/res/values/colors.xml
"""
import sys, tomllib
from pathlib import Path

TONES = [0, 10, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
ROLES = {  # AOSP palette role -> theme.toml key
    "accent1": "accent", "accent2": "magenta", "accent3": "cyan",
    "neutral1": "background", "neutral2": "lighter_background",
}
ERROR_KEY = "red"  # rampa system_error_{0..1000} <- red, misma función tone (design-8)

# Tokens A14+ (116): name -> clave theme.toml, opcionalmente tono. Reglas del diseño
# (design-8 «Mapeo de roles»); en claro, las lecturas ambiguas documentadas en el reporte:
#   surface*/background*: container*->lighter_background, dim->darker_background,
#     bright->light_foreground, variant->muted, tint->accent, disabled->muted
#   on_* en superficie: on_surface->foreground, on_background->bright_foreground
#     (pareja «foreground|bright_foreground»); colas disabled/variant->muted
#   on_* sobre primarios/error («texto oscuro sobre acento», pareja «dark_background|darker_background»):
#     primarios (primary/secondary/tertiary)->dark_background, error->darker_background
#   fixed->tone(base,150), fixed_dim->tone(base,300), container_dark->tone(base,800),
#     container_light->tone(base,200); pares _dark/_light con el mismo hex base salvo fixed/container
#   text*->foreground (colas disabled/disable_only->muted); outline*->muted
#   control*->accent|muted (activado/realce->accent, normal->muted)
#   scrim|shadow->darker_background; notification_accent_color->accent
#   palette_key_color_*->clave base exacta (neutral->background, neutral_variant->lighter_background)
#   inverse_*->contraparte del par (surface,on_surface) y (primary,on_primary)
TOKENS = {
    # --- superficie / fondo (surface*, background*) ---
    "system_background_dark": ("background",),
    "system_background_light": ("background",),
    "system_surface_dark": ("background",),
    "system_surface_light": ("background",),
    "system_surface_dim_dark": ("darker_background",),
    "system_surface_dim_light": ("darker_background",),
    "system_surface_bright_dark": ("light_foreground",),
    "system_surface_bright_light": ("light_foreground",),
    "system_surface_variant_dark": ("muted",),
    "system_surface_variant_light": ("muted",),
    "system_surface_tint_dark": ("accent",),
    "system_surface_tint_light": ("accent",),
    "system_surface_disabled": ("muted",),
    "system_surface_container_dark": ("lighter_background",),
    "system_surface_container_light": ("lighter_background",),
    "system_surface_container_low_dark": ("lighter_background",),
    "system_surface_container_low_light": ("lighter_background",),
    "system_surface_container_lowest_dark": ("lighter_background",),
    "system_surface_container_lowest_light": ("lighter_background",),
    "system_surface_container_high_dark": ("lighter_background",),
    "system_surface_container_high_light": ("lighter_background",),
    "system_surface_container_highest_dark": ("lighter_background",),
    "system_surface_container_highest_light": ("lighter_background",),
    # --- on_* sobre superficie ---
    "system_on_surface_dark": ("foreground",),
    "system_on_surface_light": ("foreground",),
    "system_on_surface_disabled": ("muted",),
    "system_on_surface_variant_dark": ("muted",),
    "system_on_surface_variant_light": ("muted",),
    "system_on_background_dark": ("bright_foreground",),
    "system_on_background_light": ("bright_foreground",),
    # --- primarios / error (familia base + sufijos fixed/container) ---
    "system_primary_dark": ("accent",),
    "system_primary_light": ("accent",),
    "system_primary_container_dark": ("accent", 800),
    "system_primary_container_light": ("accent", 200),
    "system_primary_fixed": ("accent", 150),
    "system_primary_fixed_dim": ("accent", 300),
    "system_secondary_dark": ("magenta",),
    "system_secondary_light": ("magenta",),
    "system_secondary_container_dark": ("magenta", 800),
    "system_secondary_container_light": ("magenta", 200),
    "system_secondary_fixed": ("magenta", 150),
    "system_secondary_fixed_dim": ("magenta", 300),
    "system_tertiary_dark": ("cyan",),
    "system_tertiary_light": ("cyan",),
    "system_tertiary_container_dark": ("cyan", 800),
    "system_tertiary_container_light": ("cyan", 200),
    "system_tertiary_fixed": ("cyan", 150),
    "system_tertiary_fixed_dim": ("cyan", 300),
    "system_error_dark": ("red",),
    "system_error_light": ("red",),
    "system_error_container_dark": ("red", 800),
    "system_error_container_light": ("red", 200),
    # --- on_primarios / on_error (texto oscuro sobre acento) ---
    "system_on_primary_dark": ("dark_background",),
    "system_on_primary_light": ("dark_background",),
    "system_on_primary_container_dark": ("dark_background",),
    "system_on_primary_container_light": ("dark_background",),
    "system_on_primary_fixed": ("dark_background",),
    "system_on_primary_fixed_variant": ("dark_background",),
    "system_on_secondary_dark": ("dark_background",),
    "system_on_secondary_light": ("dark_background",),
    "system_on_secondary_container_dark": ("dark_background",),
    "system_on_secondary_container_light": ("dark_background",),
    "system_on_secondary_fixed": ("dark_background",),
    "system_on_secondary_fixed_variant": ("dark_background",),
    "system_on_tertiary_dark": ("dark_background",),
    "system_on_tertiary_light": ("dark_background",),
    "system_on_tertiary_container_dark": ("dark_background",),
    "system_on_tertiary_container_light": ("dark_background",),
    "system_on_tertiary_fixed": ("dark_background",),
    "system_on_tertiary_fixed_variant": ("dark_background",),
    "system_on_error_dark": ("darker_background",),
    "system_on_error_light": ("darker_background",),
    "system_on_error_container_dark": ("darker_background",),
    "system_on_error_container_light": ("darker_background",),
    # --- inverse_*: contraparte del par (surface,on_surface) / (primary,on_primary) ---
    "system_inverse_surface_dark": ("foreground",),
    "system_inverse_surface_light": ("foreground",),
    "system_inverse_on_surface_dark": ("background",),
    "system_inverse_on_surface_light": ("background",),
    "system_inverse_primary_dark": ("dark_background",),
    "system_inverse_primary_light": ("dark_background",),
    # --- text* ---
    "system_text_primary_inverse_dark": ("foreground",),
    "system_text_primary_inverse_light": ("foreground",),
    "system_text_primary_inverse_disable_only_dark": ("muted",),
    "system_text_primary_inverse_disable_only_light": ("muted",),
    "system_text_secondary_and_tertiary_inverse_dark": ("foreground",),
    "system_text_secondary_and_tertiary_inverse_light": ("foreground",),
    "system_text_secondary_and_tertiary_inverse_disabled_dark": ("muted",),
    "system_text_secondary_and_tertiary_inverse_disabled_light": ("muted",),
    "system_text_hint_inverse_dark": ("foreground",),
    "system_text_hint_inverse_light": ("foreground",),
    # --- outline* ---
    "system_outline_dark": ("muted",),
    "system_outline_light": ("muted",),
    "system_outline_disabled": ("muted",),
    "system_outline_variant_dark": ("muted",),
    "system_outline_variant_light": ("muted",),
    # --- control* ---
    "system_control_activated_dark": ("accent",),
    "system_control_activated_light": ("accent",),
    "system_control_highlight_dark": ("accent",),
    "system_control_highlight_light": ("accent",),
    "system_control_normal_dark": ("muted",),
    "system_control_normal_light": ("muted",),
    # --- scrim | shadow ---
    "system_scrim_dark": ("darker_background",),
    "system_scrim_light": ("darker_background",),
    "system_shadow_dark": ("darker_background",),
    "system_shadow_light": ("darker_background",),
    # --- notificación y claves de paleta ---
    "system_notification_accent_color": ("accent",),
    "system_palette_key_color_primary_dark": ("accent",),
    "system_palette_key_color_primary_light": ("accent",),
    "system_palette_key_color_secondary_dark": ("magenta",),
    "system_palette_key_color_secondary_light": ("magenta",),
    "system_palette_key_color_tertiary_dark": ("cyan",),
    "system_palette_key_color_tertiary_light": ("cyan",),
    "system_palette_key_color_neutral_dark": ("background",),
    "system_palette_key_color_neutral_light": ("background",),
    "system_palette_key_color_neutral_variant_dark": ("lighter_background",),
    "system_palette_key_color_neutral_variant_light": ("lighter_background",),
}

SYSTEM_COLORS_TXT = Path(__file__).with_name("system-colors.txt")

def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def rgb2hex(c): return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)
def mix(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

def tone(rgb, t):
    """t=0 -> white, t=1000 -> black, 500 -> the colour itself (AOSP convention: 0 lightest)."""
    if t <= 500: return mix((255, 255, 255), rgb, t / 500)
    return mix(rgb, (0, 0, 0), (t - 500) / 500)

def expected_tokens():
    return [ln for ln in SYSTEM_COLORS_TXT.read_text().splitlines() if ln.strip()]

def palette(theme):
    out = {}
    # rampa clásica 65: ROLES sin cambios (design-8; mapeo en docs/THEMING.md:20)
    for role, key in ROLES.items():
        base = hex2rgb(theme[key])
        for t in TONES:
            out[f"system_{role}_{t}"] = rgb2hex(tone(base, t))
    # rampa system_error_{0..1000} (13) <- red, misma función tone
    base = hex2rgb(theme[ERROR_KEY])
    for t in TONES:
        out[f"system_error_{t}"] = rgb2hex(tone(base, t))
    # tokens A14+ (116)
    for name, spec in TOKENS.items():
        key = spec[0]
        out[name] = rgb2hex(tone(hex2rgb(theme[key]), spec[1])) if len(spec) == 2 else theme[key]
    # regla 100% cobertura (design-8): todo token de system-colors.txt mapeado, nada sobrante
    want = expected_tokens()
    missing, extra = sorted(set(want) - set(out)), sorted(set(out) - set(want))
    if missing or extra:
        sys.exit(f"gen-palette: cobertura != 100% — faltan={missing} sobran={extra}")
    return {n: out[n] for n in want}

def to_xml(colors):
    body = "\n".join(f'    <color name="{k}">{v}</color>' for k, v in colors.items())
    return f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n{body}\n</resources>\n'

def selfcheck():
    p = palette({"accent": "#7aa2f7", "magenta": "#bb9af7", "cyan": "#449dab",
                 "background": "#1a1b26", "lighter_background": "#24283b",
                 "red": "#f7768e", "dark_background": "#13141c",
                 "darker_background": "#0e0e14", "foreground": "#a9b1d6",
                 "bright_foreground": "#c0caf5", "light_foreground": "#b4bee6",
                 "muted": "#414868"})
    assert len(p) == 194, len(p)  # 65 + 13 + 116 = 194 (tools/system-colors.txt, D2)
    assert p["system_accent1_0"] == "#ffffff" and p["system_accent1_1000"] == "#000000"
    assert p["system_accent1_500"] == "#7aa2f7", p["system_accent1_500"]
    assert p["system_neutral1_500"] == "#1a1b26"
    assert p["system_error_500"] == "#f7768e", p["system_error_500"]
    assert p["system_on_surface_dark"] == "#a9b1d6" and p["system_surface_dark"] == "#1a1b26"
    assert p["system_primary_fixed"] == rgb2hex(tone(hex2rgb("#7aa2f7"), 150))
    assert p["system_primary_container_dark"] == rgb2hex(tone(hex2rgb("#7aa2f7"), 800))

if __name__ == "__main__":
    selfcheck()
    if len(sys.argv) != 2: sys.exit(__doc__)
    with open(sys.argv[1], "rb") as f: theme = tomllib.load(f)
    sys.stdout.write(to_xml(palette(theme)))
