"""Tests de QA del issue #26 (design-26 «Verificación por criterio», Pieza 3).

Criterios verificables SIN host de build ni Pixel:
  C1. themes/{rose-pine,catppuccin-latte,flexoki-light}/theme.toml con mode = "light" y sus
      RROs con colors.xml versionado (`git ls-files --error-unmatch`).
  C2. tools/check-contrast.py themes/*/theme.toml -> exit 0 (los 9 temas; aquí: solo los
      >= 3 light, el resto ya lo cubre test_i8_palette_tokens.py::test_criterio3_contraste_min_4_5).
  C4. Cada colors.xml contiene exactamente los nombres de tools/system-colors.txt, en orden
      (x9; ya lo cubre test_i8_palette_tokens.py::test_criterio2_nombres_xml_igual_txt, se
      repite aquí sin depender de ese módulo).
  Regresión i26: los 6 oscuros (catppuccin, everforest, gruvbox, kanagawa, nord, tokyo-night)
  siguen regenerando su colors.xml byte a byte pese a ADAPTIVE_TOKENS nuevo (design-26
  Pieza 1 punto 6: «si algún oscuro cambia, la preferida no alcanzaba 4.5 hoy»).

Criterio C3 (diff vacío de los 6 oscuros contra origin/develop) y C7 (Pixel) no son de esta
pieza: C3 es terreno del overlay-builder sobre overlay/themes/*, C7 exige build/dispositivo.

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures).
Cada test se vio en ROJO con su sabotaje (ver reporte de QA): el sabotaje de la tabla
ADAPTIVE_TOKENS y de pick_text ocurre en memoria sobre el módulo cargado (nunca se edita
tools/gen-palette.py en disco).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
GEN = TOOLS / "gen-palette.py"
CHECK = TOOLS / "check-contrast.py"
TXT = TOOLS / "system-colors.txt"
THEMES = REPO / "themes"

DARK_THEMES = ["catppuccin", "everforest", "gruvbox", "kanagawa", "nord", "tokyo-night"]
LIGHT_THEMES_NUEVOS = ["rose-pine", "catppuccin-latte", "flexoki-light"]


def load_gen():
    """Carga tools/gen-palette.py como módulo fresco (el nombre tiene guion: no es importable).

    Fresco en cada llamada: los tests de sabotaje mutan ADAPTIVE_TOKENS/pick_text en memoria
    y no deben filtrarse a otros tests.
    """
    spec = importlib.util.spec_from_file_location("gen_palette_i26", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def theme_tomls() -> list[Path]:
    return sorted(THEMES.glob("*/theme.toml"))


def colors_xmls() -> list[Path]:
    return sorted((REPO / "overlay" / "themes").glob("*/*/res/values/colors.xml"))


def colors_xml_for(theme_id: str) -> Path:
    matches = list((REPO / "overlay" / "themes" / theme_id).glob("*/res/values/colors.xml"))
    assert len(matches) == 1, f"{theme_id}: se esperaba un único colors.xml, hay {matches}"
    return matches[0]


def color_names(xml: Path) -> list[str]:
    import re
    return re.findall(r'<color name="([^"]+)"', xml.read_text())


def light_theme_ids() -> list[str]:
    return sorted(
        t.parent.name for t in theme_tomls()
        if tomllib.loads(t.read_text()).get("mode") == "light"
    )


# --- C1 · los 3 temas light nuevos están trackeados ---------------------------

def test_i26_c1_tres_temas_light_versionados():
    for theme_id in LIGHT_THEMES_NUEVOS:
        toml = THEMES / theme_id / "theme.toml"
        assert toml.is_file(), f"falta {toml.relative_to(REPO)}"
        theme = tomllib.loads(toml.read_text())
        assert theme.get("mode") == "light", f"{theme_id}: mode != \"light\" ({theme.get('mode')!r})"
        for rel in (toml, colors_xml_for(theme_id)):
            out = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(rel)],
                capture_output=True, cwd=REPO, text=True,
            )
            assert out.returncode == 0, f"{rel.relative_to(REPO)}: NO trackeado por git"


def test_i26_c1_al_menos_tres_light_en_disco():
    ids = light_theme_ids()
    assert len(ids) >= 3, f"se esperaban >= 3 themes/*/theme.toml con mode=\"light\", hay {ids}"
    for theme_id in LIGHT_THEMES_NUEVOS:
        assert theme_id in ids, f"{theme_id} no aparece como mode=\"light\" en disco"


# --- C2 · los light pasan check-contrast.py -----------------------------------

def test_i26_c2_light_pasan_check_contrast():
    ids = light_theme_ids()
    tomls = [THEMES / i / "theme.toml" for i in ids]
    out = subprocess.run(
        [sys.executable, str(CHECK), *[str(t) for t in tomls]],
        capture_output=True, cwd=REPO, text=True,
    )
    assert out.returncode == 0, f"check-contrast.py falló sobre los light:\n{out.stdout}{out.stderr}"
    assert "FALLA" not in out.stdout, f"par por debajo de su umbral:\n{out.stdout}"


def test_i26_sabotaje_sin_pick_text_rompe_contraste():
    """Si ADAPTIVE_TOKENS devolviera theme[preferred] a secas (sin pick_text), algún on_* de
    un tema light quedaría por debajo de 4.5 contra su fondo real -> rojo.

    Monkeypatch de gp.pick_text en memoria sobre un módulo recién cargado; nunca toca
    tools/gen-palette.py en disco.
    """
    gp = load_gen()
    ids = light_theme_ids()
    assert ids, "no hay temas mode=\"light\" para sabotear"

    def sin_contraste(theme, preferred, bgs):
        return theme[preferred]

    gp.pick_text = sin_contraste
    bad = []
    for theme_id in ids:
        theme = tomllib.loads((THEMES / theme_id / "theme.toml").read_text())
        pal = gp.palette(theme)
        for name, (preferred, bg_token) in gp.ADAPTIVE_TOKENS.items():
            if gp.contrast(pal[name], pal[bg_token]) < 4.5:
                bad.append((theme_id, name))
    assert bad, (
        "sabotaje sin efecto esperado: sin pick_text, algún on_* de un tema light debía "
        "quedar por debajo de 4.5 contra su fondo"
    )


# --- Regresión · los 6 oscuros no cambian con ADAPTIVE_TOKENS nuevo -----------

def test_i26_seis_oscuros_colors_xml_identico_byte_a_byte():
    """Regenerar los 6 oscuros reproduce su colors.xml versionado byte a byte.

    design-26 Pieza 1 punto 6: si alguno cambiara, la preferida de ADAPTIVE_TOKENS no
    alcanzaba 4.5 hoy y no se debe «arreglar» cambiando la preferida: se reporta.
    """
    tomls = {t.parent.name: t for t in theme_tomls() if t.parent.name in DARK_THEMES}
    assert set(tomls) == set(DARK_THEMES), f"faltan oscuros: {set(DARK_THEMES) - set(tomls)}"
    for theme_id, toml in tomls.items():
        xml = colors_xml_for(theme_id)
        out = subprocess.run(
            [sys.executable, str(GEN), str(toml)], capture_output=True, cwd=REPO
        )
        assert out.returncode == 0, f"gen-palette.py {theme_id} falló: {out.stderr.decode()}"
        assert out.stdout == xml.read_bytes(), (
            f"{xml.relative_to(REPO)}: ADAPTIVE_TOKENS movió un byte de un tema oscuro"
        )


def test_i26_sabotaje_preferida_on_primary_container_dark_da_rojo():
    """Cambiar la preferida de system_on_primary_container_dark mueve el valor emitido para
    al menos un oscuro -> el test byte-a-byte de arriba se habría puesto rojo.

    design-26 Pieza 3 ejemplifica la mutación con "dark_background"; medido: para los 6
    oscuros, dark_background NO alcanza 4.5 contra system_primary_container_dark (es un fondo
    casi tan oscuro como el propio dark_background), así que pick_text cae al primer
    TEXT_CANDIDATES que sí pasa — "foreground" — y el resultado no cambia (el fallback hace su
    trabajo). Se usa en su lugar "bright_foreground", que en tokyo-night SÍ pasa 4.5 y difiere
    de "foreground": demuestra que la tabla importa y que el byte-a-byte de arriba lo detecta.

    Monkeypatch en memoria sobre un módulo recién cargado (gp.ADAPTIVE_TOKENS); nunca toca
    tools/gen-palette.py en disco.
    """
    gp = load_gen()
    name = "system_on_primary_container_dark"
    assert name in gp.ADAPTIVE_TOKENS, f"{name} ya no está en ADAPTIVE_TOKENS"
    _, bg_token = gp.ADAPTIVE_TOKENS[name]

    tomls = {t.parent.name: t for t in theme_tomls() if t.parent.name in DARK_THEMES}
    changed = []
    for theme_id, toml in tomls.items():
        theme = tomllib.loads(toml.read_text())
        base = gp.palette(theme)[name]

        gp.ADAPTIVE_TOKENS[name] = ("bright_foreground", bg_token)
        sabotaged = gp.palette(theme)[name]
        gp.ADAPTIVE_TOKENS[name] = ("foreground", bg_token)  # restaura la preferida real

        if sabotaged != base:
            changed.append(theme_id)

    assert changed, (
        "sabotaje sin efecto esperado: cambiar la preferida debía mover "
        f"{name} en al menos un tema oscuro"
    )


# --- C4 · nombres de cada colors.xml (x9) == tools/system-colors.txt, en orden -

def test_i26_c4_nombres_colors_xml_x9_en_orden():
    xmls = colors_xmls()
    assert len(xmls) >= 9, f"esperaba >= 9 colors.xml, hay {len(xmls)}"
    want = [ln for ln in TXT.read_text().splitlines() if ln.strip()]
    for xml in xmls:
        got = color_names(xml)
        assert got == want, (
            f"{xml.relative_to(REPO)}: nombres != tools/system-colors.txt en el mismo orden "
            f"(faltan={sorted(set(want) - set(got))} sobran={sorted(set(got) - set(want))})"
        )
