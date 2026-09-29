# THEMING — temas conmutables y API para apps

## Anatomía de un tema

```
themes/<id>/theme.toml            # copia de themes/<id>/colors.toml de Omarchy + [android]
themes/<id>/backgrounds/*.jpg     # fondos (licencia verificada por archivo)
overlay/themes/<id>/OmarchyPalette<Id>/   # RRO generado: 65 system_* (+ tokens A14+)
```

### Claves de `[android]` en `theme.toml`

Las siguientes claves en la sección `[android]` permiten personalizar el comportamiento de la UI
por tema (`apps/OmarchyTheme/src/org/omarchy/theme/ThemeCatalog.kt:20-65`):

| Clave | Default | Valores válidos | Descripción |
|---|---|---|---|
| `palette_package` | — | string | Identificador del paquete RRO de paleta (obligatorio). Ej. `org.omarchy.palette.tokyonight` (`themes/tokyo-night/theme.toml:37`) |
| `theme_style` | `TONAL_SPOT` | string | Estrategia de Material You para derivar colores (ThemeCatalog.kt:31). Ej. `TONAL_SPOT`, `EXPRESSIVE` |
| `font` | `jetbrains-mono-nerd` | string | Identificador de fuente (omitido del JSON si es `system`; ThemeCatalog.kt:32) |
| `icon_shape` | `rounded-square` | `rounded-square` \| `circle` | Forma de los iconos adaptativos (ThemeCatalog.kt:37-45) |
| `themed_icons` | `true` | `"true"` \| `"false"` | Tintado de iconos del launcher (como string; ThemeCatalog.kt:47-64) |

**Valores inválidos:** si `icon_shape` o `themed_icons` contienen un valor no permitido, `ThemeCatalog`
los registra en el log con `Log.w` y aplica el default sin lanzar excepción
(`apps/OmarchyTheme/src/org/omarchy/theme/ThemeCatalog.kt:40-44, 59-62`).

**Fondos:** `backgrounds` es un array TOML opcional con rutas relativas a archivos del directorio
`themes/<id>/backgrounds/`. Solo se copian en el producto archivos con estas extensiones:
`jpg`, `jpeg`, `png`, `webp` (la lista exacta está en `omarchy.mk:41` como `OMARCHY_BG_EXTS`).

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
   ```json
   {
     "android.theme.customization.system_palette":      "org.omarchy.palette.<id>",
     "android.theme.customization.accent_color":        "org.omarchy.palette.<id>",
     "android.theme.customization.dynamic_color":       "org.omarchy.palette.<id>",
     "android.theme.customization.color_source":        "preset",
     "android.theme.customization.theme_style":         "<theme.toml [android].theme_style>",
     "android.theme.customization.adaptive_icon_shape": "org.omarchy.overlay.shape",
     "android.theme.customization.font":                "org.omarchy.overlay.font"
   }
   ```
   (la clave `font` se omite si `[android].font == "system"`; ver `ThemeSwitcher.kt:76-78`)
3. `UiModeManager.setNightMode(mode == "dark" ? YES : NO)`
4. `WallpaperManager.setStream(backgrounds[0])` (se salta si `theme.toml` omite `backgrounds` o está vacío)
5. `sendBroadcast(org.omarchy.theme.CHANGED)`

**Por qué shape y font son mutables:** `ThemeOverlayApplier.java:209-225` (GrapheneOS 17) desactiva todo overlay en las categorías de
`THEME_CATEGORIES` (`:118-128`) si su paquete no aparece en el JSON. Sin estas claves, SystemUI apaga
`org.omarchy.overlay.shape` y `org.omarchy.overlay.font` (mutables, `overlay/config/config.xml`). El mismo paquete en
`accent_color` y `dynamic_color` (en lugar de usar los FRRO Monet por defecto) evita que `ThemeOverlayController.java:822-829` (GrapheneOS 17)
habilite los FRROs dinámicos, manteniendo la paleta exacta del tema; `color_source="preset"` obliga a que no se reescriba
el JSON al cambiar wallpaper (`ThemeOverlayController.java:366-378` — GrapheneOS 17).

### Forma de iconos e iconos temáticos

**Forma de iconos adaptativos:** la clave `adaptive_icon_shape` del JSON se establece según `theme.iconShape`:
- `icon_shape = "rounded-square"` (D1) → `adaptive_icon_shape` = `org.omarchy.overlay.shape` (overlay
  `OmarchyShapeOverlay`; `overlay/OmarchyShapeOverlay/res/values/config.xml`)
- `icon_shape = "circle"` → se **omite** la clave `adaptive_icon_shape` del JSON (ThemeSwitcher.kt:95-97).
  Esto deja activo el `config_icon_mask` de stock de GrapheneOS (máscara circular,
  `core/res/res/values/config.xml:5062` — GrapheneOS 17; `ThemeOverlayApplier.java:209-225` — GrapheneOS 17 — desactiva el overlay al
  no encontrar la clave en el JSON).
- `squircle` no existe en v1: no hay un camino de `config_icon_mask` verificado en rama 17 de GrapheneOS.

**Override de forma del usuario:** si el usuario eligió una forma de icono en el ThemePicker de stock,
el launcher sigue su preferencia (`icon_shape_model`, ThemeManager.kt:149-156,236 — GrapheneOS 17) incluso cuando el
sistema tiene un overlay de forma activado (D3). El RRO manda en el sistema, pero en el launcher solo
si el usuario no fijó la forma antes.

**Iconos temáticos (tintado de launcher):** si `themed_icons = "true"`, `ThemeSwitcher` empuja la
preferencia al launcher3 en un hilo sin bloquear (`Thread`, sin `join`; ThemeSwitcher.kt:162-175).
Usa `ContentResolver.update` sobre `content://com.android.launcher3.grid_control/icon_themed` con
el valor booleano (D5, `GridCustomizationsProxy.java:130-132,139,321-328` — GrapheneOS 17). Es best-effort: si otro
launcher es el predeterminado o si Launcher3 no está disponible, no pasa nada; los errores se
registran con `Log.w` sin detener el cambio de tema. El ContentProvider está exportado y exige
permiso `BIND_WALLPAPER` o `GRID_CONTROL` (`LauncherCustomizationProvider.kt:38-58` — GrapheneOS 17);
nuestro uid `system` debería pasarlo vía chequeo de acceso no exportado (`ActivityManager.java:5513-5518` — GrapheneOS 17).
**No verificado sin host de build: requiere ejecutar en Pixel para confirmar que el uid system accede al provider.**

**Persistencia:** `BootReceiver` reaplica el tema en `BOOT_COMPLETED` si el JSON guardado no coincide con la paleta actual
(`BootReceiver.kt:26-27`). **No verificado sin host de build.**

Entradas de usuario: app "Theme" en el launcher (lista con preview, como `omarchy-theme-switcher`),
tile de Quick Settings "Theme" (tap = siguiente tema, long-press = picker), y tile "Next wallpaper"
(`WallpaperTileService`, contrato `omarchy-theme-bg-next`, D6):

**Tile "Next wallpaper":**
- Recorre los fondos del tema actual, leyendo los archivos de `themes/<id>/backgrounds/` filtrados por
  las extensiones `jpg`, `jpeg`, `png`, `webp` (lista exacta en `omarchy.mk:41` como `OMARCHY_BG_EXTS`,
  reflejada en `ThemeCatalog.BACKGROUND_EXTENSIONS`, `ThemeCatalog.kt:69`), y ordenados por nombre.
- Cada tap avanza al siguiente fondo con `(índice+1) % n`, donde `n` es el total de fondos. Vuelve al
  primero después del último (`WallpaperTileService.kt:42-58`).
- El índice se persiste por tema en las prefs device-protected bajo la clave `bg_index_<id>`
  (compartidas con `ThemeSwitcher`, `ThemeSwitcher.kt:212`).
- El tile queda `STATE_UNAVAILABLE` si el tema tiene menos de 2 fondos; de lo contrario, `STATE_ACTIVE`
  (`WallpaperTileService.kt:28-39`).
- Al cambiar de tema vía `ThemeSwitcher.set()`, el índice se reinicia a 0 (`ThemeSwitcher.kt:133`),
  coherente con el paso 4 que pone `backgrounds[0]` como fondo inicial.
- **No verificado sin host de build: requiere ejecutar en Pixel para verificar que el wallpaper cambia
  al tocar el tile.**

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

#### URIs

| URI | Descripción |
|---|---|
| `content://org.omarchy.theme/current` | Una fila: el tema actual (`apps/OmarchyTheme/src/org/omarchy/theme/ThemeContract.kt:56`) |
| `content://org.omarchy.theme/themes` | Una fila por cada tema instalado (`apps/OmarchyTheme/src/org/omarchy/theme/ThemeContract.kt:59`) |

#### Columnas

El provider devuelve exactamente estas 28 columnas en este orden (`apps/OmarchyTheme/src/org/omarchy/theme/ThemeContract.kt:20-50`):

| Columna | Significado |
|---|---|
| `id` | Identificador del tema (p.ej. `tokyo-night`); debe coincidir con `^[a-z0-9-]+$` |
| `name` | Nombre legible (p.ej. `Tokyo Night`) |
| `mode` | `dark` o `light` |
| `accent` | Color hex `#rrggbb` (rol AOSP `system_accent1`) |
| `selection` | Color hex `#rrggbb` |
| `muted` | Color hex `#rrggbb` |
| `background` | Color hex `#rrggbb` (rol AOSP `system_neutral1`) |
| `dark_background` | Color hex `#rrggbb` |
| `darker_background` | Color hex `#rrggbb` |
| `lighter_background` | Color hex `#rrggbb` (rol AOSP `system_neutral2`) |
| `foreground` | Color hex `#rrggbb` |
| `dark_foreground` | Color hex `#rrggbb` |
| `light_foreground` | Color hex `#rrggbb` |
| `bright_foreground` | Color hex `#rrggbb` |
| `red` | Color hex `#rrggbb` |
| `yellow` | Color hex `#rrggbb` |
| `orange` | Color hex `#rrggbb` |
| `green` | Color hex `#rrggbb` |
| `cyan` | Color hex `#rrggbb` (rol AOSP `system_accent3`) |
| `blue` | Color hex `#rrggbb` |
| `magenta` | Color hex `#rrggbb` (rol AOSP `system_accent2`) |
| `brown` | Color hex `#rrggbb` |
| `bright_red` | Color hex `#rrggbb` |
| `bright_yellow` | Color hex `#rrggbb` |
| `bright_green` | Color hex `#rrggbb` |
| `bright_cyan` | Color hex `#rrggbb` |
| `bright_blue` | Color hex `#rrggbb` |
| `bright_magenta` | Color hex `#rrggbb` |

**Nota:** la tabla completa de mapeísmo roles AOSP ↔ theme.toml está en `docs/THEMING.md:22-28`.

#### Comportamiento

- `query(uri, projection, null, null, null)`: devuelve un `MatrixCursor` con `COLUMNS`; se respeta `projection` si se proporciona
- `selection` y `sortOrder` se ignoran
- Permisos: ninguno (provider es permission-less, `exported="true"` sin `writePermission`)
- Sin provider (AOSP stock): `query` devuelve `null`; `registerContentObserver` lanza `SecurityException`
- Modificaciones: `insert`, `update`, `delete` devuelven `null`/`0` sin efecto

#### Cambios de tema: `protected-broadcast` y `ContentObserver`

`org.omarchy.theme.CHANGED` es un `protected-broadcast` (`apps/OmarchyTheme/AndroidManifest.xml:9`) que solo la priv-app puede enviar. **Importante:** solo es un aviso; la fuente de verdad es el provider. Lee cambios usando un `ContentObserver`:

```kotlin
val observer = object : ContentObserver(null) {
    override fun onChange(selfChange: Boolean) {
        // Re-leer el tema con current() en Dispatchers.IO
    }
}
try {
    contentResolver.registerContentObserver(OmarchyThemeContract.CURRENT, false, observer)
} catch (e: SecurityException) {
    // Sin provider (AOSP stock): usar fallback Nivel 0
}
// Al terminar (si register no lanzó):
contentResolver.unregisterContentObserver(observer)
```

Si usas la librería (`apps/sdk/omarchy-theme-android/`), `OmarchyTheme.flow(ctx)` ya implementa esta excepción (ver KDoc: `apps/sdk/omarchy-theme-android/src/main/kotlin/org/omarchy/theme/sdk/OmarchyTheme.kt:90-95`).

#### Garantías de estabilidad

El contrato solo crece; nunca cambia de nombre ni se remueve una columna. `[android]` y `backgrounds` (opcionales en `theme.toml`) no se exponen en el provider.

#### `<queries>` obligatorio en el cliente (API 30+)

`AndroidManifest.xml` de tu app debe declarar:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <queries>
        <provider android:authorities="org.omarchy.theme" />
    </queries>
</manifest>
```

Esto permite resolver el ContentProvider aunque viva en otro paquete (`apps/sdk/omarchy-theme-android/src/main/AndroidManifest.xml:4-5`).

### Nivel 2 — librería `apps/sdk/` (omarchy-theme-android + omarchy-theme-compose)

#### API principal

```kotlin
// Lectura síncrona (ejecutar en IO, devuelve null si no hay provider)
val theme: OmarchyTheme? = OmarchyTheme.current(ctx)

// Flow reactivo (emite el tema actual, luego en cada cambio)
val flow: Flow<OmarchyTheme?> = OmarchyTheme.flow(ctx)
```

(`apps/sdk/omarchy-theme-android/src/main/kotlin/org/omarchy/theme/sdk/OmarchyTheme.kt:65-106`)

#### Compose

```kotlin
@Composable
fun MyScreen() {
    val scheme = omarchyColorScheme()  // Usa flow(ctx) internamente, devuelve ColorScheme
    // ... aplica scheme a Scaffold/Surface/etc
}
```

(`apps/sdk/omarchy-theme-compose/src/main/kotlin/org/omarchy/theme/sdk/compose/OmarchyColorScheme.kt:76`)

#### Mapeo de colores a Material 3 (D7)

Con tema presente, `omarchyColorScheme()` parte de `darkColorScheme()` o `lightColorScheme()` (según `theme.mode`) y aplica:

| theme.toml | Material 3 ColorScheme |
|---|---|
| `accent` | `primary` |
| `background` | `onPrimary`, `background`, `surface`, `onError` |
| `selection` | `primaryContainer` |
| `foreground` | `onPrimaryContainer`, `onBackground`, `onSurface` |
| `magenta` | `secondary` |
| `cyan` | `tertiary` |
| `lighter_background` | `surfaceVariant` |
| `light_foreground` | `onSurfaceVariant` |
| `muted` | `outline` |
| `red` | `error` |

(`apps/sdk/omarchy-theme-compose/src/main/kotlin/org/omarchy/theme/sdk/compose/OmarchyColorScheme.kt:51-67`)

Sin tema o sin provider, `omarchyColorScheme()` devuelve `dynamicDarkColorScheme(ctx)` o `dynamicLightColorScheme(ctx)` según parámetro `dark`.

#### Compilación

```bash
gradle -p apps/sdk test :sample:assembleDebug
```

- Requiere: Gradle 9.8.0, JDK 21, sin wrapper (`gradle` instalado directamente)
- Versiones en `apps/sdk/gradle/libs.versions.toml` (compatibilidad según las release notes de AGP 9.4; ver comentario en `libs.versions.toml:2-7`)
- Sample compilado: `apps/sdk/sample/build/outputs/apk/debug/sample-debug.apk` (package `org.omarchy.sample`, `apps/sdk/sample/src/main/kotlin/org/omarchy/sample/MainActivity.kt`)

#### Publicación en Maven

Pendiente (M4).

#### Test

`gradle -p apps/sdk test` ejecuta Robolectric contra:
- `apps/sdk/omarchy-theme-android/src/test/kotlin/org/omarchy/theme/sdk/OmarchyThemeTest.kt`: parse de fila válida, id inválido, mode inválido, cursor vacío/null; `current()` sin provider devuelve null; `flow()` sin provider emite null sin lanzar

#### No verificado sin host de build

Los criterios 1–3 del issue #10 (query devuelve fila correcta en `current`, sample actualiza sin reiniciarse, emulador sin provider usa fallback) requieren Pixel/emulador y se verificarán en el PR de integración.

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
