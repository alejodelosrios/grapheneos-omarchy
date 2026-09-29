#!/usr/bin/env bash
# tools/make-wallpapers.sh — fondos Tokyo Night + default_wallpaper.png (determinista, sin red)
#
# Salidas (se sobrescriben en cada corrida):
#   themes/tokyo-night/backgrounds/1-pagoda.jpg
#   themes/tokyo-night/backgrounds/2-moon-lake.jpg
#   themes/tokyo-night/backgrounds/3-city-night.jpg
#   overlay/OmarchyFrameworkOverlay/res/drawable-nodpi/default_wallpaper.png  (1-pagoda.jpg -> PNG)
#
# La paleta NO se escribe aqui: se lee de themes/tokyo-night/theme.toml (claves TOML literales).
# Determinismo byte a byte: sin aleatoriedad (posiciones por aritmetica modular fija) y, en cada
# salida, -strip +set date:create +set date:modify (mas -define png:exclude-chunk=date,time en PNG)
# para que ImageMagick no meta chunks con fecha. Verificacion: correr dos veces y comparar sha256sum.
#
# ImageMagick usado al crearlo (la version del encoder afecta a los bytes):
#   $ magick -version | head -1
#   Version: ImageMagick 7.1.2-32 Q16-HDRI aarch64 68f8d115a:20260926 https://imagemagick.org
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

W=1080
H=2424
BG_DIR="themes/tokyo-night/backgrounds"
WALLPAPER_PNG="overlay/OmarchyFrameworkOverlay/res/drawable-nodpi/default_wallpaper.png"

command -v magick >/dev/null || { echo "magick (ImageMagick 7) no esta en PATH" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 no esta en PATH" >&2; exit 1; }

# --- paleta desde themes/tokyo-night/theme.toml (sin hex en este script) ---
eval "$(python3 - <<'PY'
import tomllib
t = tomllib.load(open("themes/tokyo-night/theme.toml", "rb"))
keys = (
    "background", "dark_background", "darker_background", "lighter_background",
    "accent", "cyan", "bright_foreground", "foreground", "dark_foreground",
    "muted", "yellow", "red",
)
for k in keys:
    print(f'{k.upper()}="{t[k]}"')
PY
)"

# --- flags de determinismo (fechas y metadatos fuera) ---
DET_JPG=(-strip +set date:create +set date:modify -quality 85)
DET_PNG=(-strip +set date:create +set date:modify -define png:exclude-chunk=date,time)

# capa de halo radial con alfa (suave, sin anillos); se compone bajo cada luna
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
HALO="$WORK/halo.png"
magick -size 512x512 "radial-gradient:${BRIGHT_FOREGROUND}-${BRIGHT_FOREGROUND}00" "${DET_PNG[@]}" "$HALO"

# --- helpers MVG (posiciones fijas o aritmetica modular; jamas $RANDOM) ---
linea=""

# estrellas <n> <y_max>: n puntos deterministicos en la franja superior
estrellas() {
  local n=$1 y_max=$2 i x y r o out=""
  for ((i = 0; i < n; i++)); do
    x=$((40 + (i * 137) % 1000))
    y=$((60 + (i * 211) % y_max))
    r=$((2 + (i * 7) % 3))
    o=$((25 + (i * 13) % 45))
    printf -v linea 'fill-opacity 0.%02d fill %s circle %d,%d %d,%d\n' "$o" "$FOREGROUND" "$x" "$y" "$x" "$((y - r))"
    out+="$linea"
  done
  printf '%s' "$out"
}

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

mkdir -p "$BG_DIR" "$(dirname "$WALLPAPER_PNG")"

# --- 1-pagoda.jpg: cielo #1a1b26 -> #0e0e14, luna, pagoda sobre la colina ---
magick -size ${W}x${H} "gradient:${BACKGROUND}-${DARKER_BACKGROUND}" \
  -draw "fill-opacity 0.35 fill ${LIGHTER_BACKGROUND} ellipse 540,1560 700,260 0,360" \
  -draw "$(estrellas 36 1150)" \
  -draw "$(luna 795 470 110)" \
  -draw "$(pagoda)" \
  -draw "fill-opacity 1 fill ${DARKER_BACKGROUND} polygon 0,2424 0,1680 180,1620 420,1550 540,1515 720,1540 920,1600 1080,1660 1080,2424" \
  "${DET_JPG[@]}" "$BG_DIR/1-pagoda.jpg"

# --- 2-moon-lake.jpg: luna centrada sobre agua con reflejo y acentos ---
WATER_TOP=1320
WATER_H=$((H - WATER_TOP))
reflejo=""
# ondas de fondo (muy tenues, anchura por aritmetica modular)
for ((i = 0; i < 14; i++)); do
  y=$((WATER_TOP + 46 + i * 76))
  o=$((16 - i))
  w=$((520 + (i * 61) % 480))
  x=$((30 + (i * 97) % 260))
  printf -v linea 'fill-opacity 0.%02d fill %s rectangle %d,%d %d,%d\n' "$o" "$LIGHTER_BACKGROUND" "$x" "$y" "$((x + w))" "$((y + 4))"
  reflejo+="$linea"
done
# columna de reflejo de la luna: ancha en el horizonte, estrecha al bajar, con destellos asimetricos
for ((i = 0; i < 16; i++)); do
  y=$((WATER_TOP + 24 + i * 40))
  half=$((250 - i * 13))
  [ "$half" -lt 40 ] && half=40
  o=$((46 - i * 2))
  col="$BRIGHT_FOREGROUND"
  case $((i % 4)) in
  2) col="$ACCENT" ;;
  3) col="$CYAN" ;;
  esac
  lext=$((half + (i * 37) % 44 - 22))
  rext=$((half + (i * 23) % 44 - 22))
  [ "$lext" -lt 18 ] && lext=18
  [ "$rext" -lt 18 ] && rext=18
  if [ $((i % 3)) -eq 0 ]; then
    printf -v linea 'fill-opacity 0.%02d fill %s rectangle %d,%d %d,%d\n' "$o" "$col" "$((540 - lext))" "$y" "$((540 + rext))" "$((y + 8))"
    reflejo+="$linea"
  else
    gap=$((10 + (i * 7) % 34))
    printf -v linea 'fill-opacity 0.%02d fill %s rectangle %d,%d %d,%d\n' "$o" "$col" "$((540 - lext))" "$y" "$((540 - gap))" "$((y + 8))"
    reflejo+="$linea"
    printf -v linea 'fill-opacity 0.%02d fill %s rectangle %d,%d %d,%d\n' "$o" "$col" "$((540 + gap))" "$y" "$((540 + rext))" "$((y + 8))"
    reflejo+="$linea"
  fi
done
magick -size ${W}x${H} "gradient:${DARKER_BACKGROUND}-${BACKGROUND}" \
  \( -size ${W}x${WATER_H} "gradient:${DARK_BACKGROUND}-${DARKER_BACKGROUND}" \) -geometry +0+${WATER_TOP} -composite \
  -draw "$(estrellas 28 1050)" \
  -draw "$(luna 540 780 150)" \
  -draw "fill-opacity 1 fill ${DARKER_BACKGROUND} polygon 0,1320 0,1268 150,1180 320,1256 470,1148 640,1240 810,1168 960,1244 1080,1200 1080,1320" \
  -draw "$reflejo" \
  "${DET_JPG[@]}" "$BG_DIR/2-moon-lake.jpg"

# --- 3-city-night.jpg: luna, estrellas, skyline con ventanas encendidas ---
skyline=""
# edificios (x0 ancho techo), izquierda a derecha, sin solapes raros
set -- 10 230 1430 255 175 1270 450 250 1350 720 140 1230 880 190 1400
while [ $# -ge 3 ]; do
  x0=$1 bw=$2 top=$3
  shift 3
  x1=$((x0 + bw))
  printf -v linea 'fill-opacity 1 fill %s rectangle %d,%d %d,%d\n' "$DARKER_BACKGROUND" "$x0" "$top" "$x1" "$H"
  skyline+="$linea"
  for ((y = top + 28; y < H - 60; y += 44)); do
    for ((x = x0 + 14; x < x1 - 20; x += 30)); do
      if ((((x * 7 + y * 13) % 5) < 2)); then
        col="$YELLOW"
        case $(((x + y) % 3)) in
        1) col="$ACCENT" ;;
        2) col="$CYAN" ;;
        esac
        printf -v linea 'fill-opacity 0.85 fill %s rectangle %d,%d %d,%d\n' "$col" "$x" "$y" "$((x + 12))" "$((y + 18))"
        skyline+="$linea"
      fi
    done
  done
done
# antena con luz roja sobre el edificio de x0=720
printf -v linea 'fill-opacity 1 fill %s rectangle 788,1150 794,1230\n' "$DARKER_BACKGROUND"
skyline+="$linea"
printf -v linea 'fill-opacity 1 fill %s circle 791,1144 791,1139\n' "$RED"
skyline+="$linea"
magick -size ${W}x${H} "gradient:${DARKER_BACKGROUND}-${BACKGROUND}" \
  -draw "fill-opacity 0.4 fill ${LIGHTER_BACKGROUND} ellipse 540,1620 820,300 0,360" \
  -draw "$(estrellas 30 900)" \
  -draw "$(luna 230 360 80)" \
  -draw "$skyline" \
  "${DET_JPG[@]}" "$BG_DIR/3-city-night.jpg"

# --- default_wallpaper.png: conversion del primer fondo (misma fuente, reproducible) ---
magick "$BG_DIR/1-pagoda.jpg" "${DET_PNG[@]}" "$WALLPAPER_PNG"

echo "OK: fondos + default_wallpaper.png generados"
sha256sum "$BG_DIR/1-pagoda.jpg" "$BG_DIR/2-moon-lake.jpg" "$BG_DIR/3-city-night.jpg" "$WALLPAPER_PNG"
