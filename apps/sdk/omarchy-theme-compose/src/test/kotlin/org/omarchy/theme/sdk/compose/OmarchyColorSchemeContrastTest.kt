package org.omarchy.theme.sdk.compose

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Audit-10 #1 (M1): the adaptive `on*` text picked by [pickText] must clear WCAG AA 4.5:1
 * against its background on every shipped theme, not just the ones sampled during review. Pure
 * JUnit (no Robolectric/Context): reads the real `themes/<id>/theme.toml` so a new theme is covered
 * without touching this test.
 */
class OmarchyColorSchemeContrastTest {
    private val colorLine = Regex("""^\s*(\w+)\s*=\s*"(#[0-9a-fA-F]{6})"\s*$""")

    private fun parseTheme(file: File): Map<String, String> {
        val colors = mutableMapOf<String, String>()
        for (line in file.readLines()) {
            val match = colorLine.find(line) ?: continue
            colors[match.groupValues[1]] = match.groupValues[2]
        }
        return colors
    }

    /** (preferred key, background keys) — same pairs [schemeFor] runs through [pickText]. */
    private val cases =
        listOf(
            "onError" to Pair("background", listOf("red")),
            "onSurfaceVariant" to Pair("light_foreground", listOf("lighter_background")),
            "onPrimary" to Pair("background", listOf("accent")),
            "onPrimaryContainer" to Pair("foreground", listOf("selection")),
            "onBackground/onSurface" to Pair("foreground", listOf("background")),
        )

    @Test
    fun adaptiveTextClearsWcagAaOnEveryTheme() {
        val themesDir = File("../../../themes")
        assertTrue("expected ${themesDir.absolutePath} to exist", themesDir.isDirectory)

        val themeDirs = themesDir.listFiles { f -> f.isDirectory && File(f, "theme.toml").isFile }
        assertTrue("expected at least one themes/*/theme.toml", !themeDirs.isNullOrEmpty())

        for (dir in themeDirs!!) {
            val colors = parseTheme(File(dir, "theme.toml"))
            for ((label, case) in cases) {
                val (preferred, bgKeys) = case
                val picked = pickText(colors, preferred, bgKeys)
                assertTrue("${dir.name}: $label — pickText($preferred, $bgKeys) was null", picked != null)
                for (bgKey in bgKeys) {
                    val bg = colors.getValue(bgKey)
                    val ratio = contrastRatio(picked!!, bg)
                    assertTrue(
                        "${dir.name}: $label = $picked on $bgKey ($bg) is $ratio, want >= 4.5",
                        ratio != null && ratio >= 4.5,
                    )
                }
            }
        }
    }

    /** Audit-10 R2-1: malformed hex (short `#fff`, non-hex digits) must return null, not throw. */
    @Test
    fun pickTextReturnsNullInsteadOfThrowingOnMalformedHex() {
        val shortHexPreferred = mapOf("preferred" to "#fff", "bg" to "#111111")
        assertTrue(pickText(shortHexPreferred, "preferred", listOf("bg")) == null)

        val invalidDigitsBackground = mapOf("preferred" to "#ffffff", "bg" to "#gg0000")
        assertTrue(pickText(invalidDigitsBackground, "preferred", listOf("bg")) == null)
    }
}
