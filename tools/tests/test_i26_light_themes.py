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

Ronda 2 (audit-26 H1, fix en 02dccf5/2d95a92/57f421b): on_<rol>_fixed (primary/secondary/
tertiary, sin _variant) tiene DOS fondos en M3 (ColorSpec2021.java:763-771) — <rol>_fixed y
<rol>_fixed_dim —, no solo el homónimo. `ADAPTIVE_TOKENS` ahora es `name -> (preferida, tupla
de tokens-fondo)` y `check-contrast.py:backgrounds_for` devuelve esa misma tupla para
on_X_fixed. Guardián + sabotajes de esta regresión en la sección «H1» más abajo.

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures).
Cada test se vio en ROJO con su sabotaje (ver reporte de QA): el sabotaje de la tabla
ADAPTIVE_TOKENS, de pick_text y de check-contrast.backgrounds_for ocurre en memoria sobre el
módulo cargado (nunca se edita tools/gen-palette.py ni tools/check-contrast.py en disco).
"""
from __future__ import annotations

import importlib.util
import re
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
    return re.findall(r'<color name="([^"]+)"', xml.read_text())


def xml_colors(xml: Path) -> dict[str, str]:
    """name -> #rrggbb de un colors.xml versionado (sin pasar por gen-palette.py)."""
    return dict(re.findall(r'<color name="([^"]+)">(#[0-9a-fA-F]{6})</color>', xml.read_text()))


def load_check():
    """Carga tools/check-contrast.py como módulo fresco (incluye su load_gen() propio)."""
    spec = importlib.util.spec_from_file_location("check_contrast_i26", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        for name, (preferred, bg_tokens) in gp.ADAPTIVE_TOKENS.items():
            if any(gp.contrast(pal[name], pal[bg_token]) < 4.5 for bg_token in bg_tokens):
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

    N1 (audit-26, ronda 3): no basta con que el valor en memoria cambie — hay que probar que
    el `colors.xml` que saldría del generador sabotaged realmente difiere del versionado
    (`to_xml`, mismo formato que emite `tools/gen-palette.py` por stdout), que es lo que el
    test byte-a-byte de arriba compara de verdad.

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
        base_xml = gp.to_xml(gp.palette(theme)).encode()
        versioned_xml = colors_xml_for(theme_id).read_bytes()
        assert base_xml == versioned_xml, (
            f"{theme_id}: sin sabotear, el generador ya difiere del colors.xml versionado "
            "(el fixture de este test no sirve de línea base)"
        )

        gp.ADAPTIVE_TOKENS[name] = ("bright_foreground", bg_token)
        sabotaged_xml = gp.to_xml(gp.palette(theme)).encode()
        gp.ADAPTIVE_TOKENS[name] = ("foreground", bg_token)  # restaura la preferida real

        if sabotaged_xml != versioned_xml:
            changed.append(theme_id)

    assert changed, (
        "sabotaje sin efecto esperado: cambiar la preferida debía hacer que el colors.xml "
        f"regenerado difiriera del versionado en al menos un tema oscuro (N1: byte a byte, "
        "no solo en memoria)"
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


# --- H1/H2 (rondas 2-3) · on_<rol>_fixed[_variant] mide contra *_fixed Y *_fixed_dim --

FIXED_ROLES = ("primary", "secondary", "tertiary")
# H1 (ronda 2): on_<rol>_fixed. H2 (ronda 3, audit-26 rechazo, fix b24e1e4/41f709f):
# on_<rol>_fixed_variant tiene los MISMOS dos fondos (ColorSpec2021.java:763-771 —
# setBackground(<rol>FixedDim()) + setSecondBackground(<rol>Fixed()) para ambos, _fixed y
# _fixed_variant); solo difiere el orden en ADAPTIVE_TOKENS (no afecta el resultado: pick_text
# exige "ok" contra TODOS los fondos de la tupla). Un guardián parametrizado por sufijo cubre
# las dos filas sin duplicar el cuerpo del test.
FIXED_SUFFIXES = ("_fixed", "_fixed_variant")


def test_i26_h1_on_fixed_mide_contra_fixed_y_fixed_dim():
    """Guardián de audit-26 H1/H2: para cada tema (x9, colors.xml versionado), cada rol
    primary/secondary/tertiary y cada sufijo _fixed/_fixed_variant, system_on_<rol><sufijo>
    contrasta >= 4.5 contra system_<rol>_fixed Y contra system_<rol>_fixed_dim
    (ColorSpec2021.java:763-771: el texto fixed se lee sobre AMBOS, no solo sobre su homónimo,
    y la regla es la misma para la variante «dim» del texto).
    """
    gp = load_gen()
    for toml in theme_tomls():
        theme_id = toml.parent.name
        colors = xml_colors(colors_xml_for(theme_id))
        for rol in FIXED_ROLES:
            for suffix in FIXED_SUFFIXES:
                onf = colors[f"system_on_{rol}{suffix}"]
                for bg_name in (f"system_{rol}_fixed", f"system_{rol}_fixed_dim"):
                    ratio = gp.contrast(onf, colors[bg_name])
                    assert ratio >= 4.5, (
                        f"{theme_id}: system_on_{rol}{suffix}={onf} vs {bg_name}={colors[bg_name]}: "
                        f"{ratio:.2f} < 4.5 (H1/H2)"
                    )


def test_i26_h1_backgrounds_for_incluye_fixed_dim():
    cc = load_check()
    for rol in FIXED_ROLES:
        for suffix in FIXED_SUFFIXES:
            name = f"system_on_{rol}{suffix}"
            bgs = cc.backgrounds_for(name)
            assert f"system_{rol}_fixed_dim" in bgs, (
                f"check-contrast.backgrounds_for({name}) perdió system_{rol}_fixed_dim: {bgs}"
            )
            assert f"system_{rol}_fixed" in bgs, (
                f"check-contrast.backgrounds_for({name}) perdió system_{rol}_fixed: {bgs}"
            )


def test_i26_h1_sabotaje_adaptive_tokens_sin_fixed_dim_da_rojo():
    """Quitar system_<rol>_fixed_dim de la tupla-fondo de on_<rol>_fixed en ADAPTIVE_TOKENS
    (las 3 filas _fixed, no _fixed_variant) deja a pick_text sin ese fondo que cumplir: en
    rose-pine, el on_<rol>_fixed resultante cae por debajo de 4.5 contra *_fixed_dim -> rojo.

    Monkeypatch en memoria sobre un módulo recién cargado; nunca toca tools/gen-palette.py.
    """
    gp = load_gen()
    for rol in FIXED_ROLES:
        name = f"system_on_{rol}_fixed"
        preferred, bg_tokens = gp.ADAPTIVE_TOKENS[name]
        assert f"system_{rol}_fixed_dim" in bg_tokens, f"{name}: ya no tenía fixed_dim que quitar"
        gp.ADAPTIVE_TOKENS[name] = (preferred, (f"system_{rol}_fixed",))  # sabotaje: solo el homónimo

    theme = tomllib.loads((THEMES / "rose-pine" / "theme.toml").read_text())
    pal = gp.palette(theme)
    bad = []
    for rol in FIXED_ROLES:
        name = f"system_on_{rol}_fixed"
        dim = pal[f"system_{rol}_fixed_dim"]
        if gp.contrast(pal[name], dim) < 4.5:
            bad.append(rol)
    assert bad, (
        "sabotaje sin efecto esperado: sin fixed_dim en ADAPTIVE_TOKENS, rose-pine debía dar "
        "algún on_*_fixed < 4.5 contra *_fixed_dim"
    )


def test_i26_h2_sabotaje_adaptive_tokens_fixed_variant_sin_fixed_da_rojo():
    """H2: quitar system_<rol>_fixed (el homónimo, no el _dim) de la tupla-fondo de
    on_<rol>_fixed_variant en ADAPTIVE_TOKENS deja a pick_text sin ese segundo fondo que
    cumplir -> el test de coincidencia de 20 filas (más abajo) debe notar la divergencia.

    Monkeypatch en memoria sobre un módulo recién cargado; nunca toca tools/gen-palette.py.
    """
    gp = load_gen()
    cc = load_check()
    divergentes = []
    for rol in FIXED_ROLES:
        name = f"system_on_{rol}_fixed_variant"
        preferred, bg_tokens = gp.ADAPTIVE_TOKENS[name]
        assert f"system_{rol}_fixed" in bg_tokens, f"{name}: ya no tenía system_{rol}_fixed que quitar"
        gp.ADAPTIVE_TOKENS[name] = (preferred, (f"system_{rol}_fixed_dim",))  # sabotaje: solo el dim
        if list(gp.ADAPTIVE_TOKENS[name][1]) != cc.backgrounds_for(name):
            divergentes.append(name)
    assert divergentes == [f"system_on_{r}_fixed_variant" for r in FIXED_ROLES], (
        f"sabotaje sin efecto esperado: las 3 filas _fixed_variant debían divergir de "
        f"backgrounds_for, divergentes={divergentes}"
    )


def test_i26_h1_sabotaje_backgrounds_for_regla_vieja_pierde_el_par():
    """Si check-contrast.backgrounds_for volviera a la regla vieja (on_<rol>_fixed solo
    empareja con su homónimo, y on_<rol>_fixed_variant solo con *_fixed_dim), el guardián
    basado en PAIRS perdería justo los pares que detectaron H1 (on_<rol>_fixed vs
    <rol>_fixed_dim) y H2 (on_<rol>_fixed_variant vs <rol>_fixed) para los 3 roles -> la
    regresión pasaría en silencio. Se demuestra reconstruyendo los PAIRS derivados con la
    regla vieja monkeypatcheada y comprobando que esos 6 pares desaparecen.

    Monkeypatch en memoria sobre un módulo recién cargado; nunca toca tools/check-contrast.py.
    """
    cc = load_check()
    original = cc.backgrounds_for

    def regla_vieja(name):
        if name.startswith("system_on_") and name.endswith("_fixed_variant"):
            base = name[len("system_on_"):-len("_fixed_variant")]
            return ["system_" + base + "_fixed_dim"]
        if name.endswith("_fixed") and not name.endswith("_fixed_variant") and name.startswith("system_on_"):
            return [name.replace("system_on_", "system_")]
        return original(name)

    pairs_nuevos = set(cc.derive_pairs(cc.NAMES))
    cc.backgrounds_for = regla_vieja
    pairs_viejos = set(cc.derive_pairs(cc.NAMES))

    perdidos_h1 = {
        (fg, bg, kind) for (fg, bg, kind) in pairs_nuevos - pairs_viejos
        if fg.endswith("_fixed") and not fg.endswith("_fixed_variant") and bg.endswith("_fixed_dim")
    }
    perdidos_h2 = {
        (fg, bg, kind) for (fg, bg, kind) in pairs_nuevos - pairs_viejos
        if fg.endswith("_fixed_variant") and bg.endswith("_fixed") and not bg.endswith("_fixed_dim")
    }
    assert perdidos_h1, (
        "sabotaje sin efecto esperado (H1): la regla vieja debía perder on_<rol>_fixed vs "
        "<rol>_fixed_dim para los 3 roles"
    )
    assert perdidos_h2, (
        "sabotaje sin efecto esperado (H2): la regla vieja debía perder on_<rol>_fixed_variant "
        "vs <rol>_fixed para los 3 roles"
    )
    assert {p[0] for p in perdidos_h1} == {f"system_on_{r}_fixed" for r in FIXED_ROLES}
    assert {p[0] for p in perdidos_h2} == {f"system_on_{r}_fixed_variant" for r in FIXED_ROLES}


# --- ADAPTIVE_TOKENS == check-contrast.backgrounds_for (las 20 filas) --------

def test_i26_adaptive_tokens_coincide_con_backgrounds_for():
    """Cada fila de gen-palette.ADAPTIVE_TOKENS tiene exactamente los fondos que
    check-contrast.backgrounds_for calcula para ese mismo nombre — las dos tablas no deben
    poder divergir en silencio (es justo lo que ocultó H1 en la ronda 1)."""
    gp = load_gen()
    cc = load_check()
    assert len(gp.ADAPTIVE_TOKENS) == 20, f"se esperaban 20 filas, hay {len(gp.ADAPTIVE_TOKENS)}"
    for name, (preferred, bg_tokens) in gp.ADAPTIVE_TOKENS.items():
        want = cc.backgrounds_for(name)
        assert list(bg_tokens) == want, (
            f"{name}: ADAPTIVE_TOKENS trae {list(bg_tokens)} pero backgrounds_for trae {want}"
        )


def test_i26_sabotaje_adaptive_tokens_diverge_de_backgrounds_for_da_rojo():
    """Si una fila de ADAPTIVE_TOKENS se desincroniza de backgrounds_for (p. ej. reordenada o
    con un fondo de menos), el test de arriba debe notarlo -> rojo.

    Monkeypatch en memoria sobre un módulo recién cargado; nunca toca tools/gen-palette.py.
    """
    gp = load_gen()
    cc = load_check()
    name = "system_on_primary_fixed"
    preferred, bg_tokens = gp.ADAPTIVE_TOKENS[name]
    gp.ADAPTIVE_TOKENS[name] = (preferred, bg_tokens[:1])  # sabotaje: quita system_primary_fixed_dim

    divergentes = [
        n for n, (p, bgs) in gp.ADAPTIVE_TOKENS.items() if list(bgs) != cc.backgrounds_for(n)
    ]
    assert divergentes == [name], (
        f"sabotaje sin efecto esperado: {name} debía quedar como única fila divergente, "
        f"divergentes={divergentes}"
    )
