package org.omarchy.theme.sdk

import android.net.Uri

/**
 * Public contract for `content://org.omarchy.theme`, mirrored from the priv-app's own
 * `apps/OmarchyTheme/src/org/omarchy/theme/ThemeContract.kt`. This copy MUST stay in sync
 * with that one (same COLUMNS, same order, same ID_PATTERN); `tools/tests/test_i10_contract.py`
 * checks both against the 6 `themes/<id>/theme.toml` with `tomllib`.
 */
object OmarchyThemeContract {
    const val AUTHORITY = "org.omarchy.theme"

    /**
     * Columns returned by both CURRENT and THEMES, in this exact order: id, name, mode,
     * then the 25 top-level color keys of theme.toml. `[android]` and `backgrounds` are
     * not exposed. The contract only grows.
     */
    val COLUMNS: List<String> =
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

    /** Only lowercase letters, digits and hyphens; applied to `id` by [OmarchyTheme.parse]. */
    const val ID_PATTERN = "^[a-z0-9-]+$"

    /** One row: the current theme. Columns = COLUMNS. */
    const val CURRENT_PATH = "current"

    /** `content://$AUTHORITY/$CURRENT_PATH` */
    val CURRENT: Uri = Uri.parse("content://$AUTHORITY/$CURRENT_PATH")
}
