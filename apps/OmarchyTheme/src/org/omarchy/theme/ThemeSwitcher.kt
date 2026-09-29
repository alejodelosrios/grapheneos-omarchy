package org.omarchy.theme

import android.app.UiModeManager
import android.app.WallpaperManager
import android.content.Context
import android.content.Intent
import android.content.om.OverlayManager
import android.os.SystemProperties
import android.os.UserHandle
import android.provider.Settings
import android.util.Log
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.IOException

private const val TAG = "ThemeSwitcher"
private const val PREFS_NAME = "omarchy-theme-switcher"
private const val PREF_CURRENT = "current"

private const val KEY_SYSTEM_PALETTE = "android.theme.customization.system_palette"
private const val KEY_ACCENT_COLOR = "android.theme.customization.accent_color"
private const val KEY_DYNAMIC_COLOR = "android.theme.customization.dynamic_color"
private const val KEY_COLOR_SOURCE = "android.theme.customization.color_source"
private const val KEY_THEME_STYLE = "android.theme.customization.theme_style"
private const val KEY_ADAPTIVE_ICON_SHAPE = "android.theme.customization.adaptive_icon_shape"
private const val KEY_FONT = "android.theme.customization.font"

private const val SHAPE_OVERLAY_PACKAGE = "org.omarchy.overlay.shape"
private const val FONT_OVERLAY_PACKAGE = "org.omarchy.overlay.font"

/**
 * Android port of `omarchy-theme-set <name>`. `set` does binder calls and file I/O (wallpaper
 * decode, prefs write): never call it from the main thread.
 *
 * Steps (all verified against GrapheneOS 17 sources, see docs/research.md §2.4 and
 * .swarm/design/design-9-theme-switcher.md D1/D4/D5):
 *  1. OverlayManager.setEnabledExclusiveInCategory(palettePackage, UserHandle.CURRENT).
 *  2. Settings.Secure.THEME_CUSTOMIZATION_OVERLAY_PACKAGES <- JSON with the D1 keys. Same package
 *     in system_palette/accent_color/dynamic_color so SystemUI's Monet FRROs are skipped
 *     (ThemeOverlayController.java:822-829); shape/font are switched off by
 *     ThemeOverlayApplier.java:209-225 unless named here (font key skipped entirely when
 *     theme.font == "system").
 *  3. UiModeManager.setNightMode(mode == "dark" ? MODE_NIGHT_YES : MODE_NIGHT_NO).
 *  4. Wallpaper (D5): WallpaperManager.setStream on backgrounds[0] if present, best-effort.
 *  5. sendBroadcast(ThemeContract.ACTION_THEME_CHANGED) with id/mode extras.
 */
class ThemeSwitcher(
    private val context: Context,
) {
    fun set(themeId: String): Boolean {
        val theme = ThemeCatalog.get(themeId) ?: return false

        try {
            // 1. Exclusively enable this theme's palette overlay.
            context
                .getSystemService(OverlayManager::class.java)
                .setEnabledExclusiveInCategory(theme.palettePackage, UserHandle.CURRENT)
        } catch (e: SecurityException) {
            Log.e(TAG, "$themeId: failed to enable palette overlay", e)
            return false
        } catch (e: IllegalStateException) {
            Log.e(TAG, "$themeId: failed to enable palette overlay", e)
            return false
        }

        // 2. Write the SystemUI theme customization JSON.
        val json =
            JSONObject().apply {
                put(KEY_SYSTEM_PALETTE, theme.palettePackage)
                put(KEY_ACCENT_COLOR, theme.palettePackage)
                put(KEY_DYNAMIC_COLOR, theme.palettePackage)
                put(KEY_COLOR_SOURCE, "preset")
                put(KEY_THEME_STYLE, theme.themeStyle)
                put(KEY_ADAPTIVE_ICON_SHAPE, SHAPE_OVERLAY_PACKAGE)
                if (theme.font != "system") {
                    put(KEY_FONT, FONT_OVERLAY_PACKAGE)
                }
            }
        Settings.Secure.putString(
            context.contentResolver,
            Settings.Secure.THEME_CUSTOMIZATION_OVERLAY_PACKAGES,
            json.toString(),
        )

        // 3. Light/dark mode.
        context.getSystemService(UiModeManager::class.java).setNightMode(
            if (theme.mode == "dark") UiModeManager.MODE_NIGHT_YES else UiModeManager.MODE_NIGHT_NO,
        )

        // 4. Wallpaper (best-effort: an IOException here does not abort the switch).
        val background = theme.backgrounds.firstOrNull()
        if (background != null) {
            val file = File("${ThemeContract.CATALOG_DIR}/$themeId/$background")
            try {
                file.inputStream().use { stream ->
                    WallpaperManager.getInstance(context).setStream(
                        stream,
                        null,
                        true,
                        WallpaperManager.FLAG_SYSTEM or WallpaperManager.FLAG_LOCK,
                    )
                }
            } catch (e: IOException) {
                Log.w(TAG, "$themeId: failed to set wallpaper", e)
            }
        }

        // 5. Notify listeners.
        context.sendBroadcast(
            Intent(ThemeContract.ACTION_THEME_CHANGED)
                .putExtra(ThemeContract.EXTRA_THEME_ID, themeId)
                .putExtra(ThemeContract.EXTRA_MODE, theme.mode),
        )

        prefs().edit().putString(PREF_CURRENT, themeId).apply()
        return true
    }

    fun current(): String =
        prefs().getString(PREF_CURRENT, null)
            ?: SystemProperties.get("ro.omarchy.theme.default", "tokyo-night")

    fun next(): Theme? {
        val themes = ThemeCatalog.load()
        if (themes.isEmpty()) return null
        val index = themes.indexOfFirst { it.id == current() }
        val nextTheme = themes[(index + 1).mod(themes.size)]
        return if (set(nextTheme.id)) nextTheme else null
    }

    fun appliedPalette(): String? {
        val raw =
            Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.THEME_CUSTOMIZATION_OVERLAY_PACKAGES,
            ) ?: return null
        return try {
            JSONObject(raw).takeIf { it.has(KEY_SYSTEM_PALETTE) }?.getString(KEY_SYSTEM_PALETTE)
        } catch (e: JSONException) {
            null
        }
    }

    private fun prefs() =
        context
            .createDeviceProtectedStorageContext()
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
}
