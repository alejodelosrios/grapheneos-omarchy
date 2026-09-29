# THEMING — temas conmutables y API para apps

## Anatomía de un tema

```
themes/<id>/theme.toml            # copia de themes/<id>/colors.toml de Omarchy + [android]
themes/<id>/backgrounds/*.jpg     # fondos (licencia verificada por archivo)
overlay/themes/<id>/OmarchyPalette<Id>/   # RRO generado: 65 system_* (+ tokens A14+)
```

`theme.toml` usa **las mismas claves que Omarchy** (`accent`, `background`, `foreground`, `red`…
`bright_magenta`, `mode`), así que importar un tema nuevo es copiar el archivo y correr:

```bash
tools/gen-palette.py themes/nord/theme.toml > overlay/themes/nord/OmarchyPaletteNord/res/values/colors.xml
# + Android.bp / AndroidManifest.xml (package org.omarchy.palette.nord, misma categoría)
# + línea en omarchy.mk (PRODUCT_PACKAGES) y en overlay/config/config.xml (mutable, enabled=false)
```

Mapeo de roles (`tools/gen-palette.py` → `ROLES`):

| AOSP | theme.toml | Ejemplo Tokyo Night |
|---|---|---|
| `system_accent1_*` | `accent` | `#7aa2f7` |
| `system_accent2_*` | `magenta` | `#ad8ee6` |
| `system_accent3_*` | `cyan` | `#449dab` |
| `system_neutral1_*` | `background` | `#1a1b26` |
| `system_neutral2_*` | `lighter_background` | `#24283b` |

El tono 500 es el color exacto; 0→blanco y 1000→negro por mezcla lineal (v0). Las apps Material You
leen estos tokens: **Launcher3, Settings, SystemUI, el shade de notificaciones y cualquier app con
dynamic color cambian con el tema sin conocer Omarchy**.

## Cambiar de tema (lo que hace `OmarchyTheme`, = `omarchy-theme-set`)

1. `OverlayManager.setEnabledExclusiveInCategory("org.omarchy.palette.<id>", CURRENT)`
2. `Settings.Secure.theme_customization_overlay_packages` ←
   `{"android.theme.customization.system_palette":"org.omarchy.palette.<id>","android.theme.customization.color_source":"preset"}`
3. `UiModeManager.setNightMode(mode == "dark" ? YES : NO)`
4. `WallpaperManager.setStream(backgrounds[0])`
5. `sendBroadcast(org.omarchy.theme.CHANGED)`

Entradas de usuario: app "Theme" en el launcher (lista con preview, como `omarchy-theme-switcher`)
y tile de Quick Settings "Theme" (tap = siguiente tema, long-press = picker). Tile "Next wallpaper"
= `omarchy-theme-bg-next`.

Comprobación manual sin app (userdebug): ver `docs/BUILD.md §7`.

## API para apps de terceros

### Nivel 0 — Material You (recomendado, cero código Omarchy)

```kotlin
// Application.onCreate
DynamicColors.applyToActivitiesIfAvailable(this)
// Compose
val scheme = if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
```

### Nivel 1 — paleta Omarchy exacta (ContentProvider)

```kotlin
val c = contentResolver.query(Uri.parse("content://org.omarchy.theme/current"), null, null, null, null)
c?.use { if (it.moveToFirst()) {
    val accent = it.getString(it.getColumnIndexOrThrow("accent"))        // "#7aa2f7"
    val mode   = it.getString(it.getColumnIndexOrThrow("mode"))          // "dark"
    val name   = it.getString(it.getColumnIndexOrThrow("name"))          // "Tokyo Night"
}}
registerReceiver(receiver, IntentFilter("org.omarchy.theme.CHANGED"), RECEIVER_EXPORTED)
```

Columnas = todas las claves de `theme.toml` + `id`, `name`, `mode`. Sin permisos. Si el provider
no existe (no es OmarchyOS) `query` devuelve `null`: caer al nivel 0.

### Nivel 2 — librería `omarchy-theme-android` (issue M2)

`OmarchyTheme.current(ctx): OmarchyTheme?`, `OmarchyTheme.flow(ctx)`, y para Compose
`omarchyColorScheme(ctx)` que devuelve la paleta exacta o `dynamicColorScheme` como fallback.

## Compat (recursos overlayados, verificados en GrapheneOS 17)

| Recurso | Archivo upstream | Nuestro overlay |
|---|---|---|
| `config_dialogCornerRadius`, `config_bottomDialogCornerRadius` | `core/res/res/values/config.xml` (rounded_corner_radius retirado en #4) | OmarchyFrameworkOverlay |
| `config_icon_mask` | `core/res/res/values/config.xml:5062` | OmarchyShapeOverlay |
| `config_bodyFontFamily`, `config_headlineFontFamily` (+Medium) | `core/res/res/values/config.xml:5556-5645` | OmarchyFontOverlay |
| `notification_corner_radius`, `qs_corner_radius`, `qs_tile_margin_horizontal`, `qs_panel_padding`, `notification_shade_content_margin_horizontal` | `packages/SystemUI/res/values/dimens.xml:355,705,706,734,809` | OmarchySystemUIOverlay |
| `config_qsTileStrokeWidthActive/Inactive` | `packages/SystemUI/res/values/config.xml:374-375` | OmarchySystemUIOverlay |
| `drawable/notification_material_bg` (+ variante `drawable-night/`) — reescrito con referencias solo públicas/locales (`system_surface_container_high_{light,dark}` + stroke 1dp `system_accent1_500`) | `packages/SystemUI/res/drawable/notification_material_bg.xml` | OmarchySystemUIOverlay |
| `color/omarchy_notification_state_color` (+ variante night, nombres propios del overlay) | `packages/SystemUI/res/color/notification_state_color_default.xml` | OmarchySystemUIOverlay |
| `color/omarchy_notification_focus_overlay_color` (+ variante night, nombres propios del overlay) | `packages/SystemUI/res/color/notification_focus_overlay_color.xml` | OmarchySystemUIOverlay |
| `status_bar_clock_color` | `packages/SystemUI/res/values/colors.xml:26` | OmarchySystemUIOverlay |
| `system_{accent1,accent2,accent3,neutral1,neutral2}_{0..1000}` | `core/res/res/values/public-final.xml` | OmarchyPalette* |

Cuando un release mensual renombre uno, aapt2 falla en build con el nombre: actualizar esta tabla.

**Fuentes (#6):** headline = JetBrainsMono (`config_headlineFontFamily*` → `jetbrains-mono-nerd*` en `overlay/OmarchyFontOverlay/res/values/config.xml`), body = `sans-serif` stock por defecto (los `config_bodyFontFamily*` no se sombrean; valores stock de la fila `config_bodyFontFamily`/`config_headlineFontFamily` de la tabla Compat de arriba) y body-mono por tema queda para #9.
