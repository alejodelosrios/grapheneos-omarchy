"""Tests del issue #4 (design-4 §Cómo se verifica cada criterio / §Valores propuestos).

C4 es el único criterio verificable sin host de build: el overlay framework NO contiene
`rounded_corner_radius` (radio físico de la pantalla, `docs/research.md:181,207`), y los
diálogos quedan en los valores aprobados del diseño (12dp / 16dp). C1–C3 exigen build o
dispositivo y viven en `## No verificado sin host de build` del PR.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRAMEWORK = REPO / "overlay" / "OmarchyFrameworkOverlay"
CONFIG = FRAMEWORK / "res" / "values" / "config.xml"


def dimens(text: str) -> dict[str, str]:
    return dict(re.findall(r'<dimen name="([^"]+)">([^<]*)</dimen>', text))


def test_c4_sin_radios_fisicos_de_pantalla():
    """C4: `grep -c rounded_corner_radius …/config.xml` → 0, en todo el overlay.

    `rounded_corner_radius` es la geometría de las esquinas del display (el valor real lo pone
    el overlay del dispositivo): deformarlo rompe el recorte de la pantalla.
    """
    text = CONFIG.read_text(encoding="utf-8")
    assert "rounded_corner_radius" not in text, (
        "C4 violado: rounded_corner_radius presente en "
        f"{CONFIG.relative_to(REPO)} ({text.count('rounded_corner_radius')} ocurrencias)"
    )
    bad = sorted(
        p.relative_to(REPO).as_posix()
        for p in FRAMEWORK.rglob("*")
        if p.is_file() and "rounded_corner_radius" in p.read_text(encoding="utf-8", errors="replace")
    )
    assert bad == [], f"rounded_corner_radius en el overlay framework: {bad}"


def test_overlay_solo_los_dos_dimen_del_diseno():
    """design-4 §Archivos a tocar: ni un recurso más (vecinos como config_buttonCornerRadius no se tocan)."""
    got = sorted(dimens(CONFIG.read_text(encoding="utf-8")))
    esperado = ["config_bottomDialogCornerRadius", "config_dialogCornerRadius"]
    assert got == esperado, f"recursos en config.xml: {got}, esperado: {esperado}"


def test_valores_del_diseno_12_16dp():
    """design-4 §Valores propuestos: diálogos 12dp (Hyprland rounding≈12dp), bottom sheet 16dp."""
    got = dimens(CONFIG.read_text(encoding="utf-8"))
    assert got.get("config_dialogCornerRadius") == "12dp", (
        f"config_dialogCornerRadius={got.get('config_dialogCornerRadius')!r}, esperado '12dp'"
    )
    assert got.get("config_bottomDialogCornerRadius") == "16dp", (
        f"config_bottomDialogCornerRadius={got.get('config_bottomDialogCornerRadius')!r},"
        " esperado '16dp'"
    )


def test_comentario_wallpaper_apunta_a_issue7():
    """design-4 §Archivos a tocar: el comentario del wallpaper apunta al drawable de #7."""
    text = CONFIG.read_text(encoding="utf-8")
    assert "default_wallpaper.png" in text and "#7" in text, (
        "el comentario debe citar res/drawable-nodpi/default_wallpaper.png (issue #7)"
    )
