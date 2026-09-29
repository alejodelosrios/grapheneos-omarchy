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

Ronda de auditoría #10 (RECHAZO 1/2), corregida en be1ee1e:
  H1. En OmarchyTheme.kt `flow`: `registerContentObserver(` va dentro de un `try { }
      catch (e: SecurityException)`, y `awaitClose` solo desregistra si `registered` es
      true; `current()` captura `RuntimeException` (no solo `SecurityException`).
  M1. En OmarchyColorScheme.kt `schemeFor`, los roles `on*` de mayor riesgo de contraste
      (onPrimary, onPrimaryContainer, onSurfaceVariant, onError, onBackground, onSurface)
      pasan por `onColor(`/`pickText(`, nunca por `hex(` directo. El test de contraste
      real (WCAG AA) es el JUnit `OmarchyColorSchemeContrastTest`, no se duplica aquí.
  L5. `notify_after_broadcast` ignora comentarios (// y /* */) para que la mención de
      `sendBroadcast` en el KDoc no cuente como código y un `notifyChange` comentado no
      cuele. `id_pattern_used_in_parse` acota el cuerpo de `parse` por conteo de llaves.

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
LIB_COMPOSE_KT = (
    REPO / "apps" / "sdk" / "omarchy-theme-compose" / "src" / "main" / "kotlin"
    / "org" / "omarchy" / "theme" / "sdk" / "compose" / "OmarchyColorScheme.kt"
)

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


def strip_comments(text: str) -> str:
    """Quita comentarios `/* ... */` y `// ...` (naive, alcanza para este .kt: no hay
    literales con `//` fuera de comentario). Así un `sendBroadcast(` mencionado en un KDoc
    no cuenta como código, ni un `notifyChange(...)` comentado."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def notify_after_broadcast(text: str) -> bool:
    code = strip_comments(text)
    i_broadcast = code.find("sendBroadcast(")
    i_notify = code.find("notifyChange(ThemeContract.CURRENT")
    return i_broadcast != -1 and i_notify != -1 and i_broadcast < i_notify


def _braced_span_from(text: str, brace_start: int) -> int:
    """Índice justo después del `}` que cierra la llave abierta en `brace_start`."""
    depth = 0
    i = brace_start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise AssertionError("no se encontró el cierre de llaves")


def extract_braced_block(text: str, start_pattern: str) -> str:
    """El bloque `{ ... }` que sigue al primer match de `start_pattern`, delimitado por
    conteo de llaves (no hasta el final del archivo ni con un cierre "adivinado")."""
    m = re.search(start_pattern, text)
    assert m, f"no se encontró el patrón: {start_pattern}"
    start = text.index("{", m.end())
    end = _braced_span_from(text, start)
    return text[start:end]


def extract_try_with_catches(text: str, start_pattern: str) -> str:
    """Como [extract_braced_block] para un `try { ... }`, pero se sigue tragando cada
    `catch (...) { ... }` inmediatamente posterior (una expresión try/catch es varios
    bloques `{ }` hermanos, no uno solo)."""
    m = re.search(start_pattern, text)
    assert m, f"no se encontró el patrón: {start_pattern}"
    start = text.index("{", m.end())
    end = _braced_span_from(text, start)
    while True:
        catch_m = re.match(r"\s*catch\s*\([^)]*\)\s*", text[end:])
        if not catch_m:
            break
        catch_brace = end + catch_m.end()
        assert text[catch_brace] == "{", "catch sin bloque `{ }`"
        end = _braced_span_from(text, catch_brace)
    return text[start:end]


def extract_paren_block(text: str, start_pattern_ending_in_open_paren: str) -> str:
    """El bloque `( ... )` que abre el `(` final de `start_pattern_ending_in_open_paren`,
    delimitado por conteo de paréntesis."""
    m = re.search(start_pattern_ending_in_open_paren, text)
    assert m, f"no se encontró el patrón: {start_pattern_ending_in_open_paren}"
    start = m.end() - 1
    assert text[start] == "(", "el patrón debe terminar justo en el `(` de apertura"
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    raise AssertionError(f"no se encontró el cierre de paréntesis de: {start_pattern_ending_in_open_paren}")


FORBIDDEN_EXTRAS_PATTERNS = ["getStringExtra", "getExtras", ".extras", "registerReceiver", "BroadcastReceiver"]


def forbidden_extras_hits(text: str) -> list[str]:
    return [p for p in FORBIDDEN_EXTRAS_PATTERNS if p in text]


def sdk_main_kt_files() -> list[Path]:
    return sorted(SDK_MAIN_ROOT.glob("*/src/main/**/*.kt"))


def id_pattern_used_in_parse(text: str) -> bool:
    body = extract_braced_block(text, r"fun parse\(cursor: Cursor\?\): OmarchyTheme\?\s*")
    return "ID_REGEX" in body and "OmarchyThemeContract.ID_PATTERN" in text


FLOW_SIGNATURE = r"fun flow\(ctx: Context\): Flow<OmarchyTheme\?>\s*=\s*"
CURRENT_SIGNATURE = r"fun current\(ctx: Context\): OmarchyTheme\?\s*=\s*"


def flow_body(text: str) -> str:
    return extract_braced_block(text, FLOW_SIGNATURE)


def current_body(text: str) -> str:
    return extract_try_with_catches(text, CURRENT_SIGNATURE)


def register_observer_in_try_catch_security(flow_text: str) -> bool:
    return (
        re.search(
            r"try\s*\{[^{}]*?registerContentObserver\([^{}]*?\)[^{}]*?\}\s*catch\s*\(e:\s*SecurityException\)\s*\{",
            flow_text,
            re.DOTALL,
        )
        is not None
    )


def awaitclose_unregisters_only_if_registered(flow_text: str) -> bool:
    return (
        re.search(
            r"awaitClose\s*\{\s*if\s*\(registered\)\s*ctx\.contentResolver\.unregisterContentObserver\(observer\)\s*\}",
            flow_text,
        )
        is not None
    )


def current_catches_runtime_exception(current_text: str) -> bool:
    return "catch (e: RuntimeException)" in current_text and "catch (e: SecurityException)" not in current_text


ONCOLOR_DIRECT_ROLES = ["onPrimary", "onPrimaryContainer", "onSurfaceVariant", "onError"]


def role_via_oncolor(copy_block_text: str, role: str) -> bool:
    return re.search(rf"\b{role}\s*=\s*onColor\(", copy_block_text) is not None


def role_via_hex_directo(copy_block_text: str, role: str) -> bool:
    return re.search(rf"\b{role}\s*=\s*hex\(theme", copy_block_text) is not None


def onbackground_onsurface_via_oncolor_var(text: str, copy_block_text: str) -> bool:
    has_var = re.search(r"val onBackgroundColor\s*=\s*onColor\(", text) is not None
    used_bg = re.search(r"\bonBackground\s*=\s*onBackgroundColor\b", copy_block_text) is not None
    used_surface = re.search(r"\bonSurface\s*=\s*onBackgroundColor\b", copy_block_text) is not None
    return has_var and used_bg and used_surface


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
    # Intercambia los dos bloques de código reales (no comentarios): notifyChange queda
    # antes que el sendBroadcast real.
    broadcast_block = (
        "        // 5. Notify listeners.\n"
        "        context.sendBroadcast(\n"
        "            Intent(ThemeContract.ACTION_THEME_CHANGED)\n"
        "                .putExtra(ThemeContract.EXTRA_THEME_ID, themeId)\n"
        "                .putExtra(ThemeContract.EXTRA_MODE, theme.mode),\n"
        "        )\n"
    )
    notify_block = (
        "        // 5b. Wake up ContentResolver observers (the lib's flow(ctx), not a broadcast receiver).\n"
        "        context.contentResolver.notifyChange(ThemeContract.CURRENT, null)\n"
    )
    combo = broadcast_block + "\n" + notify_block
    assert combo in text, "no se encontraron los dos bloques consecutivos esperados"
    swapped = notify_block + "\n" + broadcast_block
    sabotaged = text.replace(combo, swapped, 1)
    assert sabotaged != text
    assert not notify_after_broadcast(sabotaged)


def test_i10_s3_sabotaje_notifychange_comentado_da_rojo():
    text = APP_SWITCHER_KT.read_text()
    assert notify_after_broadcast(text)
    line = "        context.contentResolver.notifyChange(ThemeContract.CURRENT, null)\n"
    assert line in text, "no se encontró la línea real de notifyChange"
    sabotaged = text.replace(line, "        // " + line.strip() + "\n", 1)
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


# --- H1 (auditoría #10, RECHAZO 1/2) ------------------------------------------------


def test_i10_h1_registercontentobserver_en_try_catch_securityexception():
    body = flow_body(LIB_THEME_KT.read_text())
    assert register_observer_in_try_catch_security(body)


def test_i10_h1_sabotaje_sin_try_catch_da_rojo():
    text = LIB_THEME_KT.read_text()
    assert register_observer_in_try_catch_security(flow_body(text))
    original_block = (
        "                val registered =\n"
        "                    try {\n"
        "                        ctx.contentResolver.registerContentObserver(\n"
        "                            OmarchyThemeContract.CURRENT,\n"
        "                            false,\n"
        "                            observer,\n"
        "                        )\n"
        "                        true\n"
        "                    } catch (e: SecurityException) {\n"
        "                        // No provider (stock AOSP): keep the initial emission, nothing to\n"
        "                        // unregister.\n"
        "                        false\n"
        "                    }\n"
    )
    sabotaged_block = (
        "                val registered =\n"
        "                    run {\n"
        "                        ctx.contentResolver.registerContentObserver(\n"
        "                            OmarchyThemeContract.CURRENT,\n"
        "                            false,\n"
        "                            observer,\n"
        "                        )\n"
        "                        true\n"
        "                    }\n"
    )
    assert original_block in text, "no se encontró el bloque try/catch de registerContentObserver"
    sabotaged = text.replace(original_block, sabotaged_block, 1)
    assert sabotaged != text
    assert not register_observer_in_try_catch_security(flow_body(sabotaged))


def test_i10_h1_awaitclose_desregistra_solo_si_registered():
    body = flow_body(LIB_THEME_KT.read_text())
    assert awaitclose_unregisters_only_if_registered(body)


def test_i10_h1_sabotaje_awaitclose_desregistra_incondicional_da_rojo():
    text = LIB_THEME_KT.read_text()
    assert awaitclose_unregisters_only_if_registered(flow_body(text))
    line = "awaitClose { if (registered) ctx.contentResolver.unregisterContentObserver(observer) }"
    assert line in text
    sabotaged = text.replace(
        line, "awaitClose { ctx.contentResolver.unregisterContentObserver(observer) }", 1
    )
    assert sabotaged != text
    assert not awaitclose_unregisters_only_if_registered(flow_body(sabotaged))


def test_i10_h1_current_captura_runtimeexception():
    body = current_body(LIB_THEME_KT.read_text())
    assert current_catches_runtime_exception(body)


def test_i10_h1_sabotaje_current_vuelve_a_securityexception_da_rojo():
    text = LIB_THEME_KT.read_text()
    assert current_catches_runtime_exception(current_body(text))
    original = "catch (e: RuntimeException) {"
    assert original in text
    sabotaged = text.replace(original, "catch (e: SecurityException) {", 1)
    assert sabotaged != text
    assert not current_catches_runtime_exception(current_body(sabotaged))


# --- M1 (auditoría #10, RECHAZO 1/2) ------------------------------------------------


def test_i10_m1_oncolor_roles_de_riesgo_no_usan_hex_directo():
    text = LIB_COMPOSE_KT.read_text()
    block = extract_paren_block(text, r"return base\.copy\(")
    for role in ONCOLOR_DIRECT_ROLES:
        assert role_via_oncolor(block, role), f"{role} no pasa por onColor("
        assert not role_via_hex_directo(block, role), f"{role} usa hex(theme directo"
    assert onbackground_onsurface_via_oncolor_var(text, block), (
        "onBackground/onSurface no comparten onBackgroundColor calculado con onColor("
    )


def test_i10_m1_sabotaje_onerror_directo_por_hex_da_rojo():
    text = LIB_COMPOSE_KT.read_text()
    block = extract_paren_block(text, r"return base\.copy\(")
    assert role_via_oncolor(block, "onError")
    original = 'onError = onColor("background", listOf("red"), base.onError),'
    sabotaged_line = 'onError = hex(theme, "red") ?: base.onError,'
    assert original in text, "no se encontró la línea de onError"
    sabotaged = text.replace(original, sabotaged_line, 1)
    assert sabotaged != text
    sabotaged_block = extract_paren_block(sabotaged, r"return base\.copy\(")
    assert not role_via_oncolor(sabotaged_block, "onError")
    assert role_via_hex_directo(sabotaged_block, "onError")
