package org.omarchy.theme

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri

/** Read-only. Implemented in issue M2 · Theme API. */
class ThemeProvider : ContentProvider() {
    override fun onCreate() = true
    override fun query(uri: Uri, projection: Array<String>?, selection: String?,
                       selectionArgs: Array<String>?, sortOrder: String?): Cursor? = TODO("M2 · Theme API")
    override fun getType(uri: Uri) = "vnd.android.cursor.item/vnd.org.omarchy.theme"
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<String>?) = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<String>?) = 0
}
