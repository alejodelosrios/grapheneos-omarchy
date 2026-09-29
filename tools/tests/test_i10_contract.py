"""Tests de QA del issue #10 (design-10 «Criterios estáticos S1-S5»).

Criterios verificables SIN host de build ni Pixel:
  S1. ThemeContract.COLUMNS (app) y OmarchyThemeContract.COLUMNS (lib) son la misma lista,
      en el mismo orden: id, name, mode + las claves str de nivel superior (sin name/mode)
      de cada themes/<id>/theme.toml, leídas con tomllib, idénticas en los 6 temas.
      AUTHORITY e ID_PATTERN coinciden entre app y lib.
  S2. ThemeProvider.kt: insert devuelve null y delete/update devuelven 0 (sin cuerpo con
      efectos); solo hay dos addURI ("current", "themes"). El <provider> del manifest de
      la app es exported="true" sin android:permission/writePermission/grantUriPermissions.
  S3. El manifest de la app declara <protected-broadcast android:name="org.omarchy.theme.
      CHANGED"> como hijo directo de <manifest>. ThemeSwitcher.kt llama a
      notifyChange(ThemeContract.CURRENT después de sendBroadcast(.
  S4. apps/sdk/**/src/main/**/*.kt no lee extras de ningún Intent (getStringExtra,
      getExtras, .extras, registerReceiver, BroadcastReceiver). OmarchyTheme.kt usa
      ID_PATTERN en parse. El ContentObserver de flow() no llama a current( dentro de
      onChange: solo trySend(Unit).
  S5. El manifest de la lib tiene <queries><provider android:authorities="org.omarchy.
      theme"/></queries>.

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures,
stdlib). Cada test se vio en ROJO con su sabotaje sobre el texto en memoria (ver reporte
de QA): nunca se edita un archivo del repo.
"""
from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

APP_CONTRACT_KT = REPO / "apps" / "OmarchyTheme" / "src" / "org" / "omarchy" / "theme" / "ThemeContract.kt"
APP_PROVIDER_KT = REPO / "apps" / "OmarchyTheme" / "src" / "org" / "omarchy" / "theme" / "ThemeProvider.kt"
APP_SWITCHER_KT = REPO / "apps" / "OmarchyTheme" / "src" / "org" / "omarchy" / "theme" / "ThemeSwitcher.kt"
APP_MANIFEST = REPO / "apps" / "OmarchyTheme" / "AndroidManifest.xml"

LIB_CONTRACT_KT = (
    REPO / "apps" / "sdk" / "omarchy-theme-android" / "src" / "main" / "kotlin"
    / "org" / "omarchy" / "theme" / "sdk" / "OmarchyThemeContract.kt"
)
LIB_THEME_KT = (
    REPO / "apps" / "sdk" / "omarchy-theme-android" / "src" / "main" / "kotlin"
    / "org" / "omarchy" / "theme" / "sdk" / "OmarchyTheme.kt"
)
LIB_MANIFEST = REPO / "apps" / "sdk" / "omarchy-theme-android" / "src" / "main" / "AndroidManifest.xml"

SDK_MAIN_ROOT = REPO / "apps" / "sdk"

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


# --- helpers ---------------------------------------------------------------------


def kotlin_columns(text: str) -> list[str]:
    """Las strings de listOf(...) del bloque `COLUMNS: List<String> = listOf(...)`."""
    m = re.search(r"COLUMNS\s*:\s*List<String>\s*=\s*listOf\((.*?)\n\s*\)", text, re.DOTALL)
    assert m, "no se encontró el bloque COLUMNS = listOf(...)"
    return re.findall(r'"([^"]+)"', m.group(1))


def kotlin_const(text: str, name: str) -> str:
    m = re.search(rf'const val {name}\s*=\s*"([^"]+)"', text)
    assert m, f"no se encontró const val {name}"
    return m.group(1)


def toml_top_level_str_keys(theme_toml: Path) -> list[str]:
    data = tomllib.loads(theme_toml.read_text())
    return [k for k, v in data.items() if k not in ("name", "mode") and not isinstance(v, dict)]


def expected_columns() -> list[str]:
    theme_dirs = sorted((REPO / "themes").iterdir())
    per_theme = [toml_top_level_str_keys(t / "theme.toml") for t in theme_dirs]
    assert per_theme, "no hay themes/*/theme.toml"
    first = per_theme[0]
    for dirname, keys in zip(theme_dirs, per_theme):
        assert keys == first, f"{dirname.name}/theme.toml difiere en claves/orden: {keys} != {first}"
    return ["id", "name", "mode"] + first


def insert_is_null_noop(text: str) -> bool:
    return re.search(r"override fun insert\(.*?\)\s*:\s*Uri\?\s*=\s*null", text, re.DOTALL) is not None


def delete_is_zero_noop(text: str) -> bool:
    return re.search(r"override fun delete\(.*?\)\s*=\s*0\b", text, re.DOTALL) is not None


def update_is_zero_noop(text: str) -> bool:
    return re.search(r"override fun update\(.*?\)\s*=\s*0\b", text, re.DOTALL) is not None


def addURI_names(text: str) -> list[str]:
    return re.findall(r'addURI\(\s*ThemeContract\.AUTHORITY,\s*"(\w+)"', text)


def provider_element(manifest_text: str) -> ET.Element:
    root = ET.fromstring(manifest_text)
    provider = root.find(f".//application/provider")
    assert provider is not None, "no hay <provider> en el manifest"
    return provider


def provider_is_permission_less_and_exported(manifest_text: str) -> bool:
    provider = provider_element(manifest_text)
    if provider.get(f"{ANDROID_NS}exported") != "true":
        return False
    for attr in ("permission", "writePermission", "grantUriPermissions"):
        if provider.get(f"{ANDROID_NS}{attr}") is not None:
            return False
    return True


def has_protected_broadcast(manifest_text: str) -> bool:
    root = ET.fromstring(manifest_text)
    for child in root:
        if child.tag == "protected-broadcast" and child.get(f"{ANDROID_NS}name") == "org.omarchy.theme.CHANGED":
            return True
    return False


def notify_after_broadcast(text: str) -> bool:
    i_broadcast = text.find("sendBroadcast(")
    i_notify = text.find("notifyChange(ThemeContract.CURRENT")
    return i_broadcast != -1 and i_notify != -1 and i_broadcast < i_notify


FORBIDDEN_EXTRAS_PATTERNS = ["getStringExtra", "getExtras", ".extras", "registerReceiver", "BroadcastReceiver"]


def forbidden_extras_hits(text: str) -> list[str]:
    return [p for p in FORBIDDEN_EXTRAS_PATTERNS if p in text]


def sdk_main_kt_files() -> list[Path]:
    return sorted(SDK_MAIN_ROOT.glob("*/src/main/**/*.kt"))


def id_pattern_used_in_parse(text: str) -> bool:
    m = re.search(r"fun parse\(cursor: Cursor\?\).*", text, re.DOTALL)
    assert m, "no se encontró fun parse(cursor: Cursor?)"
    body = m.group(0)
    return "ID_REGEX" in body and "OmarchyThemeContract.ID_PATTERN" in text


def onchange_body(text: str) -> str:
    m = re.search(r"override fun onChange\(selfChange: Boolean\)\s*\{(.*?)\n\s*\}", text, re.DOTALL)
    assert m, "no se encontró override fun onChange(selfChange: Boolean)"
    return m.group(1)


def lib_manifest_has_provider_queries(manifest_text: str) -> bool:
    root = ET.fromstring(manifest_text)
    for provider in root.findall(".//queries/provider"):
        if provider.get(f"{ANDROID_NS}authorities") == "org.omarchy.theme":
            return True
    return False


# --- S1 ----------------------------------------------------------------------------


def test_i10_s1_toml_keys_iguales_en_seis_temas():
    expected = expected_columns()
    assert len(expected) == 3 + 25, f"se esperaban 3+25 columnas, hay {len(expected)}"


def test_i10_s1_columns_app_y_lib_coinciden_con_toml():
    expected = expected_columns()
    app_cols = kotlin_columns(APP_CONTRACT_KT.read_text())
    lib_cols = kotlin_columns(LIB_CONTRACT_KT.read_text())
    assert app_cols == expected, f"app COLUMNS != esperado: {app_cols} != {expected}"
    assert lib_cols == expected, f"lib COLUMNS != esperado: {lib_cols} != {expected}"


def test_i10_s1_authority_e_id_pattern_coinciden():
    app_text = APP_CONTRACT_KT.read_text()
    lib_text = LIB_CONTRACT_KT.read_text()
    assert kotlin_const(app_text, "AUTHORITY") == kotlin_const(lib_text, "AUTHORITY")
    assert kotlin_const(app_text, "ID_PATTERN") == kotlin_const(lib_text, "ID_PATTERN")


def test_i10_s1_sabotaje_columna_faltante_en_lib_da_rojo():
    expected = expected_columns()
    lib_text = LIB_CONTRACT_KT.read_text()
    lib_cols = kotlin_columns(lib_text)
    assert lib_cols == expected
    sabotaged = lib_text.replace('            "accent",\n', "", 1)
    assert sabotaged != lib_text, "el sabotaje no encontró la línea \"accent\","
    sabotaged_cols = kotlin_columns(sabotaged)
    assert sabotaged_cols != expected, "sabotaje sin efecto: la columna sigue presente"
    assert "accent" not in sabotaged_cols


# --- S2 ----------------------------------------------------------------------------


def test_i10_s2_insert_delete_update_son_noop():
    text = APP_PROVIDER_KT.read_text()
    assert insert_is_null_noop(text), "insert no es `= null`"
    assert delete_is_zero_noop(text), "delete no es `= 0`"
    assert update_is_zero_noop(text), "update no es `= 0`"
    assert addURI_names(text) == ["current", "themes"], addURI_names(text)


def test_i10_s2_sabotaje_update_con_efecto_da_rojo():
    text = APP_PROVIDER_KT.read_text()
    assert update_is_zero_noop(text)
    sabotaged = text.replace(
        "    override fun update(\n"
        "        uri: Uri,\n"
        "        values: ContentValues?,\n"
        "        selection: String?,\n"
        "        selectionArgs: Array<String>?,\n"
        "    ) = 0\n",
        "    override fun update(\n"
        "        uri: Uri,\n"
        "        values: ContentValues?,\n"
        "        selection: String?,\n"
        "        selectionArgs: Array<String>?,\n"
        "    ) = 1\n",
        1,
    )
    assert sabotaged != text, "el sabotaje no encontró el cuerpo de update"
    assert not update_is_zero_noop(sabotaged)


def test_i10_s2_provider_manifest_permission_less_y_exported():
    manifest_text = APP_MANIFEST.read_text()
    assert provider_is_permission_less_and_exported(manifest_text)


def test_i10_s2_sabotaje_writepermission_en_provider_da_rojo():
    manifest_text = APP_MANIFEST.read_text()
    assert provider_is_permission_less_and_exported(manifest_text)
    sabotaged = manifest_text.replace(
        '        <provider\n'
        '            android:name=".ThemeProvider"\n'
        '            android:authorities="org.omarchy.theme"\n'
        '            android:exported="true" />',
        '        <provider\n'
        '            android:name=".ThemeProvider"\n'
        '            android:authorities="org.omarchy.theme"\n'
        '            android:exported="true"\n'
        '            android:writePermission="org.omarchy.theme.WRITE" />',
        1,
    )
    assert sabotaged != manifest_text, "el sabotaje no encontró el <provider>"
    assert not provider_is_permission_less_and_exported(sabotaged)


# --- S3 ----------------------------------------------------------------------------


def test_i10_s3_protected_broadcast_hijo_directo_de_manifest():
    assert has_protected_broadcast(APP_MANIFEST.read_text())


def test_i10_s3_sabotaje_sin_protected_broadcast_da_rojo():
    manifest_text = APP_MANIFEST.read_text()
    assert has_protected_broadcast(manifest_text)
    sabotaged = manifest_text.replace(
        '    <protected-broadcast android:name="org.omarchy.theme.CHANGED" />\n', "", 1
    )
    assert sabotaged != manifest_text, "el sabotaje no encontró <protected-broadcast>"
    assert not has_protected_broadcast(sabotaged)


def test_i10_s3_notifychange_despues_de_sendbroadcast():
    text = APP_SWITCHER_KT.read_text()
    assert notify_after_broadcast(text)


def test_i10_s3_sabotaje_orden_invertido_da_rojo():
    text = APP_SWITCHER_KT.read_text()
    assert notify_after_broadcast(text)
    # Cuela una llamada a notifyChange(ThemeContract.CURRENT antes de cualquier
    # sendBroadcast( del archivo (incluida la mención en el KDoc), simulando que el
    # observer se notifica primero que el broadcast.
    sabotaged = "// notifyChange(ThemeContract.CURRENT, null) // adelantado\n" + text
    assert sabotaged != text
    assert not notify_after_broadcast(sabotaged)


# --- S4 ----------------------------------------------------------------------------


def test_i10_s4_lib_no_lee_extras_de_intents():
    files = sdk_main_kt_files()
    assert files, "no hay .kt bajo apps/sdk/**/src/main"
    hits: dict[str, list[str]] = {}
    for f in files:
        h = forbidden_extras_hits(f.read_text())
        if h:
            hits[str(f)] = h
    assert not hits, f"extras/receiver de Intent encontrados: {hits}"


def test_i10_s4_sabotaje_registerreceiver_da_rojo():
    text = LIB_THEME_KT.read_text()
    assert not forbidden_extras_hits(text)
    sabotaged = text + "\n// registerReceiver(\n"
    assert forbidden_extras_hits(sabotaged) == ["registerReceiver"]


def test_i10_s4_parse_usa_id_pattern():
    text = LIB_THEME_KT.read_text()
    assert id_pattern_used_in_parse(text)


def test_i10_s4_oncchange_solo_trysend_unit():
    text = LIB_THEME_KT.read_text()
    body = onchange_body(text)
    assert "trySend(Unit)" in body
    assert "current(" not in body


def test_i10_s4_sabotaje_oncchange_llama_current_da_rojo():
    text = LIB_THEME_KT.read_text()
    body = onchange_body(text)
    assert "current(" not in body
    sabotaged = text.replace("trySend(Unit)\n                        }", "trySend(current(ctx))\n                        }", 1)
    assert sabotaged != text, "el sabotaje no encontró el trySend(Unit) de onChange"
    sabotaged_body = onchange_body(sabotaged)
    assert "current(" in sabotaged_body


# --- S5 ----------------------------------------------------------------------------


def test_i10_s5_lib_manifest_declara_queries_provider():
    assert lib_manifest_has_provider_queries(LIB_MANIFEST.read_text())


def test_i10_s5_sabotaje_sin_queries_da_rojo():
    manifest_text = LIB_MANIFEST.read_text()
    assert lib_manifest_has_provider_queries(manifest_text)
    sabotaged = manifest_text.replace(
        '    <queries>\n        <provider android:authorities="org.omarchy.theme" />\n    </queries>\n',
        "",
        1,
    )
    assert sabotaged != manifest_text, "el sabotaje no encontró <queries>"
    assert not lib_manifest_has_provider_queries(sabotaged)
