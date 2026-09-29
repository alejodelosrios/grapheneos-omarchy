#!/usr/bin/env python3
"""Check estático de referencias de recursos en OmarchySystemUIOverlay (design-5 §qa).

Toda referencia `@color/`, `@dimen/`, `@drawable/` y `?android:attr/` dentro de
`overlay/OmarchySystemUIOverlay/res/` debe:

  (a) existir definida en el propio overlay (p. ej. `@color/omarchy_*` locales), o
  (b) ser `@android:` público de la LISTA CERRADA del diseño (tabla de citas de
      `.swarm/design/design-5-systemui-shade.md`): `system_surface_container_high_{light,dark}`,
      `system_on_surface_{light,dark}`, `system_secondary_{light,dark}`, `system_accent1_500`,
      `transparent` y el attr `colorControlHighlight`.

`tools/system-colors.txt` NO se usa aquí (es de #8): la lista cerrada es literalmente la del
diseño, ni un símbolo más. Un `@android:` fuera de lista o un bare ref no definido rompe el link
de aapt2 en el RRO (los bare se resuelven contra el paquete del overlay, no del target).

CLI (lo usa `.swarm/gate.sh`, check `refs`):

    python3 tools/tests/overlay_refs.py overlay/OmarchySystemUIOverlay/res

Sale 0 si limpia; 1 con violaciones (una por línea: `<archivo>: <referencia> …`).
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Lista cerrada de design-5 §qa / §Tabla de citas. Únicos `@android:` / `?android:attr/`
# permitidos en este overlay. Nada de tools/system-colors.txt (#8).
CLOSED_ANDROID: dict[str, frozenset[str]] = {
    "color": frozenset({
        "system_surface_container_high_light",
        "system_surface_container_high_dark",
        "system_on_surface_light",
        "system_on_surface_dark",
        "system_secondary_light",
        "system_secondary_dark",
        "system_accent1_500",
        "transparent",
    }),
    "dimen": frozenset(),      # el overlay usa literales dp (design-5 punto 3)
    "drawable": frozenset(),
    "attr": frozenset({"colorControlHighlight"}),
}

REF_RE = re.compile(r"@(android:)?(color|dimen|drawable|attr)/([A-Za-z_][A-Za-z0-9_]*)")
THEME_ATTR_RE = re.compile(r"\?(android:)?attr/([A-Za-z_][A-Za-z0-9_]*)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def iter_refs(text: str):
    """(tipo, es_android, nombre) de cada referencia en el texto, sin comentarios.

    Los comentarios XML no se compilan en el APK: una referencia prohibida solo en un
    comentario no es una referencia.
    """
    text = COMMENT_RE.sub("", text)
    for m in REF_RE.finditer(text):
        yield m.group(2), bool(m.group(1)), m.group(3)
    for m in THEME_ATTR_RE.finditer(text):
        yield "attr", bool(m.group(1)), m.group(2)


def collect_defs(res_dir: Path) -> dict[str, set[str]]:
    """Recursos definidos por el overlay: tipo -> nombres.

    `res/<tipo>[-cualificadores]/nombre.*` define `tipo/nombre` (color-night, drawable-night…);
    en `res/values*/` el tipo es el tag (`<color name=…>`, `<dimen name=…>`) o el atributo
    `type` de `<item>`.
    """
    defs: dict[str, set[str]] = {}
    for f in sorted(res_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(res_dir)
        head = rel.parts[0]
        if head.startswith("values"):
            if f.suffix != ".xml":
                continue
            for el in ET.parse(f).getroot():
                name = el.get("name")
                if not name:
                    continue
                typ = el.get("type") or el.tag
                defs.setdefault(typ, set()).add(name)
        else:
            if len(rel.parts) != 2:
                continue
            defs.setdefault(head.split("-")[0], set()).add(f.stem)
    return defs


def check_res_dir(res_dir: Path | str) -> list[str]:
    """Violaciones de la lista cerrada en `<res_dir>`. Vacía = limpia."""
    res_dir = Path(res_dir)
    defs = collect_defs(res_dir)
    out: list[str] = []
    for f in sorted(res_dir.rglob("*.xml")):
        text = f.read_text(encoding="utf-8")
        for typ, is_android, name in iter_refs(text):
            raw = f"@{'android:' if is_android else ''}{typ}/{name}"
            if is_android:
                if name not in CLOSED_ANDROID.get(typ, frozenset()):
                    out.append(f"{f}: {raw} fuera de la lista cerrada (design-5 §qa)")
            else:
                if name not in defs.get(typ, set()):
                    out.append(f"{f}: {raw} no existe en el overlay")
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: overlay_refs.py <res-dir> [...]", file=sys.stderr)
        return 2
    rc = 0
    for d in argv[1:]:
        viol = check_res_dir(d)
        for v in viol:
            print(v)
        if viol:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
