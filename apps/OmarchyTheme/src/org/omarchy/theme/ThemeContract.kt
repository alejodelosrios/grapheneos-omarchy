package org.omarchy.theme

import android.net.Uri

/**
 * Public contract for third-party apps (mirrors ~/.config/omarchy/current/theme on the desktop).
 * Stable from v0.1.0; additive changes only.
 */
object ThemeContract {
    const val AUTHORITY = "org.omarchy.theme"

    /**
     * Columns returned by both CURRENT and THEMES, in this exact order: id, name, mode,
     * then the 25 top-level color keys of theme.toml (order verified with tomllib against
     * the 6 themes under themes/, one theme.toml each). `[android]` and `backgrounds` are
     * not exposed.
     * The contract only grows; the lib copy in apps/sdk/omarchy-theme-android is kept in
     * sync by tools/tests/test_i10_contract.py.
     */
    @JvmField val COLUMNS: List<String> =
        listOf(
            "id",
            "name",
            "mode",
            "accent",
            "selection",
            "muted",
            "background",
            "dark_background",
            "darker_background",
            "lighter_background",
            "foreground",
            "dark_foreground",
            "light_foreground",
            "bright_foreground",
            "red",
            "yellow",
            "orange",
            "green",
            "cyan",
            "blue",
            "magenta",
            "brown",
            "bright_red",
            "bright_yellow",
            "bright_green",
            "bright_cyan",
            "bright_blue",
            "bright_magenta",
        )

    /** Only lowercase letters, digits and hyphens; applied to `id` by parsers/providers. */
    const val ID_PATTERN = "^[a-z0-9-]+$"

    /** One row: the current theme. Columns = COLUMNS. */
    @JvmField val CURRENT: Uri = Uri.parse("content://$AUTHORITY/current")

    /** One row per installed theme. Columns = COLUMNS (same as CURRENT). */
    @JvmField val THEMES: Uri = Uri.parse("content://$AUTHORITY/themes")

    /**
     * Broadcast sent after a switch; extras: EXTRA_THEME_ID, EXTRA_MODE. It is declared
     * `<protected-broadcast>` in the manifest, so only this system priv-app can send it;
     * the content provider (CURRENT/THEMES) is the source of truth, not these extras.
     */
    const val ACTION_THEME_CHANGED = "org.omarchy.theme.CHANGED"
    const val EXTRA_THEME_ID = "id"
    const val EXTRA_MODE = "mode"

    /** Catalog on device, copied by omarchy.mk from vendor/omarchy/themes/. */
    const val CATALOG_DIR = "/product/etc/omarchy"
}
