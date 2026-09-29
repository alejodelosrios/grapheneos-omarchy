package org.omarchy.theme.sdk.compose

import android.content.Context
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.omarchy.theme.sdk.OmarchyTheme
import kotlin.math.pow
import android.graphics.Color as AndroidColor

/**
 * Parses [theme]'s color for [key] into a Compose [Color]. Returns null (base value kept by the
 * caller's `.copy`) if [theme] is null, the key is absent, or the hex string is invalid.
 */
private fun hex(
    theme: OmarchyTheme?,
    key: String,
): Color? {
    val value = theme?.colors?.get(key) ?: return null
    return try {
        Color(AndroidColor.parseColor(value))
    } catch (e: IllegalArgumentException) {
        null
    }
}

/**
 * Candidates tried (in order) when a preferred text key doesn't clear 4.5:1, mirrors
 * `TEXT_CANDIDATES` in `tools/gen-palette.py:206-207` (audit-8).
 */
internal val TEXT_CANDIDATES =
    listOf("foreground", "bright_foreground", "light_foreground", "darker_background", "dark_background")

private fun hexToRgb(hex: String): Triple<Int, Int, Int> {
    val h = hex.removePrefix("#")
    return Triple(h.substring(0, 2).toInt(16), h.substring(2, 4).toInt(16), h.substring(4, 6).toInt(16))
}

private fun linearize(channel: Int): Double {
    val c = channel / 255.0
    return if (c <= 0.04045) c / 12.92 else ((c + 0.055) / 1.055).pow(2.4)
}

private fun relativeLuminance(rgb: Triple<Int, Int, Int>): Double {
    val (r, g, b) = rgb
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
}

/**
 * WCAG 2.x contrast ratio between two `#rrggbb` hex colors — same formula as `contrast()` /
 * `_lum()` in `tools/gen-palette.py:228-238` (audit-8). `internal` (not private) so
 * `OmarchyColorSchemeContrastTest` can exercise it directly: pure hex-string math, no [Context].
 */
internal fun contrastRatio(
    hex1: String,
    hex2: String,
): Double {
    val l1 = relativeLuminance(hexToRgb(hex1))
    val l2 = relativeLuminance(hexToRgb(hex2))
    val lighter = maxOf(l1, l2)
    val darker = minOf(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Same rule as `pick_text()` in `tools/gen-palette.py:240-260` (audit-8, ported for design-10
 * M1/audit-10 #1): [preferred] if it clears 4.5:1 against every key in [bgKeys]; else the first
 * of [TEXT_CANDIDATES] that does; else white or black, whichever has the better worst-case
 * contrast (the linear-mix extremes gen-palette falls back to are exactly white/black at t=0/1000).
 * Returns null only if [colors] is missing [preferred] or any of [bgKeys] — the caller then keeps
 * its Material base value, same policy as [hex].
 */
internal fun pickText(
    colors: Map<String, String>,
    preferred: String,
    bgKeys: List<String>,
): String? {
    val bgs = bgKeys.map { colors[it] ?: return null }

    fun contrastsOk(candidate: String): Boolean =
        try {
            bgs.all { contrastRatio(candidate, it) >= 4.5 }
        } catch (e: NumberFormatException) {
            false
        }

    colors[preferred]?.let { if (contrastsOk(it)) return it }
    for (key in TEXT_CANDIDATES) {
        val candidate = colors[key] ?: continue
        if (contrastsOk(candidate)) return candidate
    }

    val white = "#ffffff"
    val black = "#000000"
    val whiteWorst = bgs.minOf { contrastRatio(white, it) }
    val blackWorst = bgs.minOf { contrastRatio(black, it) }
    return if (whiteWorst >= blackWorst) white else black
}

/**
 * Maps [theme] to a Material 3 [ColorScheme] (design-10 D7). Without a theme, falls back to
 * dynamic color ([dynamicDarkColorScheme]/[dynamicLightColorScheme] per [dark]) so callers work
 * on stock AOSP too. With a theme, starts from [darkColorScheme]/[lightColorScheme] per
 * [OmarchyTheme.isDark] and overrides the roles below; a missing or invalid hex keeps the base
 * value. `on*` roles run through [pickText] (audit-10 #1: D7's preferred key alone can fall under
 * WCAG AA 4.5:1). Pure function: no IPC, safe to call outside Composition.
 */
fun schemeFor(
    theme: OmarchyTheme?,
    dark: Boolean,
    ctx: Context,
): ColorScheme {
    if (theme == null) {
        return if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
    }
    val base = if (theme.isDark) darkColorScheme() else lightColorScheme()
    val colors = theme.colors

    fun onColor(
        preferred: String,
        bgKeys: List<String>,
        fallback: Color,
    ): Color {
        val picked = pickText(colors, preferred, bgKeys) ?: return fallback
        return try {
            Color(AndroidColor.parseColor(picked))
        } catch (e: IllegalArgumentException) {
            fallback
        }
    }

    val onBackgroundColor = onColor("foreground", listOf("background"), base.onBackground)

    return base.copy(
        primary = hex(theme, "accent") ?: base.primary,
        onPrimary = onColor("background", listOf("accent"), base.onPrimary),
        primaryContainer = hex(theme, "selection") ?: base.primaryContainer,
        onPrimaryContainer = onColor("foreground", listOf("selection"), base.onPrimaryContainer),
        secondary = hex(theme, "magenta") ?: base.secondary,
        tertiary = hex(theme, "cyan") ?: base.tertiary,
        background = hex(theme, "background") ?: base.background,
        onBackground = onBackgroundColor,
        surface = hex(theme, "background") ?: base.surface,
        onSurface = onBackgroundColor,
        surfaceVariant = hex(theme, "lighter_background") ?: base.surfaceVariant,
        onSurfaceVariant = onColor("light_foreground", listOf("lighter_background"), base.onSurfaceVariant),
        outline = hex(theme, "muted") ?: base.outline,
        error = hex(theme, "red") ?: base.error,
        onError = onColor("background", listOf("red"), base.onError),
    )
}

/**
 * Collects [OmarchyTheme.flow] and returns the matching [ColorScheme] (design-10 D7), recomposing
 * whenever the theme changes (no restart needed). Falls back to dynamic color when there's no
 * provider (stock AOSP) or no theme is set yet.
 */
@Composable
fun omarchyColorScheme(dark: Boolean = isSystemInDarkTheme()): ColorScheme {
    val ctx = LocalContext.current
    val theme by remember(ctx) { OmarchyTheme.flow(ctx) }.collectAsStateWithLifecycle(initialValue = null)
    return schemeFor(theme, dark, ctx)
}
