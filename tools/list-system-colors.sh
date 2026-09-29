#!/usr/bin/env bash
# list-system-colors.sh — regenera tools/system-colors.txt: los 194 tokens públicos
# `system_*` con type="color" del framework (el universo que todo colors.xml debe cubrir).
#
# Trazabilidad (design-8 D2; ejecución verificada 2026-09-28 contra el mismo comando):
#   comando literal (issue #8):
#     gh api 'repos/GrapheneOS/platform_frameworks_base/contents/core/res/res/values/public-final.xml?ref=17'
#   ref=17: rama 17 de GrapheneOS, la verificada en docs/research.md (no se copia nada del
#   árbol externo: solo se LEE el JSON público vía gh api).
#   Derivación medida sobre esa respuesta (2026-09-28):
#     324 líneas name="system_*" sin sort -u  (el "324 sin -u" de D2)
#     -> 196 nombres únicos (sort -u)
#     -> 194 con type="color"  (los de este fichero; wc -l == 194, D2)
#     ->  2 con type="dimen" excluidos: system_app_widget_{background,inner}_radius
#        (radios, no colores; no pueden ir en colors.xml)
#   El ">= 201" del criterio 1 del issue contaba además líneas legacy
#   `<public name="system_*"/>` sin type (p. ej. 128 en ref=17): D2 lo corrige a == 194.
#
# Uso: tools/list-system-colors.sh   (reescribe tools/system-colors.txt, solo nombres, 1 línea c/u)
set -euo pipefail
cd "$(dirname "$0")/.."

REF=17
gh api "repos/GrapheneOS/platform_frameworks_base/contents/core/res/res/values/public-final.xml?ref=$REF" \
  | python3 -c '
import base64, json, re, sys

xml = base64.b64decode(json.load(sys.stdin)["content"]).decode()
names = {
    name
    for rtype, name in re.findall(r"<public\s+type=\"([^\"]+)\"\s+name=\"([^\"]+)\"", xml)
    if rtype == "color" and name.startswith("system_")
}
sys.stdout.write("".join(n + "\n" for n in sorted(names)))
' > tools/system-colors.txt

echo "tools/system-colors.txt: $(wc -l < tools/system-colors.txt) tokens type=color"
