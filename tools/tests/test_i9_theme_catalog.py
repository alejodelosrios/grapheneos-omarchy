"""Tests de QA del issue #9 (design-9 «Gramática del parser (S1)»).

Criterio verificable SIN host de build ni Pixel:
  S1. Las regex TABLE/STRING/ARRAY/BLANK de ThemeCatalog.kt, extraídas del propio .kt y
      compiladas con `re`, reimplementan (en Python) exactamente la gramática que describe
      design-9: BLANK se ignora; la única tabla válida es `[android]` y sus claves pasan a
      `android.<k>`; una línea que no casa (o cualquier otra tabla) rechaza el tema; claves
      obligatorias name/mode(dark|light)/accent/background/foreground/android.palette_package;
      con claves duplicadas gana la última. Los 6 themes/*/theme.toml reales se aceptan y
      coinciden con lo que lee `tomllib` (name/mode/palette_package, y backgrounds de
      tokyo-night — la clave calificada que reconoce el array de wallpapers se extrae del
      propio .kt con `backgrounds_key_from`, no un literal fijo: vigila la regresión de
      e9d1c3b, donde el .kt comparaba `"backgrounds"` sin calificar y nunca capturaba el array
      anidado en `[android]`). Un set de rechazos fijo se rechaza.

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures,
stdlib). Cada test se vio en ROJO con su sabotaje (ver reporte de QA): los helpers reciben el
texto del .kt como parámetro (`regexes_from(text)`), así el sabotaje se hace en memoria, sin
tocar ThemeCatalog.kt en disco.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG_KT = REPO / "apps" / "OmarchyTheme" / "src" / "org" / "omarchy" / "theme" / "ThemeCatalog.kt"
THEMES = REPO / "themes"

REQUIRED = ["name", "mode", "accent", "background", "foreground", "android.palette_package"]

REGEX_NAMES = ("TABLE", "STRING", "ARRAY", "BLANK")


def regexes_from(text: str) -> dict[str, re.Pattern]:
    """Extrae las 4 regex `NAME = Regex(\"\"\"...\"\"\")` literales del texto del .kt.

    Falta alguna (p. ej. un sabotaje que renombra o borra una) ya es AssertionError: la
    gramática de S1 se apoya en las 4.
    """
    pattern = re.compile(r'(TABLE|STRING|ARRAY|BLANK)\s*=\s*Regex\("""(.*?)"""\)')
    found = dict(pattern.findall(text))
    missing = [n for n in REGEX_NAMES if n not in found]
    assert not missing, f"ThemeCatalog.kt: faltan las regex {missing} (patrón NAME = Regex(\"\"\"...\"\"\"))"
    return {name: re.compile(raw) for name, raw in found.items()}


def backgrounds_key_from(text: str) -> str:
    """Extrae del .kt la clave exacta que `parse` reconoce como el array de wallpapers.

    Sigue literalmente el código real (`if (key == "...") backgrounds = items`) en vez de un
    literal fijo en el test: si el .kt cambia la clave (como pasó en e9d1c3b, de "backgrounds"
    a "android.backgrounds"), este test la sigue sin que haya que tocarlo.
    """
    m = re.search(r'if\s*\(key\s*==\s*"([^"]+)"\)\s*backgrounds\s*=\s*items', text)
    assert m, (
        'ThemeCatalog.kt: no encuentro `if (key == "...") backgrounds = items` '
        "(¿cambió la forma de reconocer el array de backgrounds?)"
    )
    return m.group(1)


ARRAY_ITEM = re.compile(r'"([^"]*)"')


def parse(
    text: str,
    regexes: dict[str, re.Pattern],
    backgrounds_key: str = "android.backgrounds",
) -> dict[str, str] | None:
    """Reimplementación en Python de ThemeCatalog.parse, ejercitando las regex del .kt.

    `backgrounds_key` es la clave calificada que el .kt compara para capturar el array de
    wallpapers (ver `backgrounds_key_from`); por defecto la actual (`"android.backgrounds"`,
    post e9d1c3b), pero cada llamada real de los tests la pasa explícitamente extraída del .kt.
    """
    table_re, string_re, array_re, blank_re = (
        regexes["TABLE"], regexes["STRING"], regexes["ARRAY"], regexes["BLANK"],
    )
    values: dict[str, str] = {}
    table: str | None = None
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        if blank_re.fullmatch(line):
            continue
        m_table = table_re.fullmatch(line)
        m_string = string_re.fullmatch(line)
        m_array = array_re.fullmatch(line)
        if m_table is not None:
            t = m_table.group(1)
            if t != "android":
                return None
            table = t
        elif m_string is not None:
            key = m_string.group(1)
            qualified = f"{table}.{key}" if table is not None else key
            values[qualified] = m_string.group(2)
        elif m_array is not None:
            key = m_array.group(1)
            qualified = f"{table}.{key}" if table is not None else key
            items = ARRAY_ITEM.findall(m_array.group(2) or "")
            if qualified == backgrounds_key:
                values["__backgrounds_list__"] = items  # type: ignore[assignment]
        else:
            return None
    for key in REQUIRED:
        if key not in values:
            return None
    mode = values.get("mode")
    if mode not in ("dark", "light"):
        return None
    return values


def kt_regexes() -> dict[str, re.Pattern]:
    return regexes_from(CATALOG_KT.read_text())


def theme_tomls() -> list[Path]:
    return sorted(THEMES.glob("*/theme.toml"))


# --- las regex existen y se extraen del .kt -----------------------------------

def test_i9_s1_regexes_extraidas_del_kt():
    regexes = kt_regexes()
    assert set(regexes) == set(REGEX_NAMES)


# --- los 6 theme.toml reales se aceptan ---------------------------------------

def test_i9_s1_los_seis_theme_toml_se_aceptan():
    regexes = kt_regexes()
    tomls = theme_tomls()
    assert len(tomls) == 6, f"esperaba 6 themes/*/theme.toml, hay {len(tomls)}"
    for toml in tomls:
        text = toml.read_text()
        values = parse(text, regexes)
        assert values is not None, f"{toml.relative_to(REPO)}: el parser Python (regex del .kt) lo rechaza"
        upstream = tomllib.loads(text)
        assert values["name"] == upstream["name"], toml
        assert values["mode"] == upstream["mode"] == "dark", toml
        assert values["android.palette_package"] == upstream["android"]["palette_package"], toml
        # backgrounds se compara aparte en test_i9_s1_tokyo_night_backgrounds (clave calificada
        # "android.backgrounds", extraída del .kt con backgrounds_key_from).


def test_i9_s1_tokyo_night_backgrounds():
    """Theme.backgrounds debe reflejar el array `backgrounds` real de tokyo-night/theme.toml.

    Vigila la regresión de e9d1c3b: `backgrounds = [...]` está DENTRO de `[android]` en el
    .toml real, así que `qualify(table, key)` en ThemeCatalog.kt produce la clave calificada
    `"android.backgrounds"`; el fix hizo que `parse` compare contra esa clave calificada (antes
    comparaba contra el literal `"backgrounds"` sin calificar y nunca matcheaba — el bug que
    detectó esta misma prueba antes de e9d1c3b). La clave a comparar se EXTRAE del .kt con
    `backgrounds_key_from` (no un literal fijo en el test), así que si el .kt vuelve a cambiarla
    el test la sigue; solo el sabotaje de abajo la fija a mano para reproducir el bug original.
    """
    kt_text = CATALOG_KT.read_text()
    regexes = regexes_from(kt_text)
    key = backgrounds_key_from(kt_text)
    assert key == "android.backgrounds", f"clave de backgrounds inesperada: {key!r}"

    text = (THEMES / "tokyo-night" / "theme.toml").read_text()
    values = parse(text, regexes, backgrounds_key=key)
    assert values is not None
    upstream = tomllib.loads(text)
    upstream_backgrounds = upstream["android"]["backgrounds"]
    assert upstream_backgrounds == ["backgrounds/1-pagoda.jpg"], "fixture de partida cambió"
    assert values.get("__backgrounds_list__") == upstream_backgrounds, (
        f"ThemeCatalog.kt (clave {key!r}) no captura backgrounds: "
        f"parseado={values.get('__backgrounds_list__')!r}, toml={upstream_backgrounds!r}"
    )


def test_i9_s1_sabotaje_backgrounds_key_sin_calificar():
    """Reproduce el bug original (pre e9d1c3b): si el .kt vuelve a comparar contra el literal
    sin calificar `"backgrounds"` en vez de `"android.backgrounds"`, tokyo-night debe rechazar
    (backgrounds vacío) — deja `test_i9_s1_tokyo_night_backgrounds` en rojo de forma permanente
    si alguien reintroduce la regresión.
    """
    kt_text = CATALOG_KT.read_text()
    regexes = regexes_from(kt_text)
    good_key = backgrounds_key_from(kt_text)
    assert good_key == "android.backgrounds"

    sabotaged = kt_text.replace(
        'if (key == "android.backgrounds") backgrounds = items',
        'if (key == "backgrounds") backgrounds = items',
    )
    assert sabotaged != kt_text, "el sabotaje no encontró la línea a revertir"
    bad_key = backgrounds_key_from(sabotaged)
    assert bad_key == "backgrounds"

    text = (THEMES / "tokyo-night" / "theme.toml").read_text()
    values = parse(text, regexes, backgrounds_key=bad_key)
    assert values is not None
    assert values.get("__backgrounds_list__") is None, (
        "sabotaje sin efecto esperado: con la clave sin calificar, tokyo-night debía quedar "
        "sin backgrounds (reproduce el bug original)"
    )


# --- casos de rechazo fijos ----------------------------------------------------

RECHAZOS = {
    "numero_sin_comillas": 'name = "x"\nmode = "dark"\naccent = "x"\nbackground = "x"\n'
    'foreground = "x"\n[android]\npalette_package = "org.omarchy.palette.x"\nx = 1\n',
    "comilla_simple": "x = 'y'\n",
    "multilinea_triple": 'x = """a"""\n',
    "tabla_con_punto": "[a.b]\n",
    "tabla_no_android": (
        'name = "x"\nmode = "dark"\naccent = "x"\nbackground = "x"\nforeground = "x"\n'
        '[colors]\npalette_package = "org.omarchy.palette.x"\n'
    ),
    "mode_invalido": (
        'name = "x"\nmode = "sepia"\naccent = "x"\nbackground = "x"\nforeground = "x"\n'
        '[android]\npalette_package = "org.omarchy.palette.x"\n'
    ),
    "falta_palette_package": (
        'name = "x"\nmode = "dark"\naccent = "x"\nbackground = "x"\nforeground = "x"\n'
        '[android]\ntheme_style = "TONAL_SPOT"\n'
    ),
}


def test_i9_s1_casos_de_rechazo():
    regexes = kt_regexes()
    for caso, text in RECHAZOS.items():
        assert parse(text, regexes) is None, f"caso {caso!r} debía ser rechazado y no lo fue"


def test_i9_s1_clave_duplicada_gana_la_ultima():
    regexes = kt_regexes()
    text = (
        'name = "Primero"\nname = "Segundo"\nmode = "dark"\naccent = "x"\nbackground = "x"\n'
        'foreground = "x"\n[android]\npalette_package = "org.omarchy.palette.x"\n'
    )
    values = parse(text, regexes)
    assert values is not None
    assert values["name"] == "Segundo"


# --- demostración de que el test ejercita la regex STRING del .kt ------------

def test_i9_s1_sabotaje_regex_string_rompe_comentario_inline():
    """Documenta el sabotaje: quitar `(#.*)?` de STRING hace que la línea con comentario
    inline de nord (`theme_style = "TONAL_SPOT"   # ...`) dependa de que no haya texto tras
    la comilla de cierre. Sin el sufijo opcional de comentario, `fullmatch` falla sobre esa
    línea completa (los grupos exigen fin de línea inmediato tras la comilla).
    """
    good_text = CATALOG_KT.read_text()
    good = regexes_from(good_text)
    nord_text = (THEMES / "nord" / "theme.toml").read_text()
    assert parse(nord_text, good) is not None, "con la regex real, nord debe aceptarse"

    sabotaged_source = good_text.replace(
        'STRING = Regex("""^\\s*([A-Za-z0-9_]+)\\s*=\\s*"([^"]*)"\\s*(#.*)?$""")',
        'STRING = Regex("""^\\s*([A-Za-z0-9_]+)\\s*=\\s*"([^"]*)"$""")',
    )
    assert sabotaged_source != good_text, "el sabotaje no encontró la línea STRING a mutar"
    bad = regexes_from(sabotaged_source)
    assert parse(nord_text, bad) is None, (
        "sabotaje sin efecto: nord (con comentario inline en theme_style) debía rechazarse "
        "al quitar el sufijo opcional de comentario de STRING"
    )
