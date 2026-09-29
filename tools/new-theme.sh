#!/usr/bin/env bash
# new-theme.sh <id> — importa un tema de basecamp/omarchy y lo deja listo como paleta RRO
# mutable (design-8 §«tools/new-theme.sh»).
#
# Uso: tools/new-theme.sh <id>      # id = directorio en basecamp/omarchy/themes (p. ej. kanagawa)
#
# Pasos (cada uno deja el artefacto del diseño):
#   1. curl https://raw.githubusercontent.com/basecamp/omarchy/master/themes/<id>/colors.toml
#      (validado con tomllib antes de escribir: juego de claves esperado de 26 + hex #rrggbb,
#      H3 de audit-8; si no valida, exit != 0 sin escribir nada)
#      -> themes/<id>/theme.toml: claves upstream idénticas (mode/colores, verbatim) + cabecera
#         `name` (preservada de upstream si la trae; si no, derivada del id como en tokyo-night
#         -> "Tokyo Night") + tabla [android] con `palette_package` derivado,
#         `theme_style="TONAL_SPOT"`, `font="jetbrains-mono-nerd"` (#6),
#         `icon_shape="rounded-square"` y `themed_icons="true"` (#11, D2). SIN `backgrounds`/fondos
#         (#7): si upstream trajera `font`, `icon_shape`, `themed_icons` o `backgrounds`, se
#         eliminan aquí (van fijos con nuestros defaults).
#   2. Scaffold del RRO espejo de Tokyo Night (mismos ficheros, solo cambian módulo/paquete):
#      overlay/themes/<id>/OmarchyPalette<Id>/{Android.bp,AndroidManifest.xml,res/values/colors.xml}
#      con colors.xml generado por tools/gen-palette.py (194 tokens, cobertura 100%).
#   3. Alta del módulo en el bloque de paletas de omarchy.mk (PRODUCT_PACKAGES, alfabético).
#   4. Línea <overlay ... enabled="false" /> en overlay/config/config.xml (alfabético por paquete).
#
# Derivación de nombres (design-8): kanagawa -> paquete org.omarchy.palette.kanagawa,
# módulo OmarchyPaletteKanagawa (igual que tokyo-night -> tokyonight / OmarchyPaletteTokyoNight).
set -euo pipefail
cd "$(dirname "$0")/.."

id="${1:?uso: tools/new-theme.sh <id>}"
[[ "$id" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "id inválido: $id" >&2; exit 2; }
[ ! -e "themes/$id" ] || { echo "themes/$id ya existe" >&2; exit 2; }

pkg_id="${id//-/}"                       # tokyo-night -> tokyonight
IFS=- read -ra parts <<< "$id"
camel=""; title=""
for p in "${parts[@]}"; do
  camel+="${p^}"                         # tokyo-night -> TokyoNight
  title+="${title:+ }${p^}"              # tokyo-night -> Tokyo Night
done
module="OmarchyPalette$camel"
package="org.omarchy.palette.$pkg_id"

template="overlay/themes/tokyo-night/OmarchyPaletteTokyoNight"
[ -d "$template" ] || { echo "falta plantilla $template" >&2; exit 1; }

# 1. upstream -> themes/<id>/theme.toml
url="https://raw.githubusercontent.com/basecamp/omarchy/master/themes/$id/colors.toml"
raw=$(mktemp); trap 'rm -f "$raw"' EXIT
curl -fsSL "$url" -o "$raw" || { echo "curl falló: $url" >&2; exit 1; }

# H3 (audit-8): valida el colors.toml descargado ANTES de escribir nada — tomllib + juego de
# claves esperado (26: mode + 25 colores) + hex #rrggbb en los colores + mode dark|light.
# name/font/backgrounds se toleran porque el filtro de abajo los elimina (#6/#7). Sin pin SHA
# (decisión PM: la validación basta; el curl solo corre en importación, el build usa lo commiteado).
python3 - "$raw" <<'PY' || { echo "colors.toml de $id ($url) no pasa la validación — no se escribe nada" >&2; exit 1; }
import re, sys, tomllib

expected = {
    "mode", "accent", "selection", "muted", "background", "dark_background",
    "darker_background", "lighter_background", "foreground", "dark_foreground",
    "light_foreground", "bright_foreground", "red", "yellow", "orange", "green",
    "cyan", "blue", "magenta", "brown", "bright_red", "bright_yellow",
    "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
}
allowed_extra = {"name", "font", "icon_shape", "themed_icons", "backgrounds"}
try:
    d = tomllib.loads(open(sys.argv[1]).read())
except Exception as e:
    sys.exit(f"colors.toml ilegible: {e.__class__.__name__}: {e}")
keys = set(d)
missing, extra = sorted(expected - keys), sorted(keys - expected - allowed_extra)
bad = sorted(k for k in expected - {"mode"} - set(missing)
             if not (isinstance(d[k], str) and re.fullmatch(r"#[0-9a-fA-F]{6}", d[k])))
if missing or extra or bad or d.get("mode") not in ("dark", "light"):
    sys.exit(f"colors.toml no esperado: faltan={missing} sobran={extra} "
             f"hex_mal={bad} mode={d.get('mode')!r}")
PY

mkdir -p "themes/$id"
python3 - "$raw" "themes/$id/theme.toml" "$title" "$package" <<'PY'
import re, sys

raw, out, title, package = sys.argv[1:5]
keep, upstream_name = [], None
for line in open(raw):
    m = re.match(r"^(name|font|icon_shape|themed_icons|backgrounds)\s*=", line.strip())
    if m:
        if m.group(1) == "name":
            upstream_name = re.sub(r'^name\s*=\s*', "", line.strip()).strip().strip('"')
        continue  # font/icon_shape/themed_icons de upstream (#6/#11: van fijos con nuestros
                  # defaults) y backgrounds/fondos (#7) quedan fuera
    keep.append(line)
body = "".join(keep).rstrip() + "\n"
name = upstream_name or title  # name/mode "preservados de upstream"; name se deriva del id si no viene
text = (
    f"# Port of basecamp/omarchy themes/{out.split('/')[1]}/colors.toml (MIT). Keys are identical\n"
    f"# so a theme can be re-imported with tools/new-theme.sh; the [android] table is ours.\n"
    f'name = "{name}"\n'
    f"{body}\n"
    f"[android]\n"
    f'palette_package = "{package}"\n'
    f'theme_style = "TONAL_SPOT"   # fallback seed mode if the palette RRO is unavailable\n'
    f'font = "jetbrains-mono-nerd"\n'
    f'icon_shape = "rounded-square"\n'
    f'themed_icons = "true"\n'
)
open(out, "w").write(text)
PY

# 2. scaffold RRO espejo de Tokyo Night
rro="overlay/themes/$id/$module"
[ ! -e "$rro" ] || { echo "$rro ya existe" >&2; exit 2; }
mkdir -p "$rro/res/values"
sed "s/OmarchyPaletteTokyoNight/$module/g; s/org\.omarchy\.palette\.tokyonight/$package/g" \
  "$template/Android.bp" > "$rro/Android.bp"
sed "s/OmarchyPaletteTokyoNight/$module/g; s/org\.omarchy\.palette\.tokyonight/$package/g" \
  "$template/AndroidManifest.xml" > "$rro/AndroidManifest.xml"
python3 tools/gen-palette.py "themes/$id/theme.toml" > "$rro/res/values/colors.xml"

# 3. omarchy.mk (bloque paletas, alfabético) + 4. config.xml (enabled="false", alfabético)
python3 - "$module" "$package" <<'PY'
import re, sys

module, package = sys.argv[1], sys.argv[2]

mk = "omarchy.mk"
text = open(mk).read()
pat = re.compile(r"PRODUCT_PACKAGES \+= \\\n((?:    OmarchyPalette\w+(?: \\\n|\n))+)")
m = pat.search(text)
if not m:
    sys.exit("omarchy.mk: bloque de paletas PRODUCT_PACKAGES no encontrado")
mods = sorted(set(re.findall(r"OmarchyPalette\w+", m.group(1))) | {module})
block = "PRODUCT_PACKAGES += \\\n" + "".join(
    f"    {mod}" + (" \\\n" if i < len(mods) - 1 else "\n") for i, mod in enumerate(mods))
open(mk, "w").write(text[: m.start()] + block + text[m.end():])

cfg = "overlay/config/config.xml"
lines = open(cfg).read().splitlines(keepends=True)
if any(f'package="{package}"' in l for l in lines):
    sys.exit(f"config.xml: {package} ya existe")
idxs = [i for i, l in enumerate(lines) if 'package="org.omarchy.palette.' in l]
pos = next((i for i in idxs
            if re.search(r'package="([^"]+)"', lines[i]).group(1) > package), None)
if pos is None:
    if not idxs:
        sys.exit("config.xml: no hay líneas de paleta donde insertar")
    pos = idxs[-1] + 1
lines.insert(pos, f'    <overlay package="{package}" mutable="true" enabled="false" />\n')
open(cfg, "w").write("".join(lines))
PY

echo "OK $id -> $package / $module"
echo "  themes/$id/theme.toml"
echo "  $rro/{Android.bp,AndroidManifest.xml,res/values/colors.xml}"
echo "  omarchy.mk + overlay/config/config.xml"
