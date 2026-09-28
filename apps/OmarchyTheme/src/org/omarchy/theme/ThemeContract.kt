package org.omarchy.theme

import android.net.Uri

/**
 * Public contract for third-party apps (mirrors ~/.config/omarchy/current/theme on the desktop).
 * Stable from v0.1.0; additive changes only.
 */
object ThemeContract {
    const val AUTHORITY = "org.omarchy.theme"
    /** One row: the current theme. Columns = every key of theme.toml + [name, id, mode]. */
    @JvmField val CURRENT: Uri = Uri.parse("content://$AUTHORITY/current")
    /** One row per installed theme (id, name, mode, accent, background, foreground). */
    @JvmField val THEMES: Uri = Uri.parse("content://$AUTHORITY/themes")
    /** Broadcast sent after a switch; extras: EXTRA_THEME_ID, EXTRA_MODE. */
    const val ACTION_THEME_CHANGED = "org.omarchy.theme.CHANGED"
    const val EXTRA_THEME_ID = "id"
    const val EXTRA_MODE = "mode"
    /** Catalog on device, copied by omarchy.mk from vendor/omarchy/themes/. */
    const val CATALOG_DIR = "/product/etc/omarchy"
}
