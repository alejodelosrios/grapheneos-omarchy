package org.omarchy.theme

import android.app.UiModeManager
import android.app.WallpaperManager
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.om.OverlayManager
import android.net.Uri
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

// Launcher3's themed-icons toggle, content://com.android.launcher3.grid_control/icon_themed
// (GridCustomizationsProxy.java:130-132,139,321-328).
private const val LAUNCHER3_ICON_THEMED_URI = "content://com.android.launcher3.grid_control/icon_themed"

// File-level lock: the tile/picker create a new ThemeSwitcher per tap, so this must be shared
// across instances, not a per-instance field, to actually serialize concurrent taps.
private val LOCK = Any()

/**
 * Android port of `omarchy-theme-set <name>`. `set` does binder calls and file I/O (wallpaper
 * decode, prefs write): never call it from the main thread.
 *
 * Steps (all verified against GrapheneOS 17 sources, see docs/research.md §2.4 and
 * .swarm/design/design-9-theme-switcher.md D1/D4/D5):
 *  1. OverlayManager.setEnabledExclusiveInCategory(palettePackage, UserHandle.CURRENT).
 *  2. Settings.Secure.THEME_CUSTOMIZATION_OVERLAY_PACKAGES <- JSON with the D1 keys. Same package
 *     in system_palette/accent_color/dynamic_color so SystemUI's Monet FRROs are skipped
 *     (ThemeOverlayController.java:818-829); shape/font are switched off by
 *     ThemeOverlayApplier.java:209-225 unless named here (font key skipped entirely when
 *     theme.font == "system", shape key skipped entirely when theme.iconShape == "circle": see
 *     design-11-icons-bg-next.md D1, core/res/res/values/config.xml:5062).
 *  3. UiModeManager.setNightMode(mode == "dark" ? MODE_NIGHT_YES : MODE_NIGHT_NO).
 *  4. Wallpaper (D5): WallpaperManager.setStream on backgrounds[0] if present, best-effort.
 *  5. sendBroadcast(ThemeContract.ACTION_THEME_CHANGED) with id/mode extras.
 *  5b. notifyChange on the content provider Uri, then a best-effort themed-icons update to
 *      Launcher3 (see applyThemedIcons).
 */
class ThemeSwitcher(
    private val context: Context,
) {
    fun set(themeId: String): Boolean =
        synchronized(LOCK) {
            val theme = ThemeCatalog.get(themeId) ?: return@synchronized false
            setLocked(themeId, theme)
        }

    private fun setLocked(
        themeId: String,
        theme: Theme,
    ): Boolean {
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
                if (theme.iconShape == "rounded-square") {
                    put(KEY_ADAPTIVE_ICON_SHAPE, SHAPE_OVERLAY_PACKAGE)
                }
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

        // 4. Wallpaper: setWallpaper() below does setStream (best-effort, does not abort the switch).
        val background = theme.backgrounds.firstOrNull()
        if (background != null) {
            setWallpaper(File("${ThemeContract.CATALOG_DIR}/$themeId/$background"))
        }

        // 5. Notify listeners.
        context.sendBroadcast(
            Intent(ThemeContract.ACTION_THEME_CHANGED)
                .putExtra(ThemeContract.EXTRA_THEME_ID, themeId)
                .putExtra(ThemeContract.EXTRA_MODE, theme.mode),
        )

        // 5b. Wake up ContentResolver observers (the lib's flow(ctx), not a broadcast receiver).
        context.contentResolver.notifyChange(ThemeContract.CURRENT, null)
        applyThemedIcons(theme.themedIcons)

        prefs()
            .edit()
            .putString(PREF_CURRENT, themeId)
            .putInt(bgIndexKey(themeId), 0)
            .apply()
        return true
    }

    /** Best-effort wallpaper set, shared with the "Next wallpaper" tile. */
    fun setWallpaper(file: File): Boolean =
        try {
            file.inputStream().use { stream ->
                WallpaperManager.getInstance(context).setStream(
                    stream,
                    null,
                    true,
                    WallpaperManager.FLAG_SYSTEM or WallpaperManager.FLAG_LOCK,
                )
            }
            true
        } catch (e: IOException) {
            Log.w(TAG, "failed to set wallpaper $file", e)
            false
        }

    /**
     * Best-effort push of the themed-icons toggle to Launcher3 (D5). No new permission: our
     * priv-app runs as android.uid.system (AndroidManifest.xml:4), and
     * LauncherCustomizationProvider.kt:38-58 requires BIND_WALLPAPER or GRID_CONTROL for an
     * exported check that ActivityManager.java:5513-5518 (canAccessUnexportedComponents) waives
     * for SYSTEM_UID. Runs off a bare Thread, not joined: `set()` must not wait on Launcher3.
     */
    private fun applyThemedIcons(enabled: Boolean) {
        Thread {
            try {
                context.contentResolver.update(
                    Uri.parse(LAUNCHER3_ICON_THEMED_URI),
                    ContentValues().apply { put("boolean_value", enabled) },
                    null,
                    null,
                )
            } catch (e: RuntimeException) {
                Log.w(TAG, "failed to push themed-icons state to Launcher3", e)
            }
        }.start()
    }

    fun current(): String =
        prefs().getString(PREF_CURRENT, null)
            ?: SystemProperties.get("ro.omarchy.theme.default", "tokyo-night")

    fun next(): Theme? =
        synchronized(LOCK) {
            // next() calls set(), which re-acquires LOCK: the JVM intrinsic lock is reentrant
            // for the same thread, so this does not deadlock.
            val themes = ThemeCatalog.load()
            if (themes.isEmpty()) return@synchronized null
            val index = themes.indexOfFirst { it.id == current() }
            val nextTheme = themes[(index + 1).mod(themes.size)]
            if (set(nextTheme.id)) nextTheme else null
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

    internal fun prefs() =
        context
            .createDeviceProtectedStorageContext()
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    companion object {
        /** Shared with WallpaperTileService, which stores/reads the "Next wallpaper" index. */
        fun bgIndexKey(id: String) = "bg_index_$id"
    }
}
