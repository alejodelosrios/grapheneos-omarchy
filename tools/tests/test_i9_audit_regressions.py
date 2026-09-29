"""Tests de QA del issue #9 — regresiones de la ronda de auditoría (F1, N1).

Criterios verificables SIN host de build ni Pixel:
  F1 (ALTA, corregido en 49860d4): en `ThemePickerActivity.kt`, `ListView(this).apply { ... }`
      NO debe traer `setAdapter(adapter)` ni `adapter = adapter` sin calificar dentro del
      bloque — Kotlin resolvería `adapter` como `ListView.getAdapter()` (null), no el
      `ArrayAdapter<Theme>` de la Activity. En su lugar debe existir en el archivo
      `listView.adapter = adapter` o `setAdapter(this@ThemePickerActivity.adapter)`.
  N1 (MEDIA, corregido en edc2382): en `ThemeSwitcher.kt`, `LOCK` está declarado a nivel de
      archivo (fuera de `class ThemeSwitcher`) y tanto `set` como `next` corren dentro de
      `synchronized(LOCK)`.
  S2 (regresión): los marcadores `// 1.` … `// 5.` (movidos a `setLocked` tras N1) siguen en
      orden ascendente con su llamada respectiva — ya cubierto por
      test_i9_switcher_static.py::test_i9_s2_pasos_en_orden_ascendente_con_su_llamada, que
      opera sobre el texto completo del archivo y no depende del nombre de la función que los
      contiene; este módulo solo deja constancia de que sigue verde (test de humo).

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures,
stdlib). Cada test se vio en ROJO con su sabotaje (ver reporte de QA): los helpers reciben
texto en memoria, nunca se edita un archivo del repo.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "apps" / "OmarchyTheme" / "src" / "org" / "omarchy" / "theme"
PICKER_KT = APP / "ThemePickerActivity.kt"
SWITCHER_KT = APP / "ThemeSwitcher.kt"


# --- F1 · adapter fuera del apply --------------------------------------------------

BAD_ADAPTER = re.compile(r"setAdapter\(adapter\)|(?<![\w.])adapter\s*=\s*adapter\b")
GOOD_ADAPTER = re.compile(
    r"listView\.adapter\s*=\s*adapter\b|setAdapter\(this@ThemePickerActivity\.adapter\)"
)


def apply_blocks(text: str) -> list[str]:
    """Cada bloque `....apply { ... }` del texto, contenido incluido, por conteo de llaves."""
    blocks = []
    for m in re.finditer(r"\.apply\s*\{", text):
        brace_start = m.end() - 1
        depth = 0
        i = brace_start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[brace_start : i + 1])
                    break
            i += 1
        else:
            raise AssertionError("bloque .apply { sin cierre (llaves desbalanceadas)")
    return blocks


def adapter_wiring_reason(text: str) -> str | None:
    """None si el adapter se asigna calificado y fuera de cualquier `.apply {}`; si no, el motivo."""
    for block in apply_blocks(text):
        m = BAD_ADAPTER.search(block)
        if m:
            return f"un bloque .apply {{ ... }} asigna el adapter sin calificar: {m.group(0)!r}"
    if not GOOD_ADAPTER.search(text):
        return (
            "no encuentro `listView.adapter = adapter` ni "
            "`setAdapter(this@ThemePickerActivity.adapter)` fuera de un apply"
        )
    return None


def test_i9_f1_adapter_asignado_fuera_del_apply():
    reason = adapter_wiring_reason(PICKER_KT.read_text())
    assert reason is None, reason


def test_i9_f1_sabotaje_reintroduce_setadapter_dentro_del_apply():
    text = PICKER_KT.read_text()
    assert adapter_wiring_reason(text) is None

    sabotaged = text.replace(
        "ListView(this).apply {\n                choiceMode = AbsListView.CHOICE_MODE_SINGLE\n            }",
        "ListView(this).apply {\n                choiceMode = AbsListView.CHOICE_MODE_SINGLE\n"
        "                setAdapter(adapter)\n            }",
    )
    assert sabotaged != text, "el sabotaje no encontró el bloque ListView(this).apply { ... } a mutar"
    reason = adapter_wiring_reason(sabotaged)
    assert reason is not None, "sabotaje sin efecto: setAdapter(adapter) dentro del apply debía rechazarse"


# --- N1 · LOCK a nivel de archivo + set/next serializados --------------------------

def member_segment(text: str, fn_name: str) -> str:
    """Texto de `fun fn_name(...)` hasta el próximo miembro de clase (`\\n    fun` /
    `\\n    private fun`, indentado a 4 espacios) o el final del archivo.
    """
    m = re.search(rf"\bfun {re.escape(fn_name)}\(", text)
    assert m, f"ThemeSwitcher.kt: no encuentro fun {fn_name}("
    tail = text[m.end() :]
    nxt = re.search(r"\n {4}(private )?fun ", tail)
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.start() : end]


def lock_declared_at_file_level(text: str) -> bool:
    class_m = re.search(r"\bclass ThemeSwitcher\b", text)
    lock_m = re.search(r"private val LOCK = Any\(\)", text)
    if class_m is None or lock_m is None:
        return False
    return lock_m.start() < class_m.start()


def test_i9_n1_lock_declarado_a_nivel_de_archivo():
    text = SWITCHER_KT.read_text()
    assert lock_declared_at_file_level(text), (
        "LOCK no está declarado como `private val LOCK = Any()` antes de `class ThemeSwitcher` "
        "(a nivel de archivo, no por-instancia)"
    )


def test_i9_n1_set_y_next_dentro_de_synchronized_lock():
    text = SWITCHER_KT.read_text()
    for name in ("set", "next"):
        seg = member_segment(text, name)
        assert "synchronized(LOCK)" in seg, f"fun {name}(...) no corre dentro de synchronized(LOCK)"


def test_i9_n1_sabotaje_quita_synchronized_de_set():
    text = SWITCHER_KT.read_text()
    seg = member_segment(text, "set")
    assert "synchronized(LOCK)" in seg

    sabotaged = text.replace(
        "fun set(themeId: String): Boolean =\n"
        "        synchronized(LOCK) {\n"
        "            val theme = ThemeCatalog.get(themeId) ?: return@synchronized false\n"
        "            setLocked(themeId, theme)\n"
        "        }",
        "fun set(themeId: String): Boolean {\n"
        "            val theme = ThemeCatalog.get(themeId) ?: return false\n"
        "            return setLocked(themeId, theme)\n"
        "        }",
    )
    assert sabotaged != text, "el sabotaje no encontró el cuerpo de fun set(...) a mutar"
    seg2 = member_segment(sabotaged, "set")
    assert "synchronized(LOCK)" not in seg2, "sabotaje sin efecto: set seguía con synchronized(LOCK)"


# --- S2 · humo tras el refactor a setLocked ----------------------------------------

STEP_MARKERS = {
    1: "setEnabledExclusiveInCategory",
    2: "THEME_CUSTOMIZATION_OVERLAY_PACKAGES",
    3: "setNightMode",
    4: "setStream",
    5: "sendBroadcast",
}


def steps_in_order_with_calls(text: str) -> str | None:
    positions: dict[int, int] = {}
    for m in re.finditer(r"//\s*(\d)\.\s", text):
        n = int(m.group(1))
        if n in (1, 2, 3, 4, 5) and n not in positions:
            positions[n] = m.start()
    missing = [n for n in range(1, 6) if n not in positions]
    if missing:
        return f"faltan marcadores de paso: {missing}"
    order = [positions[n] for n in range(1, 6)]
    if order != sorted(order):
        return f"marcadores no ascendentes: {positions}"
    bounds = [positions[n] for n in range(1, 6)] + [len(text)]
    for n in range(1, 6):
        segment = text[bounds[n - 1] : bounds[n]]
        call = STEP_MARKERS[n]
        if call not in segment:
            return f"paso {n}: no contiene {call!r} antes del siguiente marcador"
    return None


def test_i9_s2_sigue_verde_tras_mover_los_pasos_a_setlocked():
    text = SWITCHER_KT.read_text()
    seg = member_segment(text, "setLocked")
    assert "// 1." in seg, "los marcadores de paso ya no están en setLocked (¿se movieron otra vez?)"
    reason = steps_in_order_with_calls(text)
    assert reason is None, reason
