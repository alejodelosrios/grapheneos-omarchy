"""Tests de QA del issue #11 (design-11-icons-bg-next.md «Criterios estáticos S1-S6»).

Criterios verificables SIN host de build ni Pixel:
  S1. Los 6 `theme.toml` llevan `[android].icon_shape` in {rounded-square, circle} (nord =
      circle, el resto rounded-square) y `themed_icons == "true"` (ambos str). `new-theme.sh`
      emite las dos claves con sus defaults en el heredoc de scaffold.
  S2. En ThemeSwitcher.kt (sin comentarios), `put(KEY_ADAPTIVE_ICON_SHAPE` solo entra dentro de
      `if (theme.iconShape == "rounded-square")`.
  S3. ThemeCatalog.kt: `iconShape`/`themedIcons` caen a su default con `Log.w`, sin `throw` ni
      `error(`. ThemeSwitcher.kt `applyThemedIcons`: `Thread { ... }.start()`, `update(` dentro
      de `try/catch (RuntimeException)`, sin `.join(`, `Thread.sleep`, `.get(` ni `runBlocking`.
  S4. `OMARCHY_BG_EXTS` (omarchy.mk) y `BACKGROUND_EXTENSIONS` (ThemeCatalog.kt) son el mismo
      conjunto {jpg, jpeg, png, webp}; omarchy.mk ya no copia `backgrounds/*` sin filtrar; cada
      lista cita a la otra en un comentario.
  S5. El manifest declara `.WallpaperTileService` exported=true, permiso
      BIND_QUICK_SETTINGS_TILE y acción QS_TILE. `privapp-permissions` sigue idéntico a
      origin/develop (#11 no añade permisos). WallpaperTileService.kt: wrap `% files.size`,
      `setWallpaper(` dentro de un `Thread`, `STATE_UNAVAILABLE` con < 2 fondos.
  S6. Ningún `/*` ni `*/` embebido en el cuerpo de un comentario Kotlin bajo apps/**/*.kt
      (lección f4: un glob como `themes/*/theme.toml` dentro de un comentario de bloque abre
      un comentario anidado que la cierre real no cierra del todo, rompiendo el parseo).
      Entregables versionados (lección f2).

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures,
stdlib). Cada test se vio en ROJO con su sabotaje en memoria (ver reporte de QA): nunca se
edita un archivo del repo.
"""
from __future__ import annotations

import re
import subprocess
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

APP = REPO / "apps" / "OmarchyTheme"
CATALOG_KT = APP / "src" / "org" / "omarchy" / "theme" / "ThemeCatalog.kt"
SWITCHER_KT = APP / "src" / "org" / "omarchy" / "theme" / "ThemeSwitcher.kt"
TILE_KT = APP / "src" / "org" / "omarchy" / "theme" / "WallpaperTileService.kt"
MANIFEST = APP / "AndroidManifest.xml"
PRIVAPP = APP / "privapp-permissions-org.omarchy.theme.xml"

OMARCHY_MK = REPO / "omarchy.mk"
NEW_THEME_SH = REPO / "tools" / "new-theme.sh"
THEMES_DIR = REPO / "themes"

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

DELIVERABLES = [
    "themes/catppuccin/theme.toml",
    "themes/everforest/theme.toml",
    "themes/gruvbox/theme.toml",
    "themes/kanagawa/theme.toml",
    "themes/nord/theme.toml",
    "themes/tokyo-night/theme.toml",
    "tools/new-theme.sh",
    "omarchy.mk",
    "apps/OmarchyTheme/src/org/omarchy/theme/ThemeCatalog.kt",
    "apps/OmarchyTheme/src/org/omarchy/theme/ThemeSwitcher.kt",
    "apps/OmarchyTheme/src/org/omarchy/theme/WallpaperTileService.kt",
    "apps/OmarchyTheme/AndroidManifest.xml",
]


# --- helpers (copiados/adaptados de test_i10_contract.py) --------------------------------


def strip_comments(text: str) -> str:
    """Quita comentarios `/* ... */` y `// ...` (naive: alcanza para estos .kt, que no tienen
    literales con `//` fuera de comentario en el código relevante)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _braced_span_from(text: str, brace_start: int) -> int:
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


def git_show(rev_path: str) -> str:
    out = subprocess.run(["git", "show", rev_path], capture_output=True, cwd=REPO, text=True)
    assert out.returncode == 0, f"git show {rev_path} falló: {out.stderr}"
    return out.stdout


# --- S1 · theme.toml (icon_shape / themed_icons) + new-theme.sh scaffold -----------------


def theme_android_table(theme_id: str) -> dict:
    text = (THEMES_DIR / theme_id / "theme.toml").read_text()
    return tomllib.loads(text)["android"]


def test_i11_s1_seis_temas_icon_shape_y_themed_icons():
    theme_ids = sorted(p.name for p in THEMES_DIR.iterdir() if (p / "theme.toml").is_file())
    assert len(theme_ids) == 6, f"se esperaban 6 themes/*/theme.toml, hay {theme_ids}"
    for theme_id in theme_ids:
        android = theme_android_table(theme_id)
        shape = android["icon_shape"]
        themed = android["themed_icons"]
        assert isinstance(shape, str), f"{theme_id}: icon_shape no es str: {shape!r}"
        assert isinstance(themed, str), f"{theme_id}: themed_icons no es str: {themed!r}"
        assert shape in ("rounded-square", "circle"), f"{theme_id}: icon_shape inválido {shape!r}"
        assert themed == "true", f"{theme_id}: themed_icons != \"true\" ({themed!r})"
        expected_shape = "circle" if theme_id == "nord" else "rounded-square"
        assert shape == expected_shape, f"{theme_id}: icon_shape={shape!r}, se esperaba {expected_shape!r}"


def test_i11_s1_sabotaje_nord_deja_de_ser_circle_da_rojo():
    nord_text = (THEMES_DIR / "nord" / "theme.toml").read_text()
    assert tomllib.loads(nord_text)["android"]["icon_shape"] == "circle"
    sabotaged = nord_text.replace('icon_shape = "circle"', 'icon_shape = "rounded-square"', 1)
    assert sabotaged != nord_text, "el sabotaje no encontró icon_shape = \"circle\" en nord"
    assert tomllib.loads(sabotaged)["android"]["icon_shape"] != "circle"


def test_i11_s1_sabotaje_themed_icons_false_da_rojo():
    gruvbox_text = (THEMES_DIR / "gruvbox" / "theme.toml").read_text()
    assert tomllib.loads(gruvbox_text)["android"]["themed_icons"] == "true"
    sabotaged = gruvbox_text.replace('themed_icons = "true"', 'themed_icons = "false"', 1)
    assert sabotaged != gruvbox_text
    assert tomllib.loads(sabotaged)["android"]["themed_icons"] != "true"


def test_i11_s1_new_theme_sh_emite_icon_shape_y_themed_icons():
    text = NEW_THEME_SH.read_text()
    # Las dos claves van en el heredoc de scaffold, con sus valores fijos (D2), como f-strings
    # literales `key = "value"`.
    assert re.search(r"""f'icon_shape = "rounded-square"\\n'""", text), "no se ve el f-string de icon_shape"
    assert re.search(r"""f'themed_icons = "true"\\n'""", text), "no se ve el f-string de themed_icons"
    # Y se filtran del upstream para no heredar un valor ajeno (mismo patrón que font).
    assert "icon_shape" in text.split("allowed_extra")[1].split("}")[0]
    assert "themed_icons" in text.split("allowed_extra")[1].split("}")[0]


def test_i11_s1_sabotaje_new_theme_sh_sin_icon_shape_da_rojo():
    text = NEW_THEME_SH.read_text()
    assert re.search(r'icon_shape\s*=\s*"rounded-square"', text)
    line = '    f\'icon_shape = "rounded-square"\\n\'\n'
    assert line in text, "no se encontró la línea f-string de icon_shape a quitar"
    sabotaged = text.replace(line, "", 1)
    assert sabotaged != text
    assert not re.search(r"""f'icon_shape = "rounded-square"\\n'""", sabotaged)


# --- S2 · adaptive_icon_shape solo con rounded-square -------------------------------------


def icon_shape_guarded(text: str) -> bool:
    code = strip_comments(text)
    return (
        re.search(
            r'if\s*\(\s*theme\.iconShape\s*==\s*"rounded-square"\s*\)\s*\{\s*put\(KEY_ADAPTIVE_ICON_SHAPE',
            code,
        )
        is not None
    )


def test_i11_s2_adaptive_icon_shape_condicionado_a_rounded_square():
    text = SWITCHER_KT.read_text()
    assert icon_shape_guarded(text)


def test_i11_s2_sabotaje_quitar_if_da_rojo():
    text = SWITCHER_KT.read_text()
    assert icon_shape_guarded(text)
    original = (
        '                if (theme.iconShape == "rounded-square") {\n'
        "                    put(KEY_ADAPTIVE_ICON_SHAPE, SHAPE_OVERLAY_PACKAGE)\n"
        "                }\n"
    )
    assert original in text, "no se encontró el bloque if de adaptive_icon_shape"
    sabotaged_block = '                put(KEY_ADAPTIVE_ICON_SHAPE, SHAPE_OVERLAY_PACKAGE)\n'
    sabotaged = text.replace(original, sabotaged_block, 1)
    assert sabotaged != text
    assert not icon_shape_guarded(sabotaged)


# --- S3 · defaults con Log.w (ThemeCatalog) + applyThemedIcons en hilo (ThemeSwitcher) ----


ICON_SHAPE_GETTER = r"val iconShape: String\s*\n\s*get\(\)\s*"
THEMED_ICONS_GETTER = r"val themedIcons: Boolean\s*\n\s*get\(\)\s*"


def default_branch_ok(body: str) -> bool:
    return "Log.w" in body and "throw" not in body and "error(" not in body


def test_i11_s3_iconshape_default_logw_sin_throw():
    body = extract_braced_block(CATALOG_KT.read_text(), ICON_SHAPE_GETTER)
    assert default_branch_ok(body)


def test_i11_s3_sabotaje_iconshape_default_throw_da_rojo():
    text = CATALOG_KT.read_text()
    body = extract_braced_block(text, ICON_SHAPE_GETTER)
    assert default_branch_ok(body)
    original = (
        '                Log.w(TAG, "$id: invalid android.icon_shape $v, defaulting to rounded-square")\n'
        '                return "rounded-square"\n'
    )
    assert original in text, "no se encontró el default de iconShape a sabotear"
    sabotaged_line = (
        '                throw IllegalStateException("$id: invalid android.icon_shape $v")\n'
    )
    sabotaged = text.replace(original, sabotaged_line, 1)
    assert sabotaged != text
    sabotaged_body = extract_braced_block(sabotaged, ICON_SHAPE_GETTER)
    assert not default_branch_ok(sabotaged_body)


def test_i11_s3_themedicons_default_logw_sin_throw():
    body = extract_braced_block(CATALOG_KT.read_text(), THEMED_ICONS_GETTER)
    assert default_branch_ok(body)


def test_i11_s3_sabotaje_themedicons_default_error_da_rojo():
    text = CATALOG_KT.read_text()
    body = extract_braced_block(text, THEMED_ICONS_GETTER)
    assert default_branch_ok(body)
    original = (
        '                    Log.w(TAG, "$id: invalid android.themed_icons $v, defaulting to true")\n'
        "                    true\n"
    )
    assert original in text, "no se encontró el default de themedIcons a sabotear"
    sabotaged_line = '                    error("$id: invalid android.themed_icons $v")\n'
    sabotaged = text.replace(original, sabotaged_line, 1)
    assert sabotaged != text
    sabotaged_body = extract_braced_block(sabotaged, THEMED_ICONS_GETTER)
    assert not default_branch_ok(sabotaged_body)


APPLY_THEMED_ICONS_SIGNATURE = r"private fun applyThemedIcons\(enabled: Boolean\)\s*"
FORBIDDEN_BLOCKING = [".join(", "Thread.sleep", ".get(", "runBlocking"]


def apply_themed_icons_ok(text: str) -> bool:
    body = extract_braced_block(text, APPLY_THEMED_ICONS_SIGNATURE)
    if "Thread {" not in body or ".start()" not in body:
        return False
    try:
        try_body = extract_try_with_catches(body, r"try\s*")
    except AssertionError:
        return False
    if "update(" not in try_body or "catch (e: RuntimeException)" not in try_body:
        return False
    return not any(p in body for p in FORBIDDEN_BLOCKING)


def test_i11_s3_applythemedicons_thread_try_catch_sin_join():
    assert apply_themed_icons_ok(SWITCHER_KT.read_text())


def test_i11_s3_sabotaje_applythemedicons_con_join_da_rojo():
    text = SWITCHER_KT.read_text()
    assert apply_themed_icons_ok(text)
    original = (
        "            } catch (e: RuntimeException) {\n"
        '                Log.w(TAG, "failed to push themed-icons state to Launcher3", e)\n'
        "            }\n"
        "        }.start()\n"
        "    }\n"
    )
    assert original in text, "no se encontró el cierre de applyThemedIcons a sabotear"
    sabotaged_block = (
        "            } catch (e: RuntimeException) {\n"
        '                Log.w(TAG, "failed to push themed-icons state to Launcher3", e)\n'
        "            }\n"
        "        }.apply { start(); join() }\n"
        "    }\n"
    )
    sabotaged = text.replace(original, sabotaged_block, 1)
    assert sabotaged != text
    assert not apply_themed_icons_ok(sabotaged)


# --- S4 · OMARCHY_BG_EXTS == BACKGROUND_EXTENSIONS ----------------------------------------


EXPECTED_BG_EXTS = {"jpg", "jpeg", "png", "webp"}


def bg_exts_from_mk(text: str) -> set[str]:
    m = re.search(r"OMARCHY_BG_EXTS\s*:=\s*([^\n]+)", text)
    assert m, "no se encontró OMARCHY_BG_EXTS := ... en omarchy.mk"
    return set(m.group(1).split())


def bg_exts_from_kt(text: str) -> set[str]:
    m = re.search(r"BACKGROUND_EXTENSIONS\s*=\s*setOf\(([^)]*)\)", text)
    assert m, "no se encontró BACKGROUND_EXTENSIONS = setOf(...) en ThemeCatalog.kt"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def test_i11_s4_extensiones_mk_y_kt_coinciden_con_esperado():
    mk_exts = bg_exts_from_mk(OMARCHY_MK.read_text())
    kt_exts = bg_exts_from_kt(CATALOG_KT.read_text())
    assert mk_exts == EXPECTED_BG_EXTS, f"omarchy.mk: {mk_exts} != {EXPECTED_BG_EXTS}"
    assert kt_exts == EXPECTED_BG_EXTS, f"ThemeCatalog.kt: {kt_exts} != {EXPECTED_BG_EXTS}"


def test_i11_s4_mk_no_copia_backgrounds_sin_filtrar():
    text = OMARCHY_MK.read_text()
    assert re.search(r"backgrounds/\*\)", text) is None, (
        "omarchy.mk todavía copia backgrounds/* sin extensión"
    )


def test_i11_s4_cada_lista_cita_a_la_otra_en_comentario():
    mk_text = OMARCHY_MK.read_text()
    kt_text = CATALOG_KT.read_text()
    assert "BACKGROUND_EXTENSIONS" in mk_text, "omarchy.mk no cita a BACKGROUND_EXTENSIONS"
    assert "OMARCHY_BG_EXTS" in kt_text, "ThemeCatalog.kt no cita a OMARCHY_BG_EXTS"


def test_i11_s4_sabotaje_quitar_webp_de_mk_da_rojo():
    mk_text = OMARCHY_MK.read_text()
    assert bg_exts_from_mk(mk_text) == EXPECTED_BG_EXTS
    sabotaged = mk_text.replace(
        "OMARCHY_BG_EXTS := jpg jpeg png webp", "OMARCHY_BG_EXTS := jpg jpeg png", 1
    )
    assert sabotaged != mk_text
    assert bg_exts_from_mk(sabotaged) != bg_exts_from_kt(CATALOG_KT.read_text())


def test_i11_s4_sabotaje_quitar_webp_de_kt_da_rojo():
    kt_text = CATALOG_KT.read_text()
    assert bg_exts_from_kt(kt_text) == EXPECTED_BG_EXTS
    sabotaged = kt_text.replace(
        'val BACKGROUND_EXTENSIONS = setOf("jpg", "jpeg", "png", "webp")',
        'val BACKGROUND_EXTENSIONS = setOf("jpg", "jpeg", "png")',
        1,
    )
    assert sabotaged != kt_text, "el sabotaje no encontró la línea de BACKGROUND_EXTENSIONS"
    assert bg_exts_from_kt(sabotaged) != bg_exts_from_mk(OMARCHY_MK.read_text())


# --- S5 · manifest / privapp-permissions / WallpaperTileService.kt -----------------------


WALLPAPER_SERVICE_BLOCK = (
    '        <service android:name=".WallpaperTileService" android:exported="true"\n'
    '            android:label="Next wallpaper"\n'
    '            android:permission="android.permission.BIND_QUICK_SETTINGS_TILE">\n'
    "            <intent-filter>\n"
    '                <action android:name="android.service.quicksettings.action.QS_TILE" />\n'
    "            </intent-filter>\n"
    "        </service>\n"
)


def wallpapertile_service_ok(manifest_text: str) -> bool:
    root = ET.fromstring(manifest_text)
    svc = root.find(f".//service[@{ANDROID_NS}name='.WallpaperTileService']")
    if svc is None:
        return False
    if svc.get(f"{ANDROID_NS}exported") != "true":
        return False
    if svc.get(f"{ANDROID_NS}permission") != "android.permission.BIND_QUICK_SETTINGS_TILE":
        return False
    actions = {a.get(f"{ANDROID_NS}name") for a in svc.findall(".//action")}
    return "android.service.quicksettings.action.QS_TILE" in actions


def test_i11_s5_manifest_wallpapertileservice_exported_permiso_accion():
    text = MANIFEST.read_text()
    assert WALLPAPER_SERVICE_BLOCK in text, "el bloque <service .WallpaperTileService> cambió de forma"
    assert wallpapertile_service_ok(text)


def test_i11_s5_sabotaje_quitar_permiso_da_rojo():
    text = MANIFEST.read_text()
    assert wallpapertile_service_ok(text)
    sabotaged_block = (
        '        <service android:name=".WallpaperTileService" android:exported="true"\n'
        '            android:label="Next wallpaper">\n'
        "            <intent-filter>\n"
        '                <action android:name="android.service.quicksettings.action.QS_TILE" />\n'
        "            </intent-filter>\n"
        "        </service>\n"
    )
    sabotaged = text.replace(WALLPAPER_SERVICE_BLOCK, sabotaged_block, 1)
    assert sabotaged != text
    assert not wallpapertile_service_ok(sabotaged)


def test_i11_s5_privapp_permissions_sigue_identico_a_develop():
    diff = subprocess.run(
        ["git", "diff", "--quiet", "origin/develop", "--", "apps/OmarchyTheme/privapp-permissions-org.omarchy.theme.xml"],
        cwd=REPO,
    )
    assert diff.returncode == 0, "privapp-permissions difiere de origin/develop (#11 no añade permisos)"


def test_i11_s5_sabotaje_privapp_permission_nueva_da_rojo():
    text = PRIVAPP.read_text()
    develop_text = git_show(f"origin/develop:{PRIVAPP.relative_to(REPO)}")
    assert text == develop_text
    sabotaged = text.replace(
        "</privapp-permissions>",
        '    <permission name="android.permission.SET_WALLPAPER_COMPONENT"/>\n'
        "</privapp-permissions>",
        1,
    )
    assert sabotaged != text, "el sabotaje no encontró el cierre </privapp-permissions>"
    assert sabotaged != develop_text


def onclick_thread_body(text: str) -> str:
    return extract_braced_block(
        text, r"override fun onClick\(\)\s*\{\s*super\.onClick\(\)\s*Thread\s*"
    )


def onstartlistening_body(text: str) -> str:
    return extract_braced_block(text, r"override fun onStartListening\(\)\s*\{")


def test_i11_s5_wallpapertileservice_wrap_thread_y_estado():
    text = TILE_KT.read_text()
    thread_body = onclick_thread_body(text)
    assert "% files.size" in thread_body, "el índice no envuelve con % files.size"
    assert "setWallpaper(" in thread_body, "setWallpaper( no está dentro del Thread de onClick"
    start_body = onstartlistening_body(text)
    assert "n < 2" in start_body and "Tile.STATE_UNAVAILABLE" in start_body


def test_i11_s5_sabotaje_sin_wrap_modulo_da_rojo():
    text = TILE_KT.read_text()
    assert "% files.size" in onclick_thread_body(text)
    original = "val next = (prefs.getInt(key, 0) + 1) % files.size\n"
    assert original in text, "no se encontró la línea del wrap a sabotear"
    sabotaged = text.replace(original, "val next = prefs.getInt(key, 0) + 1\n", 1)
    assert sabotaged != text
    assert "% files.size" not in onclick_thread_body(sabotaged)


def test_i11_s5_sabotaje_sin_state_unavailable_da_rojo():
    text = TILE_KT.read_text()
    assert "Tile.STATE_UNAVAILABLE" in onstartlistening_body(text)
    original = "tile.state = if (n < 2) Tile.STATE_UNAVAILABLE else Tile.STATE_ACTIVE\n"
    assert original in text, "no se encontró la línea de estado a sabotear"
    sabotaged = text.replace(original, "tile.state = Tile.STATE_ACTIVE\n", 1)
    assert sabotaged != text
    assert "Tile.STATE_UNAVAILABLE" not in onstartlistening_body(sabotaged)


# --- S6 · sin /* ni */ embebido en comentarios Kotlin (lección f4) + entregables trackeados -


def kotlin_files() -> list[Path]:
    return sorted((REPO / "apps").glob("**/*.kt"))


def kotlin_comment_violations(text: str) -> list[str]:
    """Recorre el texto respetando strings (incluidas triple-quoted) para no confundir un
    literal con un comentario, y detecta si el CUERPO de un comentario (línea o bloque)
    contiene `/*` o `*/` embebido: en un comentario de bloque eso abre un anidado que la
    llave de cierre real no cierra del todo (lección f4); en uno de línea no rompe el
    parseo pero delata el mismo patrón peligroso, así que también se marca."""
    violations: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith('"""', i):
            end = text.find('"""', i + 3)
            i = (end + 3) if end != -1 else n
            continue
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if text.startswith("/*", i):
            depth = 1
            j = i + 2
            nested = False
            while j < n and depth > 0:
                if text.startswith("/*", j):
                    depth += 1
                    nested = True
                    j += 2
                elif text.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            if nested:
                violations.append(f"comentario de bloque con /* anidado en offset {i}")
            i = j
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = end if end != -1 else n
            body = text[i + 2 : end]
            if "/*" in body or "*/" in body:
                violations.append(f"comentario de línea con /* o */ embebido en offset {i}")
            i = end
            continue
        i += 1
    return violations


def test_i11_s6_sin_glob_embebido_en_comentarios_kt():
    files = kotlin_files()
    assert files, "no hay .kt bajo apps/"
    hits: dict[str, list[str]] = {}
    for f in files:
        v = kotlin_comment_violations(f.read_text())
        if v:
            hits[str(f)] = v
    assert not hits, f"lección f4: /* o */ embebido en comentario: {hits}"


def test_i11_s6_sabotaje_glob_en_kdoc_da_rojo():
    snippet = "/** ejemplo de glob peligroso: themes/*/theme.toml */\nfun x() {}\n"
    assert kotlin_comment_violations(snippet), "el sabotaje (glob con /* anidado) no fue detectado"


def test_i11_s6_url_en_comentario_no_es_falso_positivo():
    snippet = "// see https://example.com/a/b for details\nval x = 1\n"
    assert kotlin_comment_violations(snippet) == []


def test_i11_s6_string_con_glob_no_es_falso_positivo():
    snippet = 'val glob = "themes/*/theme.toml"\n// comentario normal\n'
    assert kotlin_comment_violations(snippet) == []


def test_i11_s6_entregables_trackeados():
    untracked = []
    for rel in DELIVERABLES:
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel], capture_output=True, cwd=REPO, text=True
        )
        if out.returncode != 0:
            untracked.append(rel)
    assert not untracked, f"sin commitear (git ls-files --error-unmatch falla): {untracked}"
