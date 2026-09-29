package org.omarchy.theme.sdk

import android.content.Context
import android.database.ContentObserver
import android.database.Cursor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.map

/** A theme as read from `content://org.omarchy.theme`. */
data class OmarchyTheme(
    val id: String,
    val name: String,
    val mode: String,
    val colors: Map<String, String>,
) {
    val isDark: Boolean get() = mode == "dark"

    companion object {
        private val ID_REGEX = Regex(OmarchyThemeContract.ID_PATTERN)
        private val COLOR_COLUMNS =
            OmarchyThemeContract.COLUMNS.filter {
                it != "id" && it != "name" && it != "mode"
            }

        /**
         * Parses the first row of [cursor] into an [OmarchyTheme]. `id`, `name` and `mode` are
         * required (`id` must match [OmarchyThemeContract.ID_PATTERN], `mode` must be "dark" or
         * "light"); colors are whichever color columns are present and non-null. Returns null
         * for a null/empty cursor or if anything required is missing or invalid.
         */
        fun parse(cursor: Cursor?): OmarchyTheme? {
            if (cursor == null || !cursor.moveToFirst()) return null

            val idIndex = cursor.getColumnIndex("id")
            val nameIndex = cursor.getColumnIndex("name")
            val modeIndex = cursor.getColumnIndex("mode")
            if (idIndex < 0 || nameIndex < 0 || modeIndex < 0) return null

            val id = cursor.getString(idIndex) ?: return null
            val name = cursor.getString(nameIndex) ?: return null
            val mode = cursor.getString(modeIndex) ?: return null
            if (!ID_REGEX.matches(id) || (mode != "dark" && mode != "light")) return null

            val colors = mutableMapOf<String, String>()
            for (column in COLOR_COLUMNS) {
                val index = cursor.getColumnIndex(column)
                if (index < 0) continue
                val value = cursor.getString(index) ?: continue
                colors[column] = value
            }

            return OmarchyTheme(id = id, name = name, mode = mode, colors = colors)
        }

        /**
         * Queries [OmarchyThemeContract.CURRENT] and parses the current theme. This does IPC:
         * never call it from the main thread. Returns null if the provider isn't installed
         * (stock AOSP) or the query fails for any other reason.
         */
        fun current(ctx: Context): OmarchyTheme? =
            try {
                ctx.contentResolver
                    .query(
                        OmarchyThemeContract.CURRENT,
                        null,
                        null,
                        null,
                        null,
                    )?.use { parse(it) }
            } catch (e: SecurityException) {
                null
            } catch (e: IllegalArgumentException) {
                null
            }

        /**
         * Emits the current theme, then re-emits every time it changes. Backed by a
         * [ContentObserver] on [OmarchyThemeContract.CURRENT] (no broadcast receiver
         * involved). The observer's callback does no IPC: it only sends a change signal
         * ([Unit]); the signal is conflated (so two changes in a row collapse into one
         * reread) and [current] is called downstream on [Dispatchers.IO].
         */
        fun flow(ctx: Context): Flow<OmarchyTheme?> =
            callbackFlow {
                trySend(Unit)
                // null handler: onChange is invoked directly on the thread that posted the
                // notification instead of a Looper thread, but that's harmless here since
                // onChange itself does no IPC (see KDoc above).
                val observer =
                    object : ContentObserver(null) {
                        override fun onChange(selfChange: Boolean) {
                            trySend(Unit)
                        }
                    }
                ctx.contentResolver.registerContentObserver(
                    OmarchyThemeContract.CURRENT,
                    false,
                    observer,
                )
                awaitClose { ctx.contentResolver.unregisterContentObserver(observer) }
            }.conflate().map { current(ctx) }.flowOn(Dispatchers.IO)
    }
}
