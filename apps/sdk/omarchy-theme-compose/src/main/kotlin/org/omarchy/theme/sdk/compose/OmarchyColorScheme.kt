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
 * Maps [theme] to a Material 3 [ColorScheme] (design-10 D7). Without a theme, falls back to
 * dynamic color ([dynamicDarkColorScheme]/[dynamicLightColorScheme] per [dark]) so callers work
 * on stock AOSP too. With a theme, starts from [darkColorScheme]/[lightColorScheme] per
 * [OmarchyTheme.isDark] and overrides the roles below; a missing or invalid hex keeps the base
 * value. Pure function: no IPC, safe to call outside Composition.
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
    return base.copy(
        primary = hex(theme, "accent") ?: base.primary,
        onPrimary = hex(theme, "background") ?: base.onPrimary,
        primaryContainer = hex(theme, "selection") ?: base.primaryContainer,
        onPrimaryContainer = hex(theme, "foreground") ?: base.onPrimaryContainer,
        secondary = hex(theme, "magenta") ?: base.secondary,
        tertiary = hex(theme, "cyan") ?: base.tertiary,
        background = hex(theme, "background") ?: base.background,
        onBackground = hex(theme, "foreground") ?: base.onBackground,
        surface = hex(theme, "background") ?: base.surface,
        onSurface = hex(theme, "foreground") ?: base.onSurface,
        surfaceVariant = hex(theme, "lighter_background") ?: base.surfaceVariant,
        onSurfaceVariant = hex(theme, "light_foreground") ?: base.onSurfaceVariant,
        outline = hex(theme, "muted") ?: base.outline,
        error = hex(theme, "red") ?: base.error,
        onError = hex(theme, "background") ?: base.onError,
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
