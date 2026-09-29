"""Tests de QA del issue #9 (design-9 «Criterios estáticos S2-S5» + condición de seguridad).

Criterios verificables SIN host de build ni Pixel:
  S2. ThemeSwitcher.kt contiene las 7 claves `android.theme.customization.*` de D1;
      accent_color/dynamic_color reciben theme.palettePackage; color_source = "preset";
      los comentarios `// 1.` ... `// 5.` están en orden ascendente y cada paso contiene su
      llamada (setEnabledExclusiveInCategory, THEME_CUSTOMIZATION_OVERLAY_PACKAGES,
      setNightMode, setStream, sendBroadcast) entre su marcador y el siguiente; `font` va
      condicionado a `!= "system"`.
  S3. AndroidManifest.xml: `.BootReceiver` con BOOT_COMPLETED, `uses-permission
      RECEIVE_BOOT_COMPLETED`, `.ThemePickerActivity` con QS_TILE_PREFERENCES, `<service
      .ThemeTileService>` con BIND_QUICK_SETTINGS_TILE.
  S4. `privapp-permissions-org.omarchy.theme.xml`: mismo set de permisos que
      `origin/develop`, sin RECEIVE_BOOT_COMPLETED (D3: permiso "normal", no privapp).
  S5. `omarchy.mk` ya no dice que shape/font son inmutables; `overlay/config/config.xml`
      idéntico a origin/develop y con shape/font `mutable="true"`.
  Seguridad (condición del gate de diseño): la primera sentencia de `onReceive` en
  BootReceiver.kt es el guard de acción, antes de `goAsync()`.
  Lección f2: los .kt nuevos de la pieza (ThemeCatalog, BootReceiver, ThemeTileService,
  ThemePickerActivity) están trackeados por git.

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures,
stdlib). Cada test se vio en ROJO con su sabotaje (ver reporte de QA): los helpers reciben
texto en memoria (`...from(text)` / `..._ok(text)`), nunca se edita un archivo del repo.
"""
from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "apps" / "OmarchyTheme"
SWITCHER_KT = APP / "src" / "org" / "omarchy" / "theme" / "ThemeSwitcher.kt"
BOOT_KT = APP / "src" / "org" / "omarchy" / "theme" / "BootReceiver.kt"
MANIFEST = APP / "AndroidManifest.xml"
PRIVAPP = APP / "privapp-permissions-org.omarchy.theme.xml"
OMARCHY_MK = REPO / "omarchy.mk"
CONFIG_XML = REPO / "overlay" / "config" / "config.xml"

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

D1_KEYS = [
    "android.theme.customization.system_palette",
    "android.theme.customization.accent_color",
    "android.theme.customization.dynamic_color",
    "android.theme.customization.color_source",
    "android.theme.customization.theme_style",
    "android.theme.customization.adaptive_icon_shape",
    "android.theme.customization.font",
]

STEP_MARKERS = {
    1: "setEnabledExclusiveInCategory",
    2: "THEME_CUSTOMIZATION_OVERLAY_PACKAGES",
    3: "setNightMode",
    4: "setStream",
    5: "sendBroadcast",
}


def git_show(rev_path: str) -> str:
    out = subprocess.run(
        ["git", "show", rev_path], capture_output=True, cwd=REPO, text=True
    )
    assert out.returncode == 0, f"git show {rev_path} falló: {out.stderr}"
    return out.stdout


# --- S2 · claves D1 --------------------------------------------------------------

def keys_present(text: str) -> list[str]:
    """Las claves D1 que faltan como literal en el texto (lista vacía = las 7 presentes)."""
    return [k for k in D1_KEYS if f'"{k}"' not in text]


def test_i9_s2_siete_claves_d1_presentes():
    missing = keys_present(SWITCHER_KT.read_text())
    assert not missing, f"ThemeSwitcher.kt: faltan claves D1: {missing}"


def test_i9_s2_sabotaje_clave_ausente():
    text = SWITCHER_KT.read_text()
    assert not keys_present(text)
    sabotaged = text.replace(
        'private const val KEY_FONT = "android.theme.customization.font"',
        'private const val KEY_FONT = "android.theme.customization.fontx"',
    )
    assert sabotaged != text, "el sabotaje no encontró KEY_FONT a mutar"
    missing = keys_present(sabotaged)
    assert missing == ["android.theme.customization.font"], (
        f"sabotaje sin efecto esperado: missing={missing}"
    )


def test_i9_s2_accent_y_dynamic_reciben_palette_package_color_source_preset():
    text = SWITCHER_KT.read_text()
    assert re.search(r"put\(KEY_ACCENT_COLOR,\s*theme\.palettePackage\)", text), (
        "accent_color no recibe theme.palettePackage"
    )
    assert re.search(r"put\(KEY_DYNAMIC_COLOR,\s*theme\.palettePackage\)", text), (
        "dynamic_color no recibe theme.palettePackage"
    )
    assert re.search(r'put\(KEY_COLOR_SOURCE,\s*"preset"\)', text), (
        "color_source no está fijo a \"preset\""
    )


def test_i9_s2_font_condicionado_a_no_system():
    text = SWITCHER_KT.read_text()
    m = re.search(r'if\s*\(theme\.font\s*!=\s*"system"\)\s*\{\s*put\(KEY_FONT,', text)
    assert m, "KEY_FONT no está condicionada a theme.font != \"system\""


# --- S2 · orden ascendente de los 5 pasos + llamada correcta por paso ------------

def step_positions(text: str) -> dict[int, int]:
    """Posición (offset) de cada marcador `// N.` en el texto, N en 1..5."""
    positions: dict[int, int] = {}
    for m in re.finditer(r"//\s*(\d)\.\s", text):
        n = int(m.group(1))
        if n in (1, 2, 3, 4, 5) and n not in positions:
            positions[n] = m.start()
    return positions


def steps_in_order_with_calls(text: str) -> str | None:
    """None si los 5 pasos están en orden ascendente y cada uno contiene su llamada antes del
    siguiente marcador; si no, devuelve el motivo del fallo (string no vacío)."""
    positions = step_positions(text)
    missing = [n for n in range(1, 6) if n not in positions]
    if missing:
        return f"faltan marcadores de paso: {missing}"
    order = [positions[n] for n in range(1, 6)]
    if order != sorted(order):
        return f"marcadores no ascendentes: {positions}"
    bounds = [positions[n] for n in range(1, 6)] + [len(text)]
    for n in range(1, 6):
        segment = text[bounds[n - 1]:bounds[n]]
        call = STEP_MARKERS[n]
        if call not in segment:
            return f"paso {n}: no contiene {call!r} antes del siguiente marcador"
    return None


def test_i9_s2_pasos_en_orden_ascendente_con_su_llamada():
    reason = steps_in_order_with_calls(SWITCHER_KT.read_text())
    assert reason is None, reason


def test_i9_s2_sabotaje_orden_de_pasos():
    text = SWITCHER_KT.read_text()
    assert steps_in_order_with_calls(text) is None
    # Intercambia los marcadores "// 1." y "// 3." (deja el código real donde estaba):
    # el paso 1 (offset menor) pasa a decir "// 3." y viceversa -> el orden ya no es ascendente.
    sabotaged = text.replace(
        "// 1. Exclusively enable this theme's palette overlay.",
        "// 3. Exclusively enable this theme's palette overlay.",
        1,
    ).replace(
        "// 3. Light/dark mode.",
        "// 1. Light/dark mode.",
        1,
    )
    assert sabotaged != text, "el sabotaje no encontró los marcadores // 1. / // 3. a intercambiar"
    reason = steps_in_order_with_calls(sabotaged)
    assert reason is not None, "sabotaje sin efecto: el orden debía romperse"


# --- S3 · manifest -----------------------------------------------------------------

def manifest_findings(text: str) -> list[str]:
    """Lista de problemas encontrados en el manifest (vacía = todo correcto)."""
    problems: list[str] = []
    root = ET.fromstring(text)

    def attr(el, name):
        return el.get(f"{ANDROID_NS}{name}")

    receiver = root.find(f".//receiver[@{ANDROID_NS}name='.BootReceiver']")
    if receiver is None:
        problems.append("falta <receiver .BootReceiver>")
    else:
        actions = {attr(a, "name") for a in receiver.findall(f".//action")}
        if "android.intent.action.BOOT_COMPLETED" not in actions:
            problems.append(".BootReceiver sin intent-filter BOOT_COMPLETED")

    perms = {attr(p, "name") for p in root.findall("uses-permission")}
    if "android.permission.RECEIVE_BOOT_COMPLETED" not in perms:
        problems.append("falta <uses-permission RECEIVE_BOOT_COMPLETED>")

    picker = root.find(f".//activity[@{ANDROID_NS}name='.ThemePickerActivity']")
    if picker is None:
        problems.append("falta <activity .ThemePickerActivity>")
    else:
        actions = {attr(a, "name") for a in picker.findall(".//action")}
        if "android.service.quicksettings.action.QS_TILE_PREFERENCES" not in actions:
            problems.append(".ThemePickerActivity sin acción QS_TILE_PREFERENCES")

    tile = root.find(f".//service[@{ANDROID_NS}name='.ThemeTileService']")
    if tile is None:
        problems.append("falta <service .ThemeTileService>")
    elif attr(tile, "permission") != "android.permission.BIND_QUICK_SETTINGS_TILE":
        problems.append(
            f".ThemeTileService: permission={attr(tile, 'permission')!r}, se espera BIND_QUICK_SETTINGS_TILE"
        )
    return problems


def test_i9_s3_manifest_receiver_picker_tile():
    problems = manifest_findings(MANIFEST.read_text())
    assert not problems, f"AndroidManifest.xml: {problems}"


def test_i9_s3_sabotaje_permiso_tile():
    text = MANIFEST.read_text()
    assert not manifest_findings(text)
    sabotaged = text.replace(
        'android:permission="android.permission.BIND_QUICK_SETTINGS_TILE"', ""
    )
    assert sabotaged != text, "el sabotaje no encontró el permiso del tile a quitar"
    problems = manifest_findings(sabotaged)
    assert any("BIND_QUICK_SETTINGS_TILE" in p for p in problems), (
        f"sabotaje sin efecto esperado: {problems}"
    )


# --- S4 · privapp-permissions sin permisos nuevos ---------------------------------

def permission_names(text: str) -> set[str]:
    root = ET.fromstring(text)
    return {p.get("name") for p in root.findall(".//permission")}


def test_i9_s4_privapp_permissions_igual_a_develop():
    ours = permission_names(PRIVAPP.read_text())
    theirs = permission_names(
        git_show(f"origin/develop:{PRIVAPP.relative_to(REPO)}")
    )
    assert ours == theirs, f"privapp-permissions difiere de origin/develop: {ours} != {theirs}"
    assert "android.permission.RECEIVE_BOOT_COMPLETED" not in ours, (
        "RECEIVE_BOOT_COMPLETED no debe estar en privapp-permissions (D3: protectionLevel normal)"
    )


def test_i9_s4_sabotaje_permiso_extra():
    text = PRIVAPP.read_text()
    sabotaged = text.replace(
        "</privapp-permissions>",
        '    <permission name="android.permission.RECEIVE_BOOT_COMPLETED"/>\n'
        "    </privapp-permissions>",
    )
    assert sabotaged != text, "el sabotaje no encontró el cierre </privapp-permissions>"
    ours = permission_names(sabotaged)
    theirs = permission_names(git_show(f"origin/develop:{PRIVAPP.relative_to(REPO)}"))
    assert ours != theirs, "sabotaje sin efecto: el permiso extra debía romper la igualdad"


# --- S5 · omarchy.mk y config.xml -------------------------------------------------

def test_i9_s5_omarchy_mk_ya_no_dice_shape_font_inmutables():
    text = OMARCHY_MK.read_text()
    assert "# Static, theme-independent skin (always on, immutable)" not in text, (
        "omarchy.mk todavía tiene el comentario obsoleto (shape/font ya son mutables, D2)"
    )
    assert "mutable" in text.lower() and "shape" in text.lower() and "font" in text.lower(), (
        "omarchy.mk no documenta que shape/font son mutables"
    )


def test_i9_s5_config_xml_identico_a_develop_y_shape_font_mutables():
    diff = subprocess.run(
        ["git", "diff", "--quiet", "origin/develop", "--", "overlay/config/config.xml"],
        cwd=REPO,
    )
    assert diff.returncode == 0, "overlay/config/config.xml difiere de origin/develop"
    text = CONFIG_XML.read_text()
    root = ET.fromstring(text)
    by_pkg = {o.get("package"): o for o in root.findall("overlay")}
    for pkg in ("org.omarchy.overlay.shape", "org.omarchy.overlay.font"):
        assert pkg in by_pkg, f"config.xml sin overlay {pkg}"
        assert by_pkg[pkg].get("mutable") == "true", f"{pkg} no es mutable=\"true\""


# --- Seguridad · guard de acción antes de goAsync en BootReceiver ----------------

def guard_is_first_statement(text: str) -> bool:
    m = re.search(r"override fun onReceive\([^)]*\)\s*\{\s*(.*?)\n\}", text, re.S)
    assert m, "BootReceiver.kt: no encuentro el cuerpo de onReceive"
    body = m.group(1)
    guard_m = re.search(
        r'if\s*\(intent\.action\s*!=\s*Intent\.ACTION_BOOT_COMPLETED\)\s*return', body
    )
    go_async_m = re.search(r"goAsync\(\)", body)
    if guard_m is None or go_async_m is None:
        return False
    # La primera línea no vacía / no comentario del cuerpo debe ser el guard.
    first_stmt = next(
        (ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")),
        None,
    )
    guard_line = next(
        (ln.strip() for ln in body.splitlines() if "ACTION_BOOT_COMPLETED" in ln), None
    )
    return first_stmt == guard_line and guard_m.start() < go_async_m.start()


def test_i9_seguridad_guard_boot_completed_antes_de_goasync():
    assert guard_is_first_statement(BOOT_KT.read_text()), (
        "BootReceiver.onReceive: el guard de ACTION_BOOT_COMPLETED no es la primera sentencia "
        "antes de goAsync()"
    )


def test_i9_seguridad_sabotaje_quitar_guard():
    text = BOOT_KT.read_text()
    assert guard_is_first_statement(text)
    sabotaged = text.replace(
        "        // Exported receiver: BOOT_COMPLETED is a protected broadcast, so any other action here\n"
        "        // would have to come from an explicit intent sent by a third party — ignore it.\n"
        "        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return\n\n",
        "",
    )
    assert sabotaged != text, "el sabotaje no encontró el guard a quitar"
    assert not guard_is_first_statement(sabotaged), "sabotaje sin efecto: el guard seguía detectándose"


# --- Lección f2 · los .kt nuevos están trackeados por git -------------------------

NEW_KT_FILES = [
    "apps/OmarchyTheme/src/org/omarchy/theme/ThemeCatalog.kt",
    "apps/OmarchyTheme/src/org/omarchy/theme/BootReceiver.kt",
    "apps/OmarchyTheme/src/org/omarchy/theme/ThemeTileService.kt",
    "apps/OmarchyTheme/src/org/omarchy/theme/ThemePickerActivity.kt",
]


def test_i9_leccion_f2_kt_nuevos_trackeados():
    untracked = []
    for rel in NEW_KT_FILES:
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            capture_output=True, cwd=REPO, text=True,
        )
        if out.returncode != 0:
            untracked.append(rel)
    assert not untracked, (
        f"lección f2: sin commitear (git ls-files --error-unmatch falla): {untracked}"
    )
