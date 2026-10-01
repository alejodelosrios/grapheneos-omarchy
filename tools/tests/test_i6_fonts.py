"""Tests de QA del issue #6 (design-6 «Cómo se verifica cada criterio», S1–S4 estáticos).

Criterios verificables SIN host de build ni Pixel:
  S1. fonts/OFL.txt presente; `git ls-files fonts` == 6 ficheros exactos y todos trackeados
      con `git ls-files --error-unmatch` (lección f2: entregable versionable siempre
      commiteado; el «= 5» del issue está corregido a 6 en design-6 §0.2).
  S2. `config_bodyFontFamily*` AUSENTES de overlay/OmarchyFontOverlay/res/values/config.xml
      (body = stock sans-serif: un RRO solo sombrea lo que lista) y headline* presentes con
      `jetbrains-mono-nerd` / `jetbrains-mono-nerd-medium` (nombres que existen como
      new-named-family en fonts/fonts_customization.xml).
  S3. Clave `font = "jetbrains-mono-nerd"` en la tabla [android] de los 6 themes/*/theme.toml
      + gen-palette.py regenera los 6 colors.xml byte a byte idénticos + la clave es INERTE
      (gen-palette.py no lee theme["android"]: la presencia/valor de `font` no altera el XML).
  S4. gate .swarm/gate.sh VERDE — se corre aparte (reporte de QA), no es test pytest.

Además (orden del PM): el scaffold que tools/new-theme.sh escribe en themes/<id>/theme.toml
nace con la clave `font = "jetbrains-mono-nerd"` en [android]. Se ejecuta SOLO el generador
del theme.toml (heredoc del propio script, extraído a tmp) con un colors.toml de fixture:
sin ejecutar el script end-to-end, sin red y sin tocar omarchy.mk ni overlay/. Ojo de
alcance: design-6 §4 declaraba tools/new-theme.sh fuera de alcance (hallazgo §6.1), pero el
commit 79b06f0 lo implementó y el PM exige que quede verificado.

Criterios D1–D3 (adb ls /product/fonts, cmd overlay lookup, captura + glifo \\uf303) exigen
dispositivo/flasheo: NO verificables aquí (al PR, «## No verificado sin host de build»).

Compatibles con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures).
Cada test se vio en ROJO con su sabotaje (ver reporte de QA).
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
THEMES = REPO / "themes"
GEN = REPO / "tools" / "gen-palette.py"
NEW_THEME = REPO / "tools" / "new-theme.sh"
FONT_CFG = REPO / "overlay" / "OmarchyFontOverlay" / "res" / "values" / "config.xml"
FONTS_DIR = REPO / "fonts"
CUSTOMIZATION = FONTS_DIR / "fonts_customization.xml"

MIN_TEMAS = 9  # design-26: 6 oscuros + >= 3 light, ya no un número fijo
FONT = "jetbrains-mono-nerd"
FONT_MEDIUM = "jetbrains-mono-nerd-medium"

# Los 6 entregables de fonts/ (S1: 3 TTF + OFL.txt + README.md + fonts_customization.xml)
FONTS_ESPERADOS = [
    "fonts/JetBrainsMonoNerdFont-Regular.ttf",
    "fonts/JetBrainsMonoNerdFont-Medium.ttf",
    "fonts/JetBrainsMonoNerdFont-Bold.ttf",
    "fonts/OFL.txt",
    "fonts/README.md",
    "fonts/fonts_customization.xml",
]

# Claves de colors.toml upstream que new-theme.sh valida/copía (26: mode + 25 colores).
UPSTREAM_KEYS = {
    "mode", "accent", "selection", "muted", "background", "dark_background",
    "darker_background", "lighter_background", "foreground", "dark_foreground",
    "light_foreground", "bright_foreground", "red", "yellow", "orange", "green",
    "cyan", "blue", "magenta", "brown", "bright_red", "bright_yellow",
    "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
}


def load_gen():
    """Carga tools/gen-palette.py como módulo (el nombre tiene guion: no es importable)."""
    spec = importlib.util.spec_from_file_location("gen_palette_i6", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def theme_tomls() -> list[Path]:
    return sorted(THEMES.glob("*/theme.toml"))


def colors_xmls() -> list[Path]:
    return sorted((REPO / "overlay" / "themes").glob("*/*/res/values/colors.xml"))


def palette_de(gp, theme: dict) -> dict:
    """gp.palette() con SystemExit convertido en AssertionError (vacío/usage no es éxito)."""
    try:
        return gp.palette(theme)
    except SystemExit as e:
        raise AssertionError(f"gen-palette.py abortó sobre el theme.toml: {e}")


def git_porcelain(*paths: str) -> str:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        capture_output=True, cwd=REPO, text=True,
    )
    assert out.returncode == 0, f"git status falló: {out.stderr}"
    return out.stdout


# --- S3 · clave font en los 6 theme.toml --------------------------------------

def test_criterio_s3_font_en_los_seis_theme_toml():
    """Cada themes/*/theme.toml tiene `font = "jetbrains-mono-nerd"` en la tabla [android].

    Orden del PM / design-6 §0.3 y §2 fila 5. La clave es declarativa para OmarchyTheme (#9).
    """
    tomls = theme_tomls()
    assert len(tomls) >= MIN_TEMAS, f"esperaba >= {MIN_TEMAS} themes/*/theme.toml, hay {len(tomls)}"
    for toml in tomls:
        theme = tomllib.loads(toml.read_text())
        android = theme.get("android")
        assert isinstance(android, dict), f"{toml.relative_to(REPO)}: falta la tabla [android]"
        assert "font" in android, f"{toml.relative_to(REPO)}: [android] nace sin la clave font"
        assert android["font"] == FONT, (
            f"{toml.relative_to(REPO)}: font={android['font']!r}, se espera {FONT!r}"
        )


# --- S3 · paletas regeneradas byte a byte + clave inerte ----------------------

def test_criterio_s3_paletas_regeneradas_identicas():
    """gen-palette.py sobre cada theme.toml reproduce el colors.xml versionado byte a byte.

    Extiende el patrón test_i8_palette_tokens.py (criterio 2) al criterio S3 de #6: la clave
    `font` no debe mover ni un byte del XML. «Vacío no es éxito»: exige exactamente 6 pares.
    """
    tomls = {t.parent.name: t for t in theme_tomls()}
    xmls = colors_xmls()
    assert len(xmls) >= MIN_TEMAS, f"esperaba >= {MIN_TEMAS} colors.xml, hay {len(xmls)}"
    assert len(tomls) >= MIN_TEMAS, f"esperaba >= {MIN_TEMAS} theme.toml, hay {len(tomls)}"
    for xml in xmls:
        tid = xml.relative_to(REPO / "overlay" / "themes").parts[0]
        assert tid in tomls, f"{xml.relative_to(REPO)}: sin themes/{tid}/theme.toml"
        out = subprocess.run(
            [sys.executable, str(GEN), str(tomls[tid])], capture_output=True, cwd=REPO
        )
        assert out.returncode == 0, (
            f"gen-palette.py {tomls[tid].relative_to(REPO)} falló: {out.stderr.decode()}"
        )
        assert out.stdout == xml.read_bytes(), (
            f"{xml.relative_to(REPO)} no es byte a byte lo que genera gen-palette.py "
            f"sobre {tomls[tid].relative_to(REPO)}"
        )


def test_criterio_s3_clave_font_inerte_para_paletas():
    """theme["android"] no entra en la paleta: quitarlo o mutar `font` deja el XML idéntico.

    La inercia es la prueba de que la clave es declarativa (design-6 §2 fila 5: «Inerte para
    paletas: tools/gen-palette.py nunca lee theme["android"]»).
    """
    gp = load_gen()
    tomls = theme_tomls()
    assert len(tomls) >= MIN_TEMAS, f"esperaba >= {MIN_TEMAS} temas, hay {len(tomls)}"
    for toml in tomls:
        theme = tomllib.loads(toml.read_text())
        base = palette_de(gp, theme)
        sin_android = {k: v for k, v in theme.items() if k != "android"}
        assert palette_de(gp, sin_android) == base, (
            f"{toml.relative_to(REPO)}: la tabla [android] altera la paleta (clave NO inerte)"
        )
        mutado = dict(theme)
        mutado["android"] = {**theme.get("android", {}), "font": "otra-fuente", "zzz": "x"}
        assert palette_de(gp, mutado) == base, (
            f"{toml.relative_to(REPO)}: mutar [android].font altera la paleta (clave NO inerte)"
        )
        assert gp.to_xml(base).encode() == gp.to_xml(palette_de(gp, sin_android)).encode()


# --- S2 · body ausente, headline presentes ------------------------------------

def test_criterio_s2_body_ausente_headline_presentes():
    """config_bodyFontFamily* ausentes (body = stock) y headline* -> jetbrains-mono-nerd*.

    Un RRO solo sombrea lo que lista: sin overrides de body, el framework usa el stock
    sans-serif (rama 17). Los nombres de familia deben existir en fonts/fonts_customization.xml.
    """
    text = FONT_CFG.read_text()
    assert "config_bodyFontFamily" not in text, (
        f"{FONT_CFG.relative_to(REPO)} lista config_bodyFontFamily*: sombrea body y no debe "
        "(design-6 §0.1: body = sans-serif stock, sin overrides)"
    )
    m_head = re.search(r'<string name="config_headlineFontFamily"[^>]*>([^<]+)</string>', text)
    m_med = re.search(r'<string name="config_headlineFontFamilyMedium"[^>]*>([^<]+)</string>', text)
    assert m_head, f"{FONT_CFG.relative_to(REPO)}: falta config_headlineFontFamily"
    assert m_med, f"{FONT_CFG.relative_to(REPO)}: falta config_headlineFontFamilyMedium"
    assert m_head.group(1) == FONT, f"headline={m_head.group(1)!r}, se espera {FONT!r}"
    assert m_med.group(1) == FONT_MEDIUM, f"headlineMedium={m_med.group(1)!r}, se espera {FONT_MEDIUM!r}"
    custom = CUSTOMIZATION.read_text()
    for fam in (FONT, FONT_MEDIUM):
        assert f'customizationType="new-named-family" name="{fam}"' in custom, (
            f"{CUSTOMIZATION.relative_to(REPO)}: la familia {fam!r} no existe como "
            "new-named-family (el overlay apuntaría a una familia inexistente)"
        )


# --- S1 · los 6 ficheros de fonts/ versionados --------------------------------

def test_criterio_s1_fonts_versionados():
    """Los 6 entregables de fonts/ existen y están trackeados (git ls-files --error-unmatch).

    Lección f2: un entregable versionable sin commitear construye un /product/fonts/ a medias
    en un clon limpio sin que nada se ponga rojo. S1 exige además `git ls-files fonts` == 6
    exactos (corrección del «= 5» del issue: fonts_customization.xml ya versionado).
    """
    for rel in FONTS_ESPERADOS:
        assert (REPO / rel).is_file(), f"falta {rel} en disco"
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            capture_output=True, cwd=REPO, text=True,
        )
        assert out.returncode == 0, (
            f"{rel}: NO trackeado por git (lección f2: entregable versionable siempre "
            f"commiteado) — {out.stderr.strip()}"
        )
    ls = subprocess.run(
        ["git", "ls-files", "--", "fonts"], capture_output=True, cwd=REPO, text=True
    )
    assert ls.returncode == 0, f"git ls-files fonts falló: {ls.stderr}"
    got = sorted(ln for ln in ls.stdout.splitlines() if ln.strip())
    assert got == sorted(FONTS_ESPERADOS), (
        f"git ls-files fonts | wc -l = {len(got)} (S1 exige 6 exactos): "
        f"faltan={sorted(set(FONTS_ESPERADOS) - set(got))} "
        f"sobran={sorted(set(got) - set(FONTS_ESPERADOS))}"
    )
    assert (FONTS_DIR / "OFL.txt").stat().st_size > 0, "fonts/OFL.txt está vacío"
    assert (FONTS_DIR / "README.md").stat().st_size > 0, "fonts/README.md está vacío"


# --- Scaffold de tools/new-theme.sh nace con font -----------------------------

def scaffold_writer() -> str:
    """Extrae el heredoc de tools/new-theme.sh que escribe themes/<id>/theme.toml.

    Es literalmente el código que el script ejecuta para el scaffold (sin el paso de curl ni
    los editores de omarchy.mk/overlay/config/config.xml): se corre aislado en tmp.
    """
    script = NEW_THEME.read_text()
    m = re.search(
        r"""python3 - [^\n]*"themes/\$id/theme\.toml"[^\n]*<<'PY'\n(.*?)\nPY\n""",
        script, re.S,
    )
    assert m, (
        "tools/new-theme.sh: no encuentro el generador de themes/<id>/theme.toml "
        "(heredoc python3 … <<'PY') — ¿cambió el script y el scaffold ya no es testeable?"
    )
    return m.group(1)


def test_criterio_s4_scaffold_new_theme_nace_con_font():
    """El theme.toml que genera tools/new-theme.sh lleva `font` en [android], en tmp.

    Sin ejecutar el script end-to-end (sin curl, sin RRO, sin omarchy.mk): se ejecuta solo el
    generador del scaffold con un colors.toml de fixture que además trae `font`/`backgrounds`
    upstream (deben filtrarse: el font va fijo, #6). Y no se toca omarchy.mk ni overlay/.
    """
    src = tomllib.loads((THEMES / "tokyo-night" / "theme.toml").read_text())
    faltan = sorted(UPSTREAM_KEYS - set(src))
    assert not faltan, f"themes/tokyo-night/theme.toml le faltan claves upstream: {faltan}"
    body = scaffold_writer()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        raw = tmp / "colors.toml"
        lineas = [
            'name = "Demo Upstream"',
            'font = "upstream-font-debe-filtrarse"',
            'backgrounds = ["a.png"]',
        ]
        lineas += [f'{k} = "{src[k]}"' for k in sorted(UPSTREAM_KEYS)]
        raw.write_text("\n".join(lineas) + "\n")
        gen = tmp / "gen_theme.py"
        gen.write_text(body)
        out = tmp / "themes" / "demo" / "theme.toml"
        out.parent.mkdir(parents=True)
        antes = git_porcelain("omarchy.mk", "overlay")
        r = subprocess.run(
            [sys.executable, str(gen), str(raw), str(out), "Demo", "org.omarchy.palette.demo"],
            capture_output=True, text=True, cwd=REPO,
        )
        assert r.returncode == 0, f"el generador de scaffold falló: {r.stderr}"
        assert git_porcelain("omarchy.mk", "overlay") == antes, (
            "generar el scaffold tocó omarchy.mk u overlay/ (prohibido por la orden)"
        )
        assert out.is_file(), "el scaffold no escribió themes/<id>/theme.toml en tmp"
        d = tomllib.loads(out.read_text())
        android = d.get("android")
        assert isinstance(android, dict), "el scaffold nace sin tabla [android]"
        assert "font" in android, "el scaffold de new-theme.sh nace SIN la clave font (#6)"
        assert android["font"] == FONT, f"scaffold: font={android['font']!r}, se espera {FONT!r}"
        assert android.get("palette_package") == "org.omarchy.palette.demo"
        assert android.get("theme_style") == "TONAL_SPOT"
        assert "font" not in d, "el font de upstream debe filtrarse (va fijo en [android], #6)"
        assert "backgrounds" not in d, "backgrounds de upstream debe filtrarse (#7)"
        assert d.get("name") == "Demo Upstream", "name de upstream debe preservarse"
        assert set(d) - {"name", "android"} == UPSTREAM_KEYS, (
            f"claves del scaffold: {sorted(set(d) - {'name', 'android'})}"
        )
