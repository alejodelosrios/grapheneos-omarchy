package org.omarchy.theme.sdk

import android.database.MatrixCursor
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class OmarchyThemeTest {
    private fun tokyoNightCursor(
        id: String = "tokyo-night",
        mode: String = "dark",
    ): MatrixCursor {
        val cursor = MatrixCursor(OmarchyThemeContract.COLUMNS.toTypedArray())
        cursor.addRow(
            OmarchyThemeContract.COLUMNS.map { column ->
                when (column) {
                    "id" -> id
                    "name" -> "Tokyo Night"
                    "mode" -> mode
                    "accent" -> "#7aa2f7"
                    else -> "#000000"
                }
            },
        )
        return cursor
    }

    @Test
    fun `parse valid row returns theme`() {
        val theme = OmarchyTheme.parse(tokyoNightCursor())

        assertEquals("tokyo-night", theme?.id)
        assertEquals("Tokyo Night", theme?.name)
        assertEquals("dark", theme?.mode)
        assertEquals(true, theme?.isDark)
        assertEquals("#7aa2f7", theme?.colors?.get("accent"))
    }

    @Test
    fun `parse invalid id path traversal returns null`() {
        assertNull(OmarchyTheme.parse(tokyoNightCursor(id = "../x")))
    }

    @Test
    fun `parse invalid id with space returns null`() {
        assertNull(OmarchyTheme.parse(tokyoNightCursor(id = "A B")))
    }

    @Test
    fun `parse invalid mode returns null`() {
        assertNull(OmarchyTheme.parse(tokyoNightCursor(mode = "neon")))
    }

    @Test
    fun `parse drops malformed hex colors but keeps the rest`() {
        val cursor = MatrixCursor(OmarchyThemeContract.COLUMNS.toTypedArray())
        cursor.addRow(
            OmarchyThemeContract.COLUMNS.map { column ->
                when (column) {
                    "id" -> "tokyo-night"
                    "name" -> "Tokyo Night"
                    "mode" -> "dark"
                    "accent" -> "#fff"
                    "red" -> "#gg0000"
                    else -> "#000000"
                }
            },
        )

        val theme = OmarchyTheme.parse(cursor)

        assertNull(theme?.colors?.get("accent"))
        assertNull(theme?.colors?.get("red"))
        assertEquals("#000000", theme?.colors?.get("green"))
        assertEquals(OmarchyThemeContract.COLUMNS.size - 3 - 2, theme?.colors?.size)
    }

    @Test
    fun `parse empty cursor returns null`() {
        val cursor = MatrixCursor(OmarchyThemeContract.COLUMNS.toTypedArray())
        assertNull(OmarchyTheme.parse(cursor))
    }

    @Test
    fun `parse null cursor returns null`() {
        assertNull(OmarchyTheme.parse(null))
    }

    @Test
    fun `current without a registered provider returns null without throwing`() {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()

        assertNull(OmarchyTheme.current(ctx))
    }

    @Test
    fun `flow without a registered provider emits null without throwing`() {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()

        val first = runBlocking { OmarchyTheme.flow(ctx).first() }

        assertNull(first)
    }
}
