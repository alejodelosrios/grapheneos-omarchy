# Requisitos de hardware (independientes de la máquina del autor)

Este proyecto **no asume** ningún equipo concreto. Cualquier máquina que cumpla la tabla sirve y
el resultado debe ser reproducible en ella. Hay dos perfiles distintos.

## Máquina de Desarrollo (diseñar RROs, temas y la app; sin build completo)

| Recurso | Mínimo |
|---|---|
| CPU | x86_64 o ARM64, 4 cores |
| RAM | 8 GB |
| Disco | 50 GB libres, FS **ext4 case-sensitive** (no APFS/exFAT) |
| OS | Arch Linux (Omarchy) / Ubuntu 22.04+ / Debian 12 |
| Software | Git, Python 3.11+ (`tomllib`), OpenJDK 17, Android SDK build-tools (`aapt2`) |

Con esto se puede: editar `themes/*/theme.toml`, regenerar paletas (`tools/gen-palette.py`),
compilar RROs sueltos con `aapt2` y probarlos por `adb` en un Pixel con GrapheneOS **de desarrollo**
(`cmd overlay enable`), y desarrollar `OmarchyTheme` contra un build `-userdebug`.

## Servidor de Compilación (ROM completa; **obligatorio x86_64**)

| Recurso | Mínimo | Nota |
|---|---|---|
| CPU | x86_64, 8 cores / 16 threads (Xeon, EPYC, i7 10th gen+) | ARM64 no está soportado como host por el build de AOSP/GrapheneOS |
| RAM | 32 GB (16 GB + 32 GB swap funciona, pero 32 GB evita OOM) | grapheneos.org/build pide "32GiB of memory or more" |
| Disco | 500 GB NVMe libres, ext4 case-sensitive; `ccache` 50-100 GB recomendado | grapheneos.org/build: "100GiB+ of additional free storage space" solo para el build; el árbol + out + releases superan eso |
| Red | 100 Mbps para `repo sync` (~30 GB + imágenes de fábrica de Pixel para adevtool) | |
| OS | Ubuntu 24.04 LTS / Debian bookworm / Arch; paquetes `repo git python3 clang ccache rsync openssl unzip zip yarn/nodejs` (adevtool) | Lista oficial de hosts probados en grapheneos.org/build |
| Tiempo | Primer build 2-4 h (8 cores), incrementales 30-60 min; con 4 cores 6-10 h | |

### Alternativas cloud

- Hetzner AX41 (32 GB / 1 TB NVMe) — dedicado mensual.
- GCP `c2d-highmem-16` — por horas, apagar entre builds.
- GitHub Actions larger runner (64 GB) — solo si el repo es de una org con billing; el plan es un
  **runner self-hosted** sobre el servidor anterior (issue *M3 · CI*).

### Aclaración

Un MacBook Pro M2 (VM Linux) o un MacBook Pro Intel 13" 2020 (16 GB / 256 GB) **no cumplen** el
perfil de compilación: el M2 es ARM64 y el Intel no tiene disco. Ambos sirven para el perfil de
desarrollo. El build de la ROM se hace siempre en el servidor.
