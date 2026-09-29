"""Tests de QA del issue #8 (design-8 «Cómo se verifica cada criterio», criterios 1–3).

Criterios verificables SIN host de build ni Pixel:
  1. self-check de tools/gen-palette.py + wc -l tools/system-colors.txt == 194 (D2).
  2. Nombres de cada overlay/themes/*/*/res/values/colors.xml == tools/system-colors.txt
     (y, más fuerte, identidad byte a byte con el generador = gate `palette`).
   3. tools/check-contrast.py → todos los pares texto/fondo derivados de
      tools/system-colors.txt superan su umbral (4.5 texto / 3.0 icono / exento el texto
      inactivo; derivación automática desde R5, clase cerrada tras audit-8 H2/H5/H6).

Criterios 4 (settings put + captura) y 5 (m OmarchyPalette*) exigen host de build / Pixel:
NO verificables aquí (al PR, `## No verificado sin host de build`).

Compatibles con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures).
Cada test se vio en ROJO con su sabotaje (ver reporte de QA / PR).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
GEN = TOOLS / "gen-palette.py"
TXT = TOOLS / "system-colors.txt"
CHECK = TOOLS / "check-contrast.py"
N_TOKES = 194  # D2: 65 rampa clásica + 13 system_error_* + 116 tokens A14+


def load_gen():
    """Carga tools/gen-palette.py como módulo (el nombre tiene guion: no es importable)."""
    spec = importlib.util.spec_from_file_location("gen_palette_i8", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def theme_tomls() -> list[Path]:
    return sorted((REPO / "themes").glob("*/theme.toml"))


def colors_xmls() -> list[Path]:
    return sorted((REPO / "overlay" / "themes").glob("*/*/res/values/colors.xml"))


def color_names(xml: Path) -> list[str]:
    return re.findall(r'<color name="([^"]+)"', xml.read_text())


# --- Criterio 1 ---------------------------------------------------------------

def test_criterio1_selfcheck_pasa_sin_args():
    """`python3 tools/gen-palette.py` (sin args) ejecuta el self-check sin AssertionError.

    Matiz conocido (reportado al PM): sin args el proceso termina con exit=1 porque tras el
    self-check hace `sys.exit(__doc__)` (usage). El criterio exige que el self-check pase, no
    el exit code de la CLI.
    """
    argv = sys.argv
    sys.argv = ["tools/gen-palette.py"]  # literalmente sin args
    try:
        try:
            runpy.run_path(str(GEN), run_name="__main__")
            raised = None
        except AssertionError as e:
            raise AssertionError(f"self-check del generador FALLA: {e}")
        except SystemExit as e:
            raised = e
    finally:
        sys.argv = argv
    assert isinstance(raised, SystemExit), "sin args debe terminar en SystemExit (usage)"


def test_criterio1_system_colors_txt_194():
    """wc -l tools/system-colors.txt == 194 (D2 corrige el >= 201 del issue), único y ordenado."""
    lines = [ln for ln in TXT.read_text().splitlines() if ln.strip()]
    assert len(lines) == N_TOKES, f"esperaba {N_TOKES} tokens, hay {len(lines)}"
    assert len(set(lines)) == N_TOKES, "tokens duplicados en tools/system-colors.txt"
    assert all(ln.startswith("system_") for ln in lines), "todo token debe ser system_*"
    assert lines == sorted(lines), "tools/system-colors.txt debe venir de sort -u"


# --- Criterio 2 ---------------------------------------------------------------

def test_criterio2_nombres_xml_igual_txt():
    """Nombres de cada colors.xml == tools/system-colors.txt, por tema.

    Comando documentado del criterio 2 (un solo comando por tema, diff vacío = ok):

        for t in themes/*/theme.toml; do id=$(basename "$(dirname "$t")") \\
          diff <(sed -n 's/.*<color name="\\([^"]*\\)".*/\\1/p' \\
                overlay/themes/"$id"/*/res/values/colors.xml) tools/system-colors.txt; done
    """
    xmls = colors_xmls()
    assert xmls, "no hay overlay/themes/*/*/res/values/colors.xml"
    assert len(xmls) >= len(theme_tomls()), (
        f"{len(xmls)} colors.xml para {len(theme_tomls())} temas (faltan RROs generados)"
    )
    want = [ln for ln in TXT.read_text().splitlines() if ln.strip()]
    for xml in xmls:
        got = color_names(xml)
        assert got == want, (
            f"{xml.relative_to(REPO)}: nombres != tools/system-colors.txt "
            f"(faltan={sorted(set(want) - set(got))} sobran={sorted(set(got) - set(want))})"
        )


def test_criterio2_colors_xml_identico_al_generador():
    """Cada colors.xml es byte a byte lo que genera tools/gen-palette.py (gate `palette`).

    «Vacío no es éxito»: exige un colors.xml por theme.toml, no solo iterar lo que haya.
    """
    tomls = {t.parent.name: t for t in theme_tomls()}
    xmls = colors_xmls()
    assert xmls, "no hay overlay/themes/*/*/res/values/colors.xml que comparar"
    assert len(xmls) >= len(tomls), f"{len(xmls)} colors.xml para {len(tomls)} temas"
    for xml in xmls:
        tid = xml.relative_to(REPO / "overlay" / "themes").parts[0]  # overlay/themes/<id>/<Módulo>/...
        assert tid in tomls, f"{xml.relative_to(REPO)}: no hay themes/{tid}/theme.toml"
        toml = tomls[tid]
        out = subprocess.run(
            [sys.executable, str(GEN), str(toml)], capture_output=True, cwd=REPO
        )
        assert out.returncode == 0, f"gen-palette.py {toml.name} falló: {out.stderr.decode()}"
        assert out.stdout == xml.read_bytes(), (
            f"{xml.relative_to(REPO)} no es lo que genera gen-palette.py "
            f"{toml.relative_to(REPO)} (hex alterado o a mano)"
        )


def test_criterio2_cobertura_100_por_tema():
    """Cada theme.toml produce exactamente los 194 tokens de system-colors.txt (sin más)."""
    gp = load_gen()
    want = set(TXT.read_text().split())
    for toml in theme_tomls():
        theme = tomllib.loads(toml.read_text())
        try:
            pal = gp.palette(theme)  # sys.exit() si la cobertura no es 100%
        except SystemExit as e:
            raise AssertionError(f"cobertura != 100% en {toml.relative_to(REPO)}: {e}")
        assert set(pal) == want, (
            f"{toml.relative_to(REPO)}: faltan={sorted(want - set(pal))} "
            f"sobran={sorted(set(pal) - want)}"
        )
        assert len(pal) == N_TOKES


# --- Criterio 3 ---------------------------------------------------------------

def test_criterio3_contraste_min_4_5():
    """tools/check-contrast.py → exit 0 y todas las medidas presentes, ninguna FALLA.

    Actualizado en R5 (clase cerrada): los pares ya no son una lista manual sino que se
    derivan de tools/system-colors.txt (texto/icono contra su fondo homónimo; 4.5 texto,
    3.0 icono, exento el texto inactivo). El recuento sigue derivándose del módulo
    (len(cc.PAIRS)); ahora cuenta líneas medidas (« vs ») en vez de «OK (>= 4.5)», porque
    el formato nuevo imprime umbrales distintos y líneas «exento».
    """
    tomls = theme_tomls()
    assert len(tomls) == 6, f"esperaba 6 temas, hay {len(tomls)}"
    spec = importlib.util.spec_from_file_location("check_contrast_i8", CHECK)
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)
    out = subprocess.run(
        [sys.executable, str(CHECK), *[str(t) for t in tomls]],
        capture_output=True, cwd=REPO, text=True,
    )
    assert out.returncode == 0, f"check-contrast falló:\n{out.stdout}{out.stderr}"
    assert "FALLA" not in out.stdout, f"par por debajo de su umbral:\n{out.stdout}"
    n_expected = len(cc.PAIRS) * len(tomls)
    assert out.stdout.count(" vs ") == n_expected, (
        f"esperaba {n_expected} medidas:\n{out.stdout}"
    )


# --- Reglas del generador (tonos + determinismo) -------------------------------

def test_tonos_base_y_determinismo():
    """tone(0)=blanco, tone(1000)=negro, tone(500)=base; y dos corridas idénticas."""
    gp = load_gen()
    assert gp.tone(gp.hex2rgb("#7aa2f7"), 0) == (255, 255, 255), "tone(0) debe ser blanco"
    assert gp.tone(gp.hex2rgb("#7aa2f7"), 1000) == (0, 0, 0), "tone(1000) debe ser negro"
    assert gp.tone(gp.hex2rgb("#7aa2f7"), 500) == gp.hex2rgb("#7aa2f7"), "tone(500) = base"
    toml = theme_tomls()[0]
    runs = [
        subprocess.run([sys.executable, str(GEN), str(toml)], capture_output=True, cwd=REPO)
        for _ in range(2)
    ]
    assert runs[0].returncode == 0 and runs[1].returncode == 0
    assert runs[0].stdout == runs[1].stdout, "gen-palette.py no es determinista"
    assert runs[0].stdout, "gen-palette.py no emitió XML"


# --- Entregables trackeados (audit-8 H1) --------------------------------------

def test_colors_xml_trackeados():
    """Todo RRO de paleta (overlay/themes/*/*/ con Android.bp) debe tener su
    res/values/colors.xml trackeado por git (`git ls-files --error-unmatch`).

    El gate `palette` hace glob del disco: sin este test, un colors.xml sin commitear
    construye una RRO vacía en un clon limpio sin que nada se ponga rojo (audit-8 H1).
    Sabotaje que lo vio en rojo: los 5 colors.xml de i8 sin `git add` -> exit 1 de
    ls-files --error-unmatch -> AssertionError por fichero.
    """
    rros = sorted(
        d for d in (REPO / "overlay" / "themes").glob("*/*")
        if d.is_dir() and (d / "Android.bp").is_file()
    )
    assert rros, "no hay RROs de paleta (overlay/themes/*/*/Android.bp)"
    for rro in rros:
        xml = rro / "res" / "values" / "colors.xml"
        rel = xml.relative_to(REPO)
        assert xml.is_file(), f"{rro.relative_to(REPO)}: falta res/values/colors.xml"
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(rel)],
            capture_output=True, cwd=REPO, text=True,
        )
        assert out.returncode == 0, (
            f"{rel}: NO trackeado por git (entregable sin commitear)"
        )


# --- Sabotaje H5 sobre la derivación de pares (audit-8 H7) ----------------------

def test_sabotaje_h5_surface_bright_detectado():
    """Reintroduce H5 en MEMORIA (system_surface_bright_* <- light_foreground) y exige que
    check-contrast salga con exit != 0.

    Guardián de la clase H7: si la derivación de pares vuelve a perderse los pares de
    surface_bright (familia de superficies M3), el check pasa en verde con este sabotaje y
    este test cae a rojo (así se vio en rojo ANTES del arreglo de H7: el check no medía
    surface_bright y aceptaba H5 reintroducido). No toca XML ni theme.toml commiteados.
    """
    gp = load_gen()
    saved = dict(gp.TOKENS)
    gp.TOKENS["system_surface_bright_dark"] = ("light_foreground",)
    gp.TOKENS["system_surface_bright_light"] = ("light_foreground",)
    try:
        spec = importlib.util.spec_from_file_location("check_contrast_sabotaje", CHECK)
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        cc.load_gen = lambda: gp  # el check mide el generador saboteado (solo memoria)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                cc.main([str(t) for t in theme_tomls()])
        except SystemExit as e:
            tail = "\n".join(buf.getvalue().splitlines()[-8:])
            assert e.code not in (0, None), (
                "check-contrast aceptó H5 reintroducido "
                "(system_surface_bright_* <- light_foreground) — resumen:\n" + tail
            )
        else:
            raise AssertionError("check-contrast no terminó en SystemExit")
    finally:
        gp.TOKENS.clear()
        gp.TOKENS.update(saved)
