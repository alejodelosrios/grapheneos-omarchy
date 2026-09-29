package org.omarchy.theme

import android.util.Log
import java.io.File

/**
 * Parser for `themes/<id>/theme.toml` (a strict, line-oriented TOML subset — no multiline
 * strings, no nested tables, no bare numbers/bools). The executable spec for this grammar is
 * `tools/tests/test_i9_theme_catalog.py`, which extracts [TABLE], [STRING] and [ARRAY] verbatim
 * from this file and runs them against the 6 real theme.toml files under themes/ plus a set of rejection
 * cases; keep the regex literals below in sync with that test.
 */
private const val TAG = "ThemeCatalog"

private val TABLE = Regex("""^\s*\[([A-Za-z0-9_]+)\]\s*(#.*)?$""")
private val STRING = Regex("""^\s*([A-Za-z0-9_]+)\s*=\s*"([^"]*)"\s*(#.*)?$""")
private val ARRAY = Regex("""^\s*([A-Za-z0-9_]+)\s*=\s*\[\s*("[^"]*"(\s*,\s*"[^"]*")*)?\s*,?\s*\]\s*(#.*)?$""")
private val BLANK = Regex("""^\s*(#.*)?$""")
private val ARRAY_ITEM = Regex("\"([^\"]*)\"")

private val REQUIRED = listOf("name", "mode", "accent", "background", "foreground", "android.palette_package")

data class Theme(
    val id: String,
    val values: Map<String, String>,
    val backgrounds: List<String>,
) {
    val name: String get() = values.getValue("name")
    val mode: String get() = values.getValue("mode")
    val palettePackage: String get() = values.getValue("android.palette_package")
    val themeStyle: String get() = values["android.theme_style"] ?: "TONAL_SPOT"
    val font: String get() = values["android.font"] ?: "jetbrains-mono-nerd"
    val accent: String get() = values.getValue("accent")
    val background: String get() = values.getValue("background")
    val foreground: String get() = values.getValue("foreground")
}

object ThemeCatalog {
    fun load(dir: String = ThemeContract.CATALOG_DIR): List<Theme> =
        File(dir)
            .listFiles { f -> f.isDirectory }
            ?.sortedBy { it.name }
            ?.mapNotNull { d ->
                val toml = File(d, "theme.toml")
                if (toml.isFile) parse(d.name, toml.readText()) else null
            }
            ?: emptyList()

    fun get(
        id: String,
        dir: String = ThemeContract.CATALOG_DIR,
    ): Theme? =
        File(dir, id).let { d ->
            File(d, "theme.toml").takeIf { it.isFile }?.let { parse(id, it.readText()) }
        }

    fun parse(
        id: String,
        text: String,
    ): Theme? {
        val values = mutableMapOf<String, String>()
        var backgrounds = emptyList<String>()
        var table: String? = null
        for (line in text.lineSeparator()) {
            val tableMatch = TABLE.matchEntire(line)
            val stringMatch = STRING.matchEntire(line)
            val arrayMatch = ARRAY.matchEntire(line)
            when {
                BLANK.matches(line) -> {
                    Unit
                }

                tableMatch != null -> {
                    val t = tableMatch.groupValues[1]
                    if (t != "android") {
                        Log.w(TAG, "$id: unsupported table $t")
                        return null
                    }
                    table = t
                }

                stringMatch != null -> {
                    values[qualify(table, stringMatch.groupValues[1])] = stringMatch.groupValues[2]
                }

                arrayMatch != null -> {
                    val key = qualify(table, arrayMatch.groupValues[1])
                    val items = ARRAY_ITEM.findAll(arrayMatch.groupValues[2]).map { it.groupValues[1] }.toList()
                    if (key == "android.backgrounds") backgrounds = items
                }

                else -> {
                    Log.w(TAG, "$id: unparseable line: $line")
                    return null
                }
            }
        }
        for (key in REQUIRED) {
            if (key !in values) {
                Log.w(TAG, "$id: missing required key $key")
                return null
            }
        }
        val mode = values.getValue("mode")
        if (mode != "dark" && mode != "light") {
            Log.w(TAG, "$id: invalid mode $mode")
            return null
        }
        return Theme(id, values, backgrounds)
    }

    private fun qualify(
        table: String?,
        key: String,
    ): String = if (table != null) "$table.$key" else key

    private fun String.lineSeparator(): List<String> = split('\n').map { it.trimEnd('\r') }
}
