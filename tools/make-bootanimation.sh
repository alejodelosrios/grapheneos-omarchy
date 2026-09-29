#!/usr/bin/env bash
# tools/make-bootanimation.sh — frames PNG + bootanimation/bootanimation.zip (determinista, sin red)
#
# Salida: bootanimation/bootanimation.zip (los frames son intermedios: se generan en un temporal
# y viven dentro del zip; no se versionan sueltos).
#
# Contenido por frame: fondo plano #1a1b26 + luna + silueta de pagoda + puntos de progreso.
# Estructura (desc.txt primero):
#   desc.txt          -> "1080 2424 30" / "p 1 0 part0" / "p 0 0 part1"
#   part0/frameNNN.png  intro (se reproduce una vez, sin loop): el arte aparece con fade-in
#   part1/frameNNN.png  loop: 3 puntos de progreso que ciclan
#
# Determinismo byte a byte: posiciones fijas o aritmetica modular (sin $RANDOM), cada PNG con
# -strip +set date:create +set date:modify -define png:exclude-chunk=date,time y paleta de 32
# colores sin dithering (artefacto plano = PNG de KB, no de MB), y el zip lo monta Python stdlib
# zipfile con ZIP_STORED y date_time fijo (1980-01-01), jamas el binario `zip`.
# Verificacion: correr dos veces y comparar sha256sum del zip.
#
# ImageMagick usado al crearlo (la version del encoder afecta a los bytes de los PNG):
#   $ magick -version | head -1
#   Version: ImageMagick 7.1.2-32 Q16-HDRI aarch64 68f8d115a:20260926 https://imagemagick.org
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

W=1080
H=2424
OUT="bootanimation/bootanimation.zip"
N_PART0=18 # frames de intro
N_PART1=24 # frames del loop (8 frames por punto)

command -v magick >/dev/null || { echo "magick (ImageMagick 7) no esta en PATH" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 no esta en PATH" >&2; exit 1; }

# --- paleta desde themes/tokyo-night/theme.toml (sin hex en este script) ---
eval "$(python3 - <<'PY'
import tomllib
t = tomllib.load(open("themes/tokyo-night/theme.toml", "rb"))
keys = ("background", "darker_background", "accent", "cyan", "bright_foreground", "muted")
for k in keys:
    print(f'{k.upper()}="{t[k]}"')
PY
)"

# --- flags de determinismo (fechas y metadatos fuera de cada PNG) ---
DET_PNG=(-strip +set date:create +set date:modify -define png:exclude-chunk=date,time)
# frames: ademas paleta de 32 colores sin dithering -> PNG de KB (no de MB), plano y comprimible
DET_FRAME=(-strip +set date:create +set date:modify -define png:exclude-chunk=date,time +dither -colors 32)

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/part0" "$WORK/part1"

# capa de halo radial con alfa (suave, sin anillos)
HALO="$WORK/halo.png"
magick -size 512x512 "radial-gradient:${BRIGHT_FOREGROUND}-${BRIGHT_FOREGROUND}00" "${DET_PNG[@]}" "$HALO"

# luna <cx> <cy> <r>: halo radial suave + disco #c0caf5
luna() {
  local cx=$1 cy=$2 r=$3
  local s=$((r * 4))
  cat <<EOF
image Over $((cx - s / 2)),$((cy - s / 2)) ${s},${s} '${HALO}'
fill-opacity 1 fill ${BRIGHT_FOREGROUND} circle ${cx},${cy} ${cx},$((cy - r))
EOF
}

# pagoda: silueta de 3 cuerpos + aleros + aguja, ventanas accent y faroles cyan
pagoda() {
  cat <<EOF
fill-opacity 1 fill ${DARKER_BACKGROUND} rectangle 380,1492 700,1520
fill-opacity 1 fill ${DARKER_BACKGROUND} rectangle 415,1272 665,1500
fill-opacity 1 fill ${DARKER_BACKGROUND} polygon 330,1348 750,1348 650,1272 430,1272
fill-opacity 1 fill ${DARKER_BACKGROUND} rectangle 455,1120 625,1272
fill-opacity 1 fill ${DARKER_BACKGROUND} polygon 378,1192 702,1192 618,1120 462,1120
fill-opacity 1 fill ${DARKER_BACKGROUND} rectangle 480,980 600,1120
fill-opacity 1 fill ${DARKER_BACKGROUND} polygon 415,1046 665,1046 592,980 488,980
fill-opacity 1 fill ${DARKER_BACKGROUND} rectangle 534,880 546,980
fill-opacity 1 fill ${DARKER_BACKGROUND} circle 540,875 540,866
fill-opacity 0.9 fill ${ACCENT} rectangle 455,1360 485,1400
fill-opacity 0.9 fill ${ACCENT} rectangle 525,1360 555,1400
fill-opacity 0.9 fill ${ACCENT} rectangle 595,1360 625,1400
fill-opacity 0.9 fill ${ACCENT} rectangle 500,1205 525,1238
fill-opacity 0.9 fill ${ACCENT} rectangle 555,1205 580,1238
fill-opacity 0.9 fill ${ACCENT} rectangle 515,1058 533,1088
fill-opacity 0.9 fill ${ACCENT} rectangle 548,1058 566,1088
fill-opacity 1 fill ${CYAN} circle 348,1352 348,1346
fill-opacity 1 fill ${CYAN} circle 732,1352 732,1346
EOF
}

linea=""
# progreso <activo>: 3 puntos bajo la pagoda; el activo en accent, el resto muted
progreso() {
  local activo=$1 j x col out=""
  for j in 0 1 2; do
    x=$((460 + j * 80))
    col="$MUTED"
    [ "$j" -eq "$activo" ] && col="$ACCENT"
    printf -v linea 'fill-opacity 1 fill %s circle %d,1680 %d,1662\n' "$col" "$x" "$x"
    out+="$linea"
  done
  printf '%s' "$out"
}

# frame <salida> <opacidad-del-arte 0..1> <punto-activo o -1>
frame() {
  local out=$1 t=$2 activo=$3
  local arte
  arte="$(luna 540 640 130)"$'\n'
  arte+="$(pagoda)"$'\n'
  [ "$activo" -ge 0 ] && arte+="$(progreso "$activo")"$'\n'
  magick -size ${W}x${H} "xc:${BACKGROUND}" \
    \( -size ${W}x${H} xc:none -draw "$arte" -channel A -evaluate multiply "$t" +channel \) \
    -compose over -composite "${DET_FRAME[@]}" "$out"
}

# --- part0: intro sin loop, el arte entra con fade-in ---
for ((i = 0; i < N_PART0; i++)); do
  t=$(awk "BEGIN { printf \"%.4f\", ($i + 1) / $N_PART0 }")
  frame "$WORK/part0/$(printf 'frame%03d.png' "$i")" "$t" -1
done

# --- part1: loop, 3 puntos de progreso ciclando (8 frames por punto) ---
for ((i = 0; i < N_PART1; i++)); do
  frame "$WORK/part1/$(printf 'frame%03d.png' "$i")" 1 $((i / 8 % 3))
done

# --- zip: Python stdlib zipfile, ZIP_STORED y date_time fijo ---
python3 - "$WORK" "$OUT" <<'PY'
import os
import sys
import zipfile

work, out = sys.argv[1], sys.argv[2]
DATE_TIME = (1980, 1, 1, 0, 0, 0)  # fijo: sin fecha de compilacion en el zip
DESC = "1080 2424 30\np 1 0 part0\np 0 0 part1\n"


def info(arcname):
    zi = zipfile.ZipInfo(arcname, date_time=DATE_TIME)
    zi.compress_type = zipfile.ZIP_STORED
    zi.create_system = 3
    zi.external_attr = 0o644 << 16
    return zi


with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    z.writestr(info("desc.txt"), DESC)
    for part in ("part0", "part1"):
        d = os.path.join(work, part)
        for name in sorted(os.listdir(d)):
            with open(os.path.join(d, name), "rb") as f:
                z.writestr(info(f"{part}/{name}"), f.read())
PY

echo "OK: $OUT"
unzip -lv "$OUT" | tail -3
sha256sum "$OUT"
