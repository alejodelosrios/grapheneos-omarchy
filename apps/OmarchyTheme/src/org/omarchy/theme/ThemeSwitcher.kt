package org.omarchy.theme

import android.content.Context

/**
 * Android port of `omarchy-theme-set <name>`. Implemented in issue M2 · OmarchyTheme app.
 * Steps (all verified against GrapheneOS 17 sources, see docs/research.md §2.4):
 *  1. OverlayManager.setEnabledExclusiveInCategory(palettePackage, UserHandle.CURRENT)
 *  2. Settings.Secure.THEME_CUSTOMIZATION_OVERLAY_PACKAGES <- JSON
 *     {"android.theme.customization.system_palette": palettePackage,
 *      "android.theme.customization.color_source": "preset",
 *      "android.theme.customization.theme_style": style}
 *     -> SystemUI ThemeOverlayController re-applies; Monet FRROs are skipped for a package name.
 *  3. UiModeManager.setNightMode(mode == "dark" ? MODE_NIGHT_YES : MODE_NIGHT_NO)
 *  4. WallpaperManager.setStream(theme.backgrounds[0], FLAG_SYSTEM | FLAG_LOCK)
 *  5. sendBroadcast(ACTION_THEME_CHANGED)
 */
class ThemeSwitcher(private val context: Context) {
    fun set(themeId: String): Unit = TODO("M2 · OmarchyTheme app")
}
