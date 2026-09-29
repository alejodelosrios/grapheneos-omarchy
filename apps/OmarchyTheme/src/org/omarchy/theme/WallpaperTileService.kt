package org.omarchy.theme

import android.os.Handler
import android.os.Looper
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

private const val LABEL = "Next wallpaper"

// File-level lock: the tile creates a new TileService instance per binder connection, so this
// must be shared across instances, not a per-instance field, to actually serialize two taps
// (same reasoning as ThemeSwitcher.LOCK).
private val LOCK = Any()

/**
 * QS tile that cycles through the current theme's wallpapers (D6,
 * `.swarm/design/design-11-icons-bg-next.md`, contract `omarchy-theme-bg-next`). With fewer than
 * 2 backgrounds under `themes/<id>/backgrounds/` the tile is unavailable; otherwise each tap
 * advances to the next background and wraps back to the first after the last one.
 *
 * `ThemeCatalog.backgroundFiles`/`ThemeSwitcher.current`/`.setWallpaper` do file/binder I/O: never
 * on the main thread (same rule as `ThemeTileService`), so both callbacks run on a background
 * `Thread` and only touch `qsTile` on the main `Looper`.
 */
class WallpaperTileService : TileService() {
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onStartListening() {
        super.onStartListening()
        Thread {
            val n = ThemeCatalog.backgroundFiles(ThemeSwitcher(this).current()).size
            mainHandler.post {
                qsTile?.let { tile ->
                    tile.label = LABEL
                    tile.state = if (n < 2) Tile.STATE_UNAVAILABLE else Tile.STATE_ACTIVE
                    tile.updateTile()
                }
            }
        }.start()
    }

    override fun onClick() {
        super.onClick()
        Thread {
            synchronized(LOCK) {
                val switcher = ThemeSwitcher(this)
                val id = switcher.current()
                val files = ThemeCatalog.backgroundFiles(id)
                if (files.size < 2) return@synchronized
                val prefs = switcher.prefs()
                val key = ThemeSwitcher.bgIndexKey(id)
                val next = (prefs.getInt(key, 0) + 1) % files.size
                if (switcher.setWallpaper(files[next])) {
                    prefs.edit().putInt(key, next).apply()
                }
            }
        }.start()
    }
}
