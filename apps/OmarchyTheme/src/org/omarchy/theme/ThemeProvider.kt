package org.omarchy.theme

import android.content.ContentProvider
import android.content.ContentValues
import android.content.UriMatcher
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri

private const val MATCH_CURRENT = 1
private const val MATCH_THEMES = 2

private val MATCHER =
    UriMatcher(UriMatcher.NO_MATCH).apply {
        addURI(ThemeContract.AUTHORITY, "current", MATCH_CURRENT)
        addURI(ThemeContract.AUTHORITY, "themes", MATCH_THEMES)
    }

/**
 * Read-only, deliberately public (no `android:permission`, no `writePermission`): this is the
 * Android analogue of `~/.config/omarchy/current` on the Omarchy desktop, meant to be read by any
 * app. `projection` is honored, restricted to [ThemeContract.COLUMNS]; `selection`/`sortOrder` are
 * ignored — there is no SQL backing this, it is a catalog file read on every query. Callers never
 * supply an id: `current` is a single row decided
 * by [ThemeSwitcher], `themes` is the full catalog.
 */
class ThemeProvider : ContentProvider() {
    override fun onCreate() = true

    override fun query(
        uri: Uri,
        projection: Array<String>?,
        selection: String?,
        selectionArgs: Array<String>?,
        sortOrder: String?,
    ): Cursor? {
        val ctx = context ?: return null
        val themes =
            when (MATCHER.match(uri)) {
                MATCH_CURRENT -> listOfNotNull(ThemeCatalog.get(ThemeSwitcher(ctx).current()))
                MATCH_THEMES -> ThemeCatalog.load()
                else -> return null
            }
        val columns = projection?.filter { it in ThemeContract.COLUMNS } ?: ThemeContract.COLUMNS
        val cursor = MatrixCursor(columns.toTypedArray())
        for (theme in themes) {
            cursor.addRow(columns.map { if (it == "id") theme.id else theme.values[it] })
        }
        cursor.setNotificationUri(ctx.contentResolver, ThemeContract.CURRENT)
        return cursor
    }

    override fun getType(uri: Uri): String? =
        when (MATCHER.match(uri)) {
            MATCH_CURRENT -> "vnd.android.cursor.item/vnd.org.omarchy.theme"
            MATCH_THEMES -> "vnd.android.cursor.dir/vnd.org.omarchy.theme"
            else -> null
        }

    override fun insert(
        uri: Uri,
        values: ContentValues?,
    ): Uri? = null

    override fun delete(
        uri: Uri,
        selection: String?,
        selectionArgs: Array<String>?,
    ) = 0

    override fun update(
        uri: Uri,
        values: ContentValues?,
        selection: String?,
        selectionArgs: Array<String>?,
    ) = 0
}
