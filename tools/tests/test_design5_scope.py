"""Tests de alcance del issue #5 (design-5 §Cómo se verifica cada criterio / §No entra).

Cero `res/layout/` (en el árbol del overlay y en su diff), cero Java/Kotlin en SystemUI, XML
bien formado y las 4 filas nuevas de `docs/THEMING.md §Compat` con su cita upstream.
"""
from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYSUI = REPO / "overlay" / "OmarchySystemUIOverlay"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def test_sin_layouts_en_overlay():
    """§No entra: res/layout/ prohibido (el shade se consigue solo con drawables/dimens)."""
    layouts = sorted(p for p in SYSUI.rglob("*") if "res/layout" in p.as_posix())
    assert layouts == [], f"res/layout presente en el overlay: {layouts}"


def test_diff_del_overlay_sin_layouts():
    """Criterio del issue: `git diff --stat` del overlay no contiene res/layout/."""
    if git("rev-parse", "--verify", "-q", "origin/develop").returncode == 0:
        base = "origin/develop"
    else:
        base = "origin/main"
    diff = git("diff", "--name-only", f"{base}...HEAD").stdout.split()
    status = [ln[3:] for ln in git("status", "--porcelain").stdout.splitlines() if ln.strip()]
    touched = diff + status
    bad = sorted({
        t for t in touched
        if t.startswith("overlay/OmarchySystemUIOverlay/") and "res/layout/" in t
    })
    assert bad == [], f"res/layout/ en el diff del overlay: {bad}"


def test_sin_java_kotlin_en_systemui():
    """Solo recursos: nada de Java/Kotlin en el overlay de SystemUI."""
    code = sorted(p for p in SYSUI.rglob("*") if p.suffix in {".java", ".kt"})
    assert code == [], f"Java/Kotlin en el overlay de SystemUI: {code}"


def test_xml_del_overlay_bien_formado():
    bad = []
    for p in sorted(SYSUI.rglob("*.xml")):
        try:
            ET.parse(p)
        except Exception as e:  # noqa: BLE001 — queremos el parse error literal
            bad.append(f"{p.relative_to(REPO)}: {e}")
    assert bad == [], "XML mal formado: " + "; ".join(bad)


def test_theming_compat_cuatro_filas():
    """Ronda 2: 4 filas nuevas en §Compat, cada una con cita upstream packages/SystemUI/."""
    text = (REPO / "docs" / "THEMING.md").read_text(encoding="utf-8")
    m = re.search(r"^## Compat.*?\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.M)
    assert m, "no existe la sección `## Compat` en docs/THEMING.md"
    rows = [ln for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    esperadas = [
        "notification_material_bg",
        "omarchy_notification_state_color",
        "omarchy_notification_focus_overlay_color",
        "status_bar_clock_color",
    ]
    faltan = []
    for key in esperadas:
        if not any(key in r and "packages/SystemUI/" in r for r in rows):
            faltan.append(key)
    assert not faltan, f"filas de §Compat sin cita upstream packages/SystemUI/: {faltan}"
