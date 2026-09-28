# grapheneos-omarchy

**OmarchyOS**: GrapheneOS con la estética de [Omarchy](https://omarchy.org) (Tokyo Night por
defecto) y **temas conmutables** como en el escritorio, sin tocar una sola línea de los repos de
seguridad de GrapheneOS. Este repo es `vendor/omarchy/` dentro del árbol de GrapheneOS.

> Not GrapheneOS and not affiliated with the GrapheneOS project. Built on top of it.

## Qué hace

- **Piel base** (RROs estáticos en `product`): esquinas Hyprland, shade de notificaciones y Quick
  Settings estilo Waybar/Mako (bordes de 1dp, radio 12dp, densidad), forma de iconos, fuente
  JetBrainsMono Nerd, bootanimation.
- **Temas conmutables**: un RRO de paleta por tema (`themes/<id>/theme.toml` = `colors.toml` de
  Omarchy) activado en la categoría `android.theme.customization.system_palette`; SystemUI,
  Launcher3, Settings y toda app Material You cambian con él.
- **App `OmarchyTheme`** (priv-app): picker, tile de QS, `omarchy-theme-set` en Android.
- **API para apps**: `content://org.omarchy.theme/current` + broadcast `org.omarchy.theme.CHANGED`
  + librería Kotlin, para que una app lea el tema y se adapte igual que las plantillas de Omarchy.
- **Seguridad intacta**: `frameworks/base`, `system/core`, kernel, `bionic`… no se modifican; el
  OTA mensual de GrapheneOS entra con `repo sync`.

## Cómo se engancha (sin forks)

```
vendor/omarchy/adevtool/tegu.yml  --includes-->  vendor/adevtool/config/device/tegu.yml
                                  --adds----->  platform.extra_product_makefiles: [vendor/omarchy/omarchy.mk]
adevtool generate-all -d vendor/omarchy/adevtool/tegu.yml   # device/google/tegu/tegu.mk incluye omarchy.mk
```

## Docs

- [`docs/research.md`](docs/research.md) — investigación con `archivo:línea` verificados en la rama 17.
- [`docs/HARDWARE.md`](docs/HARDWARE.md) — requisitos de desarrollo vs. servidor de compilación.
- [`docs/BUILD.md`](docs/BUILD.md) — `repo init` → `lunch` → `m` → `generate-release.sh`.
- [`docs/THEMING.md`](docs/THEMING.md) — anatomía de un tema, cambio de tema, API para apps.

## Roadmap

Issues del repo, agrupados en milestones M0 Infra → M1 Piel base → M2 Motor de temas → M3
Build & Release → M4 Mantenimiento. Tablero: GitHub Project "GrapheneOS Omarchy Roadmap".

## Requisitos mínimos del servidor de build

x86_64, 8 cores/16 threads, 32 GB RAM, 500 GB NVMe ext4 (ver `docs/HARDWARE.md`). Dispositivos
objetivo iniciales: Pixel 9a (`tegu`) y Pixel 9 Pro Fold (`comet`).

## Licencia

MIT. GrapheneOS (MIT/Apache-2.0), Omarchy (MIT), Tokyo Night (MIT), JetBrains Mono (OFL-1.1).
