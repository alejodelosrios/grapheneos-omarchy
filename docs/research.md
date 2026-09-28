# Investigación — GrapheneOS + piel Omarchy (temas conmutables)

Fecha: 2026-09-28. Todo lo citado como `archivo:línea` fue verificado ese día contra la rama `17`
de los repos de GrapheneOS en GitHub (no contra memoria). Fuentes web al final de cada sección.

**Resultado primero.** El proyecto es viable sin tocar ningún repo forkeado por GrapheneOS: Android
ya trae (y GrapheneOS conserva) el motor de temas por categorías de overlay que usa ThemePicker, y
SystemUI lo aplica desde un solo `Settings.Secure`. Nuestro trabajo cabe entero en `vendor/omarchy/`
(RROs + una priv-app + fuentes + catálogo de temas) y se engancha al build por un YAML de adevtool
que hereda del upstream. Las apps de terceros se adaptan por dos vías: la estándar (Material You /
`system_accent*`) sin integrar nada, y un `ContentProvider` para las que quieran la paleta Omarchy
exacta (equivalente a `~/.config/omarchy/current/theme`).

---

## 1. Estructura de GrapheneOS y fork ligero

### 1.1 Manifest y ramas

| Dato | Valor verificado |
|---|---|
| Manifest | `https://github.com/GrapheneOS/platform_manifest` |
| Ramas vivas | `17` (desarrollo, `aosp_revision: android-17.0.0_r1`), `16-qpr2`, `tmp` |
| Stable actual | tag `2026091900` para los 21 dispositivos (Pixel 6 → Pixel 10a) |
| Repos forkeados de AOSP | 92 (`config.yml` → `forked_aosp_repos`), entre ellos `frameworks/base`, `frameworks/libs/systemui`, `packages/apps/{Launcher3,Settings,ThemePicker,WallpaperPicker2}`, `system/core`, `build/soong`, `bionic` |
| Repos propios (`additional_projects`) | 47: `script`, `vendor/adevtool`, `vendor/state`, `branding`, `packages/apps/Updater`, `external/vanadium`, kernels por familia… |
| Init | `repo init -u https://github.com/GrapheneOS/platform_manifest.git -b refs/tags/2026091900` (stable) o `-b 17` (dev) |

`config.yml` (rama 17) es la fuente de verdad de qué está forkeado: cualquier path listado en
`forked_aosp_repos` o `additional_projects` es **zona prohibida** para este proyecto.

### 1.2 Ciclo OTA mensual

- GrapheneOS publica releases con tag `YYYYMMDDNN` (p. ej. `2026091900`) en tres canales
  (`stable`/`beta`/`alpha`). El `Updater` (paquete `app.seamlessupdate.client`) lee
  `packages/apps/Updater/res/values/config.xml`: `url = https://releases.grapheneos.org/`,
  `channel_default = stable`. El repo del Updater no declara `<overlayable>`, así que un RRO
  preinstalado en `product` con `targetPackage="app.seamlessupdate.client"` puede sobreescribir solo
  `url` sin forkear la app. Se valida en el issue *M0 · Keys + OTA*.
- El servidor OTA es estático: `<device>-ota_update-<build>.zip` + metadata generada por
  `script/generate-metadata` (`script/generate-release.sh:127-129`).

### 1.3 Cómo se genera el árbol de dispositivo (clave para el hook)

Los `device/google/<codename>/` **no están en el manifest**: los genera `adevtool` en local
(`adevtool generate-all -d tegu`). `vendor/adevtool/src/build/make.ts:205-211` escribe
`PRODUCT_NAME := tegu` / `PRODUCT_DEVICE := tegu` y `make.ts:188-190` añade un `include` por cada
entrada de `config.platform.extra_product_makefiles` del YAML de dispositivo.

`adevtool` acepta **una ruta** a YAML en vez de un nombre (`src/config/device.ts:343-357`),
resuelve `includes` relativo al archivo que los declara y **concatena arrays** al fusionar
(`src/config/config-loader.ts:10-31`). Por tanto:

```yaml
# vendor/omarchy/adevtool/tegu.yml
includes: [ ../../adevtool/config/device/tegu.yml ]
platform:
  extra_product_makefiles: [ vendor/omarchy/omarchy.mk ]
```

`adevtool generate-all -d vendor/omarchy/adevtool/tegu.yml` produce el mismo `device/google/tegu`
de siempre más una línea `include vendor/omarchy/omarchy.mk`. **Cero cambios en repos de
GrapheneOS, cero conflictos de rebase.** El nombre del producto sigue siendo `tegu`, obligatorio
porque `script/finalize.sh:16-17` y `script/generate-release.sh:29-31` construyen
`$TARGET_PRODUCT-target_files.zip` / `$DEVICE-otatools.zip` a partir de él (un producto `omarchy_tegu`
rompería los scripts de firma).

Alternativa descartada: definir un producto nuevo en `vendor/omarchy/AndroidProducts.mk` (lo
descubre `build/make/core/product_config.mk:151`), porque obliga a renombrar el producto.

### 1.4 Rebase mensual

Con la arquitectura anterior el "rebase" es `repo sync` + rebuild: `vendor/omarchy` es un proyecto
extra en `.repo/local_manifests/omarchy.xml` y no toca nada. Riesgo residual real: que un release
renombre un recurso que overlayamos (`qs_corner_radius`, `config_qsTileStrokeWidthActive`…). Un RRO
con un recurso inexistente **falla en build** (aapt2: "resource not found"), así que se detecta en CI,
no en el teléfono. Procedimiento en `docs/BUILD.md §6`.

Fuentes: <https://grapheneos.org/source>, <https://grapheneos.org/build>, <https://grapheneos.org/releases>,
`platform_manifest/config.yml@17`, `adevtool/src/{build/make.ts,config/device.ts,config/config-loader.ts}@17`,
`script/{finalize.sh,generate-release.sh}`.

---

## 2. Sistema RRO / Overlay y cómo Android ya conmuta temas

### 2.1 Tipos de overlay

| Tipo | Qué es | Cuándo lo usamos |
|---|---|---|
| **Estático** (`android:isStatic="true"`) | Preinstalado, siempre activo, inmutable. Único tipo que afecta a `Resources.getSystem()` sobre `android`. | Base de la piel independiente del tema: esquinas, márgenes del shade, borde de tiles QS, fuente. |
| **Mutable** (sin `isStatic`, estado en `/product/overlay/config/config.xml`) | Preinstalado, se enciende/apaga en runtime con `OverlayManager` / `cmd overlay`. Con `android:category` participa de "uno-activo-por-categoría" (`setEnabledExclusiveInCategory`). | **Un RRO de paleta por tema** (Tokyo Night, Catppuccin, Nord…). |
| **Fabricado (FRRO)** | Creado en runtime por código con `FabricatedOverlay` (Android 12+); solo colores/dimens/strings/bools. Es lo que SystemUI usa para Monet. | No lo creamos nosotros; SystemUI lo genera cuando el tema pide "seed" en vez de paquete. |

Precedencia por partición (menor → mayor): `system < vendor < odm < oem < product < system_ext`
(orden por defecto; `OverlayConfig.java:76` permite `/product/overlay/partition_order.xml`).
Todo lo nuestro va en **`product`**, por encima de los overlays de Pixel en `vendor` y por debajo de
SystemUI/Launcher3 que viven en `system_ext` (`build/make/target/product/handheld_system_ext.mk:27-32`).

`<overlayable>`: en la rama 17 **ni `android` (core/res) ni SystemUI ni Settings ni Launcher3
declaran `overlayable.xml`** (búsqueda en los cuatro árboles; solo aparece en
`packages/CredentialManager/wear`). Sin `<overlayable>`, un overlay **preinstalado** puede cubrir
cualquier recurso; uno instalado a posteriori no. Es exactamente nuestro caso.

### 2.2 El motor de temas que Android ya trae (y GrapheneOS conserva)

GrapheneOS incluye `ThemePicker` en product (`handheld_product.mk:41`) y su SystemUI aplica temas
por **categorías** de overlay. Constantes verificadas en
`packages/SystemUI/src/com/android/systemui/theme/ThemeOverlayApplier.java:70-132` y
`ThemePicker/src/com/android/customization/model/ResourceConstants.java`:

```
android.theme.customization.system_palette   -> target android   (paleta system_*)
android.theme.customization.accent_color     -> target android
android.theme.customization.dynamic_color    -> target android   (tokens A14+: system_primary_*, surface…)
android.theme.customization.theme_style      -> TONAL_SPOT | VIBRANT | EXPRESSIVE | ...
android.theme.customization.font             -> target android   (config_bodyFontFamily / headline)
android.theme.customization.adaptive_icon_shape -> target android (config_icon_mask)
android.theme.customization.icon_pack.{android,systemui,settings,launcher,themepicker}
android.theme.customization.color_source     -> preset | home_wallpaper | lock_wallpaper
```

Todo se controla desde **un solo setting**: `Settings.Secure.THEME_CUSTOMIZATION_OVERLAY_PACKAGES`
(JSON categoría → paquete o color). `ThemeOverlayController.java:356-398` lo observa y
`ThemeOverlayApplier` hace `setEnabledExclusiveInCategory` por categoría (una sola activa).

### 2.3 Paleta exacta vs. paleta derivada (Monet)

`ThemeOverlayController.java:786-796`:

```java
OverlayIdentifier systemPalette = categoryToPackage.get(OVERLAY_CATEGORY_SYSTEM_PALETTE);
if (mIsMonetEnabled && systemPalette != null && systemPalette.getPackageName() != null) {
    try { createOverlays(Color.parseColor(colorString)); ... }   // hex -> FRROs Monet
    catch (Exception e) { Log.w(TAG, "Invalid color definition: " ...); } // paquete -> se conserva
}
// "Compatibility with legacy themes, where full packages were defined, instead of just colors."
```

Es decir, la misma categoría admite **dos modos**:

| Modo | Valor en el JSON | Resultado | Uso |
|---|---|---|---|
| **Paquete** (recomendado) | `"…system_palette": "org.omarchy.palette.tokyonight"` | Se activa nuestro RRO que define los 65 `system_{accent1..3,neutral1,2}_{0..1000}` (+ tokens A14+) con los hex **exactos** de `colors.toml`. SystemUI **no** fabrica Monet. | Temas Omarchy. |
| **Seed** | `"…system_palette": "7aa2f7"`, `color_source: preset`, `theme_style: TONAL_SPOT` | SystemUI genera FRROs con Material Color Utilities: colores *parecidos*, no exactos. Cero recursos nuestros. | Fallback / temas sin RRO generado. |

`flag_monet` sigue en `true` en GrapheneOS (`packages/SystemUI/res/values/flags.xml:21`), así que
el modo seed funciona tal cual y el modo paquete lo esquiva por el `catch` anterior.

Las 201 entradas `system_*` públicas (`core/res/res/values/public-final.xml`) son las que leen
Material Components (`DynamicColors.applyToActivitiesIfAvailable`) y Compose
(`dynamicDarkColorScheme`). Por eso **cualquier app con dynamic color se adapta sola** al tema
Omarchy elegido, sin conocer Omarchy: es la vía "cero integración". Los colores del shade de
notificaciones derivan de esos mismos tokens (`packages/SystemUI/res/values/colors.xml:40-44`:
`notification_scrim_base → system_accent1_100`, `shade_panel_fallback → system_accent2_200`).

### 2.4 Qué necesita nuestra app para conmutar (equivalente a `omarchy-theme-set`)

| Paso | API | Permiso | Verificado en |
|---|---|---|---|
| Activar RRO de paleta | `OverlayManager.setEnabledExclusiveInCategory(pkg, UserHandle.CURRENT)` | `CHANGE_OVERLAY_PACKAGES` (signature\|privileged) + `INTERACT_ACROSS_USERS` | `core/java/android/content/om/OverlayManager.java:169-175`, `OverlayManagerService.java:775` |
| Que SystemUI lo asuma y aplique fuente/forma | escribir el JSON en `Settings.Secure.theme_customization_overlay_packages` | `WRITE_SECURE_SETTINGS` | `ThemeOverlayController.java:356,498` |
| Modo claro/oscuro (`mode` del `colors.toml`) | `UiModeManager.setNightMode` | `MODIFY_DAY_NIGHT_MODE` | AOSP |
| Fondo | `WallpaperManager.setStream(...)` | `SET_WALLPAPER` (normal) | AOSP |

→ `OmarchyTheme` es una **priv-app en `/product/priv-app` firmada con `platform`** y con
`privapp-permissions-org.omarchy.theme.xml` (ya en el esqueleto). Sin permisos de firma nada de
esto es posible desde una app normal: es la razón de que el tema viva en la ROM.

Riesgo a validar en dispositivo (issue *M2 · OmarchyTheme*): SELinux `platform_app` alcanzando
`overlay_service`. Mitigación de un paso: `sharedUserId="android.uid.system"` (ya declarado en el
manifest) → dominio `system_app`.

### 2.5 Fuentes y forma de iconos

- Fuentes OEM: `graphics/java/android/graphics/fonts/SystemFonts.java:65-67` lee
  `/product/etc/fonts_customization.xml` y `/product/fonts/`. Con `new-named-family` se registra
  `jetbrains-mono-nerd`, y el RRO de categoría `font` pone `config_bodyFontFamily`/`config_headlineFontFamily`
  (`core/res/res/values/config.xml:5556,5643`).
- Forma: `config_icon_mask` (`config.xml:5062`) por RRO de categoría `adaptive_icon_shape`.
- Esquinas: `rounded_corner_radius` (`config.xml:7282`), `notification_corner_radius`
  (`SystemUI/res/values/dimens.xml:355`), `qs_corner_radius` (`:705`).
- Borde estilo Mako/Hyprland en tiles QS: `config_qsTileStrokeWidthActive/Inactive`
  (`SystemUI/res/values/config.xml:374-375`, `-1dp` = sin borde en stock).
- Boot animation: `/product/media/bootanimation.zip` y `bootanimation-dark.zip`
  (`cmds/bootanimation/BootAnimation.cpp:76-78`).

Fuentes: <https://source.android.com/docs/core/runtime/rros>,
<https://developer.android.com/develop/ui/views/theming/dynamic-colors>, código citado.

---

## 3. Mapeo Omarchy → Android

Omarchy es un conjunto de **plantillas** que `omarchy-theme-set` rellena con `colors.toml` y
reenvía por IPC a `omarchy-shell` (`bin/omarchy-theme-set:120` `shell applyTheme "$colors_payload"`).
El análogo Android es: RRO de paleta + JSON de SystemUI + broadcast/ContentProvider para apps.

| Omarchy (desktop) | Android | Viabilidad | Técnica |
|---|---|---|---|
| `themes/<t>/colors.toml` | `themes/<t>/theme.toml` (mismas claves) → `OmarchyPalette<T>` RRO | ✅ | `tools/gen-palette.py`, categoría `system_palette` |
| `omarchy-theme-set` / `omarchy-theme-switcher` (walker) | `OmarchyTheme`: picker + tile QS "Theme" | ✅ | §2.4 |
| `omarchy-theme-bg-next` | tile/acción "Next wallpaper" (cicla `backgrounds/`) | ✅ | `WallpaperManager` |
| `mode = dark/light` | `UiModeManager` night mode | ✅ | `MODIFY_DAY_NIGHT_MODE` |
| Waybar (barra, pills) | Status bar + Quick Settings | ✅ parcial | `OmarchySystemUIOverlay`: `qs_corner_radius`, `qs_tile_margin_*`, `config_qsTileStrokeWidth*`, colores vía tokens. Layouts XML también son overlayables pero se evita (frágil mes a mes). |
| Mako / notificaciones de omarchy-shell (bg oscuro, borde acento, radio 8-12) | Shade de notificaciones | ✅ parcial | `notification_corner_radius`, `drawable/notification_material_bg.xml` (layer-list con `<stroke>` ya existente → borde de color acento), fondo vía `system_neutral1_*`/`surface_container`. **Animaciones y comportamiento no** (sería Java en SystemUI = prohibido). |
| Hyprland (gaps, rounding, borders) | Esquinas de ventana/diálogos | ✅ | `rounded_corner_radius`, `config_dialogCornerRadius` |
| Hyprlock | Lockscreen | ⚠️ | Solo colores/fondo/fuente por tokens; reloj Compose de A17 no es overlayable en layout. |
| Walker (launcher) | Launcher3 (GrapheneOS lo forkea) / Lawnchair opcional | ✅ | Launcher3 usa `system_*` + `icon_pack.launcher`; Lawnchair queda como app instalable, no de ROM. |
| Alacritty/Ghostty + JetBrainsMono Nerd | Fuente de sistema | ✅ | §2.5; Nerd glyphs funcionan en `TextView` |
| btop / Neovim | n/a (apps de terceros vía API §4) | — | — |
| `~/.config/omarchy/current/theme` (lo que leen las apps) | `content://org.omarchy.theme/current` + `org.omarchy.theme.CHANGED` + tokens `system_*` | ✅ | `apps/OmarchyTheme/…/ThemeContract.kt` |
| Plymouth (boot) | `bootanimation.zip` | ✅ | `/product/media` |
| `omarchy-theme-install <git>` (temas de terceros) | ❌ en v1 | — | Un tema = RRO firmado en la ROM; instalar temas de terceros exigiría FRRO + validación → fuera de alcance (riesgo de seguridad y de firma). |

---

## 4. API para apps de terceros (equivalente a las plantillas de Omarchy)

Tres niveles, del más barato al más rico para el desarrollador de la app:

1. **Cero integración**: la app usa Material You (`DynamicColors.applyToActivitiesIfAvailable`,
   `dynamicDarkColorScheme`). Al cambiar de tema, SystemUI reactiva el RRO de paleta y el sistema
   recrea las Activities con los nuevos `system_*`. Funciona igual en un Pixel stock (allí con Monet).
2. **Paleta Omarchy exacta**: `ContentResolver.query(ThemeContract.CURRENT)` devuelve una fila con
   todas las claves de `theme.toml` (`accent`, `background`, `red`… + `id`, `name`, `mode`);
   `THEMES` lista las instaladas. Broadcast `org.omarchy.theme.CHANGED` tras cada cambio. Es la
   copia 1:1 de leer `current/theme/colors.toml`.
3. **Librería** `omarchy-theme-android` (Kotlin, Maven Central, issue M2): `OmarchyTheme.current(ctx)`,
   `Flow<OmarchyTheme>`, `OmarchyColorScheme()` para Compose con **fallback a `dynamicColorScheme`**
   cuando el provider no existe (misma app corre en cualquier Android 12+).

Comparativa con OEM: One UI / Nothing OS meten el motor de temas en `system_ext` con SystemUI
forkeado y "Theme Park"/"Galaxy Themes" como app de plataforma; Nothing usa paquetes de iconos por
`icon_pack.*` como aquí. Nosotros mantenemos SystemUI intacto y solo la app en `product`, que es
la partición pensada para personalización del fabricante (`handheld_product.mk`), y por eso
sobrevive al OTA de GrapheneOS sin merge.

---

## 5. Riesgos

| Riesgo | Impacto | Lectura verificada | Mitigación |
|---|---|---|---|
| **Play Integrity / SafetyNet** | Apps bancarias | GrapheneOS pasa `basicIntegrity`, falla `ctsProfileMatch`/device/strong porque la clave de Verified Boot no es de Google (<https://grapheneos.org/usage#banking-apps>). Nuestra ROM está en el mismo caso, con nuestra clave: **ni mejor ni peor**. | No prometer banca. Sandboxed Google Play funciona igual. |
| **Auditor / atestación** | Auditor no reconocerá la ROM como GrapheneOS | Auditor verifica el hash de la clave de VB conocida. | Documentar; opcional: fork de Auditor con nuestra clave (fuera de alcance). |
| **Kernel / CVEs** | Ninguno añadido | No tocamos kernel, bionic, framework: los parches llegan enteros con `repo sync`. Solo añadimos una priv-app con permisos de firma → superficie: el propio `OmarchyTheme`. | Código mínimo, sin red, sin exportar nada escribible (`ThemeProvider` read-only). |
| **Rebase mensual** | Build roto por recurso renombrado | RRO con recurso inexistente falla en aapt2 (detectable en CI). | Issue *M3 · rebase*: build en CI el día del release. |
| **Nombre/marca** | Licencia | FAQ de GrapheneOS: derivados permitidos "provided that they make it clear that they're not GrapheneOS or officially associated" (<https://grapheneos.org/faq>). | El producto se llama **OmarchyOS (based on GrapheneOS)**; `ro.omarchy.version` en `omarchy.mk`; no se reutiliza `branding/`. El nombre del repo `grapheneos-omarchy` es descriptivo, no marca. |
| **Licencias** | Compatibilidad | GrapheneOS propio: MIT; AOSP: Apache-2.0; kernel: GPL-2.0 (no se toca); Omarchy: MIT (verificado en GitHub); Tokyo Night / Catppuccin / Nord / Gruvbox: MIT; JetBrains Mono: OFL-1.1; Nerd Fonts patcher: MIT. **Wallpapers de Omarchy: licencia por archivo no verificada** (`themes/tokyo-night/backgrounds/*.webp`). | Repo MIT. Wallpapers no se copian hasta confirmar por archivo (`themes/*/backgrounds/ATTRIBUTION.md`). |
| **Contraste / accesibilidad** | Textos ilegibles con paleta exacta | Los tonos 0-1000 de `gen-palette.py` son una mezcla lineal (no HCT). | Issue *M2 · paleta*: revisar contraste WCAG por tema; upgrade a material-color-utilities si hace falta. |
| **Compatibilidad Android 14+ tokens** | Apps Compose en API 34+ leen `system_primary_*`… | 201 colores públicos; el RRO debe cubrirlos o esos roles caen al valor stock. | Generador emite ambas tablas (issue M2 · paleta). |
